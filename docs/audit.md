# Code audit

A record of the defects found by screening `src/cdse`, what was fixed, what is still open, and
why each fix was done the way it was. It is not user documentation — it exists so that the
state of the code is legible without reading the whole git history.

- **Screening**: 23 August 2026, against `5acb0db`
- **Coverage**: all 13 modules of `src/cdse`. The screening is complete.
- **Method**: `[P]` = reproduced by running the code · `[L]` = read from the source, not yet run
- **Fixes**: 15 of 29 closed, each with a regression test
- **Tests**: 102 → 188 passing with the optional extras installed; 136 in CI, which
  installs only `.[dev]` (see the note on skipped tests at the end)

## Status

| # | Sev | Module | Defect | State |
|---|-----|--------|--------|-------|
| 01 | 🔴 | downloader.py | Truncated downloads reported as successful, then never re-fetched `[P]` | ✅ **fixed** |
| 02 | 🔴 | catalog.py | `limit` applied by the server before the local filters `[P]` | ✅ **fixed** |
| 03 | 🔴 | async_client.py | Partial files kept forever, no cleanup `[L]` | ✅ **fixed** |
| 04 | 🟠 | client.py | The catalog never refreshes its token, searches die after ~10 min `[P]` | ✅ **fixed** |
| 05 | 🟠 | async_client.py | Token never refreshed during a batch `[L]` | ✅ **fixed** |
| 06 | 🟠 | downloader.py | A single `requests.Session` shared across threads `[L]` | open |
| 07 | 🟠 | cli.py | Exit code 0 even when nothing is downloaded `[P]` | ✅ **fixed** |
| 08 | 🟡 | catalog.py | Only the first polygon of a MultiPolygon is evaluated `[L]` | open |
| 09 | 🟡 | async_client.py | Async and sync return different results (`s3://` guard, center-point filter) `[L]` | ✅ **fixed** |
| 10 | 🟡 | downloader.py | `max_retries=0` raises `UnboundLocalError` `[P]` | ✅ **fixed** |
| 11 | 🟡 | cli.py | `ValidationError` uncaught, escapes as a traceback `[P]` | ✅ **fixed** |
| 12 | 🟡 | downloader.py | `except Exception: return None` swallows every URL-resolution error `[L]` | ✅ **fixed** |
| 13 | ⚪ | downloader.py | Pointless sleep after the final retry attempt `[P]` | ✅ **fixed** |
| 14 | ⚪ | downloader.py | Streamed responses never closed between retries `[P]` | ✅ **fixed** |
| 15 | 🔴 | processing.py | L1C via ZIP: no band ever extracted `[P]` | ✅ **fixed** |
| 16 | 🔴 | processing.py | Missing bands: bare `KeyError`, or a silently shorter stack `[P]` | ✅ **fixed** |
| 17 | 🟠 | processing.py | `crop_to_bbox` outside the tile: raw rasterio `ValueError` `[P]` | open |
| 18 | 🟠 | processing.py | `crop_to_bbox` on a raster with no CRS: `AttributeError` `[P]` | open |
| 19 | 🟡 | processing.py | The ZIP extractor loads each whole band into RAM `[P]` | open |
| 20 | ⚪ | processing.py | `calculate_ndvi` emits a numpy RuntimeWarning `[P]` | open |
| 21 | 🟠 | product.py | STAC results carry no `size`: every search reports 0.00 GB `[P]` | open |
| 22 | 🟡 | converters.py | `to_dataframe([])` returns a 0×0 frame with no columns `[P]` | open |
| 23 | 🟡 | converters.py | `to_geojson` emits `bbox: []` and `geometry: {}`, invalid GeoJSON `[P]` | open |
| 24 | 🟡 | geocoding.py | `get_city_bbox` returns a tuple that `search()` rejects `[P]` | open |
| 25 | 🟡 | geocoding.py | `search_by_city` docstring incompatible with `use_predefined=True` `[P]` | open |
| 26 | 🟡 | geocoding.py | Nominatim: retries with no pause, and a shared user agent `[P]` | open |
| 27 | ⚪ | geocoding.py | Near the poles the buffer produces an absurd bbox `[P]` | open |
| 28 | ⚪ | geometry.py | `geojson_to_wkt` on empty coordinates emits `POLYGON ()` `[P]` | open |
| 29 | ⚪ | processing.py | `crop_to_bbox` discarded band descriptions `[P]` | ✅ **fixed** |

