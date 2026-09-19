"""Map burn severity after a wildfire with the differenced Normalized Burn Ratio (dNBR).

Persona:
    A civil protection or regional GIS analyst who needs a first burn-severity map
    and burned-area figures a few weeks after a fire.

What you get (in --output, default ./output/wildfire_dnbr):
    dnbr.tif           float32 dNBR (NBR_pre - NBR_post), NaN where masked
    dnbr_severity.tif  uint8 severity classes with an embedded colour table
                       (0 masked, 1 unburned, 2 low, 3 moderate-low,
                       4 moderate-high, 5 high)
    severity.png       severity map with hectares per class in the legend
    before_after.png   true-colour previews of the pre- and post-fire scenes
    plus a hectares-per-class table printed to the console.

    The default event is the Montiferru wildfire (Oristano, Sardinia), which
    started on 2021-07-24 and burned about 13,000 ha. The default bbox is an
    approximate box around the burned area, not an official perimeter.

Requires:
    pip install "cdse-client[processing]"

Auth:
    CDSE_CLIENT_ID and CDSE_CLIENT_SECRET environment variables (a CDSE OAuth client).

Run:
    python examples/wildfire_dnbr.py
    python examples/wildfire_dnbr.py --bbox 8.45,40.05,8.75,40.25 \
        --event-date 2021-07-24 --window-days 30 --max-cloud 20

Where the library stops:
    - You must already know the event date and a bbox around it; there is no
      fire-perimeter lookup and no polygon search (the bbox is a rectangle).
    - Each date means downloading a full Sentinel-2 L2A product (~1 GB) even if
      only a small window is used. Downloads are reused on a second run.
    - Scenes are picked by tile-level cloud cover, which may not reflect clouds
      or smoke over the fire itself; the SCL mask catches most of it, not all.
    - Since processing baseline 04.00 (January 2022, and in CDSE's reprocessed
      N0500 copies of older dates) L2A DNs carry BOA_ADD_OFFSET = -1000. NBR is
      therefore computed here rather than with compute_index("nbr"), after
      removing the offset read from MTD_MSIL2A.xml inside each product (falling
      back to the baseline in the name, then to the acquisition date).
    - SCL water and snow are masked with the clouds: dNBR over sea is noise.
    - No vectorisation of the burned area: use rasterio.features.shapes on
      dnbr_severity.tif if you need polygons.
    - The Key & Benson / USGS thresholds are generic; calibrate them locally
      (e.g. against field plots or CBI) before any official use.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import warnings
import zipfile
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

from cdse import CDSEClient  # noqa: E402
from cdse.exceptions import CDSEError  # noqa: E402
from cdse.processing import (  # noqa: E402
    SCL_CLOUD_CLASSES,
    cloud_mask_from_scl,
    compare_previews,
    crop_and_stack,
    crop_to_bbox,
    extract_bands_from_safe,
)

log = logging.getLogger("wildfire_dnbr")

# compare_previews calls plt.show(), which only warns under the Agg backend.
warnings.filterwarnings("ignore", message=".*non-interactive.*")

# Clouds, shadow and no-data, plus water (6) and snow (11): neither burns, and
# sun glint on the sea changes NBR between dates enough to look like a fire.
MASKED_SCL = SCL_CLOUD_CLASSES | {6, 11}
BOA_OFFSET = 1000

# Key & Benson (2006) / USGS dNBR breaks. Negative values (regrowth) fold into
# "unburned": for an emergency map only burned vs not burned matters.
BREAKS = [0.10, 0.27, 0.44, 0.66]
CLASSES = [
    # (value, name, RGB) - the usual USGS severity palette
    (0, "masked (cloud/water/no data)", (200, 200, 200)),
    (1, "unburned", (26, 152, 80)),
    (2, "low", (255, 255, 115)),
    (3, "moderate-low", (255, 170, 0)),
    (4, "moderate-high", (230, 0, 0)),
    (5, "high", (122, 0, 160)),
]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bbox", default="8.45,40.05,8.75,40.25", help="min_lon,min_lat,...")
    parser.add_argument("--event-date", default="2021-07-24", help="fire start, YYYY-MM-DD")
    parser.add_argument("--window-days", type=int, default=30, help="days searched each side")
    parser.add_argument("--max-cloud", type=float, default=20.0, help="max tile cloud cover %%")
    parser.add_argument("--output", default="./output/wildfire_dnbr", help="output directory")
    args = parser.parse_args(argv)
    try:
        args.bbox = [float(v) for v in args.bbox.split(",")]
        args.event_date = date.fromisoformat(args.event_date)
    except ValueError as exc:
        parser.error(f"bad --bbox or --event-date: {exc}")
    if len(args.bbox) != 4 or not (args.bbox[0] < args.bbox[2] and args.bbox[1] < args.bbox[3]):
        parser.error("--bbox needs min_lon,min_lat,max_lon,max_lat with min < max")
    if args.window_days < 2:
        parser.error("--window-days must be >= 2")
    return args


def pick_scene(
    client: CDSEClient,
    bbox: list[float],
    start: date,
    end: date,
    event: date,
    max_cloud: float,
    label: str,
):
    """Least cloudy product in the window; ties go to the date closest to the event."""
    products = client.search(
        bbox,
        start.isoformat(),
        end.isoformat(),
        collection="sentinel-2-l2a",
        cloud_cover_max=max_cloud,
        limit=50,
        coverage="center",
    )
    log.info("%s window %s..%s: %d product(s)", label, start, end, len(products))
    if not products:
        return None

    def rank(p):
        cloud = p.cloud_cover if p.cloud_cover is not None else 101.0
        gap = abs((p.datetime.date() - event).days) if p.datetime else 10_000
        return (cloud, gap)

    best = min(products, key=rank)
    log.info("%s scene: %s (cloud %s%%)", label, best.name, best.cloud_cover)
    return best


def boa_offset(zip_path: Path, product) -> int:
    """DN offset to subtract from an L2A product: 1000 from processing baseline 04.00 on.

    Read from MTD_MSIL2A.xml inside the product, where BOA_ADD_OFFSET actually
    lives (as a negative number), because the baseline in the name is only a proxy.
    """
    with zipfile.ZipFile(zip_path) as zf:
        mtd = next((n for n in zf.namelist() if n.endswith("MTD_MSIL2A.xml")), None)
        text = zf.read(mtd).decode("utf-8", "ignore") if mtd else ""
    found = re.search(r"<BOA_ADD_OFFSET[^>]*>\s*(-?\d+)", text)
    if found:
        return -int(found.group(1))
    match = re.search(r"_N(\d{4})_", product.name)
    if match:
        return BOA_OFFSET if int(match.group(1)) >= 400 else 0
    # Neither metadata nor baseline: fall back to the date baseline 04.00 went live.
    acquired = product.datetime.date() if product.datetime else None
    return BOA_OFFSET if acquired and acquired >= date(2022, 1, 25) else 0


def nbr(product_zip: Path, bbox: list[float], work: Path, offset: int) -> Path:
    """NBR = (B8A - B12) / (B8A + B12) at 20 m, on reflectance with the BOA offset removed."""
    paths = extract_bands_from_safe(product_zip, ["B8A", "B12"], output_dir=work, resolution=20)
    crops = {b: crop_to_bbox(p, bbox, work / f"{b}_crop.tif") for b, p in paths.items()}
    with rasterio.open(crops["B8A"]) as a, rasterio.open(crops["B12"]) as b:
        nir = np.clip(a.read(1).astype(np.float32) - offset, 0, None)
        swir = np.clip(b.read(1).astype(np.float32) - offset, 0, None)
        profile = grid_profile(a)
    total = nir + swir
    index = np.full(total.shape, np.nan, dtype=np.float32)
    np.divide(nir - swir, total, out=index, where=total > 0)
    out = work / "nbr.tif"
    with rasterio.open(out, "w", **dict(profile, dtype="float32", nodata=np.nan)) as dst:
        dst.write(index, 1)
        dst.set_band_description(1, "NBR")
    return out


def clear_mask(product_zip: Path, bbox: list[float], work: Path) -> Path:
    """SCL at 20 m, cropped like the NBR bands so both land on the same pixel grid."""
    scl = extract_bands_from_safe(product_zip, ["SCL"], output_dir=work, resolution=20)["SCL"]
    scl_crop = crop_to_bbox(scl, bbox, work / "SCL_crop.tif")
    return cloud_mask_from_scl(scl_crop, work / "clear.tif", classes=MASKED_SCL)


def grid_profile(ds) -> dict:
    """Minimal single-band GeoTIFF profile on the grid of `ds` (no inherited block sizes)."""
    return {
        "driver": "GTiff",
        "height": ds.height,
        "width": ds.width,
        "count": 1,
        "crs": ds.crs,
        "transform": ds.transform,
        "compress": "lzw",
    }


def read_on_grid(path: Path, ref, resampling: Resampling) -> np.ndarray:
    """Read band 1 of `path`, warping it onto the grid of the open dataset `ref` if needed."""
    with rasterio.open(path) as src:
        if src.shape == ref.shape and src.transform == ref.transform and src.crs == ref.crs:
            return src.read(1)
        # Pre and post come from different tiles (or UTM zones): resample post onto pre.
        log.info("Resampling %s onto the pre-fire grid", path.name)
        # Outside the post footprint: NaN for NBR, 0 (= not clear) for the mask.
        fill = src.nodata if src.nodata is not None else 0
        out = np.full(ref.shape, fill, dtype=src.dtypes[0])
        reproject(
            rasterio.band(src, 1),
            out,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=resampling,
        )
        return out


def classify(dnbr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    severity = (np.digitize(dnbr, BREAKS) + 1).astype(np.uint8)
    severity[~valid] = 0
    return severity


def write_outputs(out: Path, profile: dict, dnbr: np.ndarray, severity: np.ndarray) -> None:
    with rasterio.open(
        out / "dnbr.tif", "w", **dict(profile, dtype="float32", nodata=np.nan)
    ) as dst:
        dst.write(dnbr.astype(np.float32), 1)
        dst.set_band_description(1, "dNBR")
    # The colour table must be set before the pixels: GTiff fixes the
    # photometric tag at the first write.
    with rasterio.open(
        out / "dnbr_severity.tif", "w", **dict(profile, dtype="uint8", nodata=0)
    ) as dst:
        dst.write_colormap(1, {v: (*rgb, 255) for v, _, rgb in CLASSES})
        dst.write(severity, 1)
        dst.set_band_description(1, "burn severity (0 masked, 1 unburned .. 5 high)")


def hectares_per_class(severity: np.ndarray, transform) -> dict[int, float]:
    # The grid is UTM, so pixel size is in metres (20 m -> 0.04 ha per pixel).
    pixel_ha = abs(transform.a * transform.e) / 10_000
    counts = np.bincount(severity.ravel(), minlength=len(CLASSES))
    return {v: float(counts[v] * pixel_ha) for v, _, _ in CLASSES}


def plot_severity(path: Path, severity: np.ndarray, ha: dict[int, float], title: str) -> None:
    cmap = ListedColormap([np.array(rgb) / 255 for _, _, rgb in CLASSES])
    norm = BoundaryNorm(np.arange(-0.5, len(CLASSES) + 0.5), cmap.N)
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.imshow(severity, cmap=cmap, norm=norm, interpolation="nearest")
    ax.set_title(title)
    ax.axis("off")
    handles = [
        Patch(color=np.array(rgb) / 255, label=f"{name}: {ha[v]:,.0f} ha")
        for v, name, rgb in CLASSES
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.9)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    bbox, event = args.bbox, args.event_date
    out = Path(args.output)
    downloads, work = out / "downloads", out / "work"
    out.mkdir(parents=True, exist_ok=True)

    try:
        client = CDSEClient(output_dir=str(downloads))
        one = timedelta(days=1)
        window = timedelta(days=args.window_days)
        pre = pick_scene(client, bbox, event - window, event - one, event, args.max_cloud, "pre")
        post = pick_scene(client, bbox, event + one, event + window, event, args.max_cloud, "post")
        if pre is None or post is None:
            print(
                "error: no Sentinel-2 L2A scene in the pre or post window; try a larger "
                "--window-days or --max-cloud",
                file=sys.stderr,
            )
            return 1

        zips = {
            tag: client.download(p, output_dir=str(downloads))
            for tag, p in (("pre", pre), ("post", post))
        }
        nbr_path, clear = {}, {}
        for tag, product in (("pre", pre), ("post", post)):
            offset = boa_offset(zips[tag], product)
            log.info("Computing NBR (BOA offset %d) and SCL clear mask for %s", offset, tag)
            nbr_path[tag] = nbr(zips[tag], bbox, work / tag, offset)
            clear[tag] = clear_mask(zips[tag], bbox, work / tag)

        with rasterio.open(nbr_path["pre"]) as ref:
            profile, transform = grid_profile(ref), ref.transform
            nbr_pre = ref.read(1)
            nbr_post = read_on_grid(nbr_path["post"], ref, Resampling.bilinear)
            valid = (read_on_grid(clear["pre"], ref, Resampling.nearest) == 1) & (
                read_on_grid(clear["post"], ref, Resampling.nearest) == 1
            )
        valid &= np.isfinite(nbr_pre) & np.isfinite(nbr_post)

        dnbr = np.where(valid, nbr_pre - nbr_post, np.nan).astype(np.float32)
        severity = classify(np.nan_to_num(dnbr), valid)
        write_outputs(out, profile, dnbr, severity)
        ha = hectares_per_class(severity, transform)

        pre_d, post_d = (
            p.datetime.date().isoformat() if p.datetime else p.name for p in (pre, post)
        )
        plot_severity(
            out / "severity.png", severity, ha, f"Burn severity (dNBR) {pre_d} vs {post_d}"
        )

        # 10 m true colour gives the human check that the map is not a cloud artefact.
        rgb = [
            crop_and_stack(
                zips[t],
                bbox,
                bands=["B04", "B03", "B02"],
                output_path=work / t / "rgb.tif",
                resolution=10,
            )
            for t in ("pre", "post")
        ]
        fig = compare_previews(rgb, titles=[f"pre-fire {pre_d}", f"post-fire {post_d}"])
        fig.savefig(out / "before_after.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
    except CDSEError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"\nBurn severity {pre_d} -> {post_d}, bbox {bbox}")
    print(f"{'class':<30}{'hectares':>12}")
    for v, name, _ in CLASSES:
        print(f"{name:<30}{ha[v]:>12,.1f}")
    burned = sum(ha[v] for v in (2, 3, 4, 5))
    print(f"{'burned (low..high)':<30}{burned:>12,.1f}")
    print(f"\nWrote dnbr.tif, dnbr_severity.tif, severity.png, before_after.png in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
