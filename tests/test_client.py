"""Tests for CDSEClient class."""

from unittest.mock import MagicMock, patch

import pytest

from cdse import CDSEClient
from cdse.catalog import Catalog
from cdse.downloader import Downloader
from cdse.product import Product


class TestCDSEClient:
    """Tests for CDSEClient class."""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock OAuth2Auth."""
        with patch("cdse.client.OAuth2Auth") as mock:
            auth_instance = MagicMock()
            auth_instance.get_session.return_value = MagicMock()
            auth_instance.get_bearer_session.return_value = MagicMock()
            mock.return_value = auth_instance
            yield mock

    @pytest.fixture
    def client(self, mock_auth):
        """Create a CDSEClient instance with mocked auth."""
        return CDSEClient(
            client_id="test-id",
            client_secret="test-secret",
            output_dir="./downloads",
        )

    def test_init(self, mock_auth):
        """Test client initialization."""
        client = CDSEClient("id", "secret")

        mock_auth.assert_called_once_with("id", "secret")

    def test_catalog_lazy_init(self, client, mock_auth):
        """Test catalog is lazily initialized."""
        assert client._catalog is None

        catalog = client.catalog

        assert catalog is not None
        assert isinstance(catalog, Catalog)
        assert client._catalog is catalog  # Same instance

    def test_downloader_lazy_init(self, client, mock_auth):
        """Test downloader is lazily initialized."""
        assert client._downloader is None

        downloader = client.downloader

        assert downloader is not None
        assert isinstance(downloader, Downloader)
        assert client._downloader is downloader

    @patch.object(Catalog, "search")
    def test_search(self, mock_search, client):
        """Test search delegates to catalog."""
        mock_products = [MagicMock(spec=Product)]
        mock_search.return_value = mock_products

        products = client.search(
            bbox=[9.0, 45.0, 9.5, 45.5],
            start_date="2024-01-01",
            end_date="2024-01-31",
            collection="sentinel-2-l2a",
            cloud_cover_max=20.0,
        )

        assert products == mock_products
        mock_search.assert_called_once_with(
            bbox=[9.0, 45.0, 9.5, 45.5],
            start_date="2024-01-01",
            end_date="2024-01-31",
            collection="sentinel-2-l2a",
            cloud_cover_max=20.0,
            limit=10,
        )

    @patch.object(Catalog, "search_by_point")
    def test_search_by_point(self, mock_search, client):
        """Test search_by_point delegates to catalog."""
        mock_products = [MagicMock(spec=Product)]
        mock_search.return_value = mock_products

        products = client.search_by_point(
            lon=9.25,
            lat=45.25,
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        assert products == mock_products
        mock_search.assert_called_once()

    @patch.object(Downloader, "download")
    def test_download(self, mock_download, client):
        """Test download delegates to downloader."""
        from pathlib import Path

        mock_path = Path("/downloads/product.zip")
        mock_download.return_value = mock_path

        product = MagicMock(spec=Product)
        path = client.download(product)

        assert path == mock_path
        mock_download.assert_called_once()

    @patch.object(Downloader, "download_all")
    def test_download_all(self, mock_download_all, client):
        """Test download_all delegates to downloader."""
        from pathlib import Path

        mock_paths = [Path("/downloads/p1.zip"), Path("/downloads/p2.zip")]
        mock_download_all.return_value = mock_paths

        products = [MagicMock(spec=Product) for _ in range(2)]
        paths = client.download_all(products)

        assert paths == mock_paths
        mock_download_all.assert_called_once()

    def test_get_collections(self, client):
        """Test get_collections returns collection dict."""
        collections = client.get_collections()

        assert isinstance(collections, dict)
        assert "sentinel-2-l2a" in collections

    def test_refresh_auth(self, client, mock_auth):
        """Test refresh_auth resets clients."""
        # Access catalog and downloader to initialize them
        _ = client.catalog
        _ = client.downloader

        assert client._catalog is not None
        assert client._downloader is not None

        client.refresh_auth()

        # Should reset both
        assert client._catalog is None
        assert client._downloader is None
