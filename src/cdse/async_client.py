"""Async client for Copernicus Data Space Ecosystem.

This module provides asynchronous versions of the CDSE client
for high-performance concurrent downloads.

Requires: aiohttp, aiofiles (install with: pip install cdse-client[async])
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Optional

from cdse.exceptions import AuthenticationError, CatalogError, DownloadError
from cdse.product import Product

logger = logging.getLogger(__name__)


class CDSEClientAsync:
    """Async client for Copernicus Data Space Ecosystem.

    This client provides async methods for downloading products,
    enabling concurrent downloads for better performance.

    Example:
        >>> async with CDSEClientAsync(client_id, client_secret) as client:
        ...     products = await client.search(...)
        ...     paths = await client.download_all(products)
    """

    TOKEN_URL = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"  # nosec B105
    )
    CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
    ODATA_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"
    CATALOG_ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        output_dir: str = ".",
        max_concurrent: int = 4,
    ):
        """Initialize the async client.

        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            output_dir: Default output directory for downloads
            max_concurrent: Maximum concurrent downloads
        """
        import os

        self.client_id = client_id or os.environ.get("CDSE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("CDSE_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise AuthenticationError(
                "OAuth2 credentials required. Provide client_id and client_secret "
                "or set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET environment variables."
            )

        self.output_dir = Path(output_dir)
        self.max_concurrent = max_concurrent
        self._session: Any = None
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def __aenter__(self) -> "CDSEClientAsync":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is created and token is valid."""
        try:
            import aiohttp
        except ImportError as e:
            raise ImportError(
                "aiohttp is required for async support. "
                "Install with: pip install cdse-client[async]"
            ) from e

        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
            await self._authenticate()
        elif not self._is_token_valid():
            logger.debug("Async token expired, refreshing")
            await self._authenticate()

    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid (with 60s buffer)."""
        if self._access_token is None:
            return False
        return time.time() < (self._token_expires_at - 60)

    async def _authenticate(self) -> None:
        """Authenticate and get access token."""
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with self._session.post(self.TOKEN_URL, data=data) as response:
            if response.status != 200:
                text = await response.text()
                raise AuthenticationError(f"Authentication failed: {text}")

            token_data = await response.json()
            self._access_token = token_data.get("access_token")
            self._token_expires_at = token_data.get(
                "expires_at", time.time() + token_data.get("expires_in", 600)
            )

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers with authorization."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        bbox: list[float],
        start_date: str,
        end_date: str,
        collection: str = "sentinel-2-l2a",
        cloud_cover_max: float = 100.0,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[Product]:
        """Search for products asynchronously.

        Args:
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            collection: Collection name
            cloud_cover_max: Maximum cloud cover percentage
            limit: Maximum results
            **kwargs: Additional STAC parameters

        Returns:
            List of products matching criteria
        """
        await self._ensure_session()

        query = {
            "collections": [collection],
            "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
            "bbox": bbox,
            "limit": limit,
        }
        query.update(kwargs)

        async with self._session.post(
            self.CATALOG_URL,
            json=query,
            headers=self._get_headers(),
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise CatalogError(f"Search failed: {response.status} - {text}")

            data = await response.json()
            features = data.get("features", [])

            # Filter by cloud cover
            filtered = [
                f
                for f in features
                if f.get("properties", {}).get("eo:cloud_cover", 100) <= cloud_cover_max
            ]

            return [Product.from_stac_feature(f) for f in filtered[:limit]]

    async def download(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        progress: bool = True,
    ) -> Path:
        """Download a single product asynchronously.

        Args:
            product: Product to download
            output_dir: Override output directory
            progress: Show progress bar (default: True)

        Returns:
            Path to downloaded file
        """
        try:
            import aiofiles
        except ImportError as e:
            raise ImportError(
                "aiofiles is required for async downloads. "
                "Install with: pip install cdse-client[async]"
            ) from e

        from tqdm import tqdm

        await self._ensure_session()

        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{product.name}.zip"
        output_path = out_dir / filename

        if output_path.exists():
            return output_path

        # Get download URL
        download_url = await self._get_download_url(product)
        if not download_url:
            raise DownloadError(
                f"Could not get download URL for {product.name}",
                product_id=product.id,
            )

        # Download with semaphore for concurrency control
        async with self._semaphore:
            headers = {"Authorization": f"Bearer {self._access_token}"}

            async with self._session.get(download_url, headers=headers) as response:
                if response.status != 200:
                    raise DownloadError(
                        f"Download failed: {response.status}",
                        product_id=product.id,
                    )

                total_size = int(response.headers.get("content-length", 0))
                pbar = None
                if progress and total_size > 0:
                    pbar = tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=filename[:50],
                    )

                async with aiofiles.open(output_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):  # 128KB
                        await f.write(chunk)
                        if pbar:
                            pbar.update(len(chunk))

                if pbar:
                    pbar.close()

        return output_path

    async def download_all(
        self,
        products: list[Product],
        output_dir: Optional[str] = None,
        progress: bool = True,
    ) -> list[Path]:
        """Download multiple products concurrently.

        Args:
            products: List of products to download
            output_dir: Override output directory
            progress: Show overall progress bar (default: True)

        Returns:
            List of paths to downloaded files
        """
        from tqdm import tqdm

        await self._ensure_session()

        # Disable per-file progress in concurrent mode; show overall bar
        tasks = [self.download(product, output_dir, progress=False) for product in products]

        downloaded: list[Path] = []
        pbar = tqdm(total=len(products), desc="Downloading", disable=not progress)

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                downloaded.append(result)
            except Exception as exc:
                logger.warning("Download failed: %s", exc)
            pbar.update(1)

        pbar.close()
        return downloaded

    async def _get_download_url(self, product: Product) -> Optional[str]:
        """Get download URL for a product."""
        if product.download_url:
            return product.download_url

        # Ensure .SAFE suffix for exact match
        product_name = product.name
        if not product_name.endswith(".SAFE"):
            product_name = f"{product_name}.SAFE"

        # Use exact Name match - 60x FASTER than contains() or startswith()!
        query_url = f"{self.CATALOG_ODATA_URL}?$filter=Name eq '{product_name}'"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.get(query_url, headers=headers) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                items = data.get("value", [])

                if items:
                    product_uuid = items[0].get("Id")
                    if product_uuid:
                        return f"{self.ODATA_URL}({product_uuid})/$value"

        except Exception:
            return None

        return None


async def download_products_async(
    client_id: str,
    client_secret: str,
    products: list[Product],
    output_dir: str = ".",
    max_concurrent: int = 4,
) -> list[Path]:
    """Convenience function for async downloads.

    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        products: List of products to download
        output_dir: Output directory
        max_concurrent: Maximum concurrent downloads

    Returns:
        List of downloaded file paths

    Example:
        >>> from cdse import CDSEClient
        >>> from cdse.async_client import download_products_async
        >>>
        >>> # First search with sync client
        >>> client = CDSEClient(client_id, client_secret)
        >>> products = client.search(...)
        >>>
        >>> # Then download asynchronously
        >>> import asyncio
        >>> paths = asyncio.run(download_products_async(
        ...     client_id, client_secret, products, max_concurrent=8
        ... ))
    """
    async with CDSEClientAsync(
        client_id=client_id,
        client_secret=client_secret,
        output_dir=output_dir,
        max_concurrent=max_concurrent,
    ) as client:
        return await client.download_all(products)
