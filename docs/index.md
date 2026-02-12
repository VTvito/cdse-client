# cdse-client

Python client for **Copernicus Data Space Ecosystem (CDSE)** — a modern replacement for `sentinelsat`.

!!! info "Latest Release"
    **v0.4.0** (2026-02-12) — Production hardening with auto-refresh tokens, resilient retries, and logging. [Release notes →](releases.md)

**Highlights**
- STAC search (`search`, `search_by_point`, collections)
- OData catalogue helpers (`search_by_name`, `search_by_id`)
- OData downloads with progress (`download`, `download_all`, checksum)
- Exports compatible with common `sentinelsat` workflows (`to_dataframe`, `to_geojson`, `to_geodataframe`)
- Optional extras: geo, dataframe, processing, async

## Install

```bash
pip install cdse-client
```

Optional extras:

```bash
pip install cdse-client[geo]
pip install cdse-client[dataframe]
pip install cdse-client[processing]
pip install cdse-client[async]
pip install cdse-client[all]
```

## Credentials

Create OAuth2 credentials in your CDSE account and set:

=== "macOS/Linux"

    ```bash
    export CDSE_CLIENT_ID="..."
    export CDSE_CLIENT_SECRET="..."
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:CDSE_CLIENT_ID = "..."
    $env:CDSE_CLIENT_SECRET = "..."
    ```

## Quick example

```python
from cdse import CDSEClient

client = CDSEClient()  # reads env vars

products = client.search(
    bbox=[9.10, 45.40, 9.28, 45.52],
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=5,
)

path = client.download(products[0])
print(path)
```

Next steps:
- [Getting started](getting-started.md)
- [Migration from sentinelsat](migration.md)
