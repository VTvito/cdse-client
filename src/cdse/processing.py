"""Post-download processing utilities for CDSE products.

This module provides functions for cropping, reprojecting, extracting
bands, and previewing downloaded Sentinel products. These operations help
users work with data centered on their area of interest rather than full tiles.

Key features:
- Extract specific bands from SAFE/ZIP products
- Crop to bounding box (city, AOI)
- Stack bands into multi-band GeoTIFF
- Generate RGB preview images (PNG/JPEG)
- Display interactive previews in Jupyter notebooks
- Calculate vegetation indices (NDVI)

Requires: rasterio (install with: pip install cdse-client[processing])
"""

import base64
import io
import logging
import zipfile
from pathlib import Path
from typing import Any, Optional, Union

from cdse.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Sentinel-2 band information
SENTINEL2_BANDS = {
    # 10m resolution
    "B02": {"name": "Blue", "resolution": 10, "wavelength": "490nm"},
    "B03": {"name": "Green", "resolution": 10, "wavelength": "560nm"},
    "B04": {"name": "Red", "resolution": 10, "wavelength": "665nm"},
    "B08": {"name": "NIR", "resolution": 10, "wavelength": "842nm"},
    # 20m resolution
    "B05": {"name": "Red Edge 1", "resolution": 20, "wavelength": "705nm"},
    "B06": {"name": "Red Edge 2", "resolution": 20, "wavelength": "740nm"},
    "B07": {"name": "Red Edge 3", "resolution": 20, "wavelength": "783nm"},
    "B8A": {"name": "NIR Narrow", "resolution": 20, "wavelength": "865nm"},
    "B11": {"name": "SWIR 1", "resolution": 20, "wavelength": "1610nm"},
    "B12": {"name": "SWIR 2", "resolution": 20, "wavelength": "2190nm"},
    # 60m resolution
    "B01": {"name": "Coastal Aerosol", "resolution": 60, "wavelength": "443nm"},
    "B09": {"name": "Water Vapour", "resolution": 60, "wavelength": "945nm"},
    "B10": {"name": "Cirrus", "resolution": 60, "wavelength": "1375nm"},
}

# Common band combinations
BAND_COMBINATIONS = {
    "true_color": ["B04", "B03", "B02"],  # RGB
    "false_color": ["B08", "B04", "B03"],  # NIR-R-G
    "agriculture": ["B11", "B08", "B02"],  # SWIR-NIR-B
    "vegetation": ["B08", "B11", "B04"],  # NIR-SWIR-R
    "ndvi": ["B08", "B04"],  # NIR and Red for NDVI calculation
    "ndwi": ["B03", "B08"],  # Green and NIR for water detection
    "all_10m": ["B02", "B03", "B04", "B08"],
    "all_20m": ["B05", "B06", "B07", "B8A", "B11", "B12"],
}


def crop_to_bbox(
    input_path: Union[str, Path],
    bbox: list[float],
    output_path: Optional[Union[str, Path]] = None,
    bands: Optional[list[str]] = None,
) -> Path:
    """Crop a raster file to a bounding box.

    Args:
        input_path: Path to input raster file (GeoTIFF or JP2)
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84
        output_path: Output path (default: input_cropped.tif)
        bands: List of band indices to extract (1-based), None for all

    Returns:
        Path to cropped output file

    Raises:
        ValidationError: If input is invalid
        ImportError: If rasterio is not installed

    Example:
        >>> cropped = crop_to_bbox(
        ...     "S2A_MSIL2A.../B04.jp2",
        ...     bbox=[9.15, 45.45, 9.20, 45.50],  # Milan center
        ... )
    """
    try:
        import rasterio
        from rasterio.mask import mask
        from rasterio.warp import transform_bounds
        from shapely.geometry import box
    except ImportError as e:
        raise ImportError(
            "rasterio and shapely are required for processing. "
            "Install with: pip install cdse-client[processing]"
        ) from e

    input_path = Path(input_path)
    if not input_path.exists():
        raise ValidationError(f"Input file not found: {input_path}", field="input_path")

    if len(bbox) != 4:
        raise ValidationError(
            "bbox must have 4 values: [min_lon, min_lat, max_lon, max_lat]", field="bbox"
        )

    # Default output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_cropped.tif"
    output_path = Path(output_path)

    with rasterio.open(input_path) as src:
        # Transform bbox to source CRS
        if src.crs.to_epsg() != 4326:
            # bbox is in WGS84, transform to source CRS
            from rasterio.warp import transform_bounds

            transformed_bbox = transform_bounds("EPSG:4326", src.crs, *bbox)
        else:
            transformed_bbox = bbox

        # Create geometry for masking
        geom = box(*transformed_bbox)

        # Crop
        out_image, out_transform = mask(src, [geom], crop=True, all_touched=True)

        # Select bands if specified
        if bands:
            band_indices = [b - 1 for b in bands]  # Convert to 0-based
            out_image = out_image[band_indices]

        # Update metadata
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "count": out_image.shape[0],
                "compress": "lzw",
            }
        )

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **out_meta) as dst:
            dst.write(out_image)

    return output_path


