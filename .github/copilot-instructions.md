# Copilot Instructions for cdse-client

## Project Overview

`cdse-client` is a Python client for the **Copernicus Data Space Ecosystem (CDSE)** - a drop-in replacement for the deprecated `sentinelsat` library.

**Version**: 0.3.0 | **Python**: 3.9+ | **License**: MIT

## Architecture

```
src/cdse/
├── __init__.py       # Package exports
├── auth.py           # OAuth2 authentication
├── catalog.py        # STAC API search
├── client.py         # Main CDSEClient facade
├── converters.py     # DataFrame/GeoJSON/GeoDataFrame export
├── downloader.py     # OData downloads + quicklook
├── product.py        # Product dataclass
├── geometry.py       # GeoJSON/WKT utilities
├── geocoding.py      # City bbox lookup
├── processing.py     # Raster crop/stack/preview
├── async_client.py   # Async downloads
├── cli.py            # CLI (search, download, collections)
└── exceptions.py     # Custom exceptions
```

## Key APIs

| Endpoint | URL |
|----------|-----|
| Auth | `identity.dataspace.copernicus.eu/.../token` |
| STAC | `sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search` |
| OData | `zipper.dataspace.copernicus.eu/odata/v1/Products` |

## Standards

- **Style**: PEP 8, ruff (format+lint), mypy
- **Docs**: Google-style docstrings, type hints required
- **Tests**: pytest + responses for mocking
- **Exceptions**: Use `cdse.exceptions.*` hierarchy

## Collections

`sentinel-1-grd`, `sentinel-2-l1c`, `sentinel-2-l2a`, `sentinel-3-olci`, `sentinel-3-slstr`, `sentinel-5p-l2`

## Installation Extras

```bash
pip install cdse-client[geo]         # + shapely, geopandas, geopy
pip install cdse-client[dataframe]   # + pandas
pip install cdse-client[processing]  # + rasterio, matplotlib
pip install cdse-client[async]       # + aiohttp, aiofiles
pip install cdse-client[all]         # Everything
```

---

## Agentic AI Development Guide

Instructions for AI coding agents (Copilot, Claude, etc.) working on this codebase.

### Before Any Change

1. **Read context** - Understand the file before editing
2. **Check exports** - New public APIs go in `__init__.py`
3. **Run tests** - `pytest tests/ -q` before and after

### Development Workflow

```bash
# Test
pytest tests/ -v --cov=cdse

# Quality
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/cdse

# Build
python -m build
```

### Adding Features

| Feature Type | Files to Update |
|--------------|-----------------|
| Search filter | `catalog.py` → `client.py` → `cli.py` → tests |
| Download feature | `downloader.py` → `client.py` → tests |
| Converter | `converters.py` → `__init__.py` → tests |
| CLI command | `cli.py` → `test_cli.py` |

### Code Patterns

```python
# Optional import (lazy loading)
def to_geodataframe(products):
    try:
        import geopandas as gpd
    except ImportError as e:
        raise ImportError("Install: pip install cdse-client[geo]") from e
    # implementation...

# Exception handling
from cdse.exceptions import DownloadError
raise DownloadError(f"Failed: {response.status_code}")

# Progress bar (required for downloads)
from tqdm import tqdm
with tqdm(total=size, unit='B', unit_scale=True) as pbar:
    # download loop...
```

### Testing Requirements

- New module → `tests/test_<module>.py`
- Mock HTTP with `responses` library
- Cover: success, empty results, errors
- Aim for good coverage on critical paths

### Release Checklist

1. Bump `__version__` in `src/cdse/__init__.py`
2. Bump `version` in `pyproject.toml`
3. Add CHANGELOG.md entry
4. Update README.md if API changed

### Key Guidelines

- **Always use tqdm** for download progress
- **Cache OData UUIDs** on `product._odata_uuid`
- **Stream large files** - never load fully in memory
- **Handle rate limits** - CDSE has API quotas

### Sentinelsat Migration Status

- ✅ `to_dataframe()`, `to_geojson()`, `to_geodataframe()`
- ✅ `download_quicklook()`, geometry utilities
- ⬜ Node filter, .netrc support (future)

