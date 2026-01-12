"""Product representation for CDSE catalog results."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Product:
    """Represents a satellite product from CDSE catalog.

    This class wraps the raw STAC feature response and provides
    convenient access to common properties.

    Attributes:
        id: Unique product identifier
        name: Product name (e.g., S2A_MSIL2A_...)
        collection: Collection name (e.g., sentinel-2-l2a)
        datetime: Acquisition datetime
        cloud_cover: Cloud cover percentage (0-100)
        geometry: GeoJSON geometry of the product footprint
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
        properties: Full properties dictionary from STAC response
        assets: Available assets for download
        raw: Original STAC feature dictionary
    """

    id: str
    name: str
    collection: str
    datetime: Optional[datetime]
    cloud_cover: Optional[float]
    geometry: Dict[str, Any]
    bbox: List[float]
    properties: Dict[str, Any]
    assets: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_stac_feature(cls, feature: Dict[str, Any]) -> "Product":
        """Create a Product from a STAC feature dictionary.

        Args:
            feature: STAC feature dictionary from catalog search

        Returns:
            Product instance
        """
        props = feature.get("properties", {})

        # Parse datetime
        dt_str = props.get("datetime")
        dt = None
        if dt_str:
            try:
                # Handle various datetime formats
                dt_str = dt_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
            except ValueError:
                pass

        # Get product name - try multiple fields
        name = (
            feature.get("id")
            or props.get("id")
            or props.get("title")
            or "unknown"
        )

        return cls(
            id=feature.get("id", ""),
            name=name,
            collection=props.get("collection", feature.get("collection", "")),
            datetime=dt,
            cloud_cover=props.get("eo:cloud_cover"),
            geometry=feature.get("geometry", {}),
            bbox=feature.get("bbox", []),
            properties=props,
            assets=feature.get("assets", {}),
            raw=feature,
        )

    @property
    def size(self) -> Optional[int]:
        """Get product size in bytes if available."""
        return self.properties.get("size") or self.properties.get("content-length")

    @property
    def size_mb(self) -> Optional[float]:
        """Get product size in megabytes."""
        size = self.size
        return size / (1024 * 1024) if size else None

    @property
    def platform(self) -> Optional[str]:
        """Get satellite platform (e.g., sentinel-2a)."""
        return self.properties.get("platform")

    @property
    def instrument(self) -> Optional[str]:
        """Get instrument (e.g., MSI)."""
        instruments = self.properties.get("instruments", [])
        return instruments[0] if instruments else None

    @property
    def processing_level(self) -> Optional[str]:
        """Get processing level (e.g., L2A)."""
        return self.properties.get("processing:level")

    @property
    def tile_id(self) -> Optional[str]:
        """Get tile ID for Sentinel-2 products."""
        return self.properties.get("s2:tile_id") or self.properties.get("tile_id")

    @property
    def orbit_number(self) -> Optional[int]:
        """Get orbit number."""
        return self.properties.get("sat:relative_orbit")

    @property
    def download_url(self) -> Optional[str]:
        """Get direct download URL if available in assets."""
        # Try common asset keys
        for key in ["download", "data", "product"]:
            if key in self.assets:
                return self.assets[key].get("href")
        return None

    def __str__(self) -> str:
        """Return string representation."""
        dt_str = self.datetime.strftime("%Y-%m-%d") if self.datetime else "N/A"
        cloud = f"{self.cloud_cover:.1f}%" if self.cloud_cover is not None else "N/A"
        return f"Product({self.name}, date={dt_str}, cloud={cloud})"

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"Product(id='{self.id}', name='{self.name}', "
            f"collection='{self.collection}', datetime={self.datetime}, "
            f"cloud_cover={self.cloud_cover})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the product.
        """
        return {
            "id": self.id,
            "name": self.name,
            "collection": self.collection,
            "datetime": self.datetime.isoformat() if self.datetime else None,
            "cloud_cover": self.cloud_cover,
            "geometry": self.geometry,
            "bbox": self.bbox,
            "properties": self.properties,
        }