def extract_bands_from_safe(
    safe_path: Union[str, Path],
    bands: list[str],
    output_dir: Optional[Union[str, Path]] = None,
    resolution: int = 10,
) -> dict[str, Path]:
    """Extract specific bands from a Sentinel-2 SAFE folder or ZIP.

    Args:
        safe_path: Path to .SAFE folder or .zip file
        bands: List of band names (e.g., ["B02", "B03", "B04", "B08"])
        output_dir: Output directory (default: same as input)
        resolution: Target resolution in meters (10, 20, or 60)

    Returns:
        Dictionary mapping band names to extracted file paths

    Example:
        >>> bands = extract_bands_from_safe(
        ...     "S2A_MSIL2A_20240115.zip",
        ...     bands=["B04", "B03", "B02"],  # RGB
        ...     resolution=10
        ... )
    """
    safe_path = Path(safe_path)

    if not safe_path.exists():
        raise ValidationError(f"Path not found: {safe_path}", field="safe_path")

    # Handle ZIP files
    if safe_path.suffix.lower() == ".zip":
        return _extract_bands_from_zip(safe_path, bands, output_dir, resolution)

    # Handle SAFE folders
    if safe_path.suffix.upper() == ".SAFE" or safe_path.is_dir():
        return _extract_bands_from_safe_folder(safe_path, bands, output_dir, resolution)

    raise ValidationError(
        f"Unsupported format: {safe_path.suffix}. Expected .SAFE folder or .zip", field="safe_path"
    )


def _extract_bands_from_zip(
    zip_path: Path,
    bands: list[str],
    output_dir: Optional[Path],
    resolution: int,
) -> dict[str, Path]:
    """Extract bands from a ZIP file without full extraction."""

    output_dir = Path(output_dir) if output_dir else zip_path.parent / zip_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find band files
        for band in bands:
            res_pattern = f"R{resolution}m"

            for name in zf.namelist():
                if band in name and res_pattern in name and name.endswith(".jp2"):
                    # Extract this band
                    out_path = output_dir / f"{band}_{resolution}m.jp2"

                    with zf.open(name) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())

                    extracted[band] = out_path
                    break

    return extracted


def _extract_bands_from_safe_folder(
    safe_path: Path,
    bands: list[str],
    output_dir: Optional[Path],
    resolution: int,
) -> dict[str, Path]:
    """Extract bands from a SAFE folder structure."""
    output_dir = Path(output_dir) if output_dir else safe_path.parent / f"{safe_path.stem}_bands"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find IMG_DATA folder
    img_data = None
    for pattern in ["GRANULE/*/IMG_DATA", "IMG_DATA"]:
        candidates = list(safe_path.glob(pattern))
        if candidates:
            img_data = candidates[0]
            break

    if not img_data:
        raise ValidationError(f"IMG_DATA folder not found in {safe_path}", field="safe_path")

    # Look for resolution subfolder
    res_folder = img_data / f"R{resolution}m"
    if not res_folder.exists():
        res_folder = img_data  # L1C doesn't have resolution subfolders

    extracted = {}
    for band in bands:
        # Find band file
        band_files = list(res_folder.glob(f"*_{band}_*.jp2")) + list(
            res_folder.glob(f"*_{band}.jp2")
        )

        if band_files:
            extracted[band] = band_files[0]

    return extracted


