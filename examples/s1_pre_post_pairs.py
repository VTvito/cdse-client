"""Sentinel-1 pre/post event pairs from the same relative orbit.

Persona:
  Emergency analyst (floods, landslides). During the event the sky is overcast, so
  optical imagery is useless; radar sees through clouds. Change detection on SAR only
  works when the "before" and "after" images share the same viewing geometry, i.e.
  the same relative orbit (track). This script finds those pairs.

What you get (under --output, default ./output/s1_pre_post_pairs):
  - pairs.csv      one row per track: latest pre-event and earliest post-event GRD
  - pairs.geojson  the two footprints of each best pair (property "role": pre/post)
  - downloads/     with --download, the best pair overall as .zip (reused on re-runs)
  A table sorted by days between the two acquisitions is printed to the console.

Requires:
  pip install cdse-client[geo]        (shapely is used for the bbox coverage figure)

Auth:
  Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET.

Run:
  python examples/s1_pre_post_pairs.py
  (= --bbox 11.6,44.1,12.3,44.5 --event-date 2023-05-17 --window-days 24 --limit 100,
   the May 2023 Emilia-Romagna floods)

Where the library stops:
  - It only finds and downloads. GRD must be calibrated, speckle filtered and terrain
    corrected before any change detection (SNAP, pyroSAR, or the Sentinel Hub
    processing API); none of that is done here.
  - Each GRD is roughly 1 GB; --download fetches two of them.
  - Search is by bbox only (no polygon). The relative orbit is taken from
    "sat:relative_orbit" when the catalogue provides it, otherwise computed from the
    absolute orbit in the product name (S1A/S1B only); other platforms get an
    approximate track key. Which STAC properties the catalogue returns for
    sentinel-1-grd, and the server-side CQL2 filter behind --server-filter, have not
    been verified against the live API.
  - Checksums are often absent from STAC metadata; download_with_checksum then only
    logs a warning.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from shapely.geometry import box, shape

from cdse import CDSEClient
from cdse.exceptions import CDSEError

log = logging.getLogger("s1_pre_post_pairs")

POLARISATION_CODES = {"1SDV": "VV+VH", "1SSV": "VV", "1SDH": "HH+HV", "1SSH": "HH"}
# Offsets that map the absolute orbit onto the 175-orbit repeat cycle (12 days).
RELATIVE_ORBIT_OFFSETS = {"S1A": 73, "S1B": 27}


def name_fields(product) -> list[str]:
    # S1A_IW_GRDH_1SDV_<start>_<stop>_<abs orbit>_<datatake>_<crc>
    return product.name.split("_")


def acquisition_time(product) -> datetime | None:
    if product.datetime is not None:
        return product.datetime.replace(tzinfo=None)
    fields = name_fields(product)
    try:
        return datetime.strptime(fields[4], "%Y%m%dT%H%M%S")
    except (IndexError, ValueError):
        return None


def orbit_direction(product) -> str:
    state = product.properties.get("sat:orbit_state")
    return str(state).lower() if state else "unknown"


def polarisation(product) -> str:
    pols = product.properties.get("sar:polarizations") or product.properties.get("s1:polarization")
    if pols:
        return "+".join(pols) if isinstance(pols, (list, tuple)) else str(pols)
    fields = name_fields(product)
    return POLARISATION_CODES.get(fields[3], "unknown") if len(fields) > 3 else "unknown"


def track_key(product) -> tuple[str, bool]:
    """Return (track label, exact). Same label means same viewing geometry."""
    if product.orbit_number is not None:
        return f"rel {int(product.orbit_number):03d}", True
    fields = name_fields(product)
    platform = fields[0] if fields else "?"
    if platform in RELATIVE_ORBIT_OFFSETS and len(fields) > 6 and fields[6].isdigit():
        absolute = int(fields[6])
        return f"rel {((absolute - RELATIVE_ORBIT_OFFSETS[platform]) % 175) + 1:03d}", True
    # No published formula for this platform: a satellite passes over the same track at
    # the same local time, so (platform, direction, time of day) identifies it well enough.
    when = acquisition_time(product)
    prefix = f"approx track {platform} {orbit_direction(product)[:4]}"
    if when is None:
        return f"{prefix} ??:??", False
    minutes = int(round((when.hour * 60 + when.minute + when.second / 60) / 5) * 5) % 1440
    return f"{prefix} {minutes // 60:02d}:{minutes % 60:02d}", False


def bbox_coverage(product, bbox: list[float]) -> float:
    area = box(*bbox)
    try:
        return shape(product.geometry).intersection(area).area / area.area
    except Exception:  # malformed or missing footprint
        return 0.0


def best_pairs(products: list, event: date, bbox: list[float]) -> list[dict]:
    tracks: dict[str, dict] = {}
    for p in products:
        when = acquisition_time(p)
        if when is None:
            log.warning("Skipping %s: no acquisition time", p.name)
            continue
        key, exact = track_key(p)
        entry = tracks.setdefault(key, {"exact": exact, "pre": [], "post": []})
        # An acquisition on the event day itself counts as "post": it may already show it.
        entry["pre" if when.date() < event else "post"].append((when, p))

    pairs = []
    for key, entry in tracks.items():
        if not entry["pre"] or not entry["post"]:
            continue
        # Latest pre / earliest post; consecutive slices of one pass share a date, so
        # prefer the slice that covers more of the area of interest.
        pre_t, pre = max(entry["pre"], key=lambda t: (t[0].date(), bbox_coverage(t[1], bbox)))
        post_t, post = min(entry["post"], key=lambda t: (t[0].date(), -bbox_coverage(t[1], bbox)))
        pairs.append(
            {
                "track": key,
                "exact_track": entry["exact"],
                "direction": orbit_direction(pre),
                "pre": pre,
                "post": post,
                "pre_date": pre_t.date().isoformat(),
                "post_date": post_t.date().isoformat(),
                "days_apart": (post_t.date() - pre_t.date()).days,
                # A pre/post mismatch (e.g. VV+VH vs VV) limits which channels can be
                # compared, so "pre|post" is shown instead of hiding it.
                "polarisation": "|".join(dict.fromkeys([polarisation(pre), polarisation(post)])),
                "coverage": min(bbox_coverage(pre, bbox), bbox_coverage(post, bbox)),
            }
        )
    pairs.sort(key=lambda r: (r["days_apart"], -r["coverage"]))
    return pairs


def write_csv(pairs: list[dict], path: Path) -> None:
    cols = ["track", "exact_track", "direction", "pre_date", "post_date", "days_apart"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(cols + ["polarisation", "bbox_coverage", "pre_name", "post_name"])
        for r in pairs:
            writer.writerow(
                [r[c] for c in cols]
                + [r["polarisation"], f"{r['coverage']:.2f}", r["pre"].name, r["post"].name]
            )


def write_geojson(pairs: list[dict], path: Path) -> None:
    features = []
    for r in pairs:
        for role in ("pre", "post"):
            product = r[role]
            props = {"track": r["track"], "role": role, "name": product.name}
            props.update({"direction": r["direction"], "date": r[f"{role}_date"]})
            geometry = product.geometry or None  # GeoJSON wants null, not {}, when missing
            features.append({"type": "Feature", "geometry": geometry, "properties": props})
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, indent=2), encoding="utf-8")


def print_table(pairs: list[dict]) -> None:
    print(f"{'track':<28} {'dir':<11} {'pre':<10} {'post':<10} {'days':>4}  pol    names")
    for r in pairs:
        print(
            f"{r['track']:<28} {r['direction']:<11} {r['pre_date']} {r['post_date']} "
            f"{r['days_apart']:>4}  {r['polarisation']:<6} {r['pre'].name}"
        )
        print(f"{'':<76}{r['post'].name}")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bbox", default="11.6,44.1,12.3,44.5", help="min_lon,min_lat,...")
    parser.add_argument("--event-date", default="2023-05-17", help="YYYY-MM-DD")
    parser.add_argument("--window-days", type=int, default=24, help="days before and after")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--direction",
        choices=["ascending", "descending"],
        help="keep one orbit direction (products without sat:orbit_state are dropped)",
    )
    parser.add_argument(
        "--server-filter",
        action="store_true",
        help="also send --direction to the catalogue as a CQL2 filter (unverified)",
    )
    parser.add_argument("--download", action="store_true", help="download the best pair")
    parser.add_argument("--output", default="./output/s1_pre_post_pairs")
    args = parser.parse_args(argv)
    try:
        args.bbox = [float(v) for v in args.bbox.split(",")]
        args.event_date = date.fromisoformat(args.event_date)
    except ValueError as exc:
        parser.error(f"bad --bbox or --event-date: {exc}")
    if len(args.bbox) != 4 or args.bbox[0] >= args.bbox[2] or args.bbox[1] >= args.bbox[3]:
        parser.error("--bbox must be min_lon,min_lat,max_lon,max_lat")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        args = parse_args(argv)
    except SystemExit as exc:  # argparse error or --help
        return int(exc.code or 0)
    bbox, event = args.bbox, args.event_date
    if args.window_days < 1:
        print("--window-days must be at least 1", file=sys.stderr)
        return 2
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    stac_kwargs = {}
    if args.server_filter and not args.direction:
        log.warning("--server-filter has no effect without --direction")
    if args.server_filter and args.direction:
        # STAC API "filter" extension, passed through search(**kwargs) untouched. Whether
        # the Sentinel Hub catalogue accepts exactly this CQL2-JSON form for
        # sat:orbit_state is unverified, so the client-side filter below always runs too.
        stac_kwargs = {
            "filter-lang": "cql2-json",
            "filter": {"op": "=", "args": [{"property": "sat:orbit_state"}, args.direction]},
        }

    try:
        client = CDSEClient(output_dir=str(out))
        start = (event - timedelta(days=args.window_days)).isoformat()
        end = (event + timedelta(days=args.window_days)).isoformat()
        log.info("Searching sentinel-1-grd %s..%s over %s", start, end, bbox)
        # Radar has no cloud cover; "any" because S1 swaths are ~250 km wide and the
        # bbox centre may sit near a slice edge.
        products = client.search(
            bbox=bbox,
            start_date=start,
            end_date=end,
            collection="sentinel-1-grd",
            limit=args.limit,
            coverage="any",
            **stac_kwargs,
        )
        log.info("Found %d GRD products", len(products))
        if len(products) >= args.limit:
            # The page may have been cut before the late (post-event) acquisitions.
            log.warning("Hit --limit %d; results may be truncated, raise it", args.limit)
        if args.direction:
            products = [p for p in products if orbit_direction(p) == args.direction]
            log.info("%d products after %s filter", len(products), args.direction)
        if not products:
            print(f"No Sentinel-1 GRD products found {start}..{end}.", file=sys.stderr)
            return 1

        pairs = best_pairs(products, event, bbox)
        if not pairs:
            print(
                "No track has acquisitions both before and after the event; "
                "try a larger --window-days.",
                file=sys.stderr,
            )
            return 1

        print_table(pairs)
        write_csv(pairs, out / "pairs.csv")
        write_geojson(pairs, out / "pairs.geojson")

        downloaded = []
        if args.download:
            best = pairs[0]
            log.info(
                "Downloading best pair on %s (%d days apart)", best["track"], best["days_apart"]
            )
            for role in ("pre", "post"):
                downloaded.append(
                    client.download_with_checksum(best[role], output_dir=str(out / "downloads"))
                )
    except CDSEError as exc:
        print(f"CDSE error: {exc}", file=sys.stderr)
        return 1

    print(f"\n{len(pairs)} same-track pair(s) written to {out / 'pairs.csv'}")
    print(f"Footprints written to {out / 'pairs.geojson'}")
    for path in downloaded:
        print(f"Downloaded {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
