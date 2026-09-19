"""Monthly tropospheric NO2 map from Sentinel-5P for a region.

Persona:
    An environmental agency or air-quality analyst who needs a monthly map of
    tropospheric NO2 over a region (default: the Po Valley, one of Europe's
    NO2 hot spots) to compare with ground stations or with previous months.

What you get (under --output, default ./output/s5p_no2_monthly):
    no2_monthly.tif   monthly mean tropospheric NO2, EPSG:4326 GeoTIFF, float32,
                      umol/m2, NaN where no valid observation fell in a cell
    no2_monthly.png   map of the same grid with colorbar and orbit count
    no2_counts.tif    number of valid observations per cell (reliability)
    downloads/        the Sentinel-5P L2 NO2 products (reused on a second run)

Requires:
    pip install "cdse-client[processing]" xarray netCDF4

Auth:
    CDSE_CLIENT_ID and CDSE_CLIENT_SECRET environment variables (OAuth client
    credentials from the Copernicus Data Space Ecosystem dashboard).

Run:
    python examples/s5p_no2_monthly.py
    (= --bbox 7.5,44.4,12.6,46.2 --month 2025-01 --limit 500 --qa 0.75 --grid 0.05)

Where the library stops:
    - cdse-client does not read NetCDF: this script opens the files with xarray.
    - Every OFFL L2 product is a full orbit (several hundred MB, size not checked),
      downloaded whole even though only a small part covers the bbox. A month
      over the Po Valley is roughly 30-50 orbits, i.e. tens of GB.
    - Gridding is pixel-centre binning: each ground pixel counts for the one
      cell its centre falls in, with no footprint-area weighting. For rigorous
      L3 products use harp (https://github.com/stcorp/harp) or satpy.
    - The catalogue mixes every S5P L2 product type (NO2, CO, O3, CH4, ...). The
      script asks for NO2 only with a CQL2 filter on "s5p:type"; that filter and
      the STAC id format (the standard S5P file name is assumed) have NOT been
      verified against the live API. If the filter is rejected the script falls
      back to an unfiltered search (capped at 1000 results) and filters by name.
    - Downloading S5P through this client relies on a recent fix that appends
      the ".nc" suffix to the OData product name. That fix has NOT yet been
      verified against the live CDSE API, nor whether the payload is a ZIP or
      the raw netCDF file (both are handled).
"""

from __future__ import annotations

import argparse
import calendar
import logging
import re
import sys
import zipfile
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cdse import CDSEClient  # noqa: E402
from cdse.exceptions import CatalogError, CDSEError  # noqa: E402

log = logging.getLogger("s5p_no2_monthly")

NO2_MARKER = "L2__NO2___"
NO2_VAR = "nitrogendioxide_tropospheric_column"
# S5P_OFFL_L2__NO2____<start>_<end>_<orbit>_<collection>_<processor>_<production time>
# Fields are padded with underscores, so match on the two timestamps instead of
# counting split fields.
NAME_PATTERN = re.compile(r"_\d{8}T\d{6}_\d{8}T\d{6}_(?P<orbit>\d{5})_")
TYPE_PATTERN = re.compile(r"L2__(.+?)_*\d{8}T\d{6}")
# STAC "filter" extension, passed through search(**kwargs) untouched.
NO2_FILTER = {
    "filter-lang": "cql2-json",
    "filter": {"op": "=", "args": [{"property": "s5p:type"}, "NO2"]},
}


def month_arg(value: str) -> str:
    try:
        year, mon = (int(part) for part in value.split("-"))
        calendar.monthrange(year, mon)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM, got {value!r}") from exc
    return f"{year:04d}-{mon:02d}"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bbox", default="7.5,44.4,12.6,46.2", help="min_lon,min_lat,max_lon,max_lat"
    )
    parser.add_argument("--month", type=month_arg, default="2025-01", help="YYYY-MM")
    parser.add_argument("--limit", type=int, default=500, help="max products from the search")
    parser.add_argument("--qa", type=float, default=0.75, help="keep pixels with qa_value > this")
    parser.add_argument("--grid", type=float, default=0.05, help="grid cell size in degrees")
    parser.add_argument("--output", default="./output/s5p_no2_monthly", help="output folder")
    return parser.parse_args(argv)


def month_range(month: str) -> tuple[str, str]:
    year, mon = (int(part) for part in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last_day:02d}"


