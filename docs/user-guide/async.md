# Async (optional)

Install:

```bash
pip install cdse-client[async]
```

## Async client

```python
import asyncio
from cdse import CDSEClientAsync

async def main():
    async with CDSEClientAsync() as client:
        products = await client.search(
            bbox=[9.10, 45.40, 9.28, 45.52],
            start_date="2025-06-01",
            end_date="2025-06-30",
            collection="sentinel-2-l2a",
            cloud_cover_max=30,
            limit=3,
        )
        # WARNING: downloads can be large
        # paths = await client.download_all(products)

asyncio.run(main())
```