def stack_bands(
    band_paths: dict[str, Path],
    output_path: Union[str, Path],
    band_order: Optional[list[str]] = None,
) -> Path:
    """Stack multiple bands into a single multi-band GeoTIFF.

    Args:
        band_paths: Dictionary mapping band names to file paths
        output_path: Output GeoTIFF path
        band_order: Order of bands in output (default: sorted keys)

    Returns:
        Path to output stacked GeoTIFF

    Example:
        >>> stacked = stack_bands(
        ...     {"B04": "red.jp2", "B03": "green.jp2", "B02": "blue.jp2"},
        ...     "rgb_stack.tif",
        ...     band_order=["B04", "B03", "B02"]
        ... )
    """
    try:
        import rasterio
    except ImportError as e:
        raise ImportError(
            "rasterio is required for processing. Install with: pip install cdse-client[processing]"
        ) from e

    output_path = Path(output_path)
    band_order = band_order or sorted(band_paths.keys())

    # Read first band for metadata
    first_band = band_paths[band_order[0]]
    with rasterio.open(first_band) as src:
        meta = src.meta.copy()
        height, width = src.height, src.width

    # Update metadata for multi-band output
    meta.update(
        {
            "driver": "GTiff",
            "count": len(band_order),
            "compress": "lzw",
        }
    )

    # Stack bands
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **meta) as dst:
        for i, band_name in enumerate(band_order, 1):
            band_path = band_paths[band_name]
            with rasterio.open(band_path) as src:
                data = src.read(1)
                # Resample if sizes don't match
                if data.shape != (height, width):
                    from rasterio.enums import Resampling

                    data = src.read(1, out_shape=(height, width), resampling=Resampling.bilinear)
                dst.write(data, i)
                dst.set_band_description(i, band_name)

    return output_path


def crop_and_stack(
    safe_path: Union[str, Path],
    bbox: list[float],
    bands: Optional[list[str]] = None,
    output_path: Optional[Union[str, Path]] = None,
    resolution: int = 10,
) -> Path:
    """Extract bands, crop to bbox, and stack into single GeoTIFF.

    This is a convenience function combining extract, crop, and stack operations.

    Args:
        safe_path: Path to .SAFE folder or .zip file
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
        bands: Band names (default: true color B04, B03, B02)
        output_path: Output path (default: auto-generated)
        resolution: Target resolution in meters

    Returns:
        Path to output cropped and stacked GeoTIFF

    Example:
        >>> result = crop_and_stack(
        ...     "S2A_MSIL2A_20240115.zip",
        ...     bbox=[9.15, 45.45, 9.25, 45.55],  # Milan
        ...     bands=["B04", "B03", "B02", "B08"],  # RGB + NIR
        ... )
    """
    import tempfile

    safe_path = Path(safe_path)
    bands = bands or ["B04", "B03", "B02"]

    if output_path is None:
        output_path = safe_path.parent / f"{safe_path.stem}_cropped.tif"
    output_path = Path(output_path)

    # Extract bands to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract bands
        band_paths = extract_bands_from_safe(
            safe_path, bands, output_dir=tmpdir, resolution=resolution
        )

        if not band_paths:
            raise ValidationError(f"No bands found in {safe_path}", field="bands")

        # Stack bands
        stacked_path = tmpdir / "stacked.tif"
        stack_bands(band_paths, stacked_path, band_order=bands)

        # Crop to bbox
        crop_to_bbox(stacked_path, bbox, output_path)

    return output_path


def calculate_ndvi(
    nir_path: Union[str, Path],
    red_path: Union[str, Path],
    output_path: Union[str, Path],
) -> Path:
    """Calculate NDVI (Normalized Difference Vegetation Index).

    NDVI = (NIR - Red) / (NIR + Red)

    Args:
        nir_path: Path to NIR band (B08 for Sentinel-2)
        red_path: Path to Red band (B04 for Sentinel-2)
        output_path: Output GeoTIFF path

    Returns:
        Path to NDVI output file (values -1 to 1)
    """
    try:
        import numpy as np
        import rasterio
    except ImportError as e:
        raise ImportError(
            "numpy and rasterio are required for processing. "
            "Install with: pip install cdse-client[processing]"
        ) from e

    output_path = Path(output_path)

    with rasterio.open(nir_path) as nir_src, rasterio.open(red_path) as red_src:
        nir = nir_src.read(1).astype(np.float32)
        red = red_src.read(1).astype(np.float32)

        # Calculate NDVI, avoiding division by zero
        denominator = nir + red
        ndvi = np.where(denominator > 0, (nir - red) / denominator, 0)

        # Clip to valid range
        ndvi = np.clip(ndvi, -1, 1)

        # Write output
        meta = nir_src.meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "dtype": "float32",
                "count": 1,
                "compress": "lzw",
            }
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **meta) as dst:
            dst.write(ndvi, 1)
            dst.set_band_description(1, "NDVI")

    return output_path


