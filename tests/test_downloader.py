"""Tests for Downloader class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from cdse.downloader import Downloader
from cdse.exceptions import DownloadError
from cdse.product import Product


class TestDownloader:
    """Tests for Downloader class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        return MagicMock(spec=requests.Session)

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def downloader(self, mock_session, temp_dir):
        """Create a Downloader instance."""
        return Downloader(mock_session, output_dir=temp_dir)

    @pytest.fixture
    def sample_product(self):
        """Create a sample product."""
        return Product(
            id="product-uuid-123",
            name="S2A_MSIL2A_20240115_T32TNR",
            collection="sentinel-2-l2a",
            datetime=None,
            cloud_cover=10.0,
            geometry={},
            bbox=[9.0, 45.0, 9.5, 45.5],
            properties={},
            assets={"download": {"href": "https://example.com/download/product.zip"}},
        )

    def test_init_creates_output_dir(self, mock_session, temp_dir):
        """Test that init creates output directory."""
        output_path = Path(temp_dir) / "downloads"
        Downloader(mock_session, output_dir=str(output_path))

        assert output_path.exists()

    def test_download_success(self, downloader, mock_session, sample_product, temp_dir):
        """Test successful download."""
        # Mock response — content-length must match the body, or the completeness
        # check will (correctly) reject it as truncated.
        payload = b"test data"
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(payload))}
        mock_response.iter_content.return_value = [payload]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        path = downloader.download(sample_product, progress=False)

        assert path.exists()
        assert path.name == "S2A_MSIL2A_20240115_T32TNR.zip"
        assert path.read_bytes() == payload

    def test_download_truncated_stream_raises(
        self, downloader, mock_session, sample_product, temp_dir
    ):
        """A stream that ends early must fail, not be reported as a success."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1048576"}
        mock_response.iter_content.return_value = [b"x" * 100]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        with pytest.raises(DownloadError, match="Incomplete download"):
            downloader.download(sample_product, progress=False)

        # The partial file must not survive: skip_existing would keep it forever.
        assert not (Path(temp_dir) / "S2A_MSIL2A_20240115_T32TNR.zip").exists()

    def test_download_unknown_length_is_accepted(self, downloader, mock_session, sample_product):
        """Without content-length there is nothing to compare against."""
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"payload"]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        path = downloader.download(sample_product, progress=False)

        assert path.read_bytes() == b"payload"

    def test_download_skip_existing(self, downloader, mock_session, sample_product, temp_dir):
        """Test that existing files are skipped."""
        # Create existing file
        existing_file = Path(temp_dir) / "S2A_MSIL2A_20240115_T32TNR.zip"
        existing_file.write_text("existing content")

        path = downloader.download(sample_product)

        # Should return existing path without making request
        assert path == existing_file
        mock_session.get.assert_not_called()

    def test_download_http_error(self, downloader, mock_session, sample_product):
        """Test download handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_session.get.return_value = mock_response

        with pytest.raises(DownloadError) as exc_info:
            downloader.download(sample_product, progress=False)

        assert "Download failed" in str(exc_info.value)

    def test_download_no_url(self, downloader, mock_session):
        """Test download with product that has no download URL."""
        product = Product(
            id="no-url-product",
            name="NoUrlProduct",
            collection="sentinel-2-l2a",
            datetime=None,
            cloud_cover=None,
            geometry={},
            bbox=[],
            properties={},
            assets={},
        )

        # Mock OData query to return no results
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        with pytest.raises(DownloadError) as exc_info:
            downloader.download(product, progress=False)

        assert "Could not determine download URL" in str(exc_info.value)

    def test_download_all(self, downloader, mock_session, temp_dir):
        """Test downloading multiple products."""
        products = [
            Product(
                id=f"product-{i}",
                name=f"Product_{i}",
                collection="sentinel-2-l2a",
                datetime=None,
                cloud_cover=10.0,
                geometry={},
                bbox=[],
                properties={},
                assets={"download": {"href": f"https://example.com/{i}.zip"}},
            )
            for i in range(3)
        ]

        # Mock successful downloads — content-length must match the body.
        payload = b"data"
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(payload))}
        mock_response.iter_content.return_value = [payload]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        paths = downloader.download_all(products, progress=False)

        assert len(paths) == 3
        assert all(p.exists() for p in paths)

    def test_format_size(self):
        """Test file size formatting."""
        assert Downloader.format_size(500) == "500.00 B"
        assert Downloader.format_size(1024) == "1.00 KB"
        assert Downloader.format_size(1048576) == "1.00 MB"
        assert Downloader.format_size(1073741824) == "1.00 GB"

    def test_get_download_url_from_odata(self, downloader, mock_session, sample_product):
        """Test getting download URL from OData API."""
        # Product without direct download URL
        product = Product(
            id="test-product",
            name="S2A_MSIL2A_20240115",
            collection="sentinel-2-l2a",
            datetime=None,
            cloud_cover=None,
            geometry={},
            bbox=[],
            properties={},
            assets={},  # No assets
        )

        # Mock OData response
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": [{"Id": "uuid-12345"}]}
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        url = downloader._get_download_url(product)

        assert url is not None
        assert "uuid-12345" in url


