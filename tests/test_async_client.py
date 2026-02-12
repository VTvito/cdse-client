"""Tests for async client."""

import pytest

from cdse.async_client import CDSEClientAsync, download_products_async

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
