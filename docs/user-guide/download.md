# Download

## Download one product

```python
path = client.download(product, output_dir="./downloads")
```

## Download multiple products

```python
paths = client.download_all(
    products,
    output_dir="./downloads",
    parallel=True,
    max_workers=4,
)
```

## Download with checksum verification

```python
path = client.download_with_checksum(product, output_dir="./downloads")
```

## Quicklooks

Quicklooks are server-provided previews and are **not guaranteed** for all products.
Some products may return 403/404.

```python
quicklook_path = client.download_quicklook(product, output_dir="./quicklooks")
```

If quicklooks are unavailable, prefer generating a local RGB preview after downloading the product (see Processing).
