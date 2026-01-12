"""Tests for geometry utilities."""

import json

import pytest

from cdse.exceptions import ValidationError
from cdse.geometry import (
    bbox_to_geojson,
    geojson_to_bbox,
    geojson_to_wkt,
    read_geojson,
    validate_geometry,
    wkt_to_geojson,
)


class TestReadGeoJSON:
    """Tests for read_geojson function."""

    def test_read_valid_geojson(self, tmp_path):
        """Test reading a valid GeoJSON file."""
        geojson_data = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
        }

        file_path = tmp_path / "test.geojson"
        file_path.write_text(json.dumps(geojson_data))

        result = read_geojson(file_path)
        assert result == geojson_data

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file raises error."""
        with pytest.raises(ValidationError) as exc_info:
            read_geojson("/nonexistent/path.geojson")
        assert "not found" in str(exc_info.value)

    def test_read_invalid_json(self, tmp_path):
        """Test reading invalid JSON raises error."""
        file_path = tmp_path / "invalid.geojson"
        file_path.write_text("not valid json {{{")

        with pytest.raises(ValidationError) as exc_info:
            read_geojson(file_path)
        assert "Invalid GeoJSON" in str(exc_info.value)


class TestGeoJSONToWKT:
    """Tests for geojson_to_wkt function."""

    def test_point_to_wkt(self):
        """Test converting Point to WKT."""
        geojson = {"type": "Point", "coordinates": [1.0, 2.0]}
        result = geojson_to_wkt(geojson)
        assert result == "POINT (1.0 2.0)"

    def test_linestring_to_wkt(self):
        """Test converting LineString to WKT."""
        geojson = {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}
        result = geojson_to_wkt(geojson)
        assert result == "LINESTRING (0 0, 1 1, 2 0)"

    def test_polygon_to_wkt(self):
        """Test converting Polygon to WKT."""
        geojson = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        result = geojson_to_wkt(geojson)
        assert result == "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"

    def test_feature_to_wkt(self):
        """Test converting Feature to WKT."""
        geojson = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1.0, 2.0]}}
        result = geojson_to_wkt(geojson)
        assert result == "POINT (1.0 2.0)"

    def test_feature_collection_to_wkt(self):
        """Test converting FeatureCollection to WKT (uses first feature)."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1.0, 2.0]}}
            ],
        }
        result = geojson_to_wkt(geojson)
        assert result == "POINT (1.0 2.0)"

    def test_empty_geojson_raises_error(self):
        """Test that empty GeoJSON raises error."""
        with pytest.raises(ValidationError):
            geojson_to_wkt({})


class TestWKTToGeoJSON:
    """Tests for wkt_to_geojson function."""

    def test_point_from_wkt(self):
        """Test converting WKT Point to GeoJSON."""
        wkt = "POINT (1 2)"
        result = wkt_to_geojson(wkt)
        assert result["type"] == "Point"
        assert result["coordinates"] == [1.0, 2.0]

    def test_polygon_from_wkt(self):
        """Test converting WKT Polygon to GeoJSON."""
        wkt = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
        result = wkt_to_geojson(wkt)
        assert result["type"] == "Polygon"
        assert len(result["coordinates"]) == 1
        assert len(result["coordinates"][0]) == 5

    def test_invalid_wkt_raises_error(self):
        """Test that invalid WKT raises error."""
        with pytest.raises(ValidationError):
            wkt_to_geojson("INVALID (1 2 3)")


class TestBboxToGeoJSON:
    """Tests for bbox_to_geojson function."""

    def test_valid_bbox(self):
        """Test converting valid bounding box."""
        bbox = [9.0, 45.0, 9.5, 45.5]
        result = bbox_to_geojson(bbox)

        assert result["type"] == "Polygon"
        assert len(result["coordinates"]) == 1
        assert len(result["coordinates"][0]) == 5  # Closed polygon

        # First point should be min_lon, min_lat
        assert result["coordinates"][0][0] == [9.0, 45.0]

    def test_invalid_bbox_length(self):
        """Test that invalid bbox length raises error."""
        with pytest.raises(ValidationError):
            bbox_to_geojson([1, 2, 3])


class TestGeoJSONToBbox:
    """Tests for geojson_to_bbox function."""

    def test_polygon_to_bbox(self):
        """Test extracting bbox from Polygon."""
        geojson = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]]}
        result = geojson_to_bbox(geojson)
        assert result == [0, 0, 10, 5]

    def test_feature_with_bbox(self):
        """Test that existing bbox is used."""
        geojson = {
            "type": "Feature",
            "bbox": [1, 2, 3, 4],
            "geometry": {"type": "Point", "coordinates": [2, 3]},
        }
        result = geojson_to_bbox(geojson)
        assert result == [1, 2, 3, 4]


class TestValidateGeometry:
    """Tests for validate_geometry function."""

    def test_valid_point(self):
        """Test validating a valid Point."""
        geojson = {"type": "Point", "coordinates": [1, 2]}
        assert validate_geometry(geojson) is True

    def test_valid_polygon(self):
        """Test validating a valid Polygon."""
        geojson = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        assert validate_geometry(geojson) is True

    def test_missing_type(self):
        """Test that missing type raises error."""
        with pytest.raises(ValidationError):
            validate_geometry({"coordinates": [1, 2]})

    def test_missing_coordinates(self):
        """Test that missing coordinates raises error."""
        with pytest.raises(ValidationError):
            validate_geometry({"type": "Point"})

    def test_invalid_type(self):
        """Test that invalid geometry type raises error."""
        with pytest.raises(ValidationError):
            validate_geometry({"type": "Circle", "coordinates": [1, 2]})
