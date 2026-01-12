"""Tests for Product class."""

from datetime import datetime

import pytest

from cdse.product import Product


class TestProduct:
    """Tests for Product class."""

    @pytest.fixture
    def sample_feature(self):
        """Create a sample STAC feature."""
        return {
            "id": "S2A_MSIL2A_20240115_T32TNR",
            "type": "Feature",
            "collection": "sentinel-2-l2a",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [9.0, 45.0],
                        [10.0, 45.0],
                        [10.0, 46.0],
                        [9.0, 46.0],
                        [9.0, 45.0],
                    ]
                ],
            },
            "bbox": [9.0, 45.0, 10.0, 46.0],
            "properties": {
                "datetime": "2024-01-15T10:30:00Z",
                "eo:cloud_cover": 15.5,
                "platform": "sentinel-2a",
                "instruments": ["MSI"],
                "processing:level": "L2A",
                "s2:tile_id": "32TNR",
                "sat:relative_orbit": 65,
            },
            "assets": {
                "download": {
                    "href": "https://example.com/download/product.zip",
                }
            },
        }

    def test_from_stac_feature(self, sample_feature):
        """Test creating Product from STAC feature."""
        product = Product.from_stac_feature(sample_feature)

        assert product.id == "S2A_MSIL2A_20240115_T32TNR"
        assert product.name == "S2A_MSIL2A_20240115_T32TNR"
        assert product.collection == "sentinel-2-l2a"
        assert product.cloud_cover == 15.5
        assert product.bbox == [9.0, 45.0, 10.0, 46.0]

    def test_datetime_parsing(self, sample_feature):
        """Test datetime parsing from feature."""
        product = Product.from_stac_feature(sample_feature)

        assert product.datetime is not None
        assert product.datetime.year == 2024
        assert product.datetime.month == 1
        assert product.datetime.day == 15

    def test_properties_access(self, sample_feature):
        """Test accessing properties."""
        product = Product.from_stac_feature(sample_feature)

        assert product.platform == "sentinel-2a"
        assert product.instrument == "MSI"
        assert product.processing_level == "L2A"
        assert product.tile_id == "32TNR"
        assert product.orbit_number == 65

    def test_download_url(self, sample_feature):
        """Test download URL extraction."""
        product = Product.from_stac_feature(sample_feature)

        assert product.download_url == "https://example.com/download/product.zip"

    def test_download_url_missing(self):
        """Test download URL when not available."""
        feature = {"id": "test", "properties": {}}
        product = Product.from_stac_feature(feature)

        assert product.download_url is None

    def test_str_representation(self, sample_feature):
        """Test string representation."""
        product = Product.from_stac_feature(sample_feature)
        str_repr = str(product)

        assert "S2A_MSIL2A_20240115_T32TNR" in str_repr
        assert "2024-01-15" in str_repr
        assert "15.5%" in str_repr

    def test_to_dict(self, sample_feature):
        """Test conversion to dictionary."""
        product = Product.from_stac_feature(sample_feature)
        d = product.to_dict()

        assert d["id"] == "S2A_MSIL2A_20240115_T32TNR"
        assert d["collection"] == "sentinel-2-l2a"
        assert d["cloud_cover"] == 15.5
        assert "datetime" in d
        assert d["bbox"] == [9.0, 45.0, 10.0, 46.0]

    def test_size_properties(self):
        """Test size property methods."""
        feature = {
            "id": "test",
            "properties": {"size": 1073741824},  # 1 GB
        }
        product = Product.from_stac_feature(feature)

        assert product.size == 1073741824
        assert product.size_mb == pytest.approx(1024.0, rel=0.01)

    def test_missing_properties(self):
        """Test handling of missing properties."""
        feature = {"id": "minimal-product", "properties": {}}
        product = Product.from_stac_feature(feature)

        assert product.id == "minimal-product"
        assert product.cloud_cover is None
        assert product.datetime is None
        assert product.platform is None
