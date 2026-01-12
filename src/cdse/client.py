"""Main client for Copernicus Data Space Ecosystem."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from cdse.auth import OAuth2Auth
from cdse.catalog import Catalog
from cdse.converters import products_size, to_dataframe, to_geodataframe, to_geojson
from cdse.downloader import Downloader
from cdse.product import Product

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd


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
        bbox: list[float],
        start_date: str,
        end_date: str,
        collection: str = "sentinel-2-l2a",
        cloud_cover_max: float = 100.0,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[Product]:
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
    ) -> list[Product]:
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
        products: list[Product],
        output_dir: Optional[str] = None,
        skip_existing: bool = True,
        progress: bool = True,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> list[Path]:
        """Download multiple products.

        Args:
            products: List of products to download
            output_dir: Override output directory
            skip_existing: Skip already downloaded products
            progress: Show progress bars
            parallel: Enable parallel downloads for faster performance
            max_workers: Number of parallel download workers (when parallel=True)

        Returns:
            List of paths to downloaded files
        """
        return self.downloader.download_all(
            products=products,
            output_dir=output_dir,
            skip_existing=skip_existing,
            progress=progress,
            parallel=parallel,
            max_workers=max_workers,
        )

    def search_by_name(
        self,
        name: str,
        exact: bool = True,
    ) -> Optional[Product]:
        """Search for a product by its name.

        Args:
            name: Product name (e.g., S2A_MSIL2A_20240115...)
            exact: If True, require exact match. If False, use prefix match.

        Returns:
            Product if found, None otherwise

        Raises:
            CatalogError: If API request fails
        """
        return self.catalog.search_by_name(name=name, exact=exact)

    def search_by_id(
        self,
        product_id: str,
    ) -> Optional[Product]:
        """Search for a product by its UUID.

        Args:
            product_id: Product UUID

        Returns:
            Product if found, None otherwise

        Raises:
            CatalogError: If API request fails
        """
        return self.catalog.search_by_id(product_id=product_id)

    def download_with_checksum(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        progress: bool = True,
    ) -> Path:
        """Download a product and verify its checksum.

        Args:
            product: Product to download
            output_dir: Override output directory
            progress: Show progress bar

        Returns:
            Path to downloaded file (verified)

        Raises:
            DownloadError: If download or checksum verification fails
        """
        return self.downloader.download_with_checksum(
            product=product,
            output_dir=output_dir,
            progress=progress,
        )

    def search_by_city(
        self,
        city_name: str,
        start_date: str,
        end_date: str,
        buffer_km: float = 15.0,
        collection: str = "sentinel-2-l2a",
        cloud_cover_max: float = 100.0,
        limit: int = 10,
        use_predefined: bool = False,
        geocoding_timeout: float = 10.0,
        geocoding_user_agent: str = "cdse-client",
        **kwargs: Any,
    ) -> list[Product]:
        """Search for products over a city.

        This method geocodes a city name to coordinates and searches
        for satellite products within a buffer around the city center.

        Args:
            city_name: Name of the city (e.g., "Milano, Italia", "Paris, France")
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            buffer_km: Buffer around city center in kilometers (default: 15)
            collection: Collection name (default: sentinel-2-l2a)
            cloud_cover_max: Maximum cloud coverage percentage (0-100)
            limit: Maximum number of results
            use_predefined: Use predefined city bbox instead of geocoding.
                Useful as fallback when geopy is not installed.
            geocoding_timeout: Network timeout in seconds for live geocoding.
            geocoding_user_agent: User agent for Nominatim geocoding.
            **kwargs: Additional STAC API parameters

        Returns:
            List of Product objects matching the search criteria

        Raises:
            ImportError: If geopy is not installed and use_predefined is False
            ValueError: If city is not found
            CatalogError: If the API request fails

        Example:
            >>> products = client.search_by_city(
            ...     city_name="Roma, Italia",
            ...     start_date="2024-08-01",
            ...     end_date="2024-08-31",
            ...     cloud_cover_max=20
            ... )
        """
        from cdse.geocoding import get_city_bbox, get_predefined_bbox

        if use_predefined:
            bbox = get_predefined_bbox(city_name)
            if bbox is None:
                raise ValueError(
                    f"City '{city_name}' not in predefined database. "
                    "Use geocoding (set use_predefined=False) or provide a bbox."
                )
        else:
            bbox = get_city_bbox(
                city_name,
                buffer_km=buffer_km,
                user_agent=geocoding_user_agent,
                timeout=geocoding_timeout,
            )

        return self.catalog.search(
            bbox=list(bbox),
            start_date=start_date,
            end_date=end_date,
            collection=collection,
            cloud_cover_max=cloud_cover_max,
            limit=limit,
            **kwargs,
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

    # ========== Data Format Conversion Methods (sentinelsat compatible) ==========

    @staticmethod
    def to_dataframe(products: list[Product]) -> "pd.DataFrame":
        """Convert products to Pandas DataFrame.

        Requires pandas to be installed: pip install pandas

        Args:
            products: List of Product objects from search results

        Returns:
            pandas.DataFrame with product metadata, indexed by product ID

        Raises:
            ImportError: If pandas is not installed

        Example:
            >>> products = client.search(...)
            >>> df = client.to_dataframe(products)
            >>> df_sorted = df.sort_values('cloud_cover')
            >>> df.head()
        """
        return to_dataframe(products)

    @staticmethod
    def to_geojson(products: list[Product]) -> dict[str, Any]:
        """Convert products to GeoJSON FeatureCollection.

        Args:
            products: List of Product objects from search results

        Returns:
            GeoJSON FeatureCollection dictionary with footprints

        Example:
            >>> products = client.search(...)
            >>> geojson = client.to_geojson(products)
            >>> with open("footprints.geojson", "w") as f:
            ...     json.dump(geojson, f)
        """
        return to_geojson(products)

    @staticmethod
    def to_geodataframe(products: list[Product]) -> "gpd.GeoDataFrame":
        """Convert products to GeoPandas GeoDataFrame.

        Requires geopandas: pip install geopandas

        Args:
            products: List of Product objects from search results

        Returns:
            geopandas.GeoDataFrame with metadata and geometry

        Raises:
            ImportError: If geopandas is not installed

        Example:
            >>> products = client.search(...)
            >>> gdf = client.to_geodataframe(products)
            >>> gdf.plot()  # Visualize footprints
        """
        return to_geodataframe(products)

    @staticmethod
    def get_products_size(products: list[Product]) -> float:
        """Calculate total size of products in GB.

        Args:
            products: List of Product objects

        Returns:
            Total size in gigabytes

        Example:
            >>> products = client.search(...)
            >>> size_gb = client.get_products_size(products)
            >>> print(f"Total: {size_gb:.2f} GB")
        """
        return products_size(products)

    def download_quicklook(
        self,
        product: Product,
        output_dir: Optional[str] = None,
    ) -> Path:
        """Download quicklook (preview) image for a product.

        Args:
            product: Product to get quicklook for
            output_dir: Output directory (default: client output_dir)

        Returns:
            Path to downloaded quicklook image

        Raises:
            DownloadError: If quicklook download fails
        """
        return self.downloader.download_quicklook(
            product=product,
            output_dir=output_dir,
        )

    def download_all_quicklooks(
        self,
        products: list[Product],
        output_dir: Optional[str] = None,
        parallel: bool = True,
        max_workers: int = 4,
    ) -> list[Path]:
        """Download quicklooks for multiple products.

        Args:
            products: List of products
            output_dir: Output directory
            parallel: Enable parallel downloads
            max_workers: Number of parallel workers

        Returns:
            List of paths to downloaded quicklook images
        """
        return self.downloader.download_all_quicklooks(
            products=products,
            output_dir=output_dir,
            parallel=parallel,
            max_workers=max_workers,
        )
