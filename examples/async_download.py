"""Async downloads example.

Requires:
  pip install cdse-client[async]

Auth:
  Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET.
"""

import asyncio

from cdse import CDSEClientAsync


async def main() -> None:
    async with CDSEClientAsync(output_dir="./downloads", max_concurrent=3) as client:
        products = await client.search(
            bbox=[9.0, 45.0, 9.5, 45.5],
            start_date="2024-01-01",
            end_date="2024-01-31",
            collection="sentinel-2-l2a",
            limit=10,
        )

        paths = await client.download_all(products)
        for path in paths:
            print(path)


if __name__ == "__main__":
    asyncio.run(main())
