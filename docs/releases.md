# Release Notes

## Version 0.4.0 (2026-02-12) ⭐ Production Ready

**cdse-client 0.4.0** brings major production hardening with automatic token refresh, resilient retry logic, comprehensive logging, and critical bug fixes. This release is recommended for all production deployments.

### 🚀 Major Features

#### **Bearer Token Auto-Refresh**
Long-running downloads no longer fail due to token expiry. `OAuth2Auth.get_bearer_session()` now returns a `_BearerSession` that automatically refreshes the token before each HTTP request.

```python
from cdse import CDSEClient

client = CDSEClient()
# Downloads lasting hours work without manual token refresh
paths = client.download_all(products, parallel=True)
```

#### **Resilient Downloads with Exponential Backoff**
Transient errors (rate limits, gateway issues) are now automatically retried with exponential backoff.

- **Retryable status codes**: 429 (rate limit), 502, 503, 504 (server errors)
- **Default behavior**: up to 3 retries with exponential backoff (1s, 2s, 4s)
- **Configurable**: `Downloader(session, max_retries=5, timeout=120)`

#### **Explicit Request Timeouts**
All HTTP requests now have explicit 60-second timeouts by default, preventing indefinite hangs.

```python
# Timeout respected in search, download, and OData queries
downloader = CDSEClient().downloader  # 60s timeout
```

#### **Production Logging**
`print()` statements replaced with structured `logging` module throughout the library. Integrate with your logging configuration:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cdse")

client = CDSEClient()
client.search(...)  # Logs retries, token refresh, download progress
```

#### **Async Client Improvements**
The async client now auto-refreshes tokens and includes `tqdm` progress bars:

```python
import asyncio
from cdse import CDSEClientAsync

async def main():
    async with CDSEClientAsync() as client:
        # Auto-refresh on token expiry
        products = await client.search(...)
        # tqdm progress bars for download_all
        paths = await client.download_all(products, progress=True)

asyncio.run(main())
```

### 🔧 Bug Fixes

| Issue | Fix |
|-------|-----|
| **High-latitude searches failed** | `search_by_point()` now uses `cos(lat)` to correct longitude buffer at high latitudes |
| **`skip_existing` ignored** | Parameter now correctly forwarded in both sequential and parallel downloads |
| **Inline import** | `import json` moved to module-level in `catalog.py` |
| **README example broken** | `bbox_from_city` → `get_city_bbox` |

### 📦 Packaging

- **`black` removed** from dev dependencies (redundant with `ruff format`)
- **Documentation extras refined** — `mkdocs` now only in `[docs]` extra, not `[all]`
- All extras remain backward-compatible: `[geo]`, `[dataframe]`, `[async]`, `[processing]`

### ✅ Quality Assurance

- **102 tests** passing (all Python 3.9–3.13)
- **Lint & format** verified with ruff
- **Security scan** passed (bandit)
- **Type checking** enforced (mypy)
- **Package integrity** verified (twine)

### 📚 Documentation

New and updated guides:
- [Async downloads](./user-guide/async.md) — Concurrent downloads with auto-refresh token handling
- [Error handling](./faq.md#resilience) — Retry configuration and timeout settings
- [Logging setup](./getting-started.md#monitoring) — Integration with Python logging

### 🔄 Migration from 0.3.3

**All changes are backward-compatible.** No code changes required, but you can opt-in to new features:

```python
# Before: timeout hangs, token expiry breaks long downloads
client = CDSEClient()

# After: same API, but now with resilience built-in
client = CDSEClient()  # Same!
# - Auto-refresh tokens on expiry
# - Retry transient errors automatically  
# - Structured logging instead of print()
```

Optional parameter enhancements:

```python
# Customize retry behavior (new in v0.4.0)
downloader = CDSEClient(max_retries=5, timeout=120).downloader

# Skip existing files (now actually works!)
path = downloader.download(product, skip_existing=True)
```

### 📦 Installation

```bash
# Recommended: production-grade install
pip install 'cdse-client>=0.4.0'

# Or specific version
pip install 'cdse-client==0.4.0'

# With all extras
pip install 'cdse-client[all]==0.4.0'
```

### 🙏 Acknowledgments

- **Sentinelsat community** for demonstrating demand for CDSE tooling
- **Contributors** reporting issues and testing edge cases
- **Copernicus Data Space Ecosystem** team for stable APIs

---

**For detailed changes**, see [CHANGELOG](https://github.com/VTvito/cdse-client/blob/main/CHANGELOG.md) and [Release commits](https://github.com/VTvito/cdse-client/compare/v0.3.3...v0.4.0).
