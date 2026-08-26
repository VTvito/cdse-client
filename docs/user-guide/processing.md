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

## NDVI

```python
from cdse.processing import calculate_ndvi

ndvi_path = calculate_ndvi(nir_path="B08.tif", red_path="B04.tif", output_path="ndvi.tif")
```

!!! note

    On some Windows/Python combinations, `rasterio` wheels may be unavailable. If you hit install issues, try Python 3.11/3.12 or conda-forge.
