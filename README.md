# cdse-client

[![PyPI version](https://badge.fury.io/py/cdse-client.svg)](https://badge.fury.io/py/cdse-client)
[![Python](https://img.shields.io/pypi/pyversions/cdse-client.svg)](https://pypi.org/project/cdse-client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Python client for Copernicus Data Space Ecosystem (CDSE)** - A modern, drop-in replacement for the deprecated `sentinelsat` library.

## 🚀 Why cdse-client?

The European Space Agency (ESA) has migrated from the old Copernicus Open Access Hub to the new **Copernicus Data Space Ecosystem (CDSE)**. The popular `sentinelsat` library no longer works with the new infrastructure.

`cdse-client` provides:
- ✅ **OAuth2 authentication** for CDSE
- ✅ **STAC API catalog search** for finding products
- ✅ **OData API integration** for downloads
- ✅ **Simple, pythonic API** similar to sentinelsat
- ✅ **Progress bars** for downloads
- ✅ **Async support** (coming soon)

## 📦 Installation

```bash
pip install cdse-client
```

For GeoJSON/Shapely support:
```bash
pip install cdse-client[geo]
```

## 🔑 Getting Credentials

1. Register at [Copernicus Data Space](https://dataspace.copernicus.eu/)
2. Go to your [Account Settings](https://dataspace.copernicus.eu/profile)
3. Create OAuth2 credentials (Client ID and Client Secret)

## 🎯 Quick Start

```python
from cdse import CDSEClient

# Initialize client with your credentials
client = CDSEClient(
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Search for Sentinel-2 products
products = client.search(
    bbox=[9.0, 45.0, 9.5, 45.5],  # Milan area
    start_date="2024-01-01",
    end_date="2024-01-31",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5
)

print(f"Found {len(products)} products")

# Download products
for product in products:
    print(f"Downloading: {product.id}")
    client.download(product, output_dir="./downloads")
```

## 📖 API Reference

### CDSEClient

Main client class for interacting with CDSE.

```python
from cdse import CDSEClient

client = CDSEClient(
    client_id: str,          # OAuth2 client ID
    client_secret: str,      # OAuth2 client secret
    output_dir: str = "."    # Default download directory
)
```

### Search Methods

#### `search()`

Search for products in the CDSE catalog.

```python
products = client.search(
    bbox: List[float],           # [min_lon, min_lat, max_lon, max_lat]
    start_date: str,             # Start date (YYYY-MM-DD)
    end_date: str,               # End date (YYYY-MM-DD)
    collection: str = "sentinel-2-l2a",  # Collection name
    cloud_cover_max: float = 100,        # Max cloud cover %
    limit: int = 10              # Max results
)
```

**Available collections:**
- `sentinel-1-grd` - Sentinel-1 GRD
- `sentinel-2-l1c` - Sentinel-2 L1C
- `sentinel-2-l2a` - Sentinel-2 L2A (atmospheric corrected)
- `sentinel-3-olci` - Sentinel-3 OLCI
- `sentinel-5p-l2` - Sentinel-5P Level-2

#### `search_by_point()`

Search by geographic point.

```python
products = client.search_by_point(
    lon: float,                  # Longitude
    lat: float,                  # Latitude
    buffer_km: float = 10,       # Search radius in km
    **kwargs                     # Other search params
)
```

#### `search_by_name()`

Search by product name pattern.

```python
products = client.search_by_name(
    name: str,                   # Product name pattern
    collection: str = None       # Optional collection filter
)
```

### Download Methods

#### `download()`

Download a single product.

```python
path = client.download(
    product: Product,            # Product to download
    output_dir: str = None,      # Output directory
    filename: str = None         # Custom filename
)
```

#### `download_all()`

Download multiple products.

```python
paths = client.download_all(
    products: List[Product],     # Products to download
    output_dir: str = None,      # Output directory
    max_concurrent: int = 2      # Max parallel downloads
)
```

### Product Class

```python
product.id          # Product ID
product.name        # Product name
product.date        # Acquisition date
product.cloud_cover # Cloud cover percentage
product.size        # File size in bytes
product.geometry    # GeoJSON geometry
product.properties  # All metadata
```

## 🔄 Migration from sentinelsat

| sentinelsat | cdse-client |
|-------------|-------------|
| `SentinelAPI(user, password)` | `CDSEClient(client_id, client_secret)` |
| `api.query(area, date, ...)` | `client.search(bbox, start_date, end_date, ...)` |
| `api.download(uuid)` | `client.download(product)` |
| `api.download_all(products)` | `client.download_all(products)` |

## 🌍 Environment Variables

You can set credentials via environment variables:

```bash
export CDSE_CLIENT_ID="your-client-id"
export CDSE_CLIENT_SECRET="your-client-secret"
```

```python
from cdse import CDSEClient

# Will use environment variables
client = CDSEClient()
```

## 🛠️ CLI Usage

```bash
# Search products
cdse search --bbox 9.0,45.0,9.5,45.5 --start 2024-01-01 --end 2024-01-31

# Download product
cdse download <product-id> --output ./downloads

# List collections
cdse collections
```

## 🧪 Development

```bash
# Clone repository
git clone https://github.com/VTvito/cdse-client.git
cd cdse-client

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
ruff check src tests
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## 📚 Resources

- [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/)
- [CDSE API Documentation](https://documentation.dataspace.copernicus.eu/)
- [STAC API Specification](https://stacspec.org/)
