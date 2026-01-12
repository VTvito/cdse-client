"""Tests for Catalog class."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from cdse.catalog import Catalog
from cdse.exceptions import CatalogError, ValidationError
from cdse.product import Product


class TestCatalog:
    """Tests for Catalog class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        return MagicMock(spec=requests.Session)

    @pytest.fixture
    def catalog(self, mock_session):
        """Create a Catalog instance with mock session."""
        return Catalog(mock_session)

    @pytest.fixture
    def sample_response(self):
        """Create a sample STAC API response."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "id": "S2A_MSIL2A_20240115_T32TNR",
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [9.0, 45.0],
                                [9.5, 45.0],
                                [9.5, 45.5],
                                [9.0, 45.5],
                                [9.0, 45.0],
                            ]
                        ],
                    },
                    "properties": {
                        "datetime": "2024-01-15T10:30:00Z",
                        "eo:cloud_cover": 10.0,
                        "collection": "sentinel-2-l2a",
                    },
                },
                {
                    "id": "S2A_MSIL2A_20240116_T32TNR",
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [9.0, 45.0],
                                [9.5, 45.0],
                                [9.5, 45.5],
                                [9.0, 45.5],
                                [9.0, 45.0],
                            ]
                        ],
                    },
                    "properties": {
                        "datetime": "2024-01-16T10:30:00Z",
                        "eo:cloud_cover": 50.0,
                        "collection": "sentinel-2-l2a",
                    },
                },
            ],
        }

    def test_search_success(self, catalog, mock_session, sample_response):
        """Test successful search."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        products = catalog.search(
            bbox=[9.0, 45.0, 9.5, 45.5],
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        assert len(products) == 2
        assert all(isinstance(p, Product) for p in products)
        mock_session.post.assert_called_once()

    def test_search_with_cloud_filter(self, catalog, mock_session, sample_response):
        """Test search with cloud cover filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        products = catalog.search(
            bbox=[9.0, 45.0, 9.5, 45.5],
            start_date="2024-01-01",
            end_date="2024-01-31",
            cloud_cover_max=20.0,
        )

        # Only product with 10% cloud cover should pass
        assert len(products) == 1
        assert products[0].cloud_cover == 10.0

    def test_search_api_error(self, catalog, mock_session):
        """Test search handles API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response
        )
        mock_session.post.return_value = mock_response

        with pytest.raises(CatalogError) as exc_info:
            catalog.search(
                bbox=[9.0, 45.0, 9.5, 45.5],
                start_date="2024-01-01",
                end_date="2024-01-31",
            )

        assert "Catalog search failed" in str(exc_info.value)

    def test_validate_bbox_invalid_length(self, catalog):
        """Test bbox validation with wrong length."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_bbox([9.0, 45.0, 9.5])  # Only 3 values

        assert "bbox must be a list of 4 values" in str(exc_info.value)

    def test_validate_bbox_invalid_longitude(self, catalog):
        """Test bbox validation with invalid longitude."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_bbox([200.0, 45.0, 210.0, 46.0])

        assert "Longitude must be between -180 and 180" in str(exc_info.value)

    def test_validate_bbox_invalid_latitude(self, catalog):
        """Test bbox validation with invalid latitude."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_bbox([9.0, 100.0, 9.5, 110.0])

        assert "Latitude must be between -90 and 90" in str(exc_info.value)

    def test_validate_bbox_min_max_order(self, catalog):
        """Test bbox validation with min > max."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_bbox([9.5, 45.0, 9.0, 45.5])  # min_lon > max_lon

        assert "min_lon must be < max_lon" in str(exc_info.value)

    def test_validate_dates_invalid_format(self, catalog):
        """Test date validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_dates("2024/01/01", "2024-01-31")

        assert "Invalid date format" in str(exc_info.value)

    def test_validate_dates_start_after_end(self, catalog):
        """Test date validation with start > end."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_dates("2024-01-31", "2024-01-01")

        assert "start_date must be before end_date" in str(exc_info.value)

    def test_validate_cloud_cover_out_of_range(self, catalog):
        """Test cloud cover validation."""
        with pytest.raises(ValidationError) as exc_info:
            catalog._validate_cloud_cover(150.0)

        assert "cloud_cover must be between 0 and 100" in str(exc_info.value)

    def test_search_by_point(self, catalog, mock_session, sample_response):
        """Test search by geographic point."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        products = catalog.search_by_point(
            lon=9.25,
            lat=45.25,
            buffer_km=10,
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        # Should call search with computed bbox
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        query = call_args[1]["json"]
        assert "bbox" in query

    def test_get_collections(self, catalog):
        """Test getting available collections."""
        collections = catalog.get_collections()

        assert "sentinel-2-l2a" in collections
        assert "sentinel-1-grd" in collections
        assert isinstance(collections, dict)
