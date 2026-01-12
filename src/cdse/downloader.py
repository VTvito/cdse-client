"""Product downloader for Copernicus Data Space Ecosystem."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from tqdm import tqdm

from cdse.exceptions import DownloadError
from cdse.product import Product


class Downloader:
    """Download products from CDSE.

    This class handles downloading satellite products from the
    Copernicus Data Space Ecosystem using the OData API.

    Attributes:
        ODATA_URL: OData API base URL for product downloads
        CATALOG_URL: OData catalog URL for product lookups

    Example:
        >>> downloader = Downloader(session, output_dir="./data")
        >>> path = downloader.download(product)
    """

    ODATA_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"
    CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    def __init__(
        self,
        session: requests.Session,
        output_dir: str = ".",
        chunk_size: int = 8192,
    ):
        """Initialize the downloader.

        Args:
            session: Authenticated requests session (with Bearer token)
            output_dir: Default directory for downloaded files
            chunk_size: Size of download chunks in bytes
        """
        self.session = session
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        progress: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download a single product.

        Args:
            product: Product to download
            output_dir: Override output directory
            filename: Custom filename (default: product_id.zip)
            progress: Show progress bar (default: True)
            progress_callback: Optional callback(downloaded, total) for progress

        Returns:
            Path to the downloaded file

        Raises:
            DownloadError: If download fails
        """
        # Determine output path
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            filename = f"{product.name}.zip"

        output_path = out_dir / filename

        # Skip if already exists
        if output_path.exists():
            return output_path

        # Get download URL
        download_url = self._get_download_url(product)
        if not download_url:
            raise DownloadError(
                f"Could not determine download URL for product",
                product_id=product.id,
            )

        try:
            # Stream download
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()

            # Get file size
            total_size = int(response.headers.get("content-length", 0))

            # Download with optional progress bar
            downloaded = 0
            with open(output_path, "wb") as f:
                iterator = response.iter_content(chunk_size=self.chunk_size)

                if progress and total_size > 0:
                    iterator = tqdm(
                        iterator,
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=filename[:50],
                    )

                for chunk in iterator:
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

            return output_path

        except requests.exceptions.HTTPError as e:
            # Clean up partial file
            if output_path.exists():
                output_path.unlink()
            raise DownloadError(
                f"Download failed: {e.response.status_code} - {e.response.text}",
                product_id=product.id,
            )
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise DownloadError(f"Download error: {e}", product_id=product.id)

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
        downloaded_files = []

        for idx, product in enumerate(products, 1):
            print(f"[{idx}/{len(products)}] Downloading: {product.name}")

            try:
                path = self.download(
                    product=product,
                    output_dir=output_dir,
                    progress=progress,
                )
                downloaded_files.append(path)
            except DownloadError as e:
                print(f"  Error: {e.message}")
                continue

        return downloaded_files

    def _get_download_url(self, product: Product) -> Optional[str]:
        """Get the download URL for a product.

        Args:
            product: Product to get URL for

        Returns:
            Download URL or None if not found
        """
        # First check if product has direct download URL
        if product.download_url:
            return product.download_url

        # Query OData catalog to get UUID
        try:
            product_name = product.name

            # Query for product UUID
            query_url = (
                f"{self.CATALOG_URL}"
                f"?$filter=startswith(Name, '{product_name}')"
            )

            response = self.session.get(query_url)
            response.raise_for_status()

            data = response.json()
            if data.get("value") and len(data["value"]) > 0:
                product_uuid = data["value"][0].get("Id")
                if product_uuid:
                    return f"{self.ODATA_URL}({product_uuid})/$value"

            return None

        except Exception:
            return None

    def get_product_info(self, product_id: str) -> Dict[str, Any]:
        """Get detailed information about a product.

        Args:
            product_id: Product UUID

        Returns:
            Dictionary with product metadata

        Raises:
            DownloadError: If API request fails
        """
        url = f"{self.CATALOG_URL}({product_id})"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise DownloadError(
                f"Failed to get product info: {e.response.status_code}",
                product_id=product_id,
            )

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.23 GB")
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
