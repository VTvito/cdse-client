"""Tests for indices, the SCL cloud mask and crop error handling.

Needs rasterio and numpy, so the whole module is skipped under the ``dev`` extra
alone (the same rule as ``test_processing.py``). Run locally with
``pip install -e ".[dev,processing]"``.
"""

import warnings
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")
np = pytest.importorskip("numpy")

from rasterio.transform import from_origin  # noqa: E402

from cdse.exceptions import ValidationError  # noqa: E402
from cdse.processing import (  # noqa: E402
    SCL_CLOUD_CLASSES,
    calculate_ndvi,
    cloud_mask_from_scl,
    compute_index,
    crop_to_bbox,
    get_bounds_from_raster,
    normalized_difference,
    scl_clear_fraction,
    stack_bands,
)

# A 1 km x 1 km patch of UTM zone 32N (Lombardy), 10 m pixels.
UTM = "EPSG:32632"
ORIGIN = (500000.0, 5040000.0)


def _write(path: Path, data, *, res: float = 10.0, crs=UTM, dtype=None) -> Path:
    """Write a single-band raster with a real georeference."""
    data = np.asarray(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=dtype or data.dtype,
        crs=crs,
        transform=from_origin(ORIGIN[0], ORIGIN[1], res, res),
    ) as dst:
        dst.write(data, 1)
    return path


class TestNormalizedDifference:
    def test_values_and_band_name(self, tmp_path):
        a = _write(tmp_path / "a.tif", np.full((10, 10), 3000, dtype="uint16"))
        b = _write(tmp_path / "b.tif", np.full((10, 10), 1000, dtype="uint16"))

        out = normalized_difference(a, b, tmp_path / "nd.tif", name="NBR")

        with rasterio.open(out) as src:
            assert src.dtypes == ("float32",)
            assert src.descriptions == ("NBR",)
            assert np.allclose(src.read(1), 0.5)

    def test_zero_denominator_is_zero_and_silent(self, tmp_path):
        """Audit 20: np.where evaluated both branches and warned on every call."""
        a = _write(tmp_path / "a.tif", np.zeros((4, 4), dtype="uint16"))
        b = _write(tmp_path / "b.tif", np.zeros((4, 4), dtype="uint16"))

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = normalized_difference(a, b, tmp_path / "nd.tif")

        with rasterio.open(out) as src:
            assert np.all(src.read(1) == 0)

    def test_shape_mismatch_is_a_validation_error(self, tmp_path):
        a = _write(tmp_path / "a.tif", np.ones((10, 10), dtype="uint16"))
        b = _write(tmp_path / "b.tif", np.ones((5, 5), dtype="uint16"), res=20.0)

        with pytest.raises(ValidationError) as exc_info:
            normalized_difference(a, b, tmp_path / "nd.tif")
        assert "same shape" in str(exc_info.value)

    def test_calculate_ndvi_is_the_same_thing_named_ndvi(self, tmp_path):
        nir = _write(tmp_path / "nir.tif", np.full((4, 4), 800, dtype="uint16"))
        red = _write(tmp_path / "red.tif", np.full((4, 4), 200, dtype="uint16"))

        out = calculate_ndvi(nir, red, tmp_path / "ndvi.tif")

        with rasterio.open(out) as src:
            assert src.descriptions == ("NDVI",)
            assert np.allclose(src.read(1), 0.6)


def _safe_folder(tmp_path: Path) -> Path:
    """A minimal L2A SAFE folder whose 'JP2' files are GeoTIFFs (GDAL reads by content)."""
    name = "S2A_MSIL2A_20240115T101031_N0510_R022_T32TQM_20240115T140512"
    img = tmp_path / f"{name}.SAFE" / "GRANULE" / "L2A_T32TQM_20240115T101031" / "IMG_DATA"
    # 100 x 100 at 10 m: NIR high, red low -> NDVI 0.6 everywhere.
    _write(img / "R10m" / "T32TQM_20240115T101031_B08_10m.jp2", np.full((100, 100), 800, "uint16"))
    _write(img / "R10m" / "T32TQM_20240115T101031_B04_10m.jp2", np.full((100, 100), 200, "uint16"))
    # 50 x 50 at 20 m: the top half is cloud (9), the bottom half vegetation (4).
    scl = np.full((50, 50), 4, dtype="uint8")
    scl[:25, :] = 9
    _write(img / "R20m" / "T32TQM_20240115T101031_SCL_20m.jp2", scl, res=20.0)
    _write(
        img / "R20m" / "T32TQM_20240115T101031_B8A_20m.jp2",
        np.full((50, 50), 700, "uint16"),
        res=20.0,
    )
    _write(
        img / "R20m" / "T32TQM_20240115T101031_B12_20m.jp2",
        np.full((50, 50), 300, "uint16"),
        res=20.0,
    )
    return img.parent.parent.parent


