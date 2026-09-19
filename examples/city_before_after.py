"""City before/after: two clean Sentinel-2 true-colour views of a city, years apart.

Persona:
    A journalist, educator or urban planner who wants a side-by-side image of a city
    at two dates (new districts, dried-up rivers, burnt parks) and, optionally, a map
    of where water (NDWI) or vegetation (NDVI) changed between them.

What you get (under --output, default ./output/city_before_after):
    before_<date>.png / .tif   true-colour preview and cropped RGB GeoTIFF, first date
    after_<date>.png / .tif    same for the second date
    before_after.png           the two views side by side with titles
    <index>_change.tif / .png  only with --index: index of date B minus date A
                               (float32 GeoTIFF, NaN = no data or cloud, plus a
                               diverging map centred at 0), and the per-date
                               <index>_a.tif / <index>_b.tif
    downloads/                 the full product ZIPs, reused on a second run
    It also prints the `cdse download --name ...` command for each picked product.

Requires:
    pip install "cdse-client[processing]" matplotlib

Auth:
    CDSE_CLIENT_ID and CDSE_CLIENT_SECRET (a free CDSE account, OAuth client credentials).

Run:
    python examples/city_before_after.py
    (= --city milano --date-a 2019-07-15 --date-b 2025-07-15 --days 20 --max-cloud 15
       --index none --size 1200)
    python examples/city_before_after.py --city roma --index ndwi
    python examples/city_before_after.py --bbox 11.20,43.73,11.30,43.81 --index ndvi

Where the library stops:
    - Each date downloads a full ~1 GB Sentinel-2 L2A product to crop a few km2 of it.
    - City boxes are rectangles from a small built-in table (--city needs one of its
      keys); there is no polygon search or administrative boundary.
    - 10 m pixels: districts, parks and roads are visible, single buildings are not.
    - The cloud filter uses the tile-level cloud percentage, so a "5 %" scene can still
      have its one cloud right over the city centre. Check the previews. The index
      change masks cloud, shadow and cirrus with the SCL band; the RGB views do not.
    - Each RGB view is contrast-stretched on its own (2-98 percentiles), so colours are
      for the eye, not for comparing brightness between dates, and a cloud covering
      more than a few % of the crop darkens the whole view.
    - compute_index() works on raw digital numbers. Products from processing baseline
      04.00 (2022) onwards store reflectance with a +1000 offset, older ones without,
      so an index change across that boundary would be biased. This script therefore
      computes the index itself after removing the offset read from MTD_MSIL2A.xml.
    - A city straddling two tiles may come out partly empty: only the tile covering the
      bbox centre is searched (coverage="center").
    - Not verified against the live API: that `cdse download --name` finds the STAC
      name (it may fall back to a prefix match) and saves under the same file name.
"""

from __future__ import annotations

import argparse
import logging
import math
import re
import sys
import tempfile
import warnings
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

from cdse import CDSEClient, Product  # noqa: E402
from cdse.exceptions import CDSEError  # noqa: E402
from cdse.geocoding import get_predefined_bbox  # noqa: E402
from cdse.processing import (  # noqa: E402
    INDEX_BANDS,
    cloud_mask_from_scl,
    compare_previews,
    crop_to_bbox,
    extract_bands_from_safe,
    preview_product,
)

log = logging.getLogger("city_before_after")
# compare_previews() calls plt.show(), which only warns under the Agg backend.
warnings.filterwarnings("ignore", message=".*non-interactive.*", category=UserWarning)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--city", default="milano", help="Built-in city key (default: milano)")
    p.add_argument("--bbox", help="min_lon,min_lat,max_lon,max_lat; overrides --city")
    p.add_argument("--date-a", default="2019-07-15", help="'Before' date (YYYY-MM-DD)")
    p.add_argument("--date-b", default="2025-07-15", help="'After' date (YYYY-MM-DD)")
    p.add_argument("--days", type=int, default=20, help="Search window +/- days (default 20)")
    p.add_argument("--max-cloud", type=float, default=15.0, help="Max tile cloud %% (15)")
    p.add_argument("--index", choices=["none", "ndwi", "ndvi"], default="none")
    p.add_argument("--size", type=int, default=1200, help="Preview long side in px (1200)")
    p.add_argument("--output", default="./output/city_before_after", help="Output folder")
    return p.parse_args(argv)


def resolve_bbox(args: argparse.Namespace) -> list[float]:
    if args.bbox:
        bbox = [float(v) for v in args.bbox.split(",")]
        if len(bbox) != 4:
            raise ValueError("--bbox needs 4 comma-separated numbers")
        return bbox
    predefined = get_predefined_bbox(args.city.lower())
    if predefined is None:
        raise ValueError(f"'{args.city}' is not a built-in city; pass --bbox instead")
    return list(predefined)


