# cdse-client

[![PyPI version](https://badge.fury.io/py/cdse-client.svg)](https://badge.fury.io/py/cdse-client)
[![Python](https://img.shields.io/pypi/pyversions/cdse-client.svg)](https://pypi.org/project/cdse-client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Python client for Copernicus Data Space Ecosystem (CDSE)** — a modern replacement for `sentinelsat`.

Requires Python >= 3.9.

## Installation

```bash
pip install cdse-client              # Core
pip install cdse-client[geo]         # + shapely, geopandas, geopy
pip install cdse-client[dataframe]   # + pandas
pip install cdse-client[processing]  # + rasterio, numpy, pillow, matplotlib, shapely
pip install cdse-client[async]       # + aiohttp, aiofiles
pip install cdse-client[all]         # Everything
```

## Setup

1. Register at [Copernicus Data Space](https://dataspace.copernicus.eu/)
2. Create OAuth2 credentials in [Account Settings](https://dataspace.copernicus.eu/profile)
3. Configure credentials using **one** of the methods below:

### Option A: Environment variables (recommended for production)

**macOS/Linux (bash/zsh)**
```bash
export CDSE_CLIENT_ID="your-client-id"
export CDSE_CLIENT_SECRET="your-client-secret"
```

**Windows (PowerShell)**
```powershell
$env:CDSE_CLIENT_ID = "your-client-id"
$env:CDSE_CLIENT_SECRET = "your-client-secret"
```

### Option B: `.env` file (recommended for development)

Copy the example file and fill in your credentials:
```bash
cp .env.example .env
# Edit .env with your credentials
```

The `.env` file format:
```
CDSE_CLIENT_ID=your-client-id
CDSE_CLIENT_SECRET=your-client-secret
```

> **Note**: The `.env` file is automatically ignored by git. Never commit credentials.

## Quick start

```python
from cdse import CDSEClient

client = CDSEClient()  # Uses environment variables

# Search Sentinel-2 products
products = client.search(
    bbox=[9.0, 45.0, 9.5, 45.5],  # Milan area
    start_date="2024-01-01",
    end_date="2024-01-31",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5
)

# Download
for product in products:
    client.download(product)
```

## Search methods

```python
# By bounding box
products = client.search(bbox=[lon_min, lat_min, lon_max, lat_max], ...)

# By geographic point
products = client.search_by_point(lon=9.19, lat=45.46, buffer_km=10, ...)

# By city name (requires [geo])
products = client.search_by_city(city_name="Milano, Italia", ...)

# By product name (OData catalogue)
products = client.search_by_name("S2A_MSIL2A_20240115T102351...", exact=True)

# By UUID (OData catalogue)
product = client.search_by_id("a1b2c3d4-e5f6...")
```

Note: `search()` returns STAC results; product identifiers there are not guaranteed to be OData UUIDs. If you need a UUID, use `search_by_name(..., exact=True)`.

**Collections**: `sentinel-1-grd`, `sentinel-2-l1c`, `sentinel-2-l2a`, `sentinel-3-olci`, `sentinel-3-slstr`, `sentinel-5p-l2`

## Download methods

```python
# Single product
client.download(product, output_dir="./downloads")

# Multiple products (parallel)
client.download_all(products, parallel=True, max_workers=4)

# With checksum verification
client.download_with_checksum(product)

# Quicklook preview only
client.download_quicklook(product)
client.download_all_quicklooks(products)
```

## Data export (sentinelsat compatible)

```python
# DataFrame for sorting/filtering
df = client.to_dataframe(products)
df.sort_values('cloud_cover').to_csv("products.csv")

# GeoJSON footprints
geojson = client.to_geojson(products)

# GeoDataFrame for spatial analysis (requires [geo])
gdf = client.to_geodataframe(products)
gdf.plot()

# Total size
size_gb = client.get_products_size(products)
```

## Geometry utilities

```python
from cdse import read_geojson, geojson_to_wkt, bbox_to_geojson

geojson = read_geojson("area.geojson")
wkt = geojson_to_wkt(geojson)
geojson = bbox_to_geojson([9.0, 45.0, 9.5, 45.5])
```

## Processing

```bash
pip install cdse-client[processing]
```

```python
from cdse.processing import calculate_ndvi, crop_and_stack, preview_product

# Extract bands, crop to AOI, stack into GeoTIFF
result = crop_and_stack(
    safe_path="S2A_MSIL2A_20240115.zip",
    bbox=[9.15, 45.45, 9.25, 45.55],
    bands=["B04", "B03", "B02", "B08"],
    resolution=10
)

# Calculate NDVI
ndvi = calculate_ndvi(nir_path="B08.tif", red_path="B04.tif")

# Preview in Jupyter
preview_product(safe_path="...", bbox=[...], display=True)
```

## Async support

```bash
pip install cdse-client[async]
```

```python
import asyncio
from cdse import CDSEClientAsync

async def main():
    async with CDSEClientAsync(client_id, client_secret) as client:
        products = await client.search(...)
        paths = await client.download_all(products)

asyncio.run(main())
```

## CLI

```bash
# Search
cdse search --bbox 9.0,45.0,9.5,45.5 -s 2024-01-01 -e 2024-01-31 -c 20 -l 5

# Download by name/UUID
cdse download --name S2A_MSIL2A_20240115T102351...
cdse download --uuid a1b2c3d4-... [--quicklook] [--checksum]

# List collections
cdse collections

# Help
cdse --help
```

## Migration from sentinelsat

| sentinelsat | cdse-client |
|-------------|-------------|
| `SentinelAPI(user, password)` | `CDSEClient(client_id, client_secret)` |
| `api.query(area, date, ...)` | `client.search(bbox, start_date, ...)` |
| `api.download(uuid)` | `client.download(product)` |
| `api.download_all(products)` | `client.download_all(products)` |
| `api.download_quicklook(uuid)` | `client.download_quicklook(product)` |
| `api.to_dataframe(products)` | `client.to_dataframe(products)` |
| `api.to_geojson(products)` | `client.to_geojson(products)` |
| `read_geojson(path)` | `read_geojson(path)` |
| `geojson_to_wkt(geojson)` | `geojson_to_wkt(geojson)` |

## Resources

- [Copernicus Data Space](https://dataspace.copernicus.eu/)
- [CDSE API Documentation](https://documentation.dataspace.copernicus.eu/)

## Documentation (MkDocs)

Build and preview locally:

```bash
pip install -e ".[docs]"
mkdocs serve
```

## Disclaimer

This is an **unofficial** client library and is not affiliated with, endorsed by, or connected to ESA, the European Commission, or the Copernicus Programme.

Copernicus Data Space Ecosystem and Sentinel data are provided by ESA and the European Commission. Users must:

1. Register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/)
2. Comply with the [Terms and Conditions](https://dataspace.copernicus.eu/terms-and-conditions)
3. Respect [API quotas and fair usage policies](https://documentation.dataspace.copernicus.eu/Quotas.html)

Sentinel data is available under a **free, full, and open** data policy for any use, including commercial. See the [Sentinel Data Legal Notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).

## License

MIT License - see [LICENSE](LICENSE)
