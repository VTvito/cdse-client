"""Tests for async client."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from cdse.async_client import CDSEClientAsync, download_products_async
from cdse.exceptions import DownloadError
from cdse.product import Product

# Skip all tests if aiohttp is not installed
aiohttp = pytest.importorskip("aiohttp")


class TestCDSEClientAsync:
    """Tests for CDSEClientAsync class."""

    def test_client_imports(self):
        """Test that async client can be imported."""
        assert CDSEClientAsync is not None

    def test_download_function_exists(self):
        """Test that convenience function exists."""
        assert callable(download_products_async)

    def test_get_collections(self):
        """Test get_collections method exists on Catalog."""
        # CDSEClientAsync delegates to Catalog.get_collections
        from cdse.catalog import Catalog

        assert hasattr(Catalog, "get_collections")


class _FakeContent:
    """Stands in for aiohttp's StreamReader."""

    def __init__(self, chunks, fail_after=None):
        self._chunks = chunks
        self._fail_after = fail_after

    async def _gen(self):
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i == self._fail_after:
                raise ConnectionResetError("connection dropped")
            yield chunk

    def iter_chunked(self, size):
        return self._gen()


class _FakeResponse:
    def __init__(self, status=200, headers=None, chunks=(), payload=None, fail_after=None):
        self.status = status
        self.headers = headers or {}
        self.content = _FakeContent(list(chunks), fail_after)
        self._payload = payload

    async def json(self):
        return self._payload

    async def text(self):
        return ""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Records requests and replays queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def _next(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self._responses.pop(0)

    def get(self, url, **kwargs):
        return self._next(url, **kwargs)

    def post(self, url, **kwargs):
        return self._next(url, **kwargs)


def _client(tmp_path, session, token="tok", expires_in=600):
    client = CDSEClientAsync(client_id="id", client_secret="secret", output_dir=str(tmp_path))
    client._session = session
    client._semaphore = asyncio.Semaphore(4)
    client._auth_lock = asyncio.Lock()
    client._access_token = token
    client._token_expires_at = time.time() + expires_in
    return client


def _product(name="S2A_TEST", download_url=None):
    return Product(
        id="uuid-1",
        name=name,
        collection="sentinel-2-l2a",
        datetime=None,
        cloud_cover=None,
        geometry={},
        bbox=[9.0, 45.0, 9.5, 45.5],
        properties={},
        assets={"download": {"href": download_url}} if download_url else {},
    )


class TestAsyncDownloadIntegrity:
    """Audit 03: partial files must never survive a failed download."""

    @pytest.mark.asyncio
    async def test_truncated_stream_raises_and_removes_the_file(self, tmp_path):
        session = _FakeSession(
            [_FakeResponse(headers={"content-length": "1048576"}, chunks=[b"x" * 100])]
        )
        client = _client(tmp_path, session)
        product = _product(download_url="https://example.invalid/p.zip")

        with pytest.raises(DownloadError, match="Incomplete download"):
            await client.download(product, progress=False)

        assert not (tmp_path / "S2A_TEST.zip").exists()

    @pytest.mark.asyncio
    async def test_connection_drop_removes_the_partial_file(self, tmp_path):
        session = _FakeSession(
            [
                _FakeResponse(
                    headers={"content-length": "1000"},
                    chunks=[b"a" * 100, b"b" * 100],
                    fail_after=1,
                )
            ]
        )
        client = _client(tmp_path, session)
        product = _product(download_url="https://example.invalid/p.zip")

        with pytest.raises(ConnectionResetError):
            await client.download(product, progress=False)

        assert not (tmp_path / "S2A_TEST.zip").exists()

    @pytest.mark.asyncio
    async def test_complete_download_is_kept(self, tmp_path):
        payload = b"z" * 512
        session = _FakeSession([_FakeResponse(headers={"content-length": "512"}, chunks=[payload])])
        client = _client(tmp_path, session)
        product = _product(download_url="https://example.invalid/p.zip")

        path = await client.download(product, progress=False)

        assert path.read_bytes() == payload


class TestAsyncTokenRefresh:
    """Audit 05: a task can wait hours in the semaphore queue before it runs."""

    @pytest.mark.asyncio
    async def test_token_is_rechecked_after_acquiring_the_semaphore(self, tmp_path):
        payload = b"y" * 16
        session = _FakeSession([_FakeResponse(headers={"content-length": "16"}, chunks=[payload])])
        client = _client(tmp_path, session)
        product = _product(download_url="https://example.invalid/p.zip")

        # Valid when download() starts, expired by the time the slot is free.
        # The third call is the double-check inside _refresh_token, which must
        # also see an expired token for the refresh to go ahead.
        token_patch = patch.object(client, "_is_token_valid", side_effect=[True, False, False])
        auth_patch = patch.object(client, "_authenticate", new=AsyncMock())

        with token_patch, auth_patch as authenticate:
            await client.download(product, progress=False)

        authenticate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_concurrent_refresh_authenticates_only_once(self, tmp_path):
        client = _client(tmp_path, _FakeSession([]), expires_in=-1)
        calls = []

        async def slow_auth():
            calls.append(1)
            await asyncio.sleep(0.01)
            client._access_token = "fresh"
            client._token_expires_at = time.time() + 600

        with patch.object(client, "_authenticate", new=slow_auth):
            await asyncio.gather(*(client._refresh_token() for _ in range(8)))

        assert len(calls) == 1, "the auth lock should collapse concurrent refreshes"


class TestAsyncDownloadUrl:
    """Audit 09: the sync client skips s3:// hrefs; async must match."""

    @pytest.mark.asyncio
    async def test_s3_url_falls_through_to_odata(self, tmp_path):
        odata = _FakeResponse(payload={"value": [{"Id": "uuid-9"}]})
        session = _FakeSession([odata])
        client = _client(tmp_path, session)

        url = await client._get_download_url(_product(download_url="s3://bucket/key"))

        assert url is not None
        assert url.startswith("https://")
        assert "uuid-9" in url

    @pytest.mark.asyncio
    async def test_https_url_is_used_directly(self, tmp_path):
        client = _client(tmp_path, _FakeSession([]))

        url = await client._get_download_url(_product(download_url="https://example.invalid/p.zip"))

        assert url == "https://example.invalid/p.zip"
