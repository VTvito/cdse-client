"""Quick start: search + download.

Requires:
  pip install cdse-client

Auth:
  Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET.
"""

from cdse import CDSEClient


def main() -> None:
    client = CDSEClient(output_dir="./downloads")

    products = client.search(
        bbox=[9.0, 45.0, 9.5, 45.5],
        start_date="2024-01-01",
        end_date="2024-01-31",
        collection="sentinel-2-l2a",
        cloud_cover_max=20,
        limit=5,
    )

    for product in products:
        path = client.download(product)
        print(path)


if __name__ == "__main__":
    main()
