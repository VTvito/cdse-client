"""NDVI time series for one field through a growing season (Sentinel-2 L2A).

Persona:
    An agronomist or agritech data scientist who follows one field from sowing
    to harvest and wants a clean, cloud-screened NDVI curve, not a pile of tiles.

What you get (in --output, default ./output/agri_ndvi_timeseries):
    ndvi_timeseries.csv   one row per selected date: date, product, clear
                          fraction over the field, NDVI mean / p10 / p90, pixel
                          count, and a status column saying why a date was skipped
    ndvi_timeseries.png   mean NDVI with the p10-p90 band; skipped dates are grey
                          ticks along the bottom
    downloads/            the L2A ZIPs, reused on a second run

Requires:
    pip install "cdse-client[processing]" matplotlib

Auth:
    CDSE_CLIENT_ID and CDSE_CLIENT_SECRET (OAuth2 client credentials from
    https://shapps.dataspace.copernicus.eu/dashboard/).

Run:
    python examples/agri_ndvi_timeseries.py
    (= --geojson examples/data/field_lombardy.geojson --start 2025-04-01
       --end 2025-09-30 --max-cloud 60 --min-clear 0.7 --every-days 7 --limit 200)

Radiometry note:
    Since processing baseline 04.00 (January 2022) L2A DNs carry
    BOA_ADD_OFFSET = -1000, i.e. reflectance = (DN - 1000) / 10000. Left in, the
    offset pulls NDVI towards zero, most over dark soil, so a series that spans
    old and new baselines would show a fake step. --apply-offset (on by default)
    reads BOA_ADD_OFFSET from MTD_MSIL2A.xml inside each product and applies it.

Where the library stops:
    - Every date downloads the full ~1 GB product even though the field is a few
      hundred pixels: CDSE OData serves whole products, there is no band subset.
      --every-days (default 7) keeps one product per window to bound that; a
      6-month season is then about 26 downloads. Use --every-days 1 for all.
    - The per-window pick uses the tile-level cloud cover, so the least cloudy
      tile can still have a cloud over the field; the SCL mask catches that, and
      SCL itself misses thin cirrus and cloud shadow edges now and then.
    - Search is by bounding box only; the polygon is applied here, in numpy.
    - The field in data/field_lombardy.geojson is a sample area, not a real
      parcel. Swap in your own polygon (EPSG:4326).
    - The offset comes from MTD_MSIL2A.xml; if a product ships without that file
      the baseline in the name (Nxxxx) is used instead, which assumes -1000.
    - Not verified against the live API: that every L2A STAC item carries a
      datetime (items without one are dropped) and the Nxxxx naming.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import rasterio.errors  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.features import geometry_mask  # noqa: E402
from rasterio.warp import reproject, transform_geom  # noqa: E402

from cdse import CDSEClient, geojson_to_bbox, read_geojson  # noqa: E402
from cdse.exceptions import CDSEError  # noqa: E402
from cdse.processing import SCL_CLOUD_CLASSES, crop_to_bbox, extract_bands_from_safe  # noqa: E402

EXAMPLE_KEY = "agri_ndvi_timeseries"
DEFAULT_GEOJSON = Path(__file__).resolve().parent / "data" / "field_lombardy.geojson"
BOA_OFFSET = 1000
# Cloud, shadow, cirrus and no-data, plus saturated (1) and snow (11): neither
# says anything about the crop.
BAD_SCL = sorted(SCL_CLOUD_CLASSES | {1, 11})
STAT_FIELDS = ["clear_fraction", "ndvi_mean", "ndvi_p10", "ndvi_p90"]
CSV_FIELDS = ["date", "product", *STAT_FIELDS, "n_pixels", "status"]
PROCESSING_ERRORS = (
    CDSEError,
    OSError,
    ValueError,
    zipfile.BadZipFile,
    rasterio.errors.RasterioError,
)

log = logging.getLogger(EXAMPLE_KEY)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cloud-screened NDVI time series for a field.")
    parser.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON, help="field polygon")
    parser.add_argument("--start", default="2025-04-01", help="start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-09-30", help="end date YYYY-MM-DD")
    parser.add_argument("--max-cloud", type=float, default=60.0, help="tile cloud cover max %%")
    parser.add_argument("--min-clear", type=float, default=0.7, help="min clear field fraction")
    parser.add_argument("--every-days", type=int, default=7, help="one product per N days")
    # Generous on purpose: the catalog is not sorted by cloud, so a tight limit
    # would cut the end of the season, not the worst dates.
    parser.add_argument("--limit", type=int, default=200, help="max products from the search")
    parser.add_argument("--output", type=Path, default=Path("output") / EXAMPLE_KEY)
    parser.add_argument(
        "--apply-offset",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="remove the -1000 BOA offset of baseline N0400+ products (default: on)",
    )
    return parser.parse_args(argv)


def field_geometry(geojson: dict) -> dict:
    """Return the first geometry of a FeatureCollection, Feature or bare geometry."""
    if geojson.get("type") == "FeatureCollection":
        geojson = geojson["features"][0]
    if geojson.get("type") == "Feature":
        return geojson["geometry"]
    return geojson


def one_per_window(products: list, days: int) -> list:
    """Keep the least cloudy product per `days`-day window (also dedups tile overlaps)."""
    dated = sorted((p for p in products if p.datetime is not None), key=lambda p: p.datetime)
    if not dated:
        return []
    first = dated[0].datetime.date()
    best: dict = {}
    for product in dated:
        window = (product.datetime.date() - first).days // max(days, 1)
        cloud = product.cloud_cover if product.cloud_cover is not None else 100.0
        if window not in best or cloud < best[window][0]:
            best[window] = (cloud, product)
    return [best[w][1] for w in sorted(best)]


def boa_offset(zip_path: Path) -> float:
    """BOA_ADD_OFFSET of an L2A product: -1000 from processing baseline 04.00 on, 0 before.

    Read from MTD_MSIL2A.xml inside the product, which is where the value actually
    lives, rather than assumed from the baseline in the file name.
    """
    with zipfile.ZipFile(zip_path) as zf:
        mtd = next((n for n in zf.namelist() if n.endswith("MTD_MSIL2A.xml")), None)
        text = zf.read(mtd).decode("utf-8", "ignore") if mtd else ""
    found = re.search(r"<BOA_ADD_OFFSET[^>]*>\s*(-?\d+)", text)
    if found:
        return float(found.group(1))
    # No metadata entry: fall back on the baseline in the name (_N0400_ and later).
    baseline = re.search(r"_N(\d{4})_", zip_path.name)
    return -float(BOA_OFFSET) if baseline and int(baseline.group(1)) >= 400 else 0.0


def read_field(zip_path: Path, bbox: list[float], workdir: Path) -> tuple:
    """B08 and B04 cropped to the bbox at 10 m, and SCL warped onto the same grid."""
    tenm = extract_bands_from_safe(zip_path, ["B08", "B04"], output_dir=workdir, resolution=10)
    # SCL only exists in the 20/60 m folders of an L2A product.
    scl_src = extract_bands_from_safe(zip_path, ["SCL"], output_dir=workdir, resolution=20)
    # Crop first: a tile is 10980 x 10980 pixels, the field a few hundred.
    arrays = []
    for band in ("B08", "B04"):
        cropped = crop_to_bbox(tenm[band], bbox, output_path=workdir / f"{band}_field.tif")
        with rasterio.open(cropped) as src:
            arrays.append(src.read(1).astype("float32"))
            transform, crs = src.transform, src.crs
    # Warp (not stretch) with nearest: SCL codes are classes, and the 20 m crop
    # does not line up exactly with the 10 m one.
    scl = np.zeros(arrays[0].shape, dtype="uint8")  # 0 = no data if nothing lands
    with rasterio.open(scl_src["SCL"]) as src:
        reproject(
            rasterio.band(src, 1),
            scl,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.nearest,
        )
    return arrays[0], arrays[1], scl, transform, crs


def field_stats(zip_path: Path, geometry: dict, bbox: list[float], apply_offset: bool) -> dict:
    """Clear fraction and NDVI statistics over the field polygon for one product."""
    with tempfile.TemporaryDirectory() as tmp:
        b08, b04, scl, transform, crs = read_field(zip_path, bbox, Path(tmp))

    geom = transform_geom("EPSG:4326", crs, geometry)
    in_field = geometry_mask([geom], out_shape=scl.shape, transform=transform, invert=True)
    n_field = int(in_field.sum())
    if n_field == 0:
        raise ValueError("the field polygon covers no pixel of the product")

    # DN 0 is L2A no-data (tile edge); SCL class 0 usually flags it too.
    clear = in_field & ~np.isin(scl, BAD_SCL) & (b08 > 0) & (b04 > 0)
    clear_fraction = float(clear.sum()) / n_field

    # reflectance = (DN + BOA_ADD_OFFSET) / 10000, and the offset is negative.
    offset = boa_offset(zip_path) if apply_offset else 0.0
    if offset:
        b08 = np.clip(b08 + offset, 0, None)
        b04 = np.clip(b04 + offset, 0, None)

    denom = b08 + b04
    valid = clear & (denom > 0)
    ndvi = (b08[valid] - b04[valid]) / denom[valid]
    stats = {"clear_fraction": clear_fraction, "n_pixels": int(valid.sum())}
    if ndvi.size:
        stats.update(
            ndvi_mean=float(ndvi.mean()),
            ndvi_p10=float(np.percentile(ndvi, 10)),
            ndvi_p90=float(np.percentile(ndvi, 90)),
        )
    return stats


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            out.update({k: f"{row[k]:.4f}" for k in STAT_FIELDS if k in row})
            writer.writerow(out)


def plot_series(rows: list[dict], title: str, path: Path) -> None:
    kept = [r for r in rows if r["status"] == "ok"]
    skipped = [r["date"] for r in rows if r["status"] != "ok"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    if kept:
        dates = [r["date"] for r in kept]
        low, high = [r["ndvi_p10"] for r in kept], [r["ndvi_p90"] for r in kept]
        ax.fill_between(dates, low, high, color="tab:green", alpha=0.2, label="p10-p90")
        ax.plot(dates, [r["ndvi_mean"] for r in kept], "o-", color="tab:green", label="mean")
    if skipped:
        # x in data units, y in axes units: the ticks hug the bottom whatever the NDVI range.
        ax.plot(
            skipped,
            [0.02] * len(skipped),
            "|",
            color="grey",
            markersize=10,
            transform=ax.get_xaxis_transform(),
            label="skipped (cloud / error)",
        )
    ax.set_ylim(-0.2, 1.0)
    ax.set_ylabel("NDVI")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def process_date(product, zip_path: Path, geometry: dict, bbox: list, args) -> dict:
    """One CSV row: statistics when the product is usable, otherwise why not."""
    row = {"date": product.datetime.date(), "product": product.name}
    if not zip_path.exists():
        return {**row, "status": "download failed"}
    try:
        row.update(field_stats(zip_path, geometry, bbox, args.apply_offset))
    except PROCESSING_ERRORS as e:
        # A truncated ZIP would be reused as-is on the next run, hence the hint.
        log.warning("%s: %s (delete %s to download it again)", product.name, e, zip_path.name)
        return {**row, "status": "processing error"}
    if row["clear_fraction"] < args.min_clear or "ndvi_mean" not in row:
        row["status"] = f"too cloudy (clear {row['clear_fraction']:.0%})"
    else:
        row["status"] = "ok"
    return row


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    downloads = args.output / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    try:
        geojson = read_geojson(args.geojson)
        geometry = field_geometry(geojson)
        bbox = list(geojson_to_bbox(geojson))
        client = CDSEClient(output_dir=str(downloads))
        found = client.search(
            bbox=bbox,
            start_date=args.start,
            end_date=args.end,
            collection="sentinel-2-l2a",
            cloud_cover_max=args.max_cloud,
            limit=args.limit,
            coverage="center",
        )
        if len(found) >= args.limit:
            log.warning("Search hit --limit %d: the end of the period may be missing", args.limit)
        products = one_per_window(found, args.every_days)
        if not products:
            print(f"No Sentinel-2 L2A products over {bbox} in {args.start}..{args.end}.")
            return 1
        log.info("%d products found, %d dates selected", len(found), len(products))
        client.download_all(products, output_dir=str(downloads), parallel=True)
    except CDSEError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    rows = []
    for product in products:
        # download_all only returns successes, unordered: match by file name instead.
        row = process_date(product, downloads / f"{product.name}.zip", geometry, bbox, args)
        if row["status"] == "ok":
            clear_pct = 100 * row["clear_fraction"]
            log.info("%s  NDVI %.3f  clear %.0f%%", row["date"], row["ndvi_mean"], clear_pct)
        else:
            log.info("%s  skipped: %s", row["date"], row["status"])
        rows.append(row)

    csv_path = args.output / "ndvi_timeseries.csv"
    png_path = args.output / "ndvi_timeseries.png"
    write_csv(rows, csv_path)
    feature = (geojson.get("features") or [{}])[0]
    name = (feature.get("properties") or {}).get("name", args.geojson.stem)
    plot_series(rows, f"NDVI, {name} ({args.start} to {args.end})", png_path)

    n_ok = sum(r["status"] == "ok" for r in rows)
    print(f"{n_ok}/{len(rows)} dates usable (clear >= {args.min_clear:.0%})")
    print(f"CSV:  {csv_path}\nPlot: {png_path}\nZIPs: {downloads}")
    if n_ok == 0:
        print("No date passed the cloud screen; try a longer period or lower --min-clear.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
