"""Main client for Copernicus Data Space Ecosystem."""

from pathlib import Path
from typing import Any, List, Optional

from cdse.auth import OAuth2Auth
from cdse.catalog import Catalog
from cdse.downloader import Downloader
from cdse.product import Product


class CDSEClient:
    """Main client for Copernicus Data Space Ecosystem.

    This is the primary interface for searching and downloading
    satellite data from CDSE. It combines authentication, catalog
    search, and download functionality into a simple API.

    Example:
        >>> client = CDSEClient(
        ...     client_id="your-client-id",
        ...     client_secret="your-client-secret"
        ... )
        >>>
        >>> # Search for products
        >>> products = client.search(
        ...     bbox=[9.0, 45.0, 9.5, 45.5],
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31",
        ...     collection="sentinel-2-l2a",
        ...     cloud_cover_max=20
        ... )
        >>>
        >>> # Download products
        >>> for product in products:
        ...     client.download(product)
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        output_dir: str = ".",
    ):
        """Initialize the CDSE client.

        Args:
            client_id: OAuth2 client ID. If not provided, reads from
                CDSE_CLIENT_ID environment variable.
            client_secret: OAuth2 client secret. If not provided, reads from
                CDSE_CLIENT_SECRET environment variable.
            output_dir: Default directory for downloaded files.

        Raises:
            AuthenticationError: If credentials are not provided.
        """
        self._auth = OAuth2Auth(client_id, client_secret)
        self._output_dir = Path(output_dir)

        # Lazy initialization
        self._catalog: Optional[Catalog] = None
        self._downloader: Optional[Downloader] = None

    @property
    def catalog(self) -> Catalog:
        """Get the catalog search client (lazy initialization)."""
        if self._catalog is None:
            session = self._auth.get_session()
            self._catalog = Catalog(session)
        return self._catalog

    @property
    def downloader(self) -> Downloader:
        """Get the downloader client (lazy initialization)."""
        if self._downloader is None:
            session = self._auth.get_bearer_session()
            self._downloader = Downloader(session, str(self._output_dir))
        return self._downloader

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
        return self.catalog.search(
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            collection=collection,
            cloud_cover_max=cloud_cover_max,
            limit=limit,
            **kwargs,
        )

    def search_by_point(
        self,
        lon: float,
        lat: float,
        start_date: str,
        end_date: str,
        buffer_km: float = 10.0,
        collection: str = "sentinel-2-l2a",
        cloud_cover_max: float = 100.0,
        limit: int = 10,
        **kwargs: Any,
    ) -> List[Product]:
        """Search for products by geographic point.

        Args:
            lon: Longitude (-180 to 180)
            lat: Latitude (-90 to 90)
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            buffer_km: Search radius in kilometers (default: 10)
            collection: Collection name
            cloud_cover_max: Maximum cloud coverage percentage
            limit: Maximum number of results
            **kwargs: Additional STAC API parameters

        Returns:
            List of Product objects
        """
        return self.catalog.search_by_point(
            lon=lon,
            lat=lat,
            buffer_km=buffer_km,
            start_date=start_date,
            end_date=end_date,
            collection=collection,
            cloud_cover_max=cloud_cover_max,
            limit=limit,
            **kwargs,
        )

    def download(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        progress: bool = True,
    ) -> Path:
        """Download a single product.

        Args:
            product: Product to download
            output_dir: Override output directory
            filename: Custom filename (default: product_name.zip)
            progress: Show progress bar

        Returns:
            Path to the downloaded file

        Raises:
            DownloadError: If download fails
        """
        return self.downloader.download(
            product=product,
            output_dir=output_dir,
            filename=filename,
            progress=progress,
        )

    def download_all(
        self,
        products: List[Product],
        output_dir: Optional[str] = None,
        skip_existing: bool = True,
        progress: bool = True,
    ) -> List[Path]:
        """Download multiple products.

        Args:
            products: List of products to download
            output_dir: Override output directory
            skip_existing: Skip already downloaded products
            progress: Show progress bars

        Returns:
            List of paths to downloaded files
        """
        return self.downloader.download_all(
            products=products,
            output_dir=output_dir,
            skip_existing=skip_existing,
            progress=progress,
        )

    def get_collections(self) -> dict:
        """Get available data collections.

        Returns:
            Dictionary mapping collection IDs to descriptions.
        """
        return self.catalog.get_collections()

    def refresh_auth(self) -> None:
        """Refresh authentication token.

        Call this if you need to refresh the token before it expires.
        """
        self._auth.refresh()
        # Reset lazy-loaded clients to use new token
        self._catalog = None
        self._downloader = None
