"""Tests for CLI functionality."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from cdse.cli import main
from cdse.product import Product


def make_sample_product(
    name: str = "S2A_MSIL2A_20240115T102351_N0510_R065_T32TQM_20240115T134815",
    cloud_cover: float = 15.5,
) -> Product:
    """Create a sample Product for testing."""
    return Product(
        id=f"test-uuid-{name[:8]}",
        name=name,
        collection="sentinel-2-l2a",
        datetime=datetime(2024, 1, 15, 10, 23, 51),
        cloud_cover=cloud_cover,
        geometry={
            "type": "Polygon",
            "coordinates": [[[9.0, 45.0], [10.0, 45.0], [10.0, 46.0], [9.0, 46.0], [9.0, 45.0]]],
        },
        bbox=[9.0, 45.0, 10.0, 46.0],
        properties={
            "platform": "sentinel-2a",
            "instruments": ["MSI"],
            "size": 1073741824,
        },
    )


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_no_command_shows_help(self, capsys):
        """Test that no command shows help."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "cdse" in captured.out

    def test_version_flag(self, capsys):
        """Test --version flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_missing_credentials(self, capsys, monkeypatch):
        """Test error when credentials not set."""
        monkeypatch.delenv("CDSE_CLIENT_ID", raising=False)
        monkeypatch.delenv("CDSE_CLIENT_SECRET", raising=False)

        result = main(["search", "--bbox", "9,45,10,46", "-s", "2024-01-01", "-e", "2024-01-31"])
        assert result == 1
        captured = capsys.readouterr()
        assert "CDSE_CLIENT_ID" in captured.err


class TestSearchCommand:
    """Tests for search command."""

    @patch("cdse.cli.CDSEClient")
    def test_search_basic(self, mock_client_class, capsys, monkeypatch):
        """Test basic search command."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        # Setup mock
        mock_client = MagicMock()
        mock_client.search.return_value = [make_sample_product()]
        mock_client.get_products_size.return_value = 1.0
        mock_client_class.return_value = mock_client

        result = main(
            [
                "search",
                "--bbox",
                "9,45,10,46",
                "-s",
                "2024-01-01",
                "-e",
                "2024-01-31",
            ]
        )

        assert result == 0
        mock_client.search.assert_called_once()
        captured = capsys.readouterr()
        assert "Found 1 products" in captured.out

    @patch("cdse.cli.CDSEClient")
    def test_search_with_json_output(self, mock_client_class, capsys, monkeypatch):
        """Test search with --json flag."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_client.search.return_value = [make_sample_product()]
        mock_client_class.return_value = mock_client

        result = main(
            [
                "search",
                "--bbox",
                "9,45,10,46",
                "-s",
                "2024-01-01",
                "-e",
                "2024-01-31",
                "--json",
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        # Should be valid JSON
        output = json.loads(captured.out)
        assert isinstance(output, list)
        assert len(output) == 1

    @patch("cdse.cli.CDSEClient")
    def test_search_no_results(self, mock_client_class, capsys, monkeypatch):
        """Test search with no results."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_client_class.return_value = mock_client

        result = main(
            [
                "search",
                "--bbox",
                "9,45,10,46",
                "-s",
                "2024-01-01",
                "-e",
                "2024-01-31",
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "No products found" in captured.out

    def test_search_invalid_bbox(self, capsys, monkeypatch):
        """Test search with invalid bbox."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        result = main(
            [
                "search",
                "--bbox",
                "invalid",
                "-s",
                "2024-01-01",
                "-e",
                "2024-01-31",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid bbox" in captured.err

    def test_search_missing_bbox_and_geometry(self, capsys, monkeypatch):
        """Test search without bbox or geometry."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        result = main(
            [
                "search",
                "-s",
                "2024-01-01",
                "-e",
                "2024-01-31",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "--bbox" in captured.err or "--geometry" in captured.err


class TestDownloadCommand:
    """Tests for download command."""

    @patch("cdse.cli.CDSEClient")
    def test_download_by_name(self, mock_client_class, capsys, monkeypatch, tmp_path):
        """Test download by product name."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_product = make_sample_product()
        mock_client.search_by_name.return_value = mock_product
        mock_client.download.return_value = tmp_path / "product.zip"
        mock_client_class.return_value = mock_client

        result = main(
            [
                "download",
                "--name",
                "S2A_MSIL2A_20240115T102351",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_client.search_by_name.assert_called()
        mock_client.download.assert_called_once()

    @patch("cdse.cli.CDSEClient")
    def test_download_by_uuid(self, mock_client_class, capsys, monkeypatch, tmp_path):
        """Test download by UUID."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_product = make_sample_product()
        mock_client.search_by_id.return_value = mock_product
        mock_client.download.return_value = tmp_path / "product.zip"
        mock_client_class.return_value = mock_client

        result = main(
            [
                "download",
                "--uuid",
                "test-uuid-12345",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_client.search_by_id.assert_called_once_with("test-uuid-12345")

    def test_download_missing_uuid_and_name(self, capsys, monkeypatch):
        """Test download without uuid or name."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        result = main(["download", "-o", "."])

        assert result == 1
        captured = capsys.readouterr()
        assert "--uuid" in captured.err or "--name" in captured.err

    @patch("cdse.cli.CDSEClient")
    def test_download_product_not_found(self, mock_client_class, capsys, monkeypatch):
        """Test download when product not found."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_client.search_by_name.return_value = None
        mock_client_class.return_value = mock_client

        result = main(
            [
                "download",
                "--name",
                "NONEXISTENT_PRODUCT",
            ]
        )

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()

    @patch("cdse.cli.CDSEClient")
    def test_download_quicklook(self, mock_client_class, capsys, monkeypatch, tmp_path):
        """Test download quicklook only."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_product = make_sample_product()
        mock_client.search_by_name.return_value = mock_product
        mock_client.download_quicklook.return_value = tmp_path / "quicklook.jpeg"
        mock_client_class.return_value = mock_client

        result = main(
            [
                "download",
                "--name",
                "S2A_MSIL2A_20240115T102351",
                "--quicklook",
                "-o",
                str(tmp_path),
            ]
        )

        assert result == 0
        mock_client.download_quicklook.assert_called_once()


class TestCollectionsCommand:
    """Tests for collections command."""

    @patch("cdse.cli.CDSEClient")
    def test_list_collections(self, mock_client_class, capsys, monkeypatch):
        """Test listing collections."""
        monkeypatch.setenv("CDSE_CLIENT_ID", "test_id")
        monkeypatch.setenv("CDSE_CLIENT_SECRET", "test_secret")

        mock_client = MagicMock()
        mock_client.get_collections.return_value = {
            "sentinel-2-l2a": "Sentinel-2 L2A",
            "sentinel-1-grd": "Sentinel-1 GRD",
        }
        mock_client_class.return_value = mock_client

        result = main(["collections"])

        assert result == 0
        captured = capsys.readouterr()
        assert "sentinel-2-l2a" in captured.out
        assert "sentinel-1-grd" in captured.out
