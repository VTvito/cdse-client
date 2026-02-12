# FAQ

## Why does `search_by_id()` fail with a STAC product id?

`search_by_id()` queries the OData catalogue and expects a UUID. STAC search results are not guaranteed to expose that UUID.
Use `search_by_name(..., exact=True)` to resolve the OData product first.

## Quicklook download fails (403/404)

Quicklooks are not guaranteed. Some products may not expose previews or may be restricted.
For a reliable preview, download the product and generate a local RGB preview via `cdse.processing.preview_product()`.

## City geocoding sometimes times out

Live geocoding depends on Nominatim (network + rate limits). You can:
- Use `use_predefined=True` (offline fallback)
- Increase `geocoding_timeout`

## Installing processing deps on Windows

If `rasterio` fails to install, try Python 3.11/3.12 or conda-forge.

## Downloads timeout or fail (v0.4.0+)

By default, downloads have a 60-second timeout and retry 3 times on transient errors (429, 502, 503, 504).

For slower networks or unreliable connections:

```python
from cdse import CDSEClient

client = CDSEClient()
downloader = client.downloader

# Increase timeout and retries
downloader.timeout = 300        # 5 minutes
downloader.max_retries = 10     # More aggressive retries
```

Monitor what's happening:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now you'll see retry attempts and token refresh
paths = client.download_all(products)
```

## Token expires during long downloads (v0.4.0+)

`cdse-client` now automatically refreshes the Bearer token before each HTTP request. Long-running downloads (hours) will not fail due to token expiry.

This is handled transparently — no configuration needed.
