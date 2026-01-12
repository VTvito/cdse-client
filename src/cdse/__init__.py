"""
CDSE Client - Python client for Copernicus Data Space Ecosystem.

A modern, drop-in replacement for the deprecated sentinelsat library.
"""

from cdse.auth import OAuth2Auth
from cdse.catalog import Catalog
from cdse.client import CDSEClient
from cdse.converters import (
    products_count,
    products_size,
    to_dataframe,
    to_geodataframe,
    to_geojson,
)
from cdse.downloader import Downloader
from cdse.exceptions import (
    AuthenticationError,
    CatalogError,
    CDSEError,
    DownloadError,
    ValidationError,
)
from cdse.geometry import (
    bbox_to_geojson,
    geojson_to_bbox,
    geojson_to_wkt,
    read_geojson,
    validate_geometry,
    wkt_to_geojson,
)
from cdse.product import Product

__version__ = "0.3.2"
__author__ = "Vito D'Elia"
__email__ = "75219756+VTvito@users.noreply.github.com"

__all__ = [
    # Main client
    "CDSEClient",
    # Core classes
    "Product",
    "OAuth2Auth",
    "Catalog",
    "Downloader",
    # Exceptions
    "CDSEError",
    "AuthenticationError",
    "CatalogError",
    "DownloadError",
    "ValidationError",
    # Geometry utilities (sentinelsat compatible)
    "read_geojson",
    "geojson_to_wkt",
    "wkt_to_geojson",
    "bbox_to_geojson",
    "geojson_to_bbox",
    "validate_geometry",
    # Data format converters (sentinelsat compatible)
    "to_dataframe",
    "to_geojson",
    "to_geodataframe",
    "products_size",
    "products_count",
    # Version
    "__version__",
]


# Lazy import for optional modules (requires optional dependencies)
def __getattr__(name):
    # Async client
    if name == "CDSEClientAsync":
        from cdse.async_client import CDSEClientAsync

        return CDSEClientAsync
    if name == "download_products_async":
        from cdse.async_client import download_products_async

        return download_products_async

    # Processing module
    # Import directly as `import cdse.processing` (requires: pip install cdse-client[processing]).

    # Geocoding module
    if name in (
        "get_city_bbox",
        "get_city_center",
        "get_location_info",
        "get_predefined_bbox",
        "ITALIAN_CITIES_BBOX",
        "EUROPEAN_CITIES_BBOX",
    ):
        from cdse import geocoding

        return getattr(geocoding, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