def search_no2(client, bbox: list[float], start: str, end: str, limit: int) -> list:
    # A ~2600 km wide S5P swath may cover most of the bbox without covering its
    # centre; every intersecting orbit adds valid pixels, so keep them all.
    common = {"bbox": bbox, "start_date": start, "end_date": end, "collection": "sentinel-5p-l2"}
    try:
        found = client.search(**common, limit=limit, coverage="any", **NO2_FILTER)
    except CatalogError as exc:
        # Without the filter a month holds every product type, about ten times
        # more items, so ask for the most the client pages through.
        log.warning("Catalogue rejected the NO2 filter (%s); filtering by name instead", exc)
        limit = max(limit, 1000)
        found = client.search(**common, limit=limit, coverage="any")
    if len(found) >= limit:
        log.warning("Search hit the limit of %d: later days may be missing", limit)
    return found


def is_no2(product) -> bool:
    return NO2_MARKER in product.name or product.properties.get("s5p:type") == "NO2"


def select_no2_products(products: list) -> list:
    """Keep NO2 products, preferring OFFL/RPRO over NRTI for the same orbit.

    NRTI (near real time) is published within hours as ~5 minute granules, so an
    orbit has several; OFFL (offline) comes days later as one full orbit with
    better auxiliary data and is the one to use for a monthly mean. When an orbit
    only has NRTI (the last days of the current month), all its granules are kept.
    """
    by_orbit: dict[str, list] = {}
    for product in products:
        if not is_no2(product):
            continue
        match = NAME_PATTERN.search(product.name)
        orbit = match.group("orbit") if match else product.name
        by_orbit.setdefault(orbit, []).append(product)

    selected = []
    for group in by_orbit.values():
        consolidated = [p for p in group if "_NRTI_" not in p.name]
        if consolidated:
            # Reprocessed versions share the orbit; the name ends with the
            # production time, so the largest name is the most recent one.
            selected.append(max(consolidated, key=lambda p: p.name))
        else:
            selected.extend(group)
    return sorted(selected, key=lambda p: p.name)


def product_types(products: list) -> list[str]:
    """Distinct product types (text between 'L2__' and the start date)."""
    types = set()
    for product in products:
        match = TYPE_PATTERN.search(product.name)
        types.add(match.group(1).rstrip("_") if match else product.name[:30])
    return sorted(types)


def ensure_netcdf(path: Path) -> Path:
    """Return a path to the .nc file, extracting it if the download is a ZIP.

    The client saves every download as <name>.zip, but for S5P the OData
    payload may be the raw netCDF file rather than an archive.
    """
    if not zipfile.is_zipfile(path):
        return path
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.namelist() if m.endswith(".nc")]
        if not members:
            raise CDSEError(f"No .nc file inside {path.name}")
        target = path.parent / Path(members[0]).name
        if not target.exists():
            target.write_bytes(archive.read(members[0]))
        return target


def accumulate(nc_path: Path, bbox: list[float], grid: float, qa: float, sums, counts) -> int:
    """Add the valid pixels of one orbit to the sum/count grids; return pixels used."""
    import xarray as xr

    # engine is explicit: the raw netCDF may sit in a file named .zip.
    with xr.open_dataset(nc_path, group="PRODUCT", engine="netcdf4") as ds:
        no2 = ds[NO2_VAR].values.ravel()
        qa_value = ds["qa_value"].values.ravel()
        lat = ds["latitude"].values.ravel()
        lon = ds["longitude"].values.ravel()

    min_lon, min_lat, max_lon, max_lat = bbox
    # qa_value > 0.75 is the recommended threshold for tropospheric NO2: it
    # removes cloudy scenes, snow/ice and retrieval failures that bias the mean.
    # Small negative columns are retrieval noise and are kept, or the mean over
    # clean areas would be biased high.
    keep = (
        np.isfinite(no2)
        & (qa_value > qa)
        & (lon >= min_lon)
        & (lon < max_lon)
        & (lat > min_lat)
        & (lat <= max_lat)
    )
    if not keep.any():
        return 0
    # Row 0 is the northern edge, matching a north-up GeoTIFF.
    rows = ((max_lat - lat[keep]) / grid).astype(int).clip(0, sums.shape[0] - 1)
    cols = ((lon[keep] - min_lon) / grid).astype(int).clip(0, sums.shape[1] - 1)
    np.add.at(sums, (rows, cols), no2[keep])
    np.add.at(counts, (rows, cols), 1)
    return int(keep.sum())


