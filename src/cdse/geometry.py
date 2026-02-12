"""Geometry utilities for CDSE Client.

This module provides functions for working with geographic data,
including GeoJSON parsing, WKT conversion, and geometry operations.
These functions are designed to be compatible with sentinelsat's API.
"""

import json
from pathlib import Path
from typing import Any, Optional, Union

from cdse.exceptions import ValidationError


def read_geojson(path: Union[str, Path]) -> dict[str, Any]:
    """Read a GeoJSON file.

    Args:
        path: Path to the GeoJSON file

    Returns:
        Parsed GeoJSON dictionary

    Raises:
        ValidationError: If file cannot be read or parsed

    Example:
        >>> geojson = read_geojson("area.geojson")
        >>> footprint = geojson_to_wkt(geojson)
    """
    path = Path(path)

    if not path.exists():
        raise ValidationError(f"GeoJSON file not found: {path}", field="path")

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid GeoJSON: {e}", field="path") from e
    except Exception as e:
        raise ValidationError(f"Failed to read GeoJSON: {e}", field="path") from e


def geojson_to_wkt(geojson: dict[str, Any]) -> str:
    """Convert GeoJSON geometry to WKT format.

    Supports GeoJSON Feature, FeatureCollection, and raw geometry objects.

    Args:
        geojson: GeoJSON dictionary (Feature, FeatureCollection, or geometry)

    Returns:
        WKT string representation of the geometry

    Raises:
        ValidationError: If GeoJSON is invalid or unsupported

    Example:
        >>> wkt = geojson_to_wkt({
        ...     "type": "Polygon",
        ...     "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
        ... })
        >>> print(wkt)
        POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))
    """
    # Extract geometry from Feature or FeatureCollection
    geometry = _extract_geometry(geojson)

    if geometry is None:
        raise ValidationError("No geometry found in GeoJSON", field="geojson")

    geom_type = geometry.get("type", "").upper()
    coordinates = geometry.get("coordinates")

    if coordinates is None:
        raise ValidationError("No coordinates in geometry", field="geojson")

    if geom_type == "POINT":
        return _point_to_wkt(coordinates)
    elif geom_type == "LINESTRING":
        return _linestring_to_wkt(coordinates)
    elif geom_type == "POLYGON":
        return _polygon_to_wkt(coordinates)
    elif geom_type == "MULTIPOINT":
        return _multipoint_to_wkt(coordinates)
    elif geom_type == "MULTILINESTRING":
        return _multilinestring_to_wkt(coordinates)
    elif geom_type == "MULTIPOLYGON":
        return _multipolygon_to_wkt(coordinates)
    else:
        raise ValidationError(f"Unsupported geometry type: {geom_type}", field="geojson")


