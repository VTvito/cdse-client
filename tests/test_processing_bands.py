"""Tests for band extraction from SAFE/ZIP products.

Kept apart from ``test_processing.py`` on purpose: that module skips entirely
without rasterio, which the ``dev`` extra does not install. Band extraction and
band-request validation are plain stdlib work, so these run everywhere --
including CI.
"""

import zipfile
from pathlib import Path

import pytest

from cdse.exceptions import ValidationError
from cdse.processing import (
    BAND_COMBINATIONS,
    L2A_BANDS_BY_RESOLUTION,
    extract_bands_from_safe,
    stack_bands,
)

L2A_NAME = "S2A_MSIL2A_20240115T101031_N0510_R022_T32TQM_20240115T140512"
L1C_NAME = "S2A_MSIL1C_20240115T101031_N0510_R022_T32TQM_20240115T124512"

L2A_PREFIX = f"{L2A_NAME}.SAFE/GRANULE/L2A_T32TQM_20240115T101031/IMG_DATA"
L1C_PREFIX = f"{L1C_NAME}.SAFE/GRANULE/L1C_T32TQM_20240115T101031/IMG_DATA"


def _make_zip(path: Path, entries: dict) -> Path:
    """Write a ZIP with the given name -> content entries."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


# The real contents of an L2A product's resolution folders. No B08 at 20m on
# purpose: L2A carries B8A there, not B08.
L2A_R10M = ("B02", "B03", "B04", "B08")
L2A_R20M = ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B8A", "B11", "B12")


def _l2a_zip(tmp_path: Path, omit: tuple = ()) -> Path:
    """A L2A layout: JP2s under R10m/R20m resolution subfolders.

    ``omit`` drops bands from the archive without touching the folder layout, to
    exercise the difference between "not valid at this resolution" and "valid,
    but this particular product does not carry it".
    """
    entries = {
        f"{L2A_PREFIX}/R10m/T32TQM_20240115T101031_{b}_10m.jp2": f"{b}@10m".encode()
        for b in L2A_R10M
        if b not in omit
    }
    entries.update(
        {
            f"{L2A_PREFIX}/R20m/T32TQM_20240115T101031_{b}_20m.jp2": f"{b}@20m".encode()
            for b in L2A_R20M
            if b not in omit
        }
    )
    name = f"{L2A_NAME}.zip" if not omit else f"{L2A_NAME}_partial.zip"
    return _make_zip(tmp_path / name, entries)


def _l1c_zip(tmp_path: Path) -> Path:
    """A L1C layout: JP2s straight in IMG_DATA, no resolution subfolders."""
    entries = {
        f"{L1C_PREFIX}/T32TQM_20240115T101031_{b}.jp2": b.encode()
        for b in ("B02", "B03", "B04", "B08", "B11")
    }
    return _make_zip(tmp_path / f"{L1C_NAME}.zip", entries)


class TestExtractBandsFromZip:
    """Band extraction from ZIP products (defect 15)."""

    def test_l1c_zip_extracts_bands(self, tmp_path):
        """L1C has no R{res}m subfolders: the bands must still be found."""
        extracted = extract_bands_from_safe(
            _l1c_zip(tmp_path),
            bands=["B04", "B03", "B02"],
            output_dir=tmp_path / "out",
            resolution=10,
        )

        assert sorted(extracted) == ["B02", "B03", "B04"]
        assert extracted["B04"].read_bytes() == b"B04"

    def test_l1c_ignores_resolution_for_native_20m_band(self, tmp_path):
        """On L1C the resolution argument selects nothing, so B11 is reachable."""
        extracted = extract_bands_from_safe(
            _l1c_zip(tmp_path),
            bands=["B11"],
            output_dir=tmp_path / "out",
            resolution=10,
        )

        assert extracted["B11"].read_bytes() == b"B11"

    def test_l2a_zip_extracts_bands(self, tmp_path):
        """L2A keeps the resolution folders: the R10m variant is the one taken."""
        extracted = extract_bands_from_safe(
            _l2a_zip(tmp_path),
            bands=["B04", "B03", "B02"],
            output_dir=tmp_path / "out",
            resolution=10,
        )

        assert sorted(extracted) == ["B02", "B03", "B04"]
        assert extracted["B04"].read_bytes() == b"B04@10m"

    def test_l2a_zip_honours_requested_resolution(self, tmp_path):
        """Asking for 20m must not hand back the 10m file."""
        extracted = extract_bands_from_safe(
            _l2a_zip(tmp_path),
            bands=["B04", "B11"],
            output_dir=tmp_path / "out",
            resolution=20,
        )

        assert extracted["B04"].read_bytes() == b"B04@20m"
        assert extracted["B11"].read_bytes() == b"B11@20m"


class TestBandRequestValidation:
    """Band/resolution validation and missing-band reporting (defect 16)."""

    def test_l2a_rejects_band_coarser_than_resolution(self, tmp_path):
        """B11 is 20m-only: at resolution=10 it is refused, not silently swapped."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=["B04", "B11"],
                output_dir=tmp_path / "out",
                resolution=10,
            )

        message = str(exc_info.value)
        assert "B11" in message
        assert "resolution=20" in message

    def test_advertised_band_combinations_fail_clearly(self, tmp_path):
        """The 20m combinations the module ships must not raise a bare KeyError."""
        for name in ("agriculture", "vegetation", "all_20m"):
            with pytest.raises(ValidationError):
                extract_bands_from_safe(
                    _l2a_zip(tmp_path),
                    bands=BAND_COMBINATIONS[name],
                    output_dir=tmp_path / "out",
                    resolution=10,
                )

    def test_band_combinations_work_at_their_resolution(self, tmp_path):
        """...and every band of them is actually extractable at 20m."""
        for name in ("agriculture", "vegetation", "all_20m"):
            bands = BAND_COMBINATIONS[name]
            extracted = extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=bands,
                output_dir=tmp_path / f"out_{name}",
                resolution=20,
            )

            assert sorted(extracted) == sorted(bands), name

    def test_every_band_combination_is_satisfiable(self):
        """No shipped combination may mix bands that share no single resolution."""
        for name, bands in BAND_COMBINATIONS.items():
            resolutions = [
                r
                for r, available in L2A_BANDS_BY_RESOLUTION.items()
                if all(b in available for b in bands)
            ]
            assert resolutions, f"{name} ({bands}) cannot be satisfied at any resolution"

    def test_unknown_band_is_rejected(self, tmp_path):
        """A typo must not come back as an empty result."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=["B04", "B99"],
                output_dir=tmp_path / "out",
                resolution=10,
            )

        assert "B99" in str(exc_info.value)

    def test_unsupported_resolution_is_rejected(self, tmp_path):
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=["B04"],
                output_dir=tmp_path / "out",
                resolution=30,
            )

        assert "30m" in str(exc_info.value)

    def test_validation_runs_before_the_archive_is_opened(self, tmp_path):
        """The check must not need a readable product to fire."""
        broken = tmp_path / f"{L2A_NAME}.zip"
        broken.write_bytes(b"not a zip at all")

        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                broken, bands=["B11"], output_dir=tmp_path / "out", resolution=10
            )

        assert "B11" in str(exc_info.value)

    def test_missing_band_reports_which_one(self, tmp_path):
        """A band absent from the product is named, not silently dropped."""
        # B06 belongs in the 20m folder of a real L2A, so it passes validation;
        # this particular archive simply does not carry it.
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path, omit=("B06",)),
                bands=["B04", "B06"],
                output_dir=tmp_path / "out",
                resolution=20,
            )

        message = str(exc_info.value)
        assert "B06" in message
        assert "not found" in message

    def test_band_present_only_at_10m_is_refused_at_20m(self, tmp_path):
        """B08 has no 20m copy - B8A is its counterpart - so the hint must say 10m."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=["B08"],
                output_dir=tmp_path / "out",
                resolution=20,
            )

        message = str(exc_info.value)
        assert "resolution=10" in message
        assert "resolution=20" not in message  # the old hint sent people the wrong way

    def test_band_resampled_up_is_allowed(self, tmp_path):
        """B01 is 60m native but L2A ships it in the 20m folder."""
        extracted = extract_bands_from_safe(
            _l2a_zip(tmp_path),
            bands=["B01"],
            output_dir=tmp_path / "out",
            resolution=20,
        )

        assert extracted["B01"].read_bytes() == b"B01@20m"

    def test_band_absent_from_l2a_entirely(self, tmp_path):
        """B10 is dropped in L2A processing; say so rather than name a resolution."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l2a_zip(tmp_path),
                bands=["B10"],
                output_dir=tmp_path / "out",
                resolution=60,
            )

        assert "L1C only" in str(exc_info.value)

    def test_l1c_missing_band_reports_which_one(self, tmp_path):
        """Leniency on L1C still ends in a named band, not a short dict."""
        with pytest.raises(ValidationError) as exc_info:
            extract_bands_from_safe(
                _l1c_zip(tmp_path),
                bands=["B04", "B12"],
                output_dir=tmp_path / "out",
                resolution=10,
            )

        assert "B12" in str(exc_info.value)


class TestStackBandsValidation:
    """stack_bands must not leak a bare KeyError (defect 16)."""

    def test_band_order_naming_absent_band(self, tmp_path):
        with pytest.raises(ValidationError) as exc_info:
            stack_bands(
                {"B04": tmp_path / "red.jp2", "B03": tmp_path / "green.jp2"},
                tmp_path / "out.tif",
                band_order=["B04", "B03", "B02"],
            )

        message = str(exc_info.value)
        assert "B02" in message
        assert "B03" in message  # lists what it does have

    def test_empty_band_paths(self, tmp_path):
        with pytest.raises(ValidationError):
            stack_bands({}, tmp_path / "out.tif")
