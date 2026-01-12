"""Tests for processing module."""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import tempfile
import numpy as np

# Skip all tests if rasterio is not installed
rasterio = pytest.importorskip("rasterio")

from cdse.processing import (
    SENTINEL2_BANDS,
    BAND_COMBINATIONS,
    crop_to_bbox,
    extract_bands_from_safe,
    stack_bands,
    crop_and_stack,
    calculate_ndvi,
    reproject,
    # Preview functions
    create_rgb_preview,
    preview_product,
    quick_preview,
    create_thumbnail,
    compare_previews,
    get_bounds_from_raster,
)
from cdse.exceptions import ValidationError


class TestConstants:
    """Tests for module constants."""

    def test_sentinel2_bands_structure(self):
        """Test SENTINEL2_BANDS has correct structure."""
        assert isinstance(SENTINEL2_BANDS, dict)

        # Check required bands exist
        required_bands = ["B02", "B03", "B04", "B08"]
        for band in required_bands:
            assert band in SENTINEL2_BANDS, f"Missing band {band}"

        # Check each band has required fields
        for band_id, info in SENTINEL2_BANDS.items():
            assert "name" in info, f"Missing 'name' in {band_id}"
            assert "resolution" in info, f"Missing 'resolution' in {band_id}"
            assert "wavelength" in info, f"Missing 'wavelength' in {band_id}"

    def test_band_combinations_structure(self):
        """Test BAND_COMBINATIONS has correct structure."""
        assert isinstance(BAND_COMBINATIONS, dict)

        # Check common combinations exist
        assert "true_color" in BAND_COMBINATIONS
        assert "ndvi" in BAND_COMBINATIONS
        assert "false_color" in BAND_COMBINATIONS

        # Check true_color is RGB
        assert BAND_COMBINATIONS["true_color"] == ["B04", "B03", "B02"]

        # Check ndvi has NIR and RED
        assert "B08" in BAND_COMBINATIONS["ndvi"]
        assert "B04" in BAND_COMBINATIONS["ndvi"]


class TestFunctionsCallable:
    """Tests that all processing functions are callable."""

    def test_crop_to_bbox_callable(self):
        """Test crop_to_bbox is callable."""
        assert callable(crop_to_bbox)

    def test_extract_bands_callable(self):
        """Test extract_bands_from_safe is callable."""
        assert callable(extract_bands_from_safe)

    def test_stack_bands_callable(self):
        """Test stack_bands is callable."""
        assert callable(stack_bands)

    def test_crop_and_stack_callable(self):
        """Test crop_and_stack is callable."""
        assert callable(crop_and_stack)

    def test_calculate_ndvi_callable(self):
        """Test calculate_ndvi is callable."""
        assert callable(calculate_ndvi)

    def test_reproject_callable(self):
        """Test reproject is callable."""
        assert callable(reproject)


class TestPreviewFunctionsCallable:
    """Tests that preview functions are callable."""

    def test_create_rgb_preview_callable(self):
        """Test create_rgb_preview is callable."""
        assert callable(create_rgb_preview)

    def test_preview_product_callable(self):
        """Test preview_product is callable."""
        assert callable(preview_product)

    def test_quick_preview_callable(self):
        """Test quick_preview is callable."""
        assert callable(quick_preview)

    def test_create_thumbnail_callable(self):
        """Test create_thumbnail is callable."""
        assert callable(create_thumbnail)

    def test_compare_previews_callable(self):
        """Test compare_previews is callable."""
        assert callable(compare_previews)

    def test_get_bounds_from_raster_callable(self):
        """Test get_bounds_from_raster is callable."""
        assert callable(get_bounds_from_raster)


# Check if PIL is available for preview tests
try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class TestCreateRgbPreview:
    """Tests for create_rgb_preview function."""

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_file_not_found_raises_error(self):
        """Test that non-existent file raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_rgb_preview("/nonexistent/file.tif")
        assert "not found" in str(exc_info.value)


class TestPreviewProduct:
    """Tests for preview_product function."""

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_wrong_band_count_raises_error(self):
        """Test that wrong number of bands raises ValidationError."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValidationError) as exc_info:
                preview_product(temp_path, bands=["B04", "B03"])  # Only 2 bands
            assert "Exactly 3 bands required" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)


class TestCropToBbox:
    """Tests for crop_to_bbox function."""

    def test_invalid_bbox_length(self):
        """Test that bbox with wrong length raises ValidationError."""
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValidationError) as exc_info:
                crop_to_bbox(temp_path, bbox=[9.1, 45.4, 9.28])  # Only 3 values
            assert "bbox must have 4 values" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_nonexistent_file_raises_error(self):
        """Test that non-existent file raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            crop_to_bbox("/nonexistent/file.tif", bbox=[9.1, 45.4, 9.28, 45.52])
        assert "not found" in str(exc_info.value)


class TestExtractBandsFromSafe:
    """Tests for extract_bands_from_safe function."""

    def test_nonexistent_path_raises_error(self):
        """Test that non-existent path raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe("/nonexistent/product.zip", bands=["B04"])
        assert "not found" in str(exc_info.value)

    def test_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValidationError."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValidationError) as exc_info:
                extract_bands_from_safe(temp_path, bands=["B04"])
            assert "Unsupported format" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)
