# Search

## STAC search

`CDSEClient.search()` queries the CDSE STAC API.

```python
products = client.search(
    bbox=[9.10, 45.40, 9.28, 45.52],
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=20,
    limit=10,
)
```

## Search by point

```python
products = client.search_by_point(
    lon=9.19,
    lat=45.46,
    buffer_km=10,
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=30,
    limit=5,
)
```

## Search by name / UUID (OData catalogue)

These helpers query the OData catalogue (not the STAC endpoint).

```python
# Resolve an OData product by exact Name
odata_product = client.search_by_name("S2A_MSIL2A_...", exact=True)

# Fetch by UUID
product = client.search_by_id("a1b2c3d4-e5f6-...")
```

!!! note

    IDs returned by STAC are not guaranteed to be OData UUIDs.

## Search by city

Two modes:

- `use_predefined=True`: offline lookup (no network), limited city list
- `use_predefined=False`: live geocoding (requires `cdse-client[geo]` and network)

```python
# Offline / predefined bbox
products = client.search_by_city(
    city_name="milano",
    start_date="2025-06-01",
    end_date="2025-06-30",
    collection="sentinel-2-l2a",
    cloud_cover_max=30,
    limit=5,
    use_predefined=True,
)

# Live geocoding
products = client.search_by_city(
    city_name="Milano, Italia",
    start_date="2025-06-01",
    end_date="2025-06-30",
    buffer_km=15,
    collection="sentinel-2-l2a",
    cloud_cover_max=30,
    limit=5,
    use_predefined=False,
    geocoding_timeout=10.0,
)
```
