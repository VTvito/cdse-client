# Export

## DataFrame

Requires `cdse-client[dataframe]`.

```python
df = client.to_dataframe(products)
df.sort_values("cloud_cover").head()
```

## GeoJSON

```python
geojson = client.to_geojson(products)
```

## GeoDataFrame

Requires `cdse-client[geo]`.

```python
gdf = client.to_geodataframe(products)
```

## Totals

```python
from cdse import products_count, products_size

count = products_count(products)
size_gb = products_size(products)
```
