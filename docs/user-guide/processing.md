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

## NDVI

```python
from cdse.processing import calculate_ndvi

ndvi = calculate_ndvi(nir_path="B08.tif", red_path="B04.tif")
```

!!! note

    On some Windows/Python combinations, `rasterio` wheels may be unavailable. If you hit install issues, try Python 3.11/3.12 or conda-forge.