---

## Detail

### 🔴 01 — Truncated downloads reported as successful `[P]` — ✅ FIXED

`downloader.py:186` through `:216`. No comparison between bytes written and `content-length`.
If the connection closes cleanly mid-stream, `iter_content` finishes without an exception and
the partial file is taken as good. Worse: `skip_existing=True` is the default, so the corrupt
ZIP is never replaced.

```
content-length advertised : 1,048,576 bytes
bytes actually written    : 100 bytes
download() raised         : No -> returned S2A_TEST.zip
second download() HTTP calls: 0  (0 = corrupt file kept)
```

`verify_checksum()` already existed in the module, but `download()` never called it.

**Fix**: after the loop, if `total_size > 0 and downloaded != total_size`, unlink and raise
`DownloadError`.

### 🔴 02 — `limit` applied before the filters `[P]` — ✅ FIXED

`catalog.py:92` (query) and `:120` (`filtered[:limit]`); identical in `async_client.py:168,
:191`. The cloud-cover and center-point filters run client-side on a page the server has
already truncated. The STAC response's `next` link is ignored: no pagination at all.

```
user asked for      : limit=5, cloud_cover_max=20
limit sent to server: 5
products delivered  : 1
```

This hits every search with a cloud filter — which is the README's headline example.

**Fix**: either move the cloud filter into the STAC query, or paginate until `limit` is
satisfied. A design choice, not a one-liner. Pagination was chosen; see
[Decisions](#fixes).

### 🔴 03 — Async: partial files kept forever `[L]` — ✅ FIXED

`async_client.py:227, :239-266`. No `try/except` (the sync path at least calls `unlink()`).
The partial file stays on disk, `download_all:294` only logs a warning, and on the next run
`:227 if output_path.exists(): return output_path` hands back the corrupt file. No recovery
path exists.

### 🟠 04 — The catalog never refreshes its token `[P]` — ✅ FIXED

`client.py:73` captures the `OAuth2Session` once and passes it to `Catalog`, which keeps it
forever. No `auto_refresh_url` is configured anywhere.

```
oauthlib.oauth2.rfc6749.errors.TokenExpiredError: (token_expired)
```

Wrapped in `CatalogError` by `catalog.py:128`, so it is not a crash — but it does not recover
either: it needs `refresh_auth()`, which no example documents. Scenario: `search()`, then a
20 GB `download()`, then `search()` again, which fails. This is the same problem 0.4.0 solved
for the downloader with `_BearerSession`.

### 🟠 05 — Async: token never refreshed during a batch `[L]` — ✅ FIXED

`async_client.py:219` calls `_ensure_session()` before `:239 async with self._semaphore`. In
`download_all` every coroutine starts together and calls `_ensure_session()` immediately, then
queues on the semaphore. From that point on nobody refreshes the token again. With
`max_concurrent=4` and gigabyte products, any batch running past ~10 minutes ends in 401.
The 0.4.0 CHANGELOG promises the opposite.

### 🟠 06 — Session shared across threads `[L]`

`downloader._download_parallel` (4 workers by default) hands the same session object to all of
them. `requests.Session` is not thread-safe. On top of that, `auth.py:32-35` does
check-then-refresh with no lock, so several threads can enter `_authenticate()` together and
fetch tokens concurrently against an endpoint that answers 429.

### 🟠 07 — CLI: exit 0 when nothing is downloaded `[P]` — ✅ FIXED

`cli.py:cmd_search` ends with an unconditional `return 0`. `download_all` returns only the
successful paths, so 10 failures out of 10 print `Downloaded 0 files.` and exit 0. In CI or a
scheduled script, total failure passes for success.

### 🟡 08 — MultiPolygon: only the first polygon `[L]`

`catalog.py:232`, `coords = coords[0] if coords else []`. Products crossing the antimeridian
(polar Sentinel-1, -3, -5P) are MultiPolygons: the second half is never evaluated and the
product is dropped by the center-point filter. The `except (IndexError, TypeError): return
True` fallback masks every malformed geometry. Combined with 02, the result set shrinks twice.

### 🟡 09 — Async/sync divergence `[L]` — ✅ FIXED

- `async_client.py:309` returns `product.download_url` without the `s3://` guard the sync path
  has explicitly (`downloader.py:377-381`). An `s3://` asset makes the async path fail on an
  unsupported URL scheme.
- The async `search` does not apply the sync path's center-point filter, so the two return
  different result sets.

### 🟡 10 — `max_retries=0` raises `UnboundLocalError` `[P]` — ✅ FIXED

`downloader.py:129-133`. If the loop never runs, `response` is never assigned and
`last_exception` stays `None`. `max_retries` is a public, documented parameter.

```
UnboundLocalError: cannot access local variable 'response' where it is not associated with a value
```

### 🟡 11 — CLI: `ValidationError` escapes as a traceback `[P]` — ✅ FIXED

`cli.py:main` catches `AuthenticationError`, `CatalogError`, `DownloadError` and
`KeyboardInterrupt`. `ValidationError` is a sibling under `CDSEError`, not a subtype of any of
those, so it is not caught. Side note: validation happens *after* authentication (the `catalog`
property triggers it), so an invalid bbox still costs a network round-trip.

### 🟡 12 — URL-resolution errors swallowed `[L]` — ✅ FIXED

`downloader.py:398`, `except Exception: return None`. Failed auth, a down network and malformed
JSON all become the same `"Could not determine download URL for product"`. Diagnosis is
impossible.

### ⚪ 13 — Pointless sleep after the final retry `[P]` — ✅ FIXED

`downloader.py:109`. Three attempts all returning 429 sleep 7s (1+2+4); the last 4 seconds
precede nothing but the exit from the loop.

### ⚪ 14 — Streamed responses never closed between retries `[P]` — ✅ FIXED

`downloader._request_with_retry`: `response.close()` called 0 times across 3 retried requests.
With `stream=True` those are connections left open.

---

### 🔴 15 — L1C via ZIP: no band ever extracted `[P]` — ✅ FIXED

`_extract_bands_from_zip` filtered entry names with `res_pattern = f"R{resolution}m"`.
**Sentinel-2 L1C products have no resolution folders** `R10m/R20m/R60m`: the JP2s sit directly
in `IMG_DATA/`. The pattern never matched and the function returned `{}`.

The *folder* extractor handled this explicitly, comment and all
(`res_folder = img_data  # L1C doesn't have resolution subfolders`). The ZIP one did not — and
the ZIP one is what matters: CDSE delivers ZIPs, and `sentinel-2-l1c` is one of the six
supported collections.

```
L2A, bands B04/B03/B02 @10m -> ['B02', 'B03', 'B04']
L1C, bands B04/B03/B02 @10m -> []          <-- L1C has no R10m folder

crop_and_stack(l1c_zip, bbox)
-> ValidationError: No bands found in L1C.zip
```

The error was not silent, but it was misleading: it said there were no bands when in fact
every band was there.

**Fix applied**: `_extract_bands_from_zip` checks once whether the archive really contains an
`R{res}m` folder; when it does not (L1C) the resolution filter is not applied. This is the
same logic as the folder branch (`if not res_folder.exists(): res_folder = img_data`), and
deliberately *not* a per-band fallback: asking for B11 at 10m on an L2A product still finds
nothing, rather than quietly handing back the 20m file. A test pins that boundary.

### 🔴 16 — Missing bands: bare `KeyError`, or a silently shorter stack `[P]` — ✅ FIXED

`extract_bands_from_safe` returned only the bands it found, saying nothing about the rest.
Two outcomes followed, both wrong:

```
stack_bands(found, out, band_order=["B04","B03","B02"])   # B02 not found
-> KeyError: 'B02'                                         # bare exception, no context

stack_bands(found, out)                                    # no band_order
-> no error; 3 bands requested, output has 2               # silent loss
```

The trigger lives inside the module itself: `BAND_COMBINATIONS` mixes resolutions, while
`crop_and_stack` defaults to `resolution=10`.

```
BAND_COMBINATIONS['agriculture'] = ['B11', 'B08', 'B02']   # B11 is 20m-only
crop_and_stack(zip, bbox, bands=BAND_COMBINATIONS['agriculture'], resolution=10)
-> KeyError: 'B11'
```

The same holds for `vegetation` and `all_20m`. In other words: the combinations the module
advertises failed at the module's own default resolution.

**Fix applied**: validate against `SENTINEL2_BANDS` *before* opening the product. Unknown band
names, unsupported resolutions and bands coarser than the requested resolution are refused up
front, with a message saying which resolution to ask for instead. The information was already
in the table; nothing had been reading it.

The band/resolution check applies to **L2A only**: it is the only product level shipping the
resampled `R10m`/`R20m`/`R60m` copies, hence the only one where `resolution` selects anything.
On L1C every band sits at its native resolution (see 15) and the argument selects nothing, so
validation stays lenient there — as it does whenever the product level cannot be read from the
filename.

Whatever passes validation is still re-checked after extraction: a band the product does not
contain ends in a `ValidationError` that names it, rather than going missing from the returned
dictionary. `stack_bands` does the same for `band_order`, and both argument checks run
**before** the optional rasterio import: a caller who got the band list wrong should be told
that, not that rasterio is missing.

The comment in `BAND_COMBINATIONS` now marks which three combinations want `resolution=20`,
and the [processing guide](user-guide/processing.md) explains it.

**Follow-up, found by smoke-testing the fix before release.** The first version of this
validation modelled availability as `native_resolution <= requested`, which is wrong in both
directions. The real L2A layout is not monotonic:

| Folder | Bands |
|---|---|
| `R10m` | B02, B03, B04, B08 |
| `R20m` | B01, B02, B03, B04, B05, B06, B07, B8A, B11, B12 |
| `R60m` | the 20m set, plus B09 |

B08 has no 20m copy — B8A is its counterpart — while B01 and B09 are resampled *up* into the
coarser folders, and B10 is dropped from L2A entirely. Under the old rule, B01 at 20m was
falsely rejected, and B08 at 20m was accepted and then failed later with a hint pointing at
`resolution=20`, which is precisely where it does not exist. Availability is now an explicit
set per folder (`L2A_BANDS_BY_RESOLUTION`).

The same check surfaced a defect in the shipped constants: `agriculture` (`B11, B08, B02`) and
`vegetation` (`B08, B11, B04`) paired a band with no 10m copy with a band with no 20m copy, so
neither could be satisfied at any resolution. Both now use B8A.

### ⚪ 29 — `crop_to_bbox` discarded band descriptions `[P]` — ✅ FIXED

`stack_bands` calls `set_band_description` for every band, and `crop_to_bbox` then rebuilt the
output from `src.meta`, which does not carry descriptions. The end product of `crop_and_stack`
therefore had no band names at all, and nothing said which of the three bands was red. Found
by the same smoke test; the descriptions are now copied across, following a band subset when
`bands=` is given.

### 🟠 17 — `crop_to_bbox` outside the tile: raw `ValueError` `[P]`

```
crop_to_bbox(tif, [0.0, 0.0, 0.1, 0.1])
-> ValueError: Input shapes do not overlap raster.
```

This comes straight from `rasterio.mask`, unwrapped. Sentinel-2 tiles are ~110 km, so passing
a bbox from a different area is an ordinary user error, not an edge case.

### 🟠 18 — `crop_to_bbox` on a raster with no CRS: `AttributeError` `[P]`

```
-> AttributeError: 'NoneType' object has no attribute 'to_epsg'
```

`src.crs.to_epsg()` without checking that `src.crs` exists.

### 🟡 19 — The ZIP extractor loads each whole band into RAM `[P]`

`dst.write(src.read())` in `_extract_bands_from_zip`. A 10 m JP2 weighs 100-150 MB, so four
bands are a half-gigabyte peak. `shutil.copyfileobj` does the same thing in constant memory.

### ⚪ 20 — `calculate_ndvi` emits a numpy RuntimeWarning `[P]`

```
warnings raised: ['invalid value encountered in divide']
```

`np.where(denominator > 0, (nir - red) / denominator, 0)` evaluates **both** branches, so the
division by zero happens regardless and the NaNs are discarded afterwards. The result is
correct (verified: all finite), but every call dirties the output. Fixed by
`np.divide(..., out=..., where=denominator > 0)`.

### Checked and found clean

- `create_rgb_preview` with too few bands already raises a clear, typed error:
  `ValidationError: Band 2 not found. File has 1 bands.`
- `create_rgb_preview` on a zero-variance image neither blows up nor warns.
- `crop_and_stack` on the happy path (all bands present at the requested resolution) works.
- `reproject` is correct. One non-defect note: `Resampling.bilinear` is hard-coded, so it is
  not suitable for categorical rasters such as SCL.

---

### 🟠 21 — STAC results carry no `size`: every search reports 0.00 GB `[P]`

`Product.size` reads `properties["size"]` or `properties["content-length"]`. Sentinel Hub's
STAC response **contains neither**: only the OData branch populates `size`, from
`ContentLength` (`catalog._odata_to_product`).

```
STAC search result:  size = None   size_mb = None
products_size(5 Sentinel-2 L2A scenes) = 0.00 GB
(one L2A scene weighs 0.6-1.1 GB)
```

Concrete consequences:

- the CLI prints `Found N products (total: 0.00 GB)` after **every** search;
- in `to_dataframe` the `size` and `size_mb` columns are all `None`;
- `to_geojson` writes `"size": null` into every footprint.

**Fix**: the size is not in the STAC response, so it has to come from OData (one lookup per
product, expensive) or the CLI must stop printing a total it does not know. A choice, not a
one-liner.

### 🟡 22 — `to_dataframe([])` returns a 0×0 frame with no columns `[P]`

```
to_dataframe([]) -> shape=(0, 0)  columns=[]  index.name=None
df.sort_values("cloud_cover") -> KeyError: 'cloud_cover'
```

`set_index("id")` is skipped when the frame is empty, so not even the documented index comes
back. The example in the function's own docstring (`df.sort_values(...)`) fails.
`to_geodataframe` handles the empty case correctly, with columns and a CRS: the two siblings
behave differently.

### 🟡 23 — `to_geojson` produces invalid GeoJSON `[P]`

For products coming from OData, `bbox` is always `[]` and `geometry` can be `{}`:

```
feature bbox     : []    <-- the standard wants 4 or 6 numbers, or the field absent
feature geometry : {}    <-- should be null
```

This affects `cdse search -f footprints.geojson` and `client.to_geojson(...)`. Some readers
(QGIS, geopandas) reject or misread these fields.

### 🟡 24 — `get_city_bbox` returns a tuple that `search()` rejects `[P]`

```
get_city_bbox("Paris, France") -> tuple (2.144638, 48.714865, 2.555362, 48.985135)
catalog.search(bbox=<tuple>)   -> ValidationError: bbox must be a list of 4 values
```

`search_by_city` works because internally it does `list(bbox)`, but composing the two public
functions directly does not. No example in the current documentation does this, so it is a
latent inconsistency rather than a broken example.

**Fix**: accept any sequence in `_validate_bbox`, or return a list.

### 🟡 25 — `search_by_city` docstring incompatible with `use_predefined=True` `[P]`

The docstring documents `city_name` as `"Milano, Italia"`, `"Paris, France"`. But with
`use_predefined=True` the lookup is an exact-key match:

```
get_predefined_bbox('milano')          -> (9.04, 45.386, 9.278, 45.536)
get_predefined_bbox('Milano, Italia')  -> None
get_predefined_bbox('Paris, France')   -> None
```

The documentation site correctly uses `"milano"` for the offline mode, so the damage is
confined to the docstrings — which nonetheless contradict each other inside the same function.

**Fix**: normalise by stripping everything after the comma, or align the docstrings.

### 🟡 26 — Nominatim: retries with no pause, and a shared user agent `[P]`

The retry loop tries 3 times **with no pause at all** between attempts, and the default value
is `user_agent="cdse-client"` for every installation of the library.

Nominatim's usage policy caps requests at 1 per second and requires an identifying, unique
user agent. Violating it gets the user agent blocked — and because it is shared, a single
aggressive user can get the function blocked **for everyone**.

### ⚪ 27 — Near the poles the buffer produces an absurd bbox `[P]`

`lon_buffer = buffer_km / (111.0 * cos(radians(lat)))`:

```
lat=45.0      lon_buffer =        0.2 degrees
lat=89.0      lon_buffer =        7.7 degrees
lat=89.9999   lon_buffer =   77,426.7 degrees
lat=90.0      lon_buffer = 2.2e15     degrees
```

It is not silent: `_validate_bbox` catches it. But the message talks about longitude being out
of range instead of saying the buffer makes no sense at that latitude.

### ⚪ 28 — `geojson_to_wkt` on empty coordinates emits `POLYGON ()` `[P]`

```
geojson_to_wkt({"type": "Polygon", "coordinates": []}) -> 'POLYGON ()'
```

Invalid WKT, returned without an error.

### Checked and found clean

- `geometry.py` is solid: Polygon and MultiPolygon roundtrips are preserved, and typed errors
  are raised for an empty dict, an unknown type and missing coordinates. `validate_geometry`
  raises instead of returning `False`, but that is **documented behaviour** in the docstring,
  not a defect.
- `search_by_city` converts correctly with `list(bbox)`.
- `Product.from_stac_feature` extracts name, collection, cloud cover and datetime correctly;
  every ISO format tested parses on Python 3.12.
- `to_geodataframe` handles the empty list correctly, with columns and a CRS.
- `products_count` is correct.

### One thing that could not be verified here

`datetime.fromisoformat` before Python 3.11 accepts only 3 or 6 fractional-second digits. A
timestamp such as `...T10:23:51.24Z` would be discarded silently
(`except ValueError: pass` → `datetime = None`) on 3.9 and 3.10, while it parses on 3.12, where
this was tested. It could not be reproduced here: it needs confirming on a real 3.9.

---

## What is still open

Fourteen defects. **None is critical.** The highest are 🟠: 06, 17, 18, 21.

### 🟠 06 — Session shared across threads `[L]`

`downloader._download_parallel` (4 workers by default) hands the same session object to all of
them. `requests.Session` is not thread-safe. `auth.py` does check-then-refresh with no lock, so
several threads can enter `_authenticate()` together and fetch tokens concurrently against an
endpoint that answers 429.

This is the only open defect that touches design: the choice is between a session per thread
(`threading.local`), a lock around the refresh, or both. The async path already solves the same
problem with an `asyncio.Lock` in `_refresh_token` — that pattern can be mirrored.

### 🟡 08 — MultiPolygon: only the first polygon `[L]`

`catalog.py`, in `_point_in_geometry`: `coords = coords[0] if coords else []`. Products crossing
the antimeridian (polar Sentinel-1, -3, -5P) are MultiPolygons: the second half is never
evaluated and the product is dropped by the center-point filter. The
`except (IndexError, TypeError): return True` fallback masks every malformed geometry. A few
lines: iterate over all polygons instead of the first.

The remaining open defects — 17, 18, 19, 20 in `processing.py`, 21 in `product.py`, 22 and 23
in `converters.py`, 24 through 27 in `geocoding.py`, 28 in `geometry.py` — are described in
full in the Detail section above.

---

## Areas of the code still to check

**The screening of `src/cdse` is complete.** All 13 modules have been examined.

- ✅ `processing.py` — 6 defects (15-20). The suspicion was right: it is all in the ZIP/SAFE
  parsing and in the handling of bands that are not found.
- ✅ `product.py` — 1 defect (21), which nonetheless propagates into the CLI and the converters.
- ✅ `converters.py` — 2 defects (22, 23).
- ✅ `geocoding.py` — 4 defects (24-27). None severe, but 26 is operational: it can get the
  shared user agent blocked for everyone.
- ✅ `geometry.py` — 1 negligible defect (28). The most solid module of the set.

What remains unexamined in depth are only the visualisation paths of `processing.py`
(`preview_product`, `quick_preview`, `create_thumbnail`, `compare_previews`,
`_display_in_jupyter`): they depend on matplotlib and IPython, the impact is low, and a defect
there shows up immediately by eye.

---

## Decisions taken

Recorded here because they cannot be inferred from the code or from the git history.

### The 1.0.0 release

| Decision | Choice | Why |
|---|---|---|
| Version number | **1.0.0**, not 0.5.0 | The API had been stable since 0.3.0. Staying in 0.x communicated "not ready" and was one of three abandonment signals |
| `Development Status` | **5 - Production/Stable** | Consistent with 1.0.0. Keeping `4 - Beta` alongside 1.0.0 would have been a contradictory signal |
| A 2.7 MB notebook | **Removed**, not moved or cleaned | It was 92% of the tracked bytes and made the repository classify as Jupyter Notebook, excluding it from `?l=python` topics. The content already existed in `docs/` and `examples/` |
| Git history | **Not rewritten** | Linguist only looks at the current tree. A rewrite would have broken clones for no benefit |
| Positioning | **Lead with the task**, `sentinelsat` second | The package ranked first for "sentinelsat alternative CDSE" but was absent from "download Sentinel-2 python". A dying niche against real demand |
| Version in the code | **Single-sourced** from `cdse.__version__` via `dynamic` | It used to be duplicated across two files kept in sync by hand |

### Fixes

| Decision | Choice | Why |
|---|---|---|
| Defect 02 (`limit` before the filters) | **Option B: pagination** | The center-point filter cannot live server-side, so pagination is needed anyway. Moving the cloud filter into the STAC query stays a possible future optimisation, to be validated against real credentials |
| Page token | **Accept both forms**, `context.next` and a STAC `next` link | Which one the API actually returns could not be verified. Accepting both makes the fix independent of that assumption |
| `catalog.py` helpers | **Made static and shared** with the async path | They did not use `self` and were about to be duplicated |
| Defect 09 | Closed **together with 02** | Aligning the async path already required touching the same function |
| `skip-existing` on PyPI | **Kept**, despite the review flagging it | A version can never be re-uploaded to PyPI: without that flag, any run failing *after* the upload becomes unrepeatable. A deliberate trade-off, documented in the workflow |
| Branch | **`fix/correctness-sync-path`**, not `main` | Fixes get reviewed before entering a release marked Production/Stable |
| Release number for the fixes | **1.1.0**, not 1.0.1 | Defect 16 changes observable behaviour: `extract_bands_from_safe` used to return a short dictionary and now raises `ValidationError`. No signature changes, so it is not major; but 1.0.1 would have told users there was nothing to read when there was |
| Defect 15 (L1C via ZIP) | **Detect the `R{res}m` folder once**, not a per-band fallback | It mirrors the folder branch. A per-band fallback would have quietly returned the 20m file to someone asking for 10m |
| Defect 16 (missing bands) | **Validate against `SENTINEL2_BANDS` before extracting** | The information was already in the table and nobody was reading it. The error now arrives before the archive is opened and says which resolution to ask for, instead of surfacing halfway through stacking |
| Scope of the 16 validation | **Strict on L2A only** | It is the only level with the resampled copies, so the only one where `resolution` selects anything. On L1C, rejecting B11 at 10m would have been a false positive, since the file is there |
| This document | **Published** under `docs/` | It was kept out of the repository while critical defects were open next to a Production/Stable release. With none left, an audit that is visible says the code has been looked at rather than the opposite |

### Still to decide

- **Defect 06** — a session per thread (`threading.local`), a lock around the refresh, or both.
  The async path already solves it with an `asyncio.Lock`; that pattern can be mirrored.
- **Defect 21** — whether to fetch the size via an OData lookup (one request per product,
  expensive) or stop printing a total that is not known.
- **`processing.py` tests in CI** — whether to add rasterio to a test extra (a heavy wheel,
  across six matrix versions) or accept that those paths stay unverified.

---

## Notes

- **All five critical defects are closed** (01, 02, 03, 15, 16). The first three shared the
  worst signature — silent loss with no error raised — and the two in `processing.py` did too,
  in a different form: a missing band that reported to nobody.
- **A slice of the test suite does not run in CI.** `ci.yml` installs only `.[dev]`, so every
  file that `importorskip`s an optional dependency is skipped across all matrix versions:
  `test_processing.py` (rasterio) and `test_async_client.py` (aiohttp) *entirely*, plus a dozen
  scattered tests in `test_converters.py` (pandas, geopandas) and `test_geocoding.py` (geopy).
  That is 18 skips out of 154 collected. It matters because the async tests and the
  `processing.py` tests cover exactly the modules the critical defects came out of. That is why
  the tests for 15 and 16 live in `tests/test_processing_bands.py`, which is plain `zipfile`
  work and runs everywhere.
- **Bandit exits 1 on any finding**, not only on High ones. The `security` job went red over an
  `assert` (B101, severity Low) introduced by the fix for 05. Bandit's output makes this easy to
  misread: it prints a table by severity and a table by confidence, and the "High: 1" line at
  the bottom was *confidence* High, severity Low. Resolved by removing the assert, which
  `python -O` would have stripped anyway.
- Defect 21 has the same character as the silent ones: it breaks nothing, but it makes the CLI
  print a 0.00 GB total after every search, which is simply false.
- **Two existing tests encoded defect 01** (`test_download_success` and `test_download_all`
  declared a `content-length` that did not match the payload). Worth keeping in mind while
  looking at the other modules: a passing test does not prove the behaviour is right.
- Defect 06 is the only one left that needs a design choice. Defect 08 is a few lines.
- To do once real credentials are available: verify pagination (defect 02) against the live
  API. The code accepts both Sentinel Hub's `context.next` and a STAC `next` link, but which
  form the API actually returns could not be confirmed.
