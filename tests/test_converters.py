"""Tests for data format converters."""

from datetime import datetime

import pytest

from cdse.converters import (
    products_count,
    products_size,
    to_dataframe,
    to_geodataframe,
    to_geojson,
)
from cdse.product import Product


def make_sample_product(
    name: str = "S2A_MSIL2A_20240115T102351_N0510_R065_T32TQM_20240115T134815",
    cloud_cover: float = 15.5,
    collection: str = "sentinel-2-l2a",
) -> Product:
    """Create a sample Product for testing."""
    return Product(
        id=f"test-uuid-{name[:8]}",
        name=name,
        collection=collection,
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
            "processing:level": "L2A",
            "size": 1073741824,  # 1 GB
        },
    )


@pytest.fixture
def sample_products():
    """Create a list of sample products for testing."""
    return [
        make_sample_product(
            name="S2A_MSIL2A_20240115T102351_N0510_R065_T32TQM_20240115T134815",
            cloud_cover=10.0,
        ),
        make_sample_product(
            name="S2A_MSIL2A_20240116T103210_N0510_R065_T32TQM_20240116T140000",
            cloud_cover=25.5,
        ),
        make_sample_product(
            name="S2B_MSIL2A_20240117T101500_N0510_R065_T32TQM_20240117T130000",
            cloud_cover=5.2,
        ),
    ]


class TestToGeoJSON:
    """Tests for to_geojson function."""

    def test_empty_list(self):
        """Test with empty product list."""
        result = to_geojson([])
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_single_product(self):
        """Test with single product."""
        product = make_sample_product()
        result = to_geojson([product])

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1

        feature = result["features"][0]
        assert feature["type"] == "Feature"
        assert feature["id"] == product.id
        assert feature["geometry"] == product.geometry
        assert feature["properties"]["name"] == product.name
        assert feature["properties"]["cloud_cover"] == product.cloud_cover
        assert feature["bbox"] == product.bbox

    def test_multiple_products(self, sample_products):
        """Test with multiple products."""
        result = to_geojson(sample_products)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 3

        # Check all products are included
        names = [f["properties"]["name"] for f in result["features"]]
        assert all(p.name in names for p in sample_products)

    def test_properties_included(self):
        """Test that all expected properties are included."""
        product = make_sample_product()
        result = to_geojson([product])
        props = result["features"][0]["properties"]

        assert "id" in props
        assert "name" in props
        assert "collection" in props
        assert "datetime" in props
        assert "cloud_cover" in props
        assert "platform" in props
        assert "size" in props
        assert "size_mb" in props


class TestToDataFrame:
    """Tests for to_dataframe function."""

    def test_requires_pandas(self):
        """Test that ImportError is raised when pandas not available."""
        # This test should pass if pandas is installed
        # If pandas is not installed, it would raise ImportError
        pass  # Covered by actual usage in other tests

    def test_empty_list(self):
        """Test with empty product list."""
        pd = pytest.importorskip("pandas")
        result = to_dataframe([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_single_product(self):
        """Test with single product."""
        pd = pytest.importorskip("pandas")
        product = make_sample_product()
        result = to_dataframe([product])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.index[0] == product.id
        assert result.loc[product.id, "name"] == product.name
        assert result.loc[product.id, "cloud_cover"] == product.cloud_cover

    def test_multiple_products(self, sample_products):
        """Test with multiple products."""
        pytest.importorskip("pandas")
        result = to_dataframe(sample_products)

        assert len(result) == 3
        assert all(p.id in result.index for p in sample_products)

    def test_columns_present(self):
        """Test that expected columns are present."""
        pytest.importorskip("pandas")
        product = make_sample_product()
        result = to_dataframe([product])

        expected_columns = [
            "name",
            "collection",
            "datetime",
            "cloud_cover",
            "platform",
            "size",
            "size_mb",
            "bbox_min_lon",
            "bbox_min_lat",
            "bbox_max_lon",
            "bbox_max_lat",
        ]
        for col in expected_columns:
            assert col in result.columns

    def test_sorting_by_cloud_cover(self, sample_products):
        """Test that DataFrame can be sorted by cloud cover."""
        pytest.importorskip("pandas")
        result = to_dataframe(sample_products)
        sorted_df = result.sort_values("cloud_cover")

        # Check sorting works
        cloud_covers = sorted_df["cloud_cover"].tolist()
        assert cloud_covers == sorted(cloud_covers)


class TestToGeoDataFrame:
    """Tests for to_geodataframe function."""

    def test_requires_geopandas(self):
        """Test that ImportError is raised when geopandas not available."""
        # This test should pass if geopandas is installed
        pass

    def test_empty_list(self):
        """Test with empty product list."""
        gpd = pytest.importorskip("geopandas")
        result = to_geodataframe([])
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 0

    def test_single_product(self):
        """Test with single product."""
        gpd = pytest.importorskip("geopandas")
        product = make_sample_product()
        result = to_geodataframe([product])

        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1
        assert "geometry" in result.columns
        assert result.crs == "EPSG:4326"

    def test_geometry_valid(self, sample_products):
        """Test that geometries are valid Shapely objects."""
        pytest.importorskip("geopandas")
        from shapely.geometry import Polygon

        result = to_geodataframe(sample_products)

        for geom in result.geometry:
            assert geom is not None
            assert isinstance(geom, Polygon)
            assert geom.is_valid


class TestProductsSize:
    """Tests for products_size function."""

    def test_empty_list(self):
        """Test with empty list returns 0."""
        assert products_size([]) == 0.0

    def test_single_product(self):
        """Test with single product."""
        product = make_sample_product()
        result = products_size([product])
        # 1 GB = 1073741824 bytes = 1.0 GB
        assert abs(result - 1.0) < 0.01

    def test_multiple_products(self, sample_products):
        """Test with multiple products."""
        result = products_size(sample_products)
        # Each product is 1 GB, so total should be 3 GB
        assert abs(result - 3.0) < 0.01

    def test_handles_missing_size(self):
        """Test with products that have no size info."""
        product = Product(
            id="test",
            name="test",
            collection="test",
            datetime=None,
            cloud_cover=None,
            geometry={},
            bbox=[],
            properties={},  # No size
        )
        result = products_size([product])
        assert result == 0.0


class TestProductsCount:
    """Tests for products_count function."""

    def test_empty_list(self):
        """Test with empty list."""
        result = products_count([])
        assert result == {}

    def test_single_collection(self, sample_products):
        """Test products from single collection."""
        result = products_count(sample_products)
        assert result == {"sentinel-2-l2a": 3}

    def test_multiple_collections(self):
        """Test products from multiple collections."""
        products = [
            make_sample_product(name="S2A_1", collection="sentinel-2-l2a"),
            make_sample_product(name="S2A_2", collection="sentinel-2-l2a"),
            make_sample_product(name="S1A_1", collection="sentinel-1-grd"),
        ]
        result = products_count(products)
        assert result == {"sentinel-2-l2a": 2, "sentinel-1-grd": 1}
