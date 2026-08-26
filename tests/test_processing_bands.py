"""Tests for band extraction from SAFE/ZIP products.

Kept apart from ``test_processing.py`` on purpose: that module skips entirely
without rasterio, which the ``dev`` extra does not install. Band extraction is
plain ``zipfile`` work, so these run everywhere -- including CI.
"""

import zipfile
from pathlib import Path

from cdse.processing import extract_bands_from_safe

L2A_PREFIX = "S2A_MSIL2A_20240115T101031.SAFE/GRANULE/L2A_T32TQM_20240115T101031/IMG_DATA"
L1C_PREFIX = "S2A_MSIL1C_20240115T101031.SAFE/GRANULE/L1C_T32TQM_20240115T101031/IMG_DATA"


def _make_zip(path: Path, entries: dict) -> Path:
    """Write a ZIP with the given name -> content entries."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def _l2a_zip(tmp_path: Path) -> Path:
    """A L2A layout: JP2s under R10m/R20m/R60m resolution subfolders."""
    entries = {
        f"{L2A_PREFIX}/R10m/T32TQM_20240115T101031_{b}_10m.jp2": f"{b}@10m".encode()
        for b in ("B02", "B03", "B04", "B08")
    }
    entries.update(
        {
            f"{L2A_PREFIX}/R20m/T32TQM_20240115T101031_{b}_20m.jp2": f"{b}@20m".encode()
            for b in ("B05", "B11", "B12")
        }
    )
    return _make_zip(tmp_path / "L2A.zip", entries)


def _l1c_zip(tmp_path: Path) -> Path:
    """A L1C layout: JP2s straight in IMG_DATA, no resolution subfolders."""
    entries = {
        f"{L1C_PREFIX}/T32TQM_20240115T101031_{b}.jp2": b.encode()
        for b in ("B02", "B03", "B04", "B08", "B11")
    }
    return _make_zip(tmp_path / "L1C.zip", entries)


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
            bands=["B05", "B11"],
            output_dir=tmp_path / "out",
            resolution=20,
        )

        assert sorted(extracted) == ["B05", "B11"]
        assert extracted["B11"].read_bytes() == b"B11@20m"

    def test_l2a_zip_does_not_substitute_resolution(self, tmp_path):
        """B11 is 20m-only: at resolution=10 it is missing, not silently swapped.

        Reporting that absence is defect 16, still open; this pins the behaviour
        so the L1C fallback cannot become a silent resolution substitution.
        """
        extracted = extract_bands_from_safe(
            _l2a_zip(tmp_path),
            bands=["B04", "B11"],
            output_dir=tmp_path / "out",
            resolution=10,
        )

        assert "B04" in extracted
        assert "B11" not in extracted
