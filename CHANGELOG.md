# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-23

First stable release. The public API has been unchanged since 0.3.0 and there are
**no breaking changes** relative to 0.4.0 — the version number reflects that the API is
now considered stable and covered by semantic versioning guarantees.

### Changed

- **Project positioning**: the README, the PyPI summary and the documentation landing page
  now lead with what the library does (search and download Sentinel data from CDSE) rather
  than with a comparison against `sentinelsat`, which has been moved to a "Migrating from
  sentinelsat" section.
- **README reduced from 352 to ~125 lines**: the API catalogue sections (search methods,
  download methods, data export, geometry utilities, processing, async) duplicated the
  documentation site and have been replaced by a compact overview plus direct links.
- **PyPI metadata**: `description` corrected — the previous "Drop-in replacement for
  sentinelsat" was inaccurate (`SentinelAPI(user, password)` and
  `CDSEClient(client_id, client_secret)` are not interchangeable). Keywords expanded with
  the per-mission and geospatial terms; added `Environment :: Console`,
  `Programming Language :: Python :: 3 :: Only` and `Typing :: Typed` classifiers.
- **`Development Status`** raised from `4 - Beta` to `5 - Production/Stable`.
- **Version is now single-sourced**: `pyproject.toml` declares `dynamic = ["version"]` and
  reads `cdse.__version__`, removing the manual two-file sync that the release checklist
  previously required.

### Fixed

- Documentation: `calculate_ndvi` example in `docs/user-guide/processing.md` was missing the
  required `output_path` argument and raised `TypeError` as written.
- README: removed links to GitHub Discussions, which is not enabled on the repository.
- README: removed the `.env` setup option, which implied the library loads `.env` files
  itself — it does not; only `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` environment variables
  are read.
- Documentation: fixed broken link in `docs/releases.md` pointing to `../CHANGELOG.md`
  (outside MkDocs docs tree) by linking to repository changelog URL.
- Documentation: added stable anchors for release-note cross-links (`#resilience` in
  `docs/faq.md`, `#monitoring` in `docs/getting-started.md`) to avoid strict-mode anchor
  drift.

### Removed

- **`notebooks/test_cdse_client.ipynb`**: a 2.7 MB end-to-end test notebook with committed
  outputs, still titled "v0.3.0" and referenced from nowhere. It made up 92% of the tracked
  bytes in the repository, causing GitHub to classify the project as a Jupyter Notebook
  repository rather than a Python library. Its content is covered by `docs/user-guide/` and
  the runnable scripts in `examples/`.
- **`.readthedocs.yml`**: no Read the Docs project exists for this package
  (`cdse-client.readthedocs.io` returns 404); documentation is published to GitHub Pages.
- Maintainer-facing `release.md` removed from the documentation navigation (the file
  remains in the repository).
- Removed redundant `RELEASE_v0.4.0.md` document from repository root to reduce duplicated
  release-note overhead.

## [0.4.0] - 2026-02-12

### Fixed

- **`search_by_point` buffer correction**: Longitude buffer now accounts for latitude using `cos(lat)` correction, matching `geocoding.py` behavior. Previously, searches at high latitudes produced overly wide bounding boxes.
- **`download_all` skip_existing**: The `skip_existing` parameter was dead code — never passed to `download()`. Now correctly forwarded in both sequential and parallel download paths.
- **Inline `import json`**: Moved `import json` from inside `Catalog._odata_to_product()` to module-level imports.
- **README `bbox_from_city`**: Replaced non-existent `bbox_from_city` with the actual function name `get_city_bbox` in the Quick Start example.

### Changed

- **Bearer session auto-refresh**: `OAuth2Auth.get_bearer_session()` now returns a `_BearerSession` that automatically refreshes the token before each request when expired. Long-running downloads no longer fail due to token expiry.
- **Retry with exponential backoff**: `Downloader` now retries on transient HTTP errors (429, 502, 503, 504) and connection errors, with exponential backoff (up to 3 attempts). Configurable via `max_retries` parameter.
- **Explicit timeouts**: All HTTP requests in `Catalog` and `Downloader` now have explicit `timeout=60` (configurable in Downloader via `timeout` parameter). Previously some requests had no timeout.
- **Logging replaces print()**: All `print()` calls in library modules (`downloader.py`, `async_client.py`, `processing.py`) replaced with `logging.getLogger(__name__)`. CLI (`cli.py`) retains `print()` as intended for user-facing output.
- **Async client token refresh**: `CDSEClientAsync` now tracks token expiration and re-authenticates automatically when the token expires.
- **Async client progress bars**: `CDSEClientAsync.download()` now shows per-file `tqdm` progress bars; `download_all()` shows an overall progress bar.

### Removed

- **`black` from dev dependencies**: Redundant with `ruff format`. The `[tool.black]` config section has also been removed.
- **`mkdocs` from `[all]` extra**: Documentation dependencies now only in `[docs]` extra. `pip install cdse-client[all]` installs only runtime extras (geo, dataframe, async, processing).

## [0.3.3] - 2026-01-12

### Changed

- README: use a more reliable PyPI downloads badge and refresh examples.
- Packaging: point project metadata documentation URL to the hosted docs site.

### Added

- New runnable examples under `examples/` (sync, async, processing).

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

[Unreleased]: https://github.com/VTvito/cdse-client/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/VTvito/cdse-client/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/VTvito/cdse-client/compare/v0.3.0...v0.3.3
[0.3.0]: https://github.com/VTvito/cdse-client/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/VTvito/cdse-client/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VTvito/cdse-client/releases/tag/v0.1.0