class TestComputeIndex:
    def test_ndvi_from_a_product(self, tmp_path):
        out = compute_index(_safe_folder(tmp_path), "ndvi", output_path=tmp_path / "ndvi.tif")

        with rasterio.open(out) as src:
            assert src.descriptions == ("NDVI",)
            assert src.shape == (100, 100)
            assert np.allclose(src.read(1), 0.6)

    def test_nbr_defaults_to_20m(self, tmp_path):
        out = compute_index(_safe_folder(tmp_path), "nbr", output_path=tmp_path / "nbr.tif")

        with rasterio.open(out) as src:
            assert src.shape == (50, 50)
            assert np.allclose(src.read(1), 0.4)

    def test_bbox_crops_the_result(self, tmp_path):
        safe = _safe_folder(tmp_path)
        full, _ = get_bounds_from_raster(
            safe
            / "GRANULE"
            / "L2A_T32TQM_20240115T101031"
            / "IMG_DATA"
            / "R10m"
            / "T32TQM_20240115T101031_B04_10m.jp2"
        )
        w, h = full[2] - full[0], full[3] - full[1]
        inner = [full[0] + w * 0.25, full[1] + h * 0.25, full[2] - w * 0.25, full[3] - h * 0.25]

        out = compute_index(safe, "ndvi", bbox=inner, output_path=tmp_path / "crop.tif")

        with rasterio.open(out) as src:
            assert src.shape[0] < 100 and src.shape[1] < 100
            assert src.shape[0] > 30 and src.shape[1] > 30

    def test_unknown_index_is_rejected(self, tmp_path):
        with pytest.raises(ValidationError) as exc_info:
            compute_index(tmp_path, "evi")
        assert exc_info.value.field == "index"

    def test_default_output_name(self, tmp_path):
        out = compute_index(_safe_folder(tmp_path), "ndvi")
        assert out.name.endswith("_ndvi.tif")
        assert ".SAFE" not in out.name

    def test_missing_band_is_reported_by_name(self, tmp_path):
        """The fixture has no B03, so NDWI must fail naming it, not with a KeyError."""
        with pytest.raises(ValidationError) as exc_info:
            compute_index(_safe_folder(tmp_path), "ndwi")
        assert "B03" in str(exc_info.value)


class TestSclMask:
    def _scl(self, tmp_path):
        scl = np.full((10, 10), 4, dtype="uint8")
        scl[:5, :] = 9  # cloud
        scl[5, :] = 3  # one row of shadow
        scl[6, 0] = 0  # one no-data pixel
        return _write(tmp_path / "scl.tif", scl, res=20.0)

    def test_mask_is_one_where_clear(self, tmp_path):
        out = cloud_mask_from_scl(self._scl(tmp_path))

        with rasterio.open(out) as src:
            mask = src.read(1)
            assert src.dtypes == ("uint8",)
            assert mask[:5].sum() == 0
            assert mask[5].sum() == 0
            assert mask[6, 0] == 0
            assert mask[6, 1:].all() and mask[7:].all()

    def test_custom_classes(self, tmp_path):
        out = cloud_mask_from_scl(self._scl(tmp_path), classes={9})

        with rasterio.open(out) as src:
            mask = src.read(1)
            assert mask[5].all()  # shadow no longer masked

    def test_clear_fraction(self, tmp_path):
        # 100 pixels: 50 cloud + 10 shadow + 1 no-data masked -> 39 clear
        assert scl_clear_fraction(self._scl(tmp_path)) == pytest.approx(0.39)
        assert scl_clear_fraction(self._scl(tmp_path), classes=set()) == 1.0

    def test_default_classes_include_no_data(self):
        assert 0 in SCL_CLOUD_CLASSES


class TestStackResampling:
    def test_scl_is_upsampled_with_nearest(self, tmp_path):
        """A categorical band must not be averaged into classes that do not exist."""
        b04 = _write(tmp_path / "b04.tif", np.full((20, 20), 100, dtype="uint16"))
        scl = np.indices((10, 10)).sum(axis=0) % 2 * 4 + 4  # checkerboard of 4 and 8
        scl_path = _write(tmp_path / "scl.tif", scl.astype("uint16"), res=20.0)

        out = stack_bands({"B04": b04, "SCL": scl_path}, tmp_path / "s.tif", ["B04", "SCL"])

        with rasterio.open(out) as src:
            assert set(np.unique(src.read(2))) == {4, 8}

    def test_explicit_resampling_overrides(self, tmp_path):
        b04 = _write(tmp_path / "b04.tif", np.full((20, 20), 100, dtype="uint16"))
        scl = np.indices((10, 10)).sum(axis=0) % 2 * 4 + 4
        scl_path = _write(tmp_path / "scl.tif", scl.astype("uint16"), res=20.0)

        out = stack_bands(
            {"B04": b04, "SCL": scl_path}, tmp_path / "s.tif", ["B04", "SCL"], resampling="bilinear"
        )

        with rasterio.open(out) as src:
            assert len(np.unique(src.read(2))) > 2


class TestCropErrors:
    def test_bbox_outside_the_raster_is_a_validation_error(self, tmp_path):
        """Audit 17: rasterio's 'shapes do not overlap' named neither file nor bbox."""
        raster = _write(tmp_path / "r.tif", np.ones((10, 10), dtype="uint16"))

        with pytest.raises(ValidationError) as exc_info:
            crop_to_bbox(raster, [0.0, 0.0, 0.1, 0.1], tmp_path / "out.tif")

        message = str(exc_info.value)
        assert "does not overlap" in message
        assert "r.tif" in message

    def test_raster_without_crs_is_a_validation_error(self, tmp_path):
        """Audit 18: used to be an AttributeError on None.to_epsg()."""
        raster = _write(tmp_path / "nocrs.tif", np.ones((10, 10), dtype="uint16"), crs=None)

        with pytest.raises(ValidationError) as exc_info:
            crop_to_bbox(raster, [9.0, 45.0, 9.1, 45.1], tmp_path / "out.tif")
        assert "no CRS" in str(exc_info.value)