def get_bounds_from_raster(raster_path: Union[str, Path]) -> tuple[list[float], str]:
    """Get bounding box and CRS from a raster file.

    Args:
        raster_path: Path to raster file

    Returns:
        Tuple of (bbox in WGS84 [min_lon, min_lat, max_lon, max_lat], original CRS string)
    """
    try:
        import rasterio
        from rasterio.warp import transform_bounds
    except ImportError as e:
        raise ImportError(
            "rasterio is required for processing. Install with: pip install cdse-client[processing]"
        ) from e

    with rasterio.open(raster_path) as src:
        bounds = src.bounds
        crs = src.crs

        # Transform to WGS84
        if crs.to_epsg() != 4326:
            bounds = transform_bounds(crs, "EPSG:4326", *bounds)

        bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]
        return bbox, str(crs)


def reproject(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    target_crs: str = "EPSG:4326",
    resolution: Optional[float] = None,
) -> Path:
    """Reproject a raster to a different CRS.

    Args:
        input_path: Input raster path
        output_path: Output raster path
        target_crs: Target CRS (default: WGS84)
        resolution: Target resolution (default: preserve original)

    Returns:
        Path to reprojected raster
    """
    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.warp import calculate_default_transform
        from rasterio.warp import reproject as rio_reproject
    except ImportError as e:
        raise ImportError(
            "rasterio is required for processing. Install with: pip install cdse-client[processing]"
        ) from e

    input_path = Path(input_path)
    output_path = Path(output_path)

    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds, resolution=resolution
        )

        meta = src.meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "compress": "lzw",
            }
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **meta) as dst:
            for i in range(1, src.count + 1):
                rio_reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

    return output_path


# =============================================================================
# PREVIEW AND VISUALIZATION FUNCTIONS
# =============================================================================


def create_rgb_preview(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    bands: tuple[int, int, int] = (1, 2, 3),
    percentile_stretch: tuple[float, float] = (2, 98),
    size: Optional[tuple[int, int]] = None,
    format: str = "PNG",
) -> Path:
    """Create an RGB preview image from a multi-band raster.

    Generates a color-balanced preview image suitable for visual inspection.
    Applies percentile stretching to enhance contrast.

    Args:
        input_path: Path to multi-band raster (GeoTIFF)
        output_path: Output image path (default: input_preview.png)
        bands: Tuple of band indices for R, G, B (1-based, default: 1, 2, 3)
        percentile_stretch: Low and high percentiles for contrast stretch
        size: Output size (width, height) or None for original size
        format: Output format ("PNG" or "JPEG")

    Returns:
        Path to preview image

    Example:
        >>> preview = create_rgb_preview(
        ...     "milan_rgb.tif",
        ...     bands=(1, 2, 3),  # R, G, B order
        ...     percentile_stretch=(2, 98)
        ... )
    """
    try:
        import numpy as np
        import rasterio
        from PIL import Image
    except ImportError as e:
        missing = "rasterio" if "rasterio" in str(e) else "Pillow"
        raise ImportError(
            f"{missing} is required for preview generation. "
            "Install with: pip install cdse-client[processing]"
        ) from e

    input_path = Path(input_path)
    if not input_path.exists():
        raise ValidationError(f"Input file not found: {input_path}", field="input_path")

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_preview.{format.lower()}"
    output_path = Path(output_path)

    with rasterio.open(input_path) as src:
        # Read bands
        rgb_data = []
        for band_idx in bands:
            if band_idx > src.count:
                raise ValidationError(
                    f"Band {band_idx} not found. File has {src.count} bands.", field="bands"
                )
            data = src.read(band_idx).astype(np.float32)
            rgb_data.append(data)

        # Stack into RGB array
        rgb = np.stack(rgb_data, axis=-1)

        # Apply percentile stretch for each channel
        for i in range(3):
            channel = rgb[:, :, i]
            valid_mask = ~np.isnan(channel) & (channel > 0)
            if valid_mask.any():
                low = np.percentile(channel[valid_mask], percentile_stretch[0])
                high = np.percentile(channel[valid_mask], percentile_stretch[1])
                if high > low:
                    channel = np.clip((channel - low) / (high - low), 0, 1)
                    rgb[:, :, i] = channel

        # Convert to 8-bit
        rgb_8bit = (rgb * 255).astype(np.uint8)

        # Create PIL image
        img = Image.fromarray(rgb_8bit, mode="RGB")

        # Resize if requested
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format=format, quality=95 if format == "JPEG" else None)

    return output_path