def write_geotiff(path: Path, data: np.ndarray, bbox: list[float], grid: float, nodata) -> None:
    import rasterio
    from rasterio.transform import from_origin

    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": data.dtype.name,
        "crs": "EPSG:4326",
        "transform": from_origin(bbox[0], bbox[3], grid, grid),
        "nodata": nodata,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def save_map(path: Path, mean_umol: np.ndarray, bbox: list[float], grid: float, title: str):
    fig, ax = plt.subplots(figsize=(10, 5))
    # The grid starts at the north-west corner; the last row/column may reach
    # slightly past the bbox when its size is not a multiple of the cell size.
    n_rows, n_cols = mean_umol.shape
    extent = (bbox[0], bbox[0] + n_cols * grid, bbox[3] - n_rows * grid, bbox[3])
    # A few noisy cells with one observation would otherwise stretch the scale.
    vmin, vmax = np.nanpercentile(mean_umol, [2, 98])
    image = ax.imshow(
        mean_umol, extent=extent, origin="upper", cmap="viridis", vmin=vmin, vmax=vmax
    )
    # A degree of longitude shrinks with latitude; without this the map is stretched E-W.
    ax.set_aspect(1 / np.cos(np.radians((bbox[1] + bbox[3]) / 2)))
    fig.colorbar(image, ax=ax, label="tropospheric NO2 [umol/m2]")
    ax.set_title(title)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    bbox = [float(v) for v in args.bbox.split(",")]
    output = Path(args.output)
    downloads = output / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    try:
        import netCDF4  # noqa: F401
        import xarray  # noqa: F401
    except ImportError:
        log.error("This example needs xarray and netCDF4: pip install xarray netCDF4")
        return 1

    try:
        start, end = month_range(args.month)
        client = CDSEClient(output_dir=str(downloads))
        found = search_no2(client, bbox, start, end, args.limit)
        log.info("Search returned %d Sentinel-5P products", len(found))
        products = select_no2_products(found)
        if not products:
            log.error(
                "No NO2 products among the results. Product types seen: %s",
                ", ".join(product_types(found)) or "none",
            )
            return 1
        log.info("%d NO2 products after OFFL/NRTI de-duplication", len(products))

        paths = client.download_all(products, output_dir=str(downloads))
        if not paths:
            log.error("No product could be downloaded")
            return 1

        # Round before ceil: 1.8 / 0.05 is 36.000000000000004 in floating point.
        n_rows = int(np.ceil(round((bbox[3] - bbox[1]) / args.grid, 6)))
        n_cols = int(np.ceil(round((bbox[2] - bbox[0]) / args.grid, 6)))
        sums = np.zeros((n_rows, n_cols), dtype=np.float64)
        counts = np.zeros((n_rows, n_cols), dtype=np.int32)
        used = 0
        for path in paths:
            try:
                nc_path = ensure_netcdf(Path(path))
                n_pixels = accumulate(nc_path, bbox, args.grid, args.qa, sums, counts)
            except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
                # One truncated or unexpected file should not sink the month.
                log.warning("Skipping %s: %s", Path(path).name, exc)
                continue
            log.info("%s: %d valid pixels", Path(path).name, n_pixels)
            used += int(n_pixels > 0)
    except CDSEError as exc:
        log.error("CDSE request failed: %s", exc)
        return 1

    if used == 0:
        log.error("No pixel passed the qa > %.2f filter inside the bbox", args.qa)
        return 1

    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(counts > 0, sums / counts, np.nan)
    # mol/m2 is awkward to read; umol/m2 gives values in the tens to hundreds.
    mean_umol = (mean * 1e6).astype(np.float32)

    write_geotiff(output / "no2_monthly.tif", mean_umol, bbox, args.grid, float("nan"))
    write_geotiff(output / "no2_counts.tif", counts, bbox, args.grid, None)
    title = f"Sentinel-5P tropospheric NO2, mean {args.month} ({used} products, qa > {args.qa})"
    save_map(output / "no2_monthly.png", mean_umol, bbox, args.grid, title)

    print(f"Monthly NO2 for {args.month} from {used} products written to {output}:")
    for name in ("no2_monthly.tif", "no2_monthly.png", "no2_counts.tif"):
        print(f"  {output / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
