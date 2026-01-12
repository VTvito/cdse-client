"""
CDSE Client - Python client for Copernicus Data Space Ecosystem.

A modern, drop-in replacement for the deprecated sentinelsat library.
"""

from cdse.client import CDSEClient
from cdse.product import Product
from cdse.auth import OAuth2Auth
from cdse.catalog import Catalog
from cdse.downloader import Downloader
from cdse.exceptions import (
    CDSEError,
    AuthenticationError,
    CatalogError,
    DownloadError,
    ValidationError,
)

__version__ = "0.1.0"
__author__ = "Vito D'Elia"
__email__ = "75219756+VTvito@users.noreply.github.com"

__all__ = [
    "CDSEClient",
    "Product",
    "OAuth2Auth",
    "Catalog",
    "Downloader",
    "CDSEError",
    "AuthenticationError",
    "CatalogError",
    "DownloadError",
    "ValidationError",
    "__version__",
]