def preview_product(
    safe_path: Union[str, Path],
    bbox: Optional[list[float]] = None,
    bands: Optional[list[str]] = None,
    resolution: int = 10,
    output_path: Optional[Union[str, Path]] = None,
    display: bool = True,
    size: tuple[int, int] = (800, 800),
) -> dict[str, Any]:
    """Generate and optionally display a preview of a Sentinel product.

    This is a convenience function that extracts RGB bands, optionally crops
    to a bounding box, and generates a preview image. When run in Jupyter,
    it can display the preview inline.

    Args:
        safe_path: Path to .SAFE folder or .zip file
        bbox: Optional bounding box to crop [min_lon, min_lat, max_lon, max_lat]
        bands: Band names for RGB (default: ["B04", "B03", "B02"] for true color)
        resolution: Resolution in meters (10, 20, or 60)
        output_path: Where to save the preview (default: auto-generated)
        display: Whether to display in Jupyter (default: True)
        size: Preview size (width, height)

    Returns:
        Dictionary with:
        - preview_path: Path to generated preview image
        - tiff_path: Path to cropped GeoTIFF (if bbox provided)
        - bounds: Geographic bounds of the preview
        - size_pixels: Size in pixels (width, height)
        - image: PIL Image object (for programmatic use)

    Example:
        >>> result = preview_product(
        ...     "S2A_MSIL2A_20240115.zip",
        ...     bbox=[9.15, 45.45, 9.25, 45.55],  # Milan
        ...     display=True
        ... )
        >>> print(f"Preview saved to: {result['preview_path']}")
    """
    import tempfile
    from importlib.util import find_spec

    missing_deps: list[str] = []
    if find_spec("numpy") is None:
        missing_deps.append("numpy")
    if find_spec("rasterio") is None:
        missing_deps.append("rasterio")
    if find_spec("PIL") is None:
        missing_deps.append("Pillow")
    if missing_deps:
        raise ImportError(
            f"{', '.join(missing_deps)} is required for preview. "
            "Install with: pip install cdse-client[processing]"
        )

    from PIL import Image

    safe_path = Path(safe_path)
    bands = bands or ["B04", "B03", "B02"]  # True color

    if len(bands) != 3:
        raise ValidationError("Exactly 3 bands required for RGB preview", field="bands")

    # Generate output paths
    stem = safe_path.stem.replace(".SAFE", "")
    if output_path is None:
        output_dir = safe_path.parent / f"{stem}_preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        tiff_path = output_dir / f"{stem}_rgb.tif"
        preview_path = output_dir / f"{stem}_preview.png"
    else:
        output_path = Path(output_path)
        tiff_path = output_path.with_suffix(".tif")
        preview_path = output_path.with_suffix(".png")

    # Extract, crop (if bbox), and stack
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract bands
        band_paths = extract_bands_from_safe(
            safe_path, bands, output_dir=tmpdir, resolution=resolution
        )

        if not band_paths:
            raise ValidationError(f"Could not extract bands from {safe_path}", field="bands")

        # Stack bands
        stacked_path = tmpdir / "stacked.tif"
        stack_bands(band_paths, stacked_path, band_order=bands)

        # Crop if bbox provided
        if bbox:
            crop_to_bbox(stacked_path, bbox, tiff_path)
        else:
            import shutil

            shutil.copy(stacked_path, tiff_path)

    # Generate preview
    preview_path = create_rgb_preview(
        tiff_path, output_path=preview_path, bands=(1, 2, 3), size=size
    )

    # Get bounds
    bounds, crs = get_bounds_from_raster(tiff_path)

    # Load image for return and display
    img = Image.open(preview_path)

    result = {
        "preview_path": preview_path,
        "tiff_path": tiff_path,
        "bounds": bounds,
        "size_pixels": img.size,
        "image": img,
    }

    # Display in Jupyter if requested
    if display:
        _display_in_jupyter(img, preview_path, bounds)

    return result


def _display_in_jupyter(
    img: Any,
    path: Path,
    bounds: list[float],
) -> None:
    """Display image in Jupyter notebook with metadata."""
    try:
        from IPython.display import HTML, display
    except ImportError:
        # Not in Jupyter, skip display
        logger.info("Preview saved to: %s", path)
        return

    # Check if we're in a Jupyter environment
    try:
        get_ipython()  # type: ignore
    except NameError:
        logger.info("Preview saved to: %s", path)
        return

    # Create HTML with image and info
    width, height = img.size

    # Convert image to base64 for inline display
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    html = f"""
    <div style="border: 1px solid #ccc; padding: 10px; border-radius: 5px; max-width: 820px;">
        <h4 style="margin: 0 0 10px 0;">🛰️ Satellite Preview</h4>
        <img src="data:image/png;base64,{img_base64}" style="max-width: 800px; border-radius: 3px;"/>
        <div style="margin-top: 10px; font-size: 12px; color: #666;">
            <b>Size:</b> {width} × {height} px &nbsp;|&nbsp;
            <b>Bounds:</b> [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]
        </div>
    </div>
    """

    display(HTML(html))


