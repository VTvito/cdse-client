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

    Only B02, B03, B04 and B08 exist at 10m. L2A products do not resample the
    20m bands (B05-B07, B8A, B11, B12) down, so asking for one of them at
    `resolution=10` raises `ValidationError` instead of quietly dropping it.
    The `agriculture`, `vegetation` and `all_20m` entries of `BAND_COMBINATIONS`
    all need `resolution=20`.

    L1C products have no resolution subfolders at all: every band comes at its
    native resolution and the `resolution` argument selects nothing.

## NDVI

```python
from cdse.processing import calculate_ndvi

ndvi_path = calculate_ndvi(nir_path="B08.tif", red_path="B04.tif", output_path="ndvi.tif")
```

!!! note

    On some Windows/Python combinations, `rasterio` wheels may be unavailable. If you hit install issues, try Python 3.11/3.12 or conda-forge.
