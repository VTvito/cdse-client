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
