"""Data format converters for CDSE Client.

This module provides functions to convert search results to various formats:
- Pandas DataFrame
- GeoPandas GeoDataFrame
- GeoJSON FeatureCollection

These functions are designed to be compatible with sentinelsat's API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd

    from cdse.product import Product


def to_geojson(products: list["Product"]) -> dict[str, Any]:
    """Convert products to GeoJSON FeatureCollection.

    Args:
        products: List of Product objects from search results

    Returns:
        GeoJSON FeatureCollection dictionary

    Example:
        >>> products = client.search(...)
        >>> geojson = to_geojson(products)
        >>> with open("footprints.geojson", "w") as f:
        ...     json.dump(geojson, f)
    """
    features = []
    for product in products:
        feature = {
            "type": "Feature",
            "id": product.id,
            "geometry": product.geometry,
            "properties": {
                "id": product.id,
                "name": product.name,
                "collection": product.collection,
                "datetime": product.datetime.isoformat() if product.datetime else None,
                "cloud_cover": product.cloud_cover,
                "platform": product.platform,
                "instrument": product.instrument,
                "tile_id": product.tile_id,
                "orbit_number": product.orbit_number,
                "processing_level": product.processing_level,
                "size": product.size,
                "size_mb": product.size_mb,
            },
            "bbox": product.bbox,
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def to_dataframe(products: list["Product"]) -> "pd.DataFrame":
    """Convert products to Pandas DataFrame.

    Requires pandas to be installed: pip install pandas

    Args:
        products: List of Product objects from search results

    Returns:
        pandas.DataFrame with product metadata

    Raises:
        ImportError: If pandas is not installed

    Example:
        >>> products = client.search(...)
        >>> df = to_dataframe(products)
        >>> df_sorted = df.sort_values('cloud_cover')
        >>> df.to_csv("products.csv")
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for to_dataframe(). Install it with: pip install pandas"
        ) from e

    data = []
    for product in products:
        row = {
            "id": product.id,
            "name": product.name,
            "collection": product.collection,
            "datetime": product.datetime,
            "cloud_cover": product.cloud_cover,
            "platform": product.platform,
            "instrument": product.instrument,
            "tile_id": product.tile_id,
            "orbit_number": product.orbit_number,
            "processing_level": product.processing_level,
            "size": product.size,
            "size_mb": product.size_mb,
            "bbox_min_lon": product.bbox[0] if len(product.bbox) >= 4 else None,
            "bbox_min_lat": product.bbox[1] if len(product.bbox) >= 4 else None,
            "bbox_max_lon": product.bbox[2] if len(product.bbox) >= 4 else None,
            "bbox_max_lat": product.bbox[3] if len(product.bbox) >= 4 else None,
        }
        data.append(row)

    df = pd.DataFrame(data)

    # Set product ID as index (like sentinelsat)
    if not df.empty:
        df.set_index("id", inplace=True)

    return df


def to_geodataframe(products: list["Product"]) -> "gpd.GeoDataFrame":
    """Convert products to GeoPandas GeoDataFrame.

    Requires geopandas to be installed: pip install geopandas

    Args:
        products: List of Product objects from search results

    Returns:
        geopandas.GeoDataFrame with product metadata and geometries

    Raises:
        ImportError: If geopandas is not installed

    Example:
        >>> products = client.search(...)
        >>> gdf = to_geodataframe(products)
        >>> gdf.plot()  # Visualize footprints
        >>> gdf.to_file("footprints.gpkg", driver="GPKG")
    """
    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError as e:
        raise ImportError(
            "geopandas and shapely are required for to_geodataframe(). "
            "Install them with: pip install geopandas shapely"
        ) from e

    # Handle empty list
    if not products:
        return gpd.GeoDataFrame(
            columns=[
                "id",
                "name",
                "collection",
                "datetime",
                "cloud_cover",
                "platform",
                "size_mb",
                "tile_id",
                "geometry",
            ],
            crs="EPSG:4326",
        ).set_index("id")

    # First get the regular dataframe
    df = to_dataframe(products)

    # Add geometry column
    geometries = []
    for product in products:
        if product.geometry:
            try:
                geom = shape(product.geometry)
                geometries.append(geom)
            except Exception:
                geometries.append(None)
        else:
            geometries.append(None)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df.reset_index(),  # Reset index to get 'id' back as column
        geometry=geometries,
        crs="EPSG:4326",  # WGS84
    )

    # Set product ID as index again
    gdf.set_index("id", inplace=True)

    return gdf


def products_size(products: list["Product"]) -> float:
    """Calculate total size of products in GB.

    Args:
        products: List of Product objects

    Returns:
        Total size in gigabytes

    Example:
        >>> products = client.search(...)
        >>> print(f"Total size: {products_size(products):.2f} GB")
    """
    total_bytes = sum(p.size or 0 for p in products)
    return total_bytes / (1024**3)


def products_count(products: list["Product"]) -> dict[str, int]:
    """Count products by collection.

    Args:
        products: List of Product objects

    Returns:
        Dictionary mapping collection names to counts

    Example:
        >>> products = client.search(...)
        >>> counts = products_count(products)
        >>> print(counts)  # {'sentinel-2-l2a': 5, 'sentinel-2-l1c': 2}
    """
    counts: dict[str, int] = {}
    for product in products:
        coll = product.collection or "unknown"
        counts[coll] = counts.get(coll, 0) + 1
    return counts
