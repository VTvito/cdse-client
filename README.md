# cdse-client

[![PyPI version](https://img.shields.io/pypi/v/cdse-client.svg)](https://pypi.org/project/cdse-client/)
[![Python](https://img.shields.io/pypi/pyversions/cdse-client.svg)](https://pypi.org/project/cdse-client/)
[![Downloads](https://img.shields.io/pypi/dm/cdse-client.svg)](https://pypistats.org/packages/cdse-client)
[![CI](https://github.com/VTvito/cdse-client/actions/workflows/ci.yml/badge.svg)](https://github.com/VTvito/cdse-client/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Search and download Copernicus Sentinel data (Sentinel-1, 2, 3, 5P) from the
**Copernicus Data Space Ecosystem** in a few lines of Python.

```bash
pip install cdse-client
```

```python
from cdse import CDSEClient

client = CDSEClient()  # reads CDSE_CLIENT_ID / CDSE_CLIENT_SECRET

products = client.search(
    bbox=[9.10, 45.40, 9.28, 45.52],  # Milan
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5,
)

print(client.download(products[0]))
```

Same thing from the terminal:

```bash
cdse search --bbox 9.10,45.40,9.28,45.52 -s 2025-06-01 -e 2025-06-30 -c 20 -l 5 --download
```

## Credentials

Register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/), create OAuth2
credentials in your [account settings](https://dataspace.copernicus.eu/profile), then:

```bash
export CDSE_CLIENT_ID="your-client-id"          # PowerShell: $env:CDSE_CLIENT_ID = "..."
export CDSE_CLIENT_SECRET="your-client-secret"  # PowerShell: $env:CDSE_CLIENT_SECRET = "..."
```

You can also pass them explicitly: `CDSEClient(client_id=..., client_secret=...)`.

## What it does

| | |
|---|---|
| **Search** | STAC — bounding box, point + radius, city name, date range, cloud cover |
| **Download** | OData/Zipper — progress bars, parallel, MD5 checksums, quicklooks |
| **Export** | `to_dataframe()`, `to_geojson()`, `to_geodataframe()` |
| **Async** | `CDSEClientAsync` with concurrency control |
| **Process** | crop, band stacking, NDVI, RGB previews (Sentinel-2) |

Collections: `sentinel-1-grd`, `sentinel-2-l1c`, `sentinel-2-l2a`, `sentinel-3-olci`,
`sentinel-3-slstr`, `sentinel-5p-l2`.

Built for long, unattended jobs: OAuth2 tokens refresh themselves mid-download, transient
`429`/`5xx` responses are retried with exponential backoff, every request has an explicit
timeout, and the package ships type hints (PEP 561).

> `search()` returns STAC results, whose ids are product *names*, not OData UUIDs.
> If you need a UUID, use `search_by_name(name, exact=True)`.

## Optional extras

```bash
pip install cdse-client[geo]         # search by city name, GeoDataFrame export
pip install cdse-client[dataframe]   # DataFrame export
pip install cdse-client[async]       # concurrent downloads
pip install cdse-client[processing]  # NDVI, band stacking, previews
pip install cdse-client[all]         # all of the above
```

## Documentation

**[Full documentation →](https://vtvito.github.io/cdse-client/)**

[Getting started](https://vtvito.github.io/cdse-client/getting-started/) ·
[Search](https://vtvito.github.io/cdse-client/user-guide/search/) ·
[Download](https://vtvito.github.io/cdse-client/user-guide/download/) ·
[CLI](https://vtvito.github.io/cdse-client/user-guide/cli/) ·
[API reference](https://vtvito.github.io/cdse-client/reference/client/) ·
[FAQ](https://vtvito.github.io/cdse-client/faq/)

Runnable scripts: [`examples/`](examples/)

## Migrating from sentinelsat

`sentinelsat` targeted DHuS/SciHub, which is closed; the project is archived and cannot
download from CDSE. The export surface here is deliberately familiar:

| sentinelsat | cdse-client |
|---|---|
| `SentinelAPI(user, password)` | `CDSEClient()` (OAuth2 client credentials) |
| `api.query(...)` | `client.search(...)` |
| `api.download(...)` | `client.download(product)` |
| `api.to_dataframe(...)` | `client.to_dataframe(products)` |

[Full migration guide →](https://vtvito.github.io/cdse-client/migration/)

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[issue tracker](https://github.com/VTvito/cdse-client/issues).

## Disclaimer

Unofficial client library, not affiliated with or endorsed by ESA, the European
Commission, or the Copernicus Programme.

Sentinel data is provided under a free, full and open data policy for any use, including
commercial. Users must register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/)
and comply with the CDSE
[Terms and Conditions](https://dataspace.copernicus.eu/terms-and-conditions) and
[quotas](https://documentation.dataspace.copernicus.eu/Quotas.html).

## License

MIT — see [LICENSE](LICENSE).
