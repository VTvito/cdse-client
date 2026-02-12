"""Product downloader for Copernicus Data Space Ecosystem."""

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from tqdm import tqdm

from cdse.exceptions import DownloadError
from cdse.product import Product

logger = logging.getLogger(__name__)

# HTTP status codes that are retryable (transient errors)
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


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
        chunk_size: int = 131072,  # 128KB - much faster than default 8KB
        max_workers: int = 4,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """Initialize the downloader.

        Args:
            session: Authenticated requests session (with Bearer token)
            output_dir: Default directory for downloaded files
            chunk_size: Size of download chunks in bytes (default: 128KB)
            max_workers: Maximum number of parallel downloads
            timeout: Request timeout in seconds (default: 60)
            max_retries: Maximum number of retries for transient errors (default: 3)
        """
        self.session = session
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.max_workers = max_workers
        self.timeout = timeout
        self.max_retries = max_retries

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an HTTP request with retry and exponential backoff.

        Retries on transient errors (429, 502, 503, 504) and
        connection errors.

        Args:
            method: HTTP method ('get' or 'post')
            url: Request URL
            **kwargs: Additional arguments passed to requests

        Returns:
            requests.Response

        Raises:
            requests.exceptions.HTTPError: After all retries exhausted
            requests.exceptions.ConnectionError: After all retries exhausted
        """
        kwargs.setdefault("timeout", self.timeout)
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = getattr(self.session, method)(url, **kwargs)

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    wait = 2**attempt
                    logger.warning(
                        "Request to %s returned %d, retrying in %ds (attempt %d/%d)",
                        url[:80],
                        response.status_code,
                        wait,
                        attempt + 1,
                        self.max_retries,
                    )
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response  # type: ignore[no-any-return]

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                wait = 2**attempt
                logger.warning(
                    "Connection error for %s, retrying in %ds (attempt %d/%d): %s",
                    url[:80],
                    wait,
                    attempt + 1,
                    self.max_retries,
                    e,
                )
                time.sleep(wait)

        # All retries exhausted — raise the last error
        if last_exception:
            raise last_exception
        # If we got here via status code retries, raise the last response
        response.raise_for_status()
        return response  # type: ignore[no-any-return]  # unreachable, but keeps mypy happy

    def download(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        progress: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        skip_existing: bool = True,
    ) -> Path:
        """Download a single product.

        Args:
            product: Product to download
            output_dir: Override output directory
            filename: Custom filename (default: product_id.zip)
            progress: Show progress bar (default: True)
            progress_callback: Optional callback(downloaded, total) for progress
            skip_existing: Skip download if file already exists (default: True)

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
        if skip_existing and output_path.exists():
            return output_path

        # Get download URL
        download_url = self._get_download_url(product)
        if not download_url:
            raise DownloadError(
                "Could not determine download URL for product",
                product_id=product.id,
            )

        try:
            # Stream download with retry
            response = self._request_with_retry("get", download_url, stream=True)

            # Get file size
            total_size = int(response.headers.get("content-length", 0))

            # Download with progress bar
            downloaded = 0
            with open(output_path, "wb") as f:
                # Create progress bar that tracks bytes properly
                pbar = None
                if progress and total_size > 0:
                    pbar = tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        desc=filename[:50],
                    )

                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        chunk_len = len(chunk)
                        downloaded += chunk_len

                        if pbar:
                            pbar.update(chunk_len)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

                if pbar:
                    pbar.close()

            return output_path

        except requests.exceptions.HTTPError as e:
            # Clean up partial file
            if output_path.exists():
                output_path.unlink()
            raise DownloadError(
                f"Download failed: {e.response.status_code} - {e.response.text}",
                product_id=product.id,
            ) from e
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise DownloadError(f"Download error: {e}", product_id=product.id) from e

    def download_all(
        self,
        products: list[Product],
        output_dir: Optional[str] = None,
        skip_existing: bool = True,
        progress: bool = True,
        parallel: bool = False,
        max_workers: Optional[int] = None,
    ) -> list[Path]:
        """Download multiple products.

        Args:
            products: List of products to download
            output_dir: Override output directory
            skip_existing: Skip already downloaded products
            progress: Show progress bars
            parallel: Enable parallel downloads
            max_workers: Override max parallel workers (default: self.max_workers)

        Returns:
            List of paths to downloaded files
        """
        if parallel:
            return self._download_parallel(
                products=products,
                output_dir=output_dir,
                skip_existing=skip_existing,
                progress=progress,
                max_workers=max_workers,
            )

        # Sequential download
        downloaded_files = []

        for idx, product in enumerate(products, 1):
            logger.info("[%d/%d] Downloading: %s", idx, len(products), product.name)

            try:
                path = self.download(
                    product=product,
                    output_dir=output_dir,
                    progress=progress,
                    skip_existing=skip_existing,
                )
                downloaded_files.append(path)
            except DownloadError as e:
                logger.error("  Error downloading %s: %s", product.name, e.message)
                continue

        return downloaded_files

    def _download_parallel(
        self,
        products: list[Product],
        output_dir: Optional[str] = None,
        skip_existing: bool = True,
        progress: bool = True,
        max_workers: Optional[int] = None,
    ) -> list[Path]:
        """Download products in parallel using ThreadPoolExecutor.

        Args:
            products: List of products to download
            output_dir: Override output directory
            skip_existing: Skip already downloaded products
            progress: Show progress bars
            max_workers: Number of parallel workers

        Returns:
            List of paths to downloaded files
        """
        workers = max_workers or self.max_workers
        downloaded_files: list[Path] = []
        failed: list[tuple[str, str]] = []

        logger.info(
            "Starting parallel download of %d products with %d workers...",
            len(products),
            workers,
        )

        def download_one(product: Product) -> tuple[Optional[Path], Optional[str]]:
            """Download a single product, return (path, error)."""
            try:
                # Disable individual progress bars in parallel mode
                path = self.download(
                    product=product,
                    output_dir=output_dir,
                    progress=False,  # Disable per-file progress in parallel
                    skip_existing=skip_existing,
                )
                return (path, None)
            except DownloadError as e:
                return (None, f"{product.name}: {e.message}")
            except Exception as e:
                return (None, f"{product.name}: {str(e)}")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_product = {executor.submit(download_one, p): p for p in products}

            # Show overall progress bar
            with tqdm(total=len(products), desc="Downloading", disable=not progress) as pbar:
                for future in as_completed(future_to_product):
                    product = future_to_product[future]
                    path, error = future.result()

                    if path:
                        downloaded_files.append(path)
                    else:
                        failed.append((product.name, error or "Unknown error"))

                    pbar.update(1)

        # Report failures
        if failed:
            logger.warning("Failed downloads (%d):", len(failed))
            for _name, error in failed:
                logger.warning("  - %s", error)

        logger.info("Successfully downloaded: %d/%d", len(downloaded_files), len(products))
        return downloaded_files

    def _get_download_url(self, product: Product) -> Optional[str]:
        """Get the download URL for a product.

        Args:
            product: Product to get URL for

        Returns:
            Download URL or None if not found
        """
        # Check cache first (stored as _odata_uuid on product)
        if hasattr(product, "_odata_uuid") and product._odata_uuid:
            return f"{self.ODATA_URL}({product._odata_uuid})/$value"

        # Check if product has direct download URL (but not S3 URLs)
        if product.download_url:
            url = product.download_url
            # Skip S3 URLs - they require different authentication
            if not url.startswith("s3://"):
                return url

        # Query OData catalog to get UUID and build proper download URL
        try:
            product_name = product.name

            # Ensure .SAFE suffix for exact match (OData stores with .SAFE)
            if not product_name.endswith(".SAFE"):
                product_name = f"{product_name}.SAFE"

            # Use exact Name match - 60x FASTER than contains() or startswith()!
            # contains(): ~25s, startswith(): ~20s, Name eq: ~0.5s
            query_url = f"{self.CATALOG_URL}?$filter=Name eq '{product_name}'"

            response = self._request_with_retry("get", query_url)

            data = response.json()
            if data.get("value") and len(data["value"]) > 0:
                product_uuid = data["value"][0].get("Id")
                if product_uuid:
                    # Cache the UUID on the product for future use
                    product._odata_uuid = product_uuid
                    return f"{self.ODATA_URL}({product_uuid})/$value"

            return None

        except Exception:
            return None

    def get_product_info(self, product_id: str) -> dict[str, Any]:
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
            response = self._request_with_retry("get", url)
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise DownloadError(
                f"Failed to get product info: {e.response.status_code}",
                product_id=product_id,
            ) from e

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

    def verify_checksum(
        self,
        file_path: Path,
        expected_checksum: str,
        algorithm: str = "md5",
    ) -> bool:
        """Verify file checksum.

        Args:
            file_path: Path to file to verify
            expected_checksum: Expected checksum value
            algorithm: Hash algorithm (md5, sha256, sha1)

        Returns:
            True if checksum matches, False otherwise
        """
        if not file_path.exists():
            return False

        hash_func = hashlib.new(algorithm)

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)

        computed = hash_func.hexdigest()
        return computed.lower() == expected_checksum.lower()

    def download_with_checksum(
        self,
        product: Product,
        output_dir: Optional[str] = None,
        progress: bool = True,
        retry_on_mismatch: bool = True,
    ) -> Path:
        """Download a product and verify its checksum.

        Args:
            product: Product to download
            output_dir: Override output directory
            progress: Show progress bar
            retry_on_mismatch: Retry download if checksum fails

        Returns:
            Path to the downloaded file

        Raises:
            DownloadError: If download or checksum verification fails
        """
        # Download the file
        path = self.download(
            product=product,
            output_dir=output_dir,
            progress=progress,
        )

        # Get checksum from product properties
        checksums = product.properties.get("checksum", [])
        if not checksums:
            # Try to get from OData
            checksums = product.raw.get("Checksum", [])

        if not checksums:
            logger.warning("No checksum available for %s", product.name)
            return path

        # Find MD5 checksum
        md5_checksum = None
        for cs in checksums:
            if isinstance(cs, dict):
                if cs.get("Algorithm", "").upper() == "MD5":
                    md5_checksum = cs.get("Value")
                    break
            elif isinstance(cs, str):
                # Assume it's MD5 if just a string
                md5_checksum = cs
                break

        if not md5_checksum:
            logger.warning("No MD5 checksum found for %s", product.name)
            return path

        # Verify checksum
        if self.verify_checksum(path, md5_checksum, "md5"):
            logger.info("✓ Checksum verified: %s", product.name)
            return path

        # Checksum mismatch
        if retry_on_mismatch:
            logger.warning("✗ Checksum mismatch, retrying: %s", product.name)
            path.unlink()
            return self.download_with_checksum(
                product=product,
                output_dir=output_dir,
                progress=progress,
                retry_on_mismatch=False,  # Only retry once
            )

        raise DownloadError(
            f"Checksum verification failed for {product.name}",
            product_id=product.id,
        )

    def calculate_checksum(
        self,
        file_path: Path,
        algorithm: str = "md5",
    ) -> str:
        """Calculate checksum of a file.

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (md5, sha256, sha1)

        Returns:
            Hexadecimal checksum string
        """
        hash_func = hashlib.new(algorithm)

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)

        return hash_func.hexdigest()

    def download_quicklook(
        self,
        product: Product,
        output_dir: Optional[str] = None,
    ) -> Path:
        """Download quicklook (preview) image for a product.

        The quicklook is a small JPEG preview of the product,
        useful for visual inspection without downloading the full product.

        Args:
            product: Product to get quicklook for
            output_dir: Override output directory

        Returns:
            Path to downloaded quicklook image (JPEG)

        Raises:
            DownloadError: If quicklook is not available or download fails
        """
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # Quicklook filename
        filename = f"{product.name}_quicklook.jpeg"
        output_path = out_dir / filename

        # Skip if already exists
        if output_path.exists():
            return output_path

        # Get product UUID first
        if hasattr(product, "_odata_uuid") and product._odata_uuid:
            product_uuid = product._odata_uuid
        else:
            # Need to look up UUID via OData
            product_name = product.name
            if not product_name.endswith(".SAFE"):
                product_name = f"{product_name}.SAFE"

            query_url = f"{self.CATALOG_URL}?$filter=Name eq '{product_name}'"

            try:
                response = self._request_with_retry("get", query_url)
                data = response.json()

                if not data.get("value") or len(data["value"]) == 0:
                    raise DownloadError(
                        f"Product not found in catalog: {product.name}",
                        product_id=product.id,
                    )

                product_uuid = data["value"][0].get("Id")
                if not product_uuid:
                    raise DownloadError(
                        f"No UUID found for product: {product.name}",
                        product_id=product.id,
                    )

                # Cache UUID on product
                product._odata_uuid = product_uuid

            except requests.exceptions.RequestException as e:
                raise DownloadError(
                    f"Failed to lookup product UUID: {e}",
                    product_id=product.id,
                ) from e

        # Build quicklook URLs.
        # Some CDSE deployments may allow the Quicklook resource on one host but not the other.
        # Try both before failing.
        quicklook_urls = [
            f"{self.ODATA_URL}({product_uuid})/Products('Quicklook')/$value",
            f"{self.CATALOG_URL}({product_uuid})/Products('Quicklook')/$value",
        ]

        last_status: Optional[int] = None
        last_content_type: str = ""

        for quicklook_url in quicklook_urls:
            try:
                response = self.session.get(quicklook_url, stream=True, timeout=60)
                last_status = response.status_code
                response.raise_for_status()

                # Check content type
                last_content_type = response.headers.get("content-type", "")
                if (
                    "image" not in last_content_type.lower()
                    and "octet-stream" not in last_content_type.lower()
                ):
                    # Not an image; try next URL.
                    continue

                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Basic sanity check: avoid returning an empty file
                if output_path.stat().st_size == 0:
                    output_path.unlink(missing_ok=True)
                    continue

                return output_path

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                last_status = status
                # 403/404 are common when quicklook isn't available for a product or host.
                if status in (403, 404):
                    continue
                raise DownloadError(
                    f"Quicklook download failed: {status}",
                    product_id=product.id,
                ) from e
            except requests.exceptions.RequestException as e:
                raise DownloadError(
                    f"Quicklook download failed: {e}",
                    product_id=product.id,
                ) from e

        # If we get here, all attempts failed.
        detail = []
        if last_status is not None:
            detail.append(f"status={last_status}")
        if last_content_type:
            detail.append(f"content-type={last_content_type}")
        suffix = f" ({', '.join(detail)})" if detail else ""
        raise DownloadError(
            f"Quicklook not available for product: {product.name}{suffix}",
            product_id=product.id,
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
            products: List of products to download quicklooks for
            output_dir: Override output directory
            parallel: Enable parallel downloads (default: True)
            max_workers: Number of parallel workers

        Returns:
            List of paths to downloaded quicklook images
        """
        downloaded_files: list[Path] = []
        failed: list[str] = []

        if parallel:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def download_one(product: Product) -> tuple[Optional[Path], Optional[str]]:
                try:
                    path = self.download_quicklook(product, output_dir)
                    return (path, None)
                except DownloadError as e:
                    return (None, f"{product.name}: {e.message}")
                except Exception as e:
                    return (None, f"{product.name}: {str(e)}")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(download_one, p): p for p in products}

                with tqdm(total=len(products), desc="Quicklooks") as pbar:
                    for future in as_completed(futures):
                        path, error = future.result()
                        if path:
                            downloaded_files.append(path)
                        else:
                            failed.append(error or "Unknown error")
                        pbar.update(1)
        else:
            # Sequential download
            for product in tqdm(products, desc="Quicklooks"):
                try:
                    path = self.download_quicklook(product, output_dir)
                    downloaded_files.append(path)
                except DownloadError as e:
                    failed.append(f"{product.name}: {e.message}")

        if failed:
            logger.warning("Failed quicklooks (%d):", len(failed))
            for error in failed[:5]:  # Show first 5
                logger.warning("  - %s", error)
            if len(failed) > 5:
                logger.warning("  ... and %d more", len(failed) - 5)

        return downloaded_files