def window(target: str, days: int) -> tuple[str, str]:
    centre = datetime.strptime(target, "%Y-%m-%d").date()
    return (centre - timedelta(days=days)).isoformat(), (centre + timedelta(days=days)).isoformat()


def pick_best(products: list[Product], target: str) -> Product | None:
    """Least cloudy first; among equals, the acquisition closest to the target date."""
    target_day = datetime.strptime(target, "%Y-%m-%d").date()

    def key(p: Product) -> tuple[float, int]:
        cloud = p.cloud_cover if p.cloud_cover is not None else 101.0
        gap = abs((p.datetime.date() - target_day).days) if p.datetime else 10_000
        return cloud, gap

    return min(products, key=key) if products else None


def find_product(client, args, bbox: list[float], target: str) -> Product:
    start, end = window(target, args.days)
    log.info("Searching %s .. %s (cloud <= %s%%)", start, end, args.max_cloud)
    # A +/-20 day window holds up to ~16 passes over one tile; ask for all of them so
    # the least cloudy one is really among the candidates.
    common = {"start_date": start, "end_date": end, "cloud_cover_max": args.max_cloud}
    if args.bbox:
        products = client.search(bbox=bbox, limit=50, **common)
    else:
        products = client.search_by_city(args.city.lower(), use_predefined=True, limit=50, **common)
    best = pick_best(products, target)
    if best is None:
        raise LookupError(
            f"No Sentinel-2 L2A product around {target} with <= {args.max_cloud}% cloud; "
            "try a larger --days or --max-cloud"
        )
    log.info("  %d found, using %s (cloud %s%%)", len(products), best.name, best.cloud_cover)
    return best


def preview_size(bbox: list[float], long_side: int) -> tuple[int, int]:
    """Width/height keeping the area's real aspect ratio (a degree of longitude shrinks
    with latitude), so the city is not squashed into a square."""
    width_km = (bbox[2] - bbox[0]) * math.cos(math.radians((bbox[1] + bbox[3]) / 2))
    height_km = bbox[3] - bbox[1]
    if width_km >= height_km:
        return long_side, max(1, round(long_side * height_km / width_km))
    return max(1, round(long_side * width_km / height_km)), long_side


def boa_offset(zip_path: Path) -> float:
    """BOA_ADD_OFFSET of an L2A product: -1000 from baseline 04.00 on, 0 before."""
    with zipfile.ZipFile(zip_path) as zf:
        mtd = next((n for n in zf.namelist() if n.endswith("MTD_MSIL2A.xml")), None)
        text = zf.read(mtd).decode("utf-8", "ignore") if mtd else ""
    found = re.search(r"<BOA_ADD_OFFSET[^>]*>\s*(-?\d+)", text)
    if found:
        return float(found.group(1))
    # No metadata entry: fall back on the baseline in the name (_N0400_ and later).
    baseline = re.search(r"_N(\d{4})_", zip_path.name)
    return -1000.0 if baseline and int(baseline.group(1)) >= 400 else 0.0


