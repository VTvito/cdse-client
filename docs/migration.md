# Migration from sentinelsat

This page helps you migrate common workflows from `sentinelsat` to `cdse-client`.

## Mapping table

| sentinelsat | cdse-client |
|---|---|
| `SentinelAPI(user, password)` | `CDSEClient(client_id, client_secret)` (OAuth2) |
| `api.query(...)` | `client.search(...)` |
| `api.download(uuid)` | `client.download(product)` |
| `api.download_all(products)` | `client.download_all(products)` |
| `api.download_quicklook(uuid)` | `client.download_quicklook(product)` |
| `api.to_dataframe(products)` | `client.to_dataframe(products)` |
| `api.to_geojson(products)` | `client.to_geojson(products)` |

## Key differences

### Authentication

CDSE uses OAuth2 client credentials instead of username/password.

### STAC vs OData identifiers

- `search()` returns STAC results; their IDs are not guaranteed to be OData UUIDs.
- `search_by_id()` requires an OData UUID.

If you need to go from STAC search result → UUID:

```python
odata_product = client.search_by_name(products[0].name, exact=True)
if odata_product:
    product = client.search_by_id(odata_product.id)
```

### Quicklooks

Quicklooks may be missing or restricted for some products. Prefer local preview generation if you need reliable visuals.
