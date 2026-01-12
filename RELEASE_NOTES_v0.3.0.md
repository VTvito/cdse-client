# 🚀 cdse-client v0.3.0

First production release of **cdse-client** - a modern Python client for Copernicus Data Space Ecosystem.

## 🎯 Overview

`cdse-client` is a drop-in replacement for the deprecated `sentinelsat` library, providing access to Sentinel-1/2/3/5P satellite data through the new CDSE infrastructure.

## ✨ Features

### Core Functionality
- 🔍 **STAC API Search**: Flexible search with bbox, date range, cloud cover, and more
- 📥 **Smart Downloads**: Automatic retry, checksum verification, quicklook support
- 🗂️ **Multiple Collections**: Sentinel-1 GRD, Sentinel-2 L1C/L2A, Sentinel-3 OLCI/SLSTR, Sentinel-5P L2
- 📊 **Export Formats**: DataFrame, GeoJSON, GeoDataFrame (sentinelsat compatible)

### Processing Tools
- 🛠️ **Band Extraction**: Extract specific bands from .SAFE or .zip files
- ✂️ **Cropping & Stacking**: Crop to AOI and stack bands into multi-band GeoTIFF
- 🌱 **NDVI Calculation**: Built-in vegetation index calculation
- 🖼️ **Preview Generation**: Create RGB previews with Jupyter notebook support

### Advanced Features
- ⚡ **Async Downloads**: High-performance concurrent downloads with `aiohttp`
- 💻 **CLI Interface**: Command-line tools for search and download
- 🗺️ **Geocoding**: Search by city name with automatic bbox lookup
- 🔒 **Type Safety**: Full type hints with `py.typed` marker

## 📦 Installation

```bash
# Core functionality
pip install cdse-client

# With all extras (recommended)
pip install cdse-client[all]

# Specific extras
pip install cdse-client[geo]         # + shapely, geopandas, geopy
pip install cdse-client[processing]  # + rasterio, numpy, matplotlib
pip install cdse-client[async]       # + aiohttp, aiofiles
pip install cdse-client[dataframe]   # + pandas
```

## 🚦 Quick Start

```python
from cdse import CDSEClient

# Initialize with OAuth2 credentials
client = CDSEClient(
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Search Sentinel-2 data over Milan
products = client.search(
    bbox=[9.0, 45.0, 9.5, 45.5],
    start_date="2024-01-01",
    end_date="2024-01-31",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5
)

# Download products
for product in products:
    path = client.download(product)
    print(f"Downloaded: {path}")
```

## 📖 Documentation

- **Documentation**: https://vtvito.github.io/cdse-client/
- **PyPI Package**: https://pypi.org/project/cdse-client/
- **Source Code**: https://github.com/VTvito/cdse-client

## 🆕 What's New in v0.3.0

### New Modules
- ✅ `cdse.processing` - Band extraction, cropping, stacking, NDVI, previews
- ✅ `cdse.async_client` - High-performance async downloads
- ✅ `cdse.converters` - DataFrame, GeoJSON, GeoDataFrame export
- ✅ `cdse.geocoding` - City-based bbox lookup
- ✅ `cdse.geometry` - GeoJSON/WKT utilities

### CLI Improvements
- ✅ `cdse search` - Search products from command line
- ✅ `cdse download` - Download by name/UUID with quicklook support
- ✅ `cdse collections` - List available collections

### Quality & Documentation
- ✅ Full test suite (135+ tests, 46% coverage)
- ✅ Complete MkDocs documentation
- ✅ Type hints with `py.typed` marker
- ✅ CI/CD with GitHub Actions
- ✅ Security policy and contributing guidelines

## 🔄 Migration from sentinelsat

| sentinelsat | cdse-client |
|-------------|-------------|
| `SentinelAPI(user, password)` | `CDSEClient(client_id, client_secret)` |
| `api.query(...)` | `client.search(...)` |
| `api.download(uuid)` | `client.download(product)` |
| `api.to_dataframe(...)` | `client.to_dataframe(...)` |
| `api.to_geojson(...)` | `client.to_geojson(...)` |

See [Migration Guide](https://vtvito.github.io/cdse-client/migration/) for details.

## 🛡️ Requirements

- Python ≥ 3.9
- OAuth2 credentials from [Copernicus Data Space](https://dataspace.copernicus.eu/)

## 🙏 Acknowledgments

This is an **unofficial** client library. The Copernicus Data Space Ecosystem and Sentinel data are provided by:
- European Space Agency (ESA)
- European Commission
- Copernicus Programme

Sentinel data is available under a **free, full, and open** data policy for any use, including commercial. See [Sentinel Data Legal Notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).

## 📄 License

MIT License - See [LICENSE](https://github.com/VTvito/cdse-client/blob/main/LICENSE)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](https://github.com/VTvito/cdse-client/blob/main/CONTRIBUTING.md)

---

**Full Changelog**: https://github.com/VTvito/cdse-client/commits/main