def wkt_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT to GeoJSON geometry.

    Args:
        wkt: WKT string

    Returns:
        GeoJSON geometry dictionary

    Raises:
        ValidationError: If WKT is invalid

    Example:
        >>> geojson = wkt_to_geojson("POINT (1 2)")
        >>> print(geojson)
        {'type': 'Point', 'coordinates': [1.0, 2.0]}
    """
    wkt = wkt.strip()

    # Extract type and coordinates
    try:
        if wkt.upper().startswith("POINT"):
            return _wkt_point_to_geojson(wkt)
        elif wkt.upper().startswith("LINESTRING"):
            return _wkt_linestring_to_geojson(wkt)
        elif wkt.upper().startswith("POLYGON"):
            return _wkt_polygon_to_geojson(wkt)
        elif wkt.upper().startswith("MULTIPOINT"):
            return _wkt_multipoint_to_geojson(wkt)
        elif wkt.upper().startswith("MULTILINESTRING"):
            return _wkt_multilinestring_to_geojson(wkt)
        elif wkt.upper().startswith("MULTIPOLYGON"):
            return _wkt_multipolygon_to_geojson(wkt)
        else:
            raise ValidationError(f"Unsupported WKT type: {wkt[:20]}", field="wkt")
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Failed to parse WKT: {e}", field="wkt") from e


def bbox_to_geojson(bbox: list[float]) -> dict[str, Any]:
    """Convert bounding box to GeoJSON Polygon.

    Args:
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]

    Returns:
        GeoJSON Polygon geometry

    Raises:
        ValidationError: If bbox is invalid

    Example:
        >>> geojson = bbox_to_geojson([9.0, 45.0, 9.5, 45.5])
    """
    if len(bbox) != 4:
        raise ValidationError("Bounding box must have 4 values", field="bbox")

    min_lon, min_lat, max_lon, max_lat = bbox

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def geojson_to_bbox(geojson: dict[str, Any]) -> list[float]:
    """Extract bounding box from GeoJSON.

    Args:
        geojson: GeoJSON dictionary

    Returns:
        Bounding box [min_lon, min_lat, max_lon, max_lat]

    Raises:
        ValidationError: If GeoJSON is invalid
    """
    geometry = _extract_geometry(geojson)

    if geometry is None:
        raise ValidationError("No geometry found in GeoJSON", field="geojson")

    # If bbox is already present, use it
    if "bbox" in geojson:
        return geojson["bbox"]

    # Calculate bbox from coordinates
    coords = _flatten_coordinates(geometry.get("coordinates", []))

    if not coords:
        raise ValidationError("No coordinates found", field="geojson")

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    return [min(lons), min(lats), max(lons), max(lats)]


def simplify_geometry(geojson: dict[str, Any], tolerance: float = 0.01) -> dict[str, Any]:
    """Simplify a GeoJSON geometry using Douglas-Peucker algorithm.

    This is a basic implementation. For production use, consider
    using shapely with the 'geo' optional dependency.

    Args:
        geojson: GeoJSON geometry
        tolerance: Simplification tolerance in degrees

    Returns:
        Simplified GeoJSON geometry
    """
    try:
        from shapely import simplify as shapely_simplify
        from shapely.geometry import mapping, shape

        geom = shape(_extract_geometry(geojson))
        simplified = shapely_simplify(geom, tolerance, preserve_topology=True)
        return mapping(simplified)
    except ImportError:
        # Return original if shapely not available
        return geojson


def validate_geometry(geojson: dict[str, Any]) -> bool:
    """Validate a GeoJSON geometry.

    Args:
        geojson: GeoJSON dictionary

    Returns:
        True if valid, raises ValidationError otherwise
    """
    geometry = _extract_geometry(geojson)

    if geometry is None:
        raise ValidationError("No geometry found", field="geojson")

    geom_type = geometry.get("type")
    if geom_type is None:
        raise ValidationError("Geometry missing type", field="geojson")

    coords = geometry.get("coordinates")
    if coords is None:
        raise ValidationError("Geometry missing coordinates", field="geojson")

    # Type-specific validation
    valid_types = [
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
    ]
    if geom_type not in valid_types:
        raise ValidationError(f"Invalid geometry type: {geom_type}", field="geojson")

    return True


# =============================================================================
# Private Helper Functions
# =============================================================================


def _extract_geometry(geojson: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extract geometry from GeoJSON (handles Feature, FeatureCollection)."""
    if not geojson:
        return None

    geom_type = geojson.get("type")

    if geom_type == "FeatureCollection":
        features = geojson.get("features", [])
        if features:
            return features[0].get("geometry")
        return None

    if geom_type == "Feature":
        return geojson.get("geometry")

    # Assume it's a raw geometry
    if geom_type in [
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
    ]:
        return geojson

    return None


def _flatten_coordinates(coords: Any) -> list[list[float]]:
    """Recursively flatten nested coordinate arrays to list of [lon, lat]."""
    if not coords:
        return []

    # Check if this is a coordinate pair [lon, lat]
    if isinstance(coords[0], (int, float)):
        return [coords]

    # Recursively flatten
    result = []
    for item in coords:
        result.extend(_flatten_coordinates(item))
    return result


def _coords_to_wkt_string(coords: list[float]) -> str:
    """Convert coordinate pair to WKT string."""
    return f"{coords[0]} {coords[1]}"


def _point_to_wkt(coords: list[float]) -> str:
    """Convert Point coordinates to WKT."""
    return f"POINT ({_coords_to_wkt_string(coords)})"


def _linestring_to_wkt(coords: list[list[float]]) -> str:
    """Convert LineString coordinates to WKT."""
    points = ", ".join(_coords_to_wkt_string(c) for c in coords)
    return f"LINESTRING ({points})"


def _polygon_to_wkt(coords: list[list[list[float]]]) -> str:
    """Convert Polygon coordinates to WKT."""
    rings = []
    for ring in coords:
        points = ", ".join(_coords_to_wkt_string(c) for c in ring)
        rings.append(f"({points})")
    return f"POLYGON ({', '.join(rings)})"


