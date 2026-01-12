# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-01-04

### Added

- **DataFrame export** (sentinelsat compatible): `to_dataframe()` converts search results to Pandas DataFrame
- **GeoJSON export** (sentinelsat compatible): `to_geojson()` converts search results to GeoJSON FeatureCollection
- **GeoDataFrame export** (sentinelsat compatible): `to_geodataframe()` converts to GeoPandas GeoDataFrame
- **Quicklook download**: `download_quicklook()` and `download_all_quicklooks()` for preview images
- **CLI enhancements**:
  - `cdse download --name <product_name>` - Download by product name
  - `cdse download --uuid <uuid>` - Download by UUID
  - `cdse download --quicklook` - Download quicklook preview only
  - `cdse search --footprints output.geojson` - Export footprints to GeoJSON
  - `cdse search -g area.geojson` - Search using GeoJSON file
  - `cdse search -d` - Download all search results
  - `cdse search --parallel` - Parallel downloads
- **Utility functions**: `products_size()`, `products_count()`, `get_products_size()`
- New optional dependencies: `[dataframe]` for pandas, geopandas now in `[geo]`

### Changed

- CLI now uses short options: `-s/--start`, `-e/--end`, `-c/--cloud`, `-l/--limit`, `-d/--download`, `-f/--footprints`, `-o/--output`
- Improved error handling with KeyboardInterrupt support in CLI

### Dependencies

- Added `pandas>=2.0.0` to `[dataframe]` extras
- Added `geopandas>=0.14.0` to `[geo]` extras

## [0.2.0] - 2026-01-02

### Added

- **Geometry utilities**: GeoJSON/WKT conversion, bbox operations (sentinelsat compatible)
- **Async client**: `CDSEClientAsync` for high-performance concurrent downloads
- **Geocoding module**: City-based search with `get_city_bbox()`, `get_city_center()`
- **GitHub Actions CI**: Automated testing across Python 3.9-3.12

### Changed

- **Download optimization**: Increased chunk_size from 8KB to 128KB for faster downloads
- **OData query optimization**: Changed from `contains()` to `Name eq` (exact match) query - **60x faster UUID resolution** (from ~25s to ~0.5s)
- **UUID caching**: Product UUID is now cached on the Product object to avoid redundant OData queries
- **Async client optimization**: Updated chunk size to 128KB and using optimized `Name eq` query

### Dependencies

- Added `geopy>=2.4.0` to `[geo]` extras for geocoding support
- Added `aiohttp` and `aiofiles` to `[async]` extras for async client

## [0.1.0] - 2024-12-30

### Added

- Initial release
- OAuth2 authentication for Copernicus Data Space Ecosystem
- STAC API catalog search
- Product download with progress bars
- Support for Sentinel-1, Sentinel-2, Sentinel-3, and Sentinel-5P collections
- Command-line interface (CLI)
- Environment variable support for credentials
- Comprehensive documentation

### Collections Supported

- `sentinel-1-grd` - Sentinel-1 GRD
- `sentinel-2-l1c` - Sentinel-2 L1C  
- `sentinel-2-l2a` - Sentinel-2 L2A (atmospherically corrected)
- `sentinel-3-olci` - Sentinel-3 OLCI
- `sentinel-3-slstr` - Sentinel-3 SLSTR
- `sentinel-5p-l2` - Sentinel-5P Level-2

[Unreleased]: https://github.com/VTvito/cdse-client/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/VTvito/cdse-client/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/VTvito/cdse-client/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VTvito/cdse-client/releases/tag/v0.1.0
