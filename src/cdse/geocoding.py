"""Geocoding utilities for city-based searches.

This module provides functions to convert city names to bounding boxes
for use in satellite imagery searches.

Optional dependency: geopy
Install with: pip install cdse-client[geo] or pip install geopy
"""

import math
from typing import Optional

# Type alias for bounding box (min_lon, min_lat, max_lon, max_lat)
BBox = tuple[float, float, float, float]


def get_city_bbox(
    city_name: str,
    buffer_km: float = 15.0,
    user_agent: str = "cdse-client",
    timeout: float = 10.0,
) -> BBox:
    """
    Get a bounding box for a city using OpenStreetMap/Nominatim geocoding.

    This function geocodes a city name and creates a bounding box with a
    configurable buffer around the city center.

    Args:
        city_name: Name of the city, preferably with country
            (e.g., "Milan, Italy", "Paris, France")
        buffer_km: Buffer around city center in kilometers.
            Default 15km provides good coverage for typical cities.
        user_agent: User agent string for Nominatim API.
        timeout: Network timeout in seconds for geocoding requests.

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat) in WGS84.

    Raises:
        ImportError: If geopy is not installed.
        ValueError: If city is not found.

    Example:
        >>> bbox = get_city_bbox("Milano, Italia", buffer_km=20)
        >>> print(bbox)
        (8.9, 45.3, 9.4, 45.6)
    """
    try:
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
        from geopy.geocoders import Nominatim
    except ImportError as e:
        raise ImportError(
            "geopy is required for geocoding. "
            "Install with: pip install cdse-client[geo] or pip install geopy"
        ) from e

    geolocator = Nominatim(user_agent=user_agent, timeout=timeout)
    location = None
    for attempt in range(3):
        try:
            location = geolocator.geocode(city_name, exactly_one=True)
            break
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt >= 2:
                raise

    if not location:
        raise ValueError(f"City not found: {city_name}")

    lat, lon = location.latitude, location.longitude

    # Convert km to degrees (approximate)
    # 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(latitude)
    lat_buffer = buffer_km / 111.0
    lon_buffer = buffer_km / (111.0 * math.cos(math.radians(lat)))

    bbox = (
        round(lon - lon_buffer, 6),  # min_lon
        round(lat - lat_buffer, 6),  # min_lat
        round(lon + lon_buffer, 6),  # max_lon
        round(lat + lat_buffer, 6),  # max_lat
    )

    return bbox


def get_city_center(
    city_name: str,
    user_agent: str = "cdse-client",
    timeout: float = 10.0,
) -> tuple[float, float]:
    """
    Get the center coordinates for a city.

    Args:
        city_name: Name of the city (e.g., "Milan, Italy")
        user_agent: User agent string for Nominatim API.

    Returns:
        Tuple of (longitude, latitude) in WGS84.

    Raises:
        ImportError: If geopy is not installed.
        ValueError: If city is not found.

    Example:
        >>> lon, lat = get_city_center("Roma, Italia")
        >>> print(f"Rome is at {lat:.2f}°N, {lon:.2f}°E")
    """
    try:
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
        from geopy.geocoders import Nominatim
    except ImportError as e:
        raise ImportError(
            "geopy is required for geocoding. "
            "Install with: pip install cdse-client[geo] or pip install geopy"
        ) from e

    geolocator = Nominatim(user_agent=user_agent, timeout=timeout)
    location = None
    for attempt in range(3):
        try:
            location = geolocator.geocode(city_name, exactly_one=True)
            break
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt >= 2:
                raise

    if not location:
        raise ValueError(f"City not found: {city_name}")

    return (location.longitude, location.latitude)


def get_location_info(
    city_name: str,
    user_agent: str = "cdse-client",
    timeout: float = 10.0,
) -> dict:
    """
    Get detailed location information for a city.

    Args:
        city_name: Name of the city (e.g., "Milan, Italy")
        user_agent: User agent string for Nominatim API.

    Returns:
        Dictionary with location details:
            - address: Full formatted address
            - latitude: Latitude coordinate
            - longitude: Longitude coordinate
            - raw: Raw response from Nominatim (if available)

    Raises:
        ImportError: If geopy is not installed.
        ValueError: If city is not found.
    """
    try:
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
        from geopy.geocoders import Nominatim
    except ImportError as e:
        raise ImportError(
            "geopy is required for geocoding. "
            "Install with: pip install cdse-client[geo] or pip install geopy"
        ) from e

    geolocator = Nominatim(user_agent=user_agent, timeout=timeout)
    location = None
    for attempt in range(3):
        try:
            location = geolocator.geocode(city_name, exactly_one=True, addressdetails=True)
            break
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt >= 2:
                raise

    if not location:
        raise ValueError(f"City not found: {city_name}")

    return {
        "address": location.address,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "raw": getattr(location, "raw", None),
    }


# Pre-defined bounding boxes for major Italian cities (fallback without geopy)
ITALIAN_CITIES_BBOX = {
    "milano": (9.040, 45.386, 9.278, 45.536),
    "roma": (12.234, 41.764, 12.668, 42.024),
    "napoli": (14.138, 40.780, 14.354, 40.920),
    "torino": (7.578, 45.006, 7.768, 45.144),
    "firenze": (11.153, 43.726, 11.333, 43.826),
    "bologna": (11.253, 44.434, 11.413, 44.534),
    "genova": (8.846, 44.364, 8.996, 44.464),
    "venezia": (12.233, 45.386, 12.433, 45.486),
    "palermo": (13.263, 38.066, 13.463, 38.186),
    "bari": (16.756, 41.056, 16.956, 41.176),
}

# Major European cities
EUROPEAN_CITIES_BBOX = {
    "paris": (2.224, 48.785, 2.470, 48.935),
    "london": (-0.351, 51.385, 0.149, 51.635),
    "berlin": (13.088, 52.338, 13.761, 52.675),
    "madrid": (-3.889, 40.312, -3.518, 40.564),
    "amsterdam": (4.729, 52.278, 5.079, 52.478),
    "brussels": (4.245, 50.763, 4.495, 50.963),
    "vienna": (16.182, 48.118, 16.582, 48.318),
    "munich": (11.360, 48.062, 11.723, 48.249),
    "barcelona": (2.052, 41.320, 2.252, 41.470),
    "lisbon": (-9.230, 38.691, -9.080, 38.796),
}


def get_predefined_bbox(city_name: str) -> Optional[BBox]:
    """
    Get a pre-defined bounding box for a city (no geocoding required).

    This is useful as a fallback when geopy is not installed.

    Args:
        city_name: Name of the city (case-insensitive)

    Returns:
        Bounding box tuple or None if city not in database.

    Example:
        >>> bbox = get_predefined_bbox("milano")
        >>> if bbox:
        ...     print(f"Milan bbox: {bbox}")
    """
    normalized = city_name.lower().strip()

    # Check Italian cities first
    if normalized in ITALIAN_CITIES_BBOX:
        return ITALIAN_CITIES_BBOX[normalized]

    # Check European cities
    if normalized in EUROPEAN_CITIES_BBOX:
        return EUROPEAN_CITIES_BBOX[normalized]

    return None
