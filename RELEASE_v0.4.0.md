# cdse-client v0.4.0 Release

**Production Ready** — Hardened downloads with automatic token refresh, resilient retries, and comprehensive logging.

## ⭐ What's New

### 🔐 Bearer Token Auto-Refresh (NEW)
Long-running downloads no longer fail due to token expiry. The OAuth2 session now automatically refreshes before each request:

```python
from cdse import CDSEClient
client = CDSEClient()
# Hours-long parallel downloads work without manual token refresh!
paths = client.download_all(products, parallel=True)
```

### 🛡️ Resilient Downloads (NEW)
Automatic retry with exponential backoff for transient errors (429, 502, 503, 504):

```python
# Configure retry behavior
from cdse import Downloader
downloader = Downloader(session, max_retries=5, timeout=120)
path = downloader.download(product)  # Auto-retries on failures
```

### ⏱️ Explicit Timeouts (IMPROVED)
All HTTP requests now have 60-second timeouts, preventing indefinite hangs:
- STAC search requests
- OData queries  
- Product downloads

### 📝 Production Logging (IMPROVED)
Library now uses structured logging instead of `print()` — integrate with your logging setup:

```python
import logging
logging.basicConfig(level=logging.INFO)
client = CDSEClient()
client.search(...)  # Logs retries, token refresh, download progress
```

### 🚀 Async Improvements (IMPROVED)
- Auto-refresh tokens on expiry
- `tqdm` progress bars for `download()` and `download_all()`

```python
from cdse import CDSEClientAsync
async with CDSEClientAsync() as client:
    products = await client.search(...)
    paths = await client.download_all(products, progress=True)
```

## 🔧 Bugs Fixed

| Issue | Resolution |
|-------|-----------|
| High-latitude searches failed | `search_by_point()` now uses cos(lat) for longitude buffer |
| `skip_existing` ignored | Parameter now forwarded in sequential AND parallel downloads |
| Inline `import json` | Moved to module-level imports |
| README example broken | `bbox_from_city` → `get_city_bbox` |

## 📦 Install

```bash
# Core library
pip install cdse-client==0.4.0

# With all extras
pip install cdse-client[all]==0.4.0

# With async support
pip install cdse-client[async]==0.4.0
```

## 📚 Docs

- [Release notes](https://vtvito.github.io/cdse-client/releases/) — Full feature overview
- [Getting started](https://vtvito.github.io/cdse-client/getting-started/) — Setup and credentials
- [Async guide](https://vtvito.github.io/cdse-client/user-guide/async/) — Concurrent downloads
- [API reference](https://vtvito.github.io/cdse-client/reference/client/) — Full API docs

## ✅ Testing

- **102 tests** passing across Python 3.9–3.13
- Lint, format, security scan, typing all verified
- Package integrity validated (twine)

## 🔄 Migration from v0.3.3

**Fully backward-compatible** — No code changes required. All improvements are automatic:

```python
# Same code as v0.3.3, but now with:
client = CDSEClient()
# ✅ Auto-refresh tokens
# ✅ Retry transient errors  
# ✅ Explicit timeouts
# ✅ Structured logging
```

## 📝 Detailed Changelog

[Full CHANGELOG →](https://github.com/VTvito/cdse-client/blob/main/CHANGELOG.md#040---2026-02-12)

[Release diff →](https://github.com/VTvito/cdse-client/compare/v0.3.3...v0.4.0)

---

**Questions?** Open an [issue](https://github.com/VTvito/cdse-client/issues) or check [FAQ](https://vtvito.github.io/cdse-client/faq/).
