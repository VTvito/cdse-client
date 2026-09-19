# Use cases

cdse-client finds, downloads and prepares Sentinel data. The analysis after that is yours.
This page shows five complete workflows, one per persona. Each is a runnable script in
[`examples/`](https://github.com/VTvito/cdse-client/tree/main/examples). Every script runs
with no arguments, writes to `./output/<example>/`, and keeps the downloads in
`./output/<example>/downloads/`, so a second run skips the download.

All five need `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` (see [Getting started](getting-started.md)).

!!! warning "Tested offline only"

    The scripts were run end to end against synthetic products that follow the real product
    layout, not against the live CDSE API. The assumptions this leaves open are listed in
    [Not yet verified against the live API](#not-yet-verified-against-the-live-api).

## Agronomist: NDVI through a growing season

A field is a few hundred pixels inside a 110 km tile, and half the dates of a season are
cloudy over it. The goal is one clean NDVI curve from sowing to harvest, with the cloudy
dates skipped and the reason recorded, instead of averaging clouds in.

**What you get** (in `./output/agri_ndvi_timeseries/`)

- `ndvi_timeseries.csv`: one row per selected date, with the clear fraction over the field,
  NDVI mean, p10 and p90, pixel count, and a `status` column that says why a date was skipped
- `ndvi_timeseries.png`: mean NDVI with the p10-p90 band, and skipped dates as grey ticks
- `downloads/`: the L2A ZIPs

**Run**
([`agri_ndvi_timeseries.py`](https://github.com/VTvito/cdse-client/blob/main/examples/agri_ndvi_timeseries.py))

```bash
pip install "cdse-client[processing]" matplotlib
python examples/agri_ndvi_timeseries.py
# = --geojson examples/data/field_lombardy.geojson --start 2025-04-01 --end 2025-09-30
#   --max-cloud 60 --min-clear 0.7 --every-days 7 --limit 200
```

The script keeps the least cloudy product in each 7-day window. It crops B08 and B04 to the
field, puts the 20 m SCL onto the same 10 m grid, and masks the pixels that SCL does not
classify as clear:

```python
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
```

!!! note "Where the library stops"

    - Every date downloads the full ~1 GB product, even though the field is a few hundred
      pixels. CDSE OData serves whole products. `--every-days 7` bounds this to about 26
      downloads for a 6-month season.
    - The pick in each window uses tile-level cloud cover. The least cloudy tile can still
      have a cloud over the field. The SCL mask catches most of these, but SCL sometimes
      misses thin cirrus and the edges of cloud shadows.
    - Search is by bounding box only. The polygon is applied afterwards, in numpy.
    - Since processing baseline 04.00 (January 2022), L2A DNs carry a -1000 offset, which
      pulls NDVI towards zero. The script removes it, reading the value from
      `MTD_MSIL2A.xml` inside the product and falling back to the `_Nxxxx_` baseline in the
      name when that file is absent.
    - `examples/data/field_lombardy.geojson` is a sample area, not a real parcel.

## Wildfire analyst: burn severity (dNBR)

A few weeks after a fire, civil protection needs a first map of burn severity and the
hectares in each class. The standard measure is the drop in the Normalized Burn Ratio
between a clear scene before the fire and one after it.

**What you get** (in `./output/wildfire_dnbr/`)

- `dnbr.tif`: float32 dNBR (NBR pre minus NBR post), NaN where masked
- `dnbr_severity.tif`: uint8 USGS severity classes (0 masked, 1 unburned to 5 high) with an
  embedded colour table
- `severity.png`: severity map with hectares per class in the legend
- `before_after.png`: true-colour previews of the pre-fire and post-fire scenes
- a hectares-per-class table printed to the console

**Run**
([`wildfire_dnbr.py`](https://github.com/VTvito/cdse-client/blob/main/examples/wildfire_dnbr.py)).
The default is the Montiferru fire in Sardinia, 24 July 2021.

```bash
pip install "cdse-client[processing]"
python examples/wildfire_dnbr.py
# = --bbox 8.45,40.05,8.75,40.25 --event-date 2021-07-24 --window-days 30 --max-cloud 20
```

For each date, NBR is computed from B8A and B12 at 20 m, with the BOA offset removed. The
post-fire rasters are put onto the pre-fire grid, and only pixels clear on both dates count:

```python
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
```

!!! note "Where the library stops"

    - You need to know the event date and a bbox around it already. There is no lookup of
      fire perimeters and no polygon search.
    - Each of the two dates downloads a full ~1 GB L2A product.
    - Scenes are picked by tile-level cloud cover, which may not reflect cloud or smoke over
      the fire. The SCL mask (cloud, shadow, water and snow) catches most of it, but not all.
      The post window starts the day after the event, so a fire that lasted several days may
      still show smoke.
    - `compute_index("nbr")` works on raw DNs and ignores the -1000 offset of baseline 04.00
      and later. With one old and one new product, unburned vegetation would show up as
      burned. The script computes NBR itself, reading the baseline from the product name.
    - The burned area is not converted to polygons. Use `rasterio.features.shapes` on
      `dnbr_severity.tif` if you need them.
    - The Key & Benson / USGS thresholds are generic. Calibrate them locally before any
      official use.

## Emergency analyst: Sentinel-1 pre/post pairs

During a flood the sky is overcast, so optical imagery is useless and radar is the only
option. SAR change detection only works when the before and after images come from the same
relative orbit (track), so the first job is to find those pairs.

**What you get** (in `./output/s1_pre_post_pairs/`)

- `pairs.csv`: one row per track, with the latest pre-event and the earliest post-event GRD,
  the days between them, the polarisation and the bbox coverage
- `pairs.geojson`: the pre and post footprints of each pair
- `downloads/`: with `--download`, the best pair as two ZIPs
- a table of the pairs, sorted by days apart, printed to the console

**Run**
([`s1_pre_post_pairs.py`](https://github.com/VTvito/cdse-client/blob/main/examples/s1_pre_post_pairs.py)).
The default is the May 2023 Emilia-Romagna floods.

```bash
pip install "cdse-client[geo]"
python examples/s1_pre_post_pairs.py
# = --bbox 11.6,44.1,12.3,44.5 --event-date 2023-05-17 --window-days 24 --limit 100
```

Products are grouped by track, then split into before and after the event. Within a track,
the script keeps the latest pre-event slice and the earliest post-event slice, choosing the
slice that covers more of the bbox:

```python
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
```

!!! note "Where the library stops"

    - It only finds and downloads. GRD data must be calibrated, speckle-filtered and
      terrain-corrected before change detection (SNAP, pyroSAR or the Sentinel Hub
      processing API). None of that is done here.
    - Each GRD is about 1 GB, and `--download` fetches two.
    - Search is by bbox only. The relative orbit comes from `sat:relative_orbit` when the
      catalogue provides it. Otherwise it is computed from the absolute orbit in the name,
      which works for S1A and S1B only. Other platforms get an approximate track key, marked
      `exact_track=False`.
    - GRD products usually have no checksum in the STAC metadata, so
      `download_with_checksum` only logs a warning.

## Journalist or planner: a city before and after

A side-by-side image of a city years apart shows new districts, dried-up rivers or burnt
parks better than any description. Optionally, a map of where vegetation (NDVI) or water
(NDWI) changed shows where to look.

**What you get** (in `./output/city_before_after/`)

- `before_<date>.png` / `.tif` and `after_<date>.png` / `.tif`: true-colour preview and
  cropped RGB GeoTIFF for each date
- `before_after.png`: the two views side by side
- with `--index ndvi|ndwi`: `<index>_a.tif`, `<index>_b.tif`, and `<index>_change.tif` / `.png`
  (after minus before, NaN where there is no data or cloud)
- the `cdse download --name ...` command for each picked product

**Run**
([`city_before_after.py`](https://github.com/VTvito/cdse-client/blob/main/examples/city_before_after.py))

```bash
pip install "cdse-client[processing]" matplotlib
python examples/city_before_after.py
# = --city milano --date-a 2019-07-15 --date-b 2025-07-15 --days 20 --max-cloud 15
#   --index none --size 1200
python examples/city_before_after.py --city roma --index ndwi
```

The default dates fall on either side of the 2022 baseline change, so the index is computed
from reflectance after removing each product's own offset, with SCL clouds masked:

```python
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
```

!!! note "Where the library stops"

    - Each date downloads a full ~1 GB L2A product to crop a few km² of it.
    - City boxes are rectangles from a small built-in table. There is no polygon search and
      no administrative boundary.
    - Pixels are 10 m: districts, parks and roads are visible, single buildings are not.
    - The cloud filter uses tile-level cloud cover. The index change masks clouds with SCL,
      but the RGB views do not.
    - Each RGB view is stretched on its own (2nd to 98th percentile). Colours are for the eye,
      not for comparing brightness between dates, and a cloud over more than a few percent
      of the crop darkens the whole view.
    - `compute_index()` ignores the baseline 04.00 offset, so the script computes the index
      itself, reading the offset from `MTD_MSIL2A.xml`.
    - Only the tile containing the bbox centre is searched, so a city that straddles two
      tiles may come out partly empty.

## Air-quality analyst: a month of Sentinel-5P NO2

An environmental agency wants a monthly map of tropospheric NO2 over a region, to compare
with ground stations or earlier months. Sentinel-5P passes over a region once or twice a day,
and each orbit is a netCDF swath that has to be quality-filtered and averaged onto a regular
grid.

**What you get** (in `./output/s5p_no2_monthly/`)

- `no2_monthly.tif`: monthly mean tropospheric NO2 in µmol/m², EPSG:4326, float32, NaN
  where no valid observation fell in a cell
- `no2_monthly.png`: the same grid as a map, with a colour bar
- `no2_counts.tif`: the number of valid observations per cell
- `downloads/`: the NO2 products

**Run**
([`s5p_no2_monthly.py`](https://github.com/VTvito/cdse-client/blob/main/examples/s5p_no2_monthly.py)).
The default is the Po Valley in January 2025.

```bash
pip install "cdse-client[processing]" xarray netCDF4
python examples/s5p_no2_monthly.py
# = --bbox 7.5,44.4,12.6,46.2 --month 2025-01 --limit 500 --qa 0.75 --grid 0.05
```

The search asks for NO2 products only and keeps one OFFL product per orbit. Each pixel with
`qa_value > 0.75` inside the bbox is then added to the grid cell its centre falls in:

```python
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
```

!!! note "Where the library stops"

    - cdse-client does not read netCDF. The script opens the files with xarray.
    - Every OFFL product is a full orbit of several hundred MB, downloaded whole although
      only a small part covers the bbox. A month over the Po Valley is roughly 30 to 50
      orbits, which means tens of GB. There is no cap on the number of products.
    - Each pixel counts in the cell its centre falls in, without weighting by footprint
      area. For rigorous L3 products use [harp](https://github.com/stcorp/harp) or satpy.
    - The catalogue mixes every S5P product type (NO2, CO, O3, CH4 and so on). The script
      sends a CQL2 filter on `s5p:type`. If the catalogue rejects the filter, the script
      falls back to an unfiltered search (up to 1000 results) and filters by name.
    - S5P downloads rely on the recent fix that appends `.nc` to the OData product name.
      This example is the acceptance test for that fix.

## Not yet verified against the live API

The scripts were run offline with synthetic products and a fake client. The assumptions
below were not checked against the live CDSE services:

**Search (STAC catalogue)**

- The catalogue's default result order, and whether the default limits are enough (200 for
  a Sentinel-2 season, 100 for Sentinel-1, 500 filtered or 1000 unfiltered for a month of
  Sentinel-5P). Each script logs a warning when a search hits its limit.
- Sentinel-2 L2A items carry `datetime` and `eo:cloud_cover`, including 2019 products over
  Milano. Items with no datetime are dropped or sorted last.
- The date range includes the whole end day. The client sends `{end}T23:59:59Z`, but the
  service was not tested.
- The tile containing the bbox centre covers the whole area of interest (Lodi field and
  Milano, assumed T32TNR; Montiferru, assumed T32TMK). Scenes under the cloud threshold
  exist in each default window.
- A search may return both the original and the reprocessed copy of an acquisition (for
  example N0301 and N0500). The scripts accept either one, and choose between them only by
  cloud cover and date.
- For `sentinel-1-grd`, the catalogue returns `sat:relative_orbit`, `sat:orbit_state` and
  `sar:polarizations` (or `s1:polarization`). Without `sat:orbit_state`, `--direction`
  drops every product.
- The collection may also contain EW/GRDM products, which are not filtered out.
- The catalogue accepts a CQL2-JSON `filter` body, with `filter-lang: cql2-json`, on
  `sat:orbit_state` and on `s5p:type`.
- On Python 3.9 and 3.10, a STAC datetime whose fractional seconds do not have 3 or 6
  digits does not parse. The Sentinel-1 script then falls back to the time in the name.

**Product names**

- Real L2A ZIPs contain `MTD_MSIL2A.xml` with `BOA_ADD_OFFSET`, including the reprocessed
  N0500 copies of older dates. That file is what the three Sentinel-2 scripts read. Where it
  is missing they fall back on the baseline in the STAC id (`_Nxxxx_`), assuming the offset
  is exactly -1000 from N0400 onwards.
- Sentinel-1 STAC ids follow the SAFE naming (start time in field 5, absolute orbit in
  field 7), and the id plus `.SAFE` is the exact OData name.
- Sentinel-5P STAC ids are the standard file names
  (`S5P_<OFFL|NRTI|RPRO>_L2__NO2____<start>_<end>_<orbit>_...`) without `.nc`.
- `cdse download --name <STAC id>` finds the product (possibly through the prefix
  fallback) and saves it under the same file name the scripts expect.

**Downloads and product contents**

- Each download is saved as `<output_dir>/<product.name>.zip`.
- CDSE OData ZIPs of L2A products use the
  `<name>.SAFE/GRANULE/*/IMG_DATA/R10m|R20m/*_<band>_<res>.jp2` layout. Real JPEG2000
  decoding speed was not tested, because the synthetic products used GeoTIFF data under
  `.jp2` names.
- SCL class codes behave as documented, and DN 0 is no-data in both the bands and SCL.
- Sentinel-1 GRD products have no checksum in STAC, so `download_with_checksum` cannot
  verify them.
- The OData lookup for Sentinel-5P works with the `.nc` suffix. The payload may be a ZIP or
  the raw netCDF file, and the script handles both.
- Sentinel-5P NO2 files open with xarray (`group="PRODUCT"`, netCDF4 engine) and contain
  `nitrogendioxide_tropospheric_column`, `qa_value`, `latitude` and `longitude`.
- Product sizes and orbit counts per month are estimates.

## Roadmap

Changes that would make these workflows cheaper:

- **Per-band download.** OData `Nodes` can fetch single files from inside a product, so an
  NDVI date would cost two bands and SCL, a few tens of MB, instead of a ~1 GB ZIP.
- **Polygon search.** A STAC `intersects` search would find products for a field or a
  district outline instead of its bounding rectangle.
- **Server-side property filters.** First-class support for CQL2 filters (orbit direction,
  relative orbit, product type) would replace the client-side filtering and the large
  search limits these scripts need.
- **Offset-aware indices.** `compute_index()` does not remove the BOA offset of baseline
  04.00 and later. Three of the scripts work around this. A fix in the library would make
  those workarounds unnecessary.
