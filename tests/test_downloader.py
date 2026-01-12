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
        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"test data"]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        path = downloader.download(sample_product, progress=False)

        assert path.exists()
        assert path.name == "S2A_MSIL2A_20240115_T32TNR.zip"

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

        # Mock successful downloads
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"data"]
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
