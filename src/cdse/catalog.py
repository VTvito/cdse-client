"""Catalog search for Copernicus Data Space Ecosystem."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from cdse.exceptions import CatalogError, ValidationError
from cdse.product import Product


class Catalog:
    """STAC API catalog search for CDSE.

    This class provides search functionality using the CDSE STAC API
    to find satellite products based on various criteria.

    Attributes:
        CATALOG_URL: CDSE STAC API endpoint
        COLLECTIONS: Available data collections

    Example:
        >>> catalog = Catalog(session)
        >>> products = catalog.search(
        ...     bbox=[9.0, 45.0, 9.5, 45.5],
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31"
        ... )
    """

    CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"

    # Available collections
    COLLECTIONS = {
        "sentinel-1-grd": "Sentinel-1 GRD",
        "sentinel-2-l1c": "Sentinel-2 L1C",
        "sentinel-2-l2a": "Sentinel-2 L2A",
        "sentinel-3-olci": "Sentinel-3 OLCI",
        "sentinel-3-slstr": "Sentinel-3 SLSTR",
        "sentinel-5p-l2": "Sentinel-5P L2",
    }

    def __init__(self, session: requests.Session):
        """Initialize catalog with authenticated session.

        Args:
            session: Authenticated requests session (from OAuth2Auth)
        """
        self.session = session

    def search(
        self,
        bbox: List[float],
        start_date: str,
        end_date: str,
        collection: str = "sentinel-2-l2a",
        cloud_cover_max: float = 100.0,
        limit: int = 10,
        **kwargs: Any,
    ) -> List[Product]:
        """Search for products in the CDSE catalog.

        Args:
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            collection: Collection name (default: sentinel-2-l2a)
            cloud_cover_max: Maximum cloud coverage percentage (0-100)
            limit: Maximum number of results
            **kwargs: Additional STAC API parameters

        Returns:
            List of Product objects matching the search criteria

        Raises:
            ValidationError: If input parameters are invalid
            CatalogError: If the API request fails
        """
        # Validate inputs
        self._validate_bbox(bbox)
        self._validate_dates(start_date, end_date)
        self._validate_cloud_cover(cloud_cover_max)

        # Build STAC API query
        query_params = {
            "collections": [collection],
            "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
            "bbox": bbox,
            "limit": limit,
        }

        # Add any additional parameters
        if kwargs:
            query_params.update(kwargs)

        try:
            response = self.session.post(
                self.CATALOG_URL,
                json=query_params,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            results = response.json()
            features = results.get("features", [])

            # Filter by cloud cover
            filtered = self._filter_by_cloud_cover(features, cloud_cover_max)

            # Filter by center point containment
            center_lon = (bbox[0] + bbox[2]) / 2
            center_lat = (bbox[1] + bbox[3]) / 2
            filtered = self._filter_by_center_point(filtered, center_lon, center_lat)

            # Convert to Product objects
            products = [Product.from_stac_feature(f) for f in filtered[:limit]]

            return products

        except requests.exceptions.HTTPError as e:
            raise CatalogError(
                f"Catalog search failed: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise CatalogError(f"Catalog search error: {e}")

    def search_by_point(
        self,
        lon: float,
        lat: float,
        buffer_km: float = 10.0,
        **kwargs: Any,
    ) -> List[Product]:
        """Search for products by geographic point.

        Args:
            lon: Longitude (-180 to 180)
            lat: Latitude (-90 to 90)
            buffer_km: Search radius in kilometers (default: 10)
            **kwargs: Additional search parameters (passed to search())

        Returns:
            List of Product objects
        """
        # Convert km to approximate degrees (rough approximation)
        # 1 degree latitude ≈ 111 km
        buffer_deg = buffer_km / 111.0

        bbox = [
            lon - buffer_deg,
            lat - buffer_deg,
            lon + buffer_deg,
            lat + buffer_deg,
        ]

        return self.search(bbox=bbox, **kwargs)

    def get_collections(self) -> Dict[str, str]:
        """Get available collections.

        Returns:
            Dictionary mapping collection IDs to descriptions.
        """
        return self.COLLECTIONS.copy()

    def _filter_by_cloud_cover(
        self, features: List[Dict[str, Any]], max_cloud: float
    ) -> List[Dict[str, Any]]:
        """Filter features by cloud cover percentage.

        Args:
            features: List of STAC features
            max_cloud: Maximum cloud cover percentage

        Returns:
            Filtered list of features
        """
        filtered = []
        for f in features:
            cloud_cover = f.get("properties", {}).get("eo:cloud_cover", 100)
            if cloud_cover <= max_cloud:
                filtered.append(f)
        return filtered

    def _filter_by_center_point(
        self,
        features: List[Dict[str, Any]],
        center_lon: float,
        center_lat: float,
    ) -> List[Dict[str, Any]]:
        """Filter features that contain the center point.

        Args:
            features: List of STAC features
            center_lon: Center longitude
            center_lat: Center latitude

        Returns:
            Filtered list of features containing the center point
        """
        filtered = []
        for f in features:
            geometry = f.get("geometry", {})
            if self._point_in_geometry(center_lon, center_lat, geometry):
                filtered.append(f)
            elif not geometry:
                # If no geometry, keep the feature
                filtered.append(f)
        return filtered

    def _point_in_geometry(
        self, lon: float, lat: float, geometry: Dict[str, Any]
    ) -> bool:
        """Check if a point is inside a geometry (simplified bbox check).

        Args:
            lon: Point longitude
            lat: Point latitude
            geometry: GeoJSON geometry

        Returns:
            True if point is inside geometry bounds
        """
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates", [])

        if geom_type == "MultiPolygon":
            coords = coords[0] if coords else []

        if not coords:
            return True  # No geometry, assume inside

        # Get outer ring
        points = coords[0] if coords and isinstance(coords[0][0], list) else coords

        if not points:
            return True

        # Simple bounding box check
        try:
            lons = [p[0] for p in points]
            lats = [p[1] for p in points]
            return min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats)
        except (IndexError, TypeError):
            return True

    def _validate_bbox(self, bbox: List[float]) -> None:
        """Validate bounding box format and values.

        Args:
            bbox: Bounding box to validate

        Raises:
            ValidationError: If bbox is invalid
        """
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValidationError(
                "bbox must be a list of 4 values: [min_lon, min_lat, max_lon, max_lat]",
                field="bbox",
            )

        min_lon, min_lat, max_lon, max_lat = bbox

        if not (-180 <= min_lon <= 180) or not (-180 <= max_lon <= 180):
            raise ValidationError(
                f"Longitude must be between -180 and 180, got {min_lon}, {max_lon}",
                field="bbox",
            )

        if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
            raise ValidationError(
                f"Latitude must be between -90 and 90, got {min_lat}, {max_lat}",
                field="bbox",
            )

        if min_lon >= max_lon:
            raise ValidationError(
                f"min_lon must be < max_lon, got {min_lon} >= {max_lon}",
                field="bbox",
            )

        if min_lat >= max_lat:
            raise ValidationError(
                f"min_lat must be < max_lat, got {min_lat} >= {max_lat}",
                field="bbox",
            )

    def _validate_dates(self, start_date: str, end_date: str) -> None:
        """Validate date format and range.

        Args:
            start_date: Start date string
            end_date: End date string

        Raises:
            ValidationError: If dates are invalid
        """
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError as e:
            raise ValidationError(
                f"Invalid date format. Use YYYY-MM-DD: {e}",
                field="date",
            )

        if start >= end:
            raise ValidationError(
                f"start_date must be before end_date: {start_date} >= {end_date}",
                field="date",
            )

    def _validate_cloud_cover(self, cloud_cover: float) -> None:
        """Validate cloud cover percentage.

        Args:
            cloud_cover: Cloud cover value

        Raises:
            ValidationError: If cloud cover is invalid
        """
        if not (0 <= cloud_cover <= 100):
            raise ValidationError(
                f"cloud_cover must be between 0 and 100, got {cloud_cover}",
                field="cloud_cover",
            )