class TestRequestWithRetry:
    """Tests for Downloader._request_with_retry."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def _response(self, status):
        resp = MagicMock()
        resp.status_code = status
        return resp

    def test_zero_retries_still_attempts_once(self, temp_dir):
        """max_retries=0 must not blow up on an unbound local."""
        session = MagicMock(spec=requests.Session)
        session.get.return_value = self._response(200)

        downloader = Downloader(session, output_dir=temp_dir, max_retries=0)
        downloader._request_with_retry("get", "https://example.invalid")

        assert session.get.call_count == 1

    def test_retryable_status_is_raised_after_last_attempt(self, temp_dir, monkeypatch):
        """Exhausting retries surfaces the last response, not an internal error."""
        monkeypatch.setattr("cdse.downloader.time.sleep", lambda _: None)

        resp = self._response(503)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        session = MagicMock(spec=requests.Session)
        session.get.return_value = resp

        downloader = Downloader(session, output_dir=temp_dir, max_retries=3)

        with pytest.raises(requests.exceptions.HTTPError):
            downloader._request_with_retry("get", "https://example.invalid")

        assert session.get.call_count == 3

    def test_no_sleep_after_the_final_attempt(self, temp_dir, monkeypatch):
        """The last wait precedes nothing, so it must not happen."""
        waits = []
        monkeypatch.setattr("cdse.downloader.time.sleep", waits.append)

        resp = self._response(429)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        session = MagicMock(spec=requests.Session)
        session.get.return_value = resp

        downloader = Downloader(session, output_dir=temp_dir, max_retries=3)

        with pytest.raises(requests.exceptions.HTTPError):
            downloader._request_with_retry("get", "https://example.invalid")

        assert waits == [1, 2]  # not [1, 2, 4]

    def test_retried_responses_are_closed(self, temp_dir, monkeypatch):
        """Streamed bodies are never consumed, so each discarded try must be closed."""
        monkeypatch.setattr("cdse.downloader.time.sleep", lambda _: None)

        resp = self._response(502)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        session = MagicMock(spec=requests.Session)
        session.get.return_value = resp

        downloader = Downloader(session, output_dir=temp_dir, max_retries=3)

        with pytest.raises(requests.exceptions.HTTPError):
            downloader._request_with_retry("get", "https://example.invalid", stream=True)

        # Two discarded attempts closed; the last is kept to raise from.
        assert resp.close.call_count == 2

    def test_connection_error_is_raised_after_last_attempt(self, temp_dir, monkeypatch):
        monkeypatch.setattr("cdse.downloader.time.sleep", lambda _: None)

        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.ConnectionError("boom")

        downloader = Downloader(session, output_dir=temp_dir, max_retries=2)

        with pytest.raises(requests.exceptions.ConnectionError):
            downloader._request_with_retry("get", "https://example.invalid")

        assert session.get.call_count == 2

    def test_most_recent_failure_wins(self, temp_dir, monkeypatch):
        """A 503 after a connection error must raise the 503, not the stale error."""
        monkeypatch.setattr("cdse.downloader.time.sleep", lambda _: None)

        resp = self._response(503)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = [requests.exceptions.ConnectionError("boom"), resp]

        downloader = Downloader(session, output_dir=temp_dir, max_retries=2)

        with pytest.raises(requests.exceptions.HTTPError):
            downloader._request_with_retry("get", "https://example.invalid")