def quick_preview(
    tiff_path: Union[str, Path],
    bands: tuple[int, int, int] = (1, 2, 3),
    figsize: tuple[int, int] = (10, 10),
    title: Optional[str] = None,
) -> Any:
    """Quick preview using matplotlib (for Jupyter notebooks).

    Simpler alternative to preview_product when you already have
    a processed GeoTIFF and want a quick visualization.

    Args:
        tiff_path: Path to GeoTIFF file
        bands: Band indices for RGB (1-based)
        figsize: Figure size in inches
        title: Optional title for the plot

    Returns:
        matplotlib figure object

    Example:
        >>> fig = quick_preview("milan_rgb.tif", title="Milan - Sentinel-2")
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import rasterio
    except ImportError as e:
        raise ImportError(
            "rasterio, numpy, and matplotlib are required for quick_preview. "
            "Install with: pip install cdse-client[processing]"
        ) from e

    tiff_path = Path(tiff_path)

    with rasterio.open(tiff_path) as src:
        # Read RGB bands
        rgb_data = []
        for band_idx in bands:
            data = src.read(band_idx).astype(np.float32)
            rgb_data.append(data)

        rgb = np.stack(rgb_data, axis=-1)

        # Percentile stretch
        for i in range(3):
            channel = rgb[:, :, i]
            valid = channel[channel > 0]
            if len(valid) > 0:
                low, high = np.percentile(valid, [2, 98])
                if high > low:
                    rgb[:, :, i] = np.clip((channel - low) / (high - low), 0, 1)

        # Get bounds for extent
        bounds = src.bounds

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(rgb, extent=[bounds.left, bounds.right, bounds.bottom, bounds.top], origin="upper")

    if title:
        ax.set_title(title, fontsize=14)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    plt.tight_layout()
    plt.show()

    return fig


def create_thumbnail(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    size: tuple[int, int] = (256, 256),
    bands: tuple[int, int, int] = (1, 2, 3),
) -> Path:
    """Create a small thumbnail from a raster.

    Args:
        input_path: Path to input raster
        output_path: Output thumbnail path
        size: Thumbnail size (width, height)
        bands: Band indices for RGB

    Returns:
        Path to thumbnail

    Example:
        >>> thumb = create_thumbnail("milan_rgb.tif", size=(128, 128))
    """
    input_path = Path(input_path)

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_thumb.png"

    return create_rgb_preview(input_path, output_path, bands=bands, size=size, format="PNG")


def compare_previews(
    paths: list[Union[str, Path]],
    titles: Optional[list[str]] = None,
    figsize: tuple[int, int] = (15, 5),
) -> Any:
    """Display multiple previews side by side for comparison.

    Args:
        paths: List of GeoTIFF paths to compare
        titles: Optional titles for each image
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> compare_previews(
        ...     ["before.tif", "after.tif"],
        ...     titles=["Before", "After"]
        ... )
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import rasterio
    except ImportError as e:
        raise ImportError(
            "rasterio, numpy, and matplotlib are required. "
            "Install with: pip install cdse-client[processing]"
        ) from e

    n = len(paths)
    fig, axes = plt.subplots(1, n, figsize=figsize)

    if n == 1:
        axes = [axes]

    titles = titles or [Path(p).stem for p in paths]

    for ax, path, title in zip(axes, paths, titles):
        with rasterio.open(path) as src:
            # Read RGB
            rgb = []
            for i in range(1, min(4, src.count + 1)):
                rgb.append(src.read(i).astype(np.float32))
            rgb = np.stack(rgb, axis=-1)

            # Stretch
            for i in range(rgb.shape[-1]):
                channel = rgb[:, :, i]
                valid = channel[channel > 0]
                if len(valid) > 0:
                    low, high = np.percentile(valid, [2, 98])
                    if high > low:
                        rgb[:, :, i] = np.clip((channel - low) / (high - low), 0, 1)

        ax.imshow(rgb)
        ax.set_title(title)
        ax.axis("off")

    plt.tight_layout()
    plt.show()

    return fig
