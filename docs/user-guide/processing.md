# Processing (optional)

Install:

```bash
pip install cdse-client[processing]
```

## Local RGB preview

`preview_product()` builds a true-color RGB preview (Sentinel-2: B04/B03/B02) from a downloaded product.

```python
from cdse.processing import preview_product

result = preview_product(
    safe_path="S2A_MSIL2A_....zip",
    bbox=[9.10, 45.40, 9.28, 45.52],
    resolution=10,
    display=True,
)

print(result["preview_path"])
```

## Crop and stack

```python
from cdse.processing import crop_and_stack

tiff = crop_and_stack(
    safe_path="S2A_MSIL2A_....zip",
    bbox=[9.10, 45.40, 9.28, 45.52],
    bands=["B04", "B03", "B02", "B08"],
    resolution=10,
)
```

!!! note "Bands and resolution"

    An L2A product ships three resolution folders, and which bands live in each
    is not simply "everything at or above its native resolution":

    | Folder | Bands |
    |---|---|
    | `R10m` | B02, B03, B04, B08 |
    | `R20m` | B01, B02, B03, B04, B05, B06, B07, B8A, B11, B12 |
    | `R60m` | the 20m set, plus B09 |

    Two consequences worth knowing. **B08 exists only at 10m** — B8A is its 20m
    and 60m counterpart, not a resampled B08 — and **B01 and B09 are resampled
    up**, so B01 is available at 20m despite being 60m native. B10 is dropped
    during L2A processing and exists in L1C only.

    Asking for a band the requested folder does not contain raises
    `ValidationError` naming the resolutions where it *is* available, rather
    than quietly dropping it from the result. The `agriculture`, `vegetation`
    and `all_20m` entries of `BAND_COMBINATIONS` need `resolution=20`.

    L1C products have no resolution subfolders at all: every band comes at its
    native resolution and the `resolution` argument selects nothing.

## Indices: NDVI, NDWI, NDMI, NBR

All four are the same formula, `(a - b) / (a + b)`, on a different band pair. `INDEX_BANDS`
lists the pairs; `compute_index()` goes from a product to a cropped index GeoTIFF in one call:

```python
from cdse.processing import compute_index

ndvi = compute_index("S2A_MSIL2A_....zip", "ndvi", bbox=[9.10, 45.40, 9.28, 45.52])
nbr = compute_index("S2A_MSIL2A_....zip", "nbr", bbox=[9.10, 45.40, 9.28, 45.52])
```

| Index | Bands | Resolution | Used for |
|---|---|---|---|
| `ndvi` | B08, B04 | 10 m | vegetation vigour |
| `ndwi` | B03, B08 | 10 m | open water |
| `ndmi` | B8A, B11 | 20 m | vegetation moisture |
| `nbr` | B8A, B12 | 20 m | burn severity (pre minus post = dNBR) |

`compute_index` picks the native resolution of the pair unless you pass `resolution=`. For
bands you already have on disk, `normalized_difference(a, b, out, name="NBR")` does the
arithmetic alone, and `calculate_ndvi(nir, red, out)` is the same thing named NDVI.

## Cloud mask from SCL

The tile-level cloud cover you filter on at search time says nothing about the clouds over
*your* field. L2A products carry a per-pixel scene classification (`SCL`, 20 m) that does:

```python
from cdse.processing import cloud_mask_from_scl, extract_bands_from_safe, scl_clear_fraction

scl = extract_bands_from_safe("S2A_MSIL2A_....zip", ["SCL"], resolution=20)["SCL"]

if scl_clear_fraction(scl) < 0.7:
    print("mostly cloud over the AOI, skip this date")

mask = cloud_mask_from_scl(scl)  # uint8 GeoTIFF: 1 = clear, 0 = cloud/shadow/no-data
```

`SCL_CLOUD_CLASSES` (no-data, cloud shadow, medium and high probability cloud, thin cirrus) is
the default set masked out; pass `classes=` to change it. `SCL_CLASSES` names all twelve.

!!! note "SCL is categorical"

    Never resample it bilinearly: the average of "vegetation" (4) and "cloud" (8) is not a
    class. `stack_bands` uses nearest-neighbour for a band named `SCL` on its own; for other
    tools, or for `reproject`, pass `resampling="nearest"` yourself.

!!! note

    On some Windows/Python combinations, `rasterio` wheels may be unavailable. If you hit install issues, try Python 3.11/3.12 or conda-forge.