def _multipoint_to_wkt(coords: list[list[float]]) -> str:
    """Convert MultiPoint coordinates to WKT."""
    points = ", ".join(f"({_coords_to_wkt_string(c)})" for c in coords)
    return f"MULTIPOINT ({points})"


def _multilinestring_to_wkt(coords: list[list[list[float]]]) -> str:
    """Convert MultiLineString coordinates to WKT."""
    lines = []
    for line in coords:
        points = ", ".join(_coords_to_wkt_string(c) for c in line)
        lines.append(f"({points})")
    return f"MULTILINESTRING ({', '.join(lines)})"


def _multipolygon_to_wkt(coords: list[list[list[list[float]]]]) -> str:
    """Convert MultiPolygon coordinates to WKT."""
    polygons = []
    for polygon in coords:
        rings = []
        for ring in polygon:
            points = ", ".join(_coords_to_wkt_string(c) for c in ring)
            rings.append(f"({points})")
        polygons.append(f"({', '.join(rings)})")
    return f"MULTIPOLYGON ({', '.join(polygons)})"


def _parse_wkt_coords(coord_str: str) -> list[float]:
    """Parse WKT coordinate string to [lon, lat]."""
    parts = coord_str.strip().split()
    return [float(parts[0]), float(parts[1])]


def _parse_wkt_coord_list(coords_str: str) -> list[list[float]]:
    """Parse WKT coordinate list."""
    coords_str = coords_str.strip()
    if not coords_str:
        return []
    return [_parse_wkt_coords(c) for c in coords_str.split(",")]


def _wkt_point_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT Point to GeoJSON."""
    # Extract coordinates from POINT (x y)
    coords_str = wkt[wkt.index("(") + 1 : wkt.rindex(")")].strip()
    coords = _parse_wkt_coords(coords_str)
    return {"type": "Point", "coordinates": coords}


def _wkt_linestring_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT LineString to GeoJSON."""
    coords_str = wkt[wkt.index("(") + 1 : wkt.rindex(")")].strip()
    coords = _parse_wkt_coord_list(coords_str)
    return {"type": "LineString", "coordinates": coords}


def _wkt_polygon_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT Polygon to GeoJSON."""
    # Find the outer parentheses
    start = wkt.index("(")
    content = wkt[start + 1 : wkt.rindex(")")].strip()

    # Parse rings
    rings = []
    depth = 0
    current = ""

    for char in content:
        if char == "(":
            depth += 1
            if depth == 1:
                current = ""
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                rings.append(_parse_wkt_coord_list(current))
                current = ""
                continue
        if depth > 0:
            current += char

    return {"type": "Polygon", "coordinates": rings}


def _wkt_multipoint_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT MultiPoint to GeoJSON."""
    start = wkt.index("(")
    content = wkt[start + 1 : wkt.rindex(")")].strip()

    # Handle both MULTIPOINT (0 0, 1 1) and MULTIPOINT ((0 0), (1 1))
    if "(" in content:
        # Format with parentheses
        coords = []
        for match in content.replace("(", "").replace(")", "").split(","):
            coords.append(_parse_wkt_coords(match.strip()))
    else:
        coords = _parse_wkt_coord_list(content)

    return {"type": "MultiPoint", "coordinates": coords}


def _wkt_multilinestring_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT MultiLineString to GeoJSON."""
    start = wkt.index("(")
    content = wkt[start + 1 : wkt.rindex(")")].strip()

    lines = []
    depth = 0
    current = ""

    for char in content:
        if char == "(":
            depth += 1
            if depth == 1:
                current = ""
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                lines.append(_parse_wkt_coord_list(current))
                current = ""
                continue
        if depth > 0:
            current += char

    return {"type": "MultiLineString", "coordinates": lines}


def _wkt_multipolygon_to_geojson(wkt: str) -> dict[str, Any]:
    """Convert WKT MultiPolygon to GeoJSON."""
    start = wkt.index("(")
    content = wkt[start + 1 : wkt.rindex(")")].strip()

    polygons = []
    depth = 0
    current = ""

    for char in content:
        if char == "(":
            depth += 1
            if depth == 1:
                current = ""
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                # Parse the polygon
                poly_geojson = _wkt_polygon_to_geojson(f"POLYGON ({current})")
                polygons.append(poly_geojson["coordinates"])
                current = ""
                continue
        if depth > 0:
            current += char

    return {"type": "MultiPolygon", "coordinates": polygons}