def clear_index(zip_path: Path, index: str, bbox: list[float], out_path: Path) -> Path:
    """Index from surface reflectance, NaN where there is no data or SCL says cloud."""
    band_a, band_b = INDEX_BANDS[index]
    offset = boa_offset(zip_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        bands = extract_bands_from_safe(zip_path, [band_a, band_b], tmp, resolution=10)
        # SCL only exists at 20 m; its clear mask is put on the 10 m grid below.
        scl = extract_bands_from_safe(zip_path, ["SCL"], tmp, resolution=20)["SCL"]
        mask_tif = cloud_mask_from_scl(crop_to_bbox(scl, bbox, tmp / "scl.tif"), tmp / "m.tif")
        with rasterio.open(crop_to_bbox(bands[band_a], bbox, tmp / "a.tif")) as src_a:
            dn_a = src_a.read(1).astype(np.float32)
            grid = {"crs": src_a.crs, "transform": src_a.transform}
        with rasterio.open(crop_to_bbox(bands[band_b], bbox, tmp / "b.tif")) as src_b:
            dn_b = src_b.read(1).astype(np.float32)
        clear = np.zeros(dn_a.shape, dtype=np.uint8)
        with rasterio.open(mask_tif) as src_m:
            reproject(
                rasterio.band(src_m, 1),
                clear,
                dst_transform=grid["transform"],
                dst_crs=grid["crs"],
                resampling=Resampling.nearest,
            )
    # DN 0 is the L2A no-data value (outside the swath), whatever the offset.
    refl_a, refl_b = (dn_a + offset) / 10000, (dn_b + offset) / 10000
    total = refl_a + refl_b
    ok = (dn_a > 0) & (dn_b > 0) & (clear == 1) & (total > 0)
    value = np.full(dn_a.shape, np.nan, dtype=np.float32)
    value[ok] = np.clip((refl_a[ok] - refl_b[ok]) / total[ok], -1, 1)
    log.info("  %s: offset %+g, %.0f%% of the area usable", out_path.name, offset, ok.mean() * 100)

    height, width = value.shape
    profile = dict(grid, driver="GTiff", width=width, height=height, count=1)
    profile.update(dtype="float32", nodata=np.nan, compress="lzw")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(value, 1)
        dst.set_band_description(1, index.upper())
    return out_path


def index_change(zip_a: Path, zip_b: Path, index: str, bbox: list[float], out: Path) -> Path:
    tif_a = clear_index(zip_a, index, bbox, out / f"{index}_a.tif")
    tif_b = clear_index(zip_b, index, bbox, out / f"{index}_b.tif")
    with rasterio.open(tif_a) as src_a, rasterio.open(tif_b) as src_b:
        a = src_a.read(1)
        profile = {k: src_a.profile[k] for k in ("driver", "width", "height", "count", "crs")}
        profile.update(transform=src_a.transform, dtype="float32", nodata=np.nan, compress="lzw")
        # The two dates can come from different tiles (even different UTM zones), so
        # put B on A's grid before subtracting pixel by pixel.
        b = np.full_like(a, np.nan)
        reproject(
            source=src_b.read(1),
            destination=b,
            src_transform=src_b.transform,
            src_crs=src_b.crs,
            src_nodata=np.nan,
            dst_transform=src_a.transform,
            dst_crs=src_a.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    diff = (b - a).astype(np.float32)
    finite = np.abs(diff[np.isfinite(diff)])
    if not finite.size:
        raise ValueError(f"No pixel is clear on both dates; no {index.upper()} change to map")

    tif = out / f"{index}_change.tif"
    with rasterio.open(tif, "w", **profile) as dst:
        dst.write(diff, 1)
        dst.set_band_description(1, f"delta {index.upper()}")

    # Symmetric limits at the 98th percentile keep a few outliers (boats, new roofs)
    # from washing out the colour scale.
    lim = max(float(np.percentile(finite, 98)), 0.05)
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_facecolor("0.6")  # grey = no data or cloud on either date
    im = ax.imshow(diff, cmap="BrBG", norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim))
    ax.set_title(f"{index.upper()} change (after minus before); green/blue = higher, grey = n/a")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.8, label=f"delta {index.upper()}")
    fig.savefig(tif.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return tif


def run(args: argparse.Namespace) -> int:
    out = Path(args.output)
    downloads = out / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    bbox = resolve_bbox(args)
    place = args.city.capitalize() if not args.bbox else "Area"
    log.info("Area %s: %s", place, bbox)

    client = CDSEClient(output_dir=str(downloads))
    tiffs, titles, picked, written = [], [], [], []
    for label, target in (("before", args.date_a), ("after", args.date_b)):
        product = find_product(client, args, bbox, target)
        zip_path = client.download(product, output_dir=str(downloads))
        acq = product.datetime.date().isoformat() if product.datetime else target
        log.info("Building %s preview from %s", label, zip_path.name)
        result = preview_product(
            zip_path,
            bbox=bbox,
            resolution=10,
            output_path=out / f"{label}_{acq}.png",
            display=False,
            size=preview_size(bbox, args.size),
        )
        tiffs.append(result["tiff_path"])
        titles.append(f"{place} {acq}")
        picked.append((product, zip_path))
        written += [result["preview_path"], result["tiff_path"]]

    fig = compare_previews(tiffs, titles=titles, figsize=(16, 8))
    side_by_side = out / "before_after.png"
    fig.savefig(side_by_side, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(side_by_side)

    if args.index != "none":
        log.info("Computing %s change", args.index.upper())
        change = index_change(picked[0][1], picked[1][1], args.index, bbox, out)
        written += [out / f"{args.index}_a.tif", out / f"{args.index}_b.tif"]
        written += [change, change.with_suffix(".png")]

    print("\nFiles written:")
    for path in written:
        print(f"  {path}")
    print("\nSame products from the command line (no Python needed):")
    for product, _ in picked:
        print(f"  cdse download --name {product.name} -o {downloads}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        return run(args)
    except (CDSEError, LookupError, ValueError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
