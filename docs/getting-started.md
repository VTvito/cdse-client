# Getting started

## 1) Install

```bash
pip install cdse-client
```

If you need geocoding/GeoDataFrame exports:

```bash
pip install cdse-client[geo]
```

## 2) Configure credentials

You can pass credentials explicitly, or use environment variables.

=== "macOS/Linux"

    ```bash
    export CDSE_CLIENT_ID="your-client-id"
    export CDSE_CLIENT_SECRET="your-client-secret"
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:CDSE_CLIENT_ID = "your-client-id"
    $env:CDSE_CLIENT_SECRET = "your-client-secret"
    ```

## 3) Create a client

```python
from cdse import CDSEClient

client = CDSEClient()  # reads env vars
```

## 4) Search and download

```python
products = client.search(
    bbox=[9.10, 45.40, 9.28, 45.52],
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5,
)

path = client.download(products[0], output_dir="./downloads")
print(path)
```

## 5) Common pitfalls

### STAC results vs OData UUID

- `search()` uses STAC and returns `Product` objects built from STAC features.
- `search_by_id()` targets the **OData catalogue** and expects a **UUID**.

If you need a UUID, resolve it from the OData catalogue:

```python
odata_product = client.search_by_name(products[0].name, exact=True)
if odata_product:
    by_uuid = client.search_by_id(odata_product.id)
```
