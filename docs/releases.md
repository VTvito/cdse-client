# Release Notes

## Version 1.1.0 (2026-08-26)

Fourteen correctness defects, found by a full screening of the source and each covered by a
regression test. No public API is added or removed. Upgrading is `pip install --upgrade
cdse-client`, but two behaviours changed — read the first one if you use the processing
module.

### Python 3.14

3.14 is now part of the tested matrix, alongside 3.9 through 3.13. The minimum stays 3.9.

### Band extraction now refuses a request it cannot satisfy

`extract_bands_from_safe` used to return only the bands it happened to find, saying nothing
about the rest. That ended two ways, both wrong: `stack_bands` raised a bare `KeyError`, or —
with no explicit `band_order` — quietly wrote a stack with fewer bands than you asked for.

It now validates the request against `SENTINEL2_BANDS` before opening the product and raises
`ValidationError` for an unknown band, an unsupported resolution, or a band coarser than the
resolution you asked for. The message says which resolution to ask for instead.

**If you relied on the partial dictionary, you will see the difference.**

The check applies to L2A, the product level that ships the resampled 10 m / 20 m / 60 m
copies. In particular, the `agriculture`, `vegetation` and `all_20m` entries of
`BAND_COMBINATIONS` need `resolution=20` — at the default `resolution=10` they now fail with
a message saying so instead of a `KeyError`. See the
[processing guide](user-guide/processing.md) for which bands exist at which resolution.

### L1C products work

The ZIP extractor filtered entry names on the `R{resolution}m` folder, which L1C products do
not have — their images sit directly in `IMG_DATA`. It found nothing and reported "no bands
found" for a product that contained every band requested. L1C is one of the six supported
collections, and CDSE delivers ZIPs, so this affected every L1C processing call.

### Searches return the number of products you asked for

`limit` was handed to the server and applied *before* the cloud-cover and center-point
filters ran locally, so those filters ate into the count and a search could come back with
fewer products than were available. Searches are now paginated until the limit is satisfied.

### Downloads no longer keep corrupt files

A download cut short mid-transfer was recorded as successful, and the short file was then
skipped by the already-downloaded check on every later run — so the corruption was permanent
and invisible. Sizes are now verified and short files discarded.

### Also fixed

- Tokens are refreshed in the sync catalog and during async batches; searches and long
  download runs no longer die about ten minutes in.
- Interrupted async downloads clean up their partial files.
- Async and sync searches return the same results.
- The CLI exits non-zero when nothing was downloaded, and reports `ValidationError` as a
  message rather than a traceback.
- `max_retries=0` performs one attempt instead of raising `UnboundLocalError`.
- Download-URL resolution errors are reported instead of being swallowed.
- No pointless sleep after the final retry; streamed responses are closed between retries.

## Version 1.0.0 (2026-08-23) 🎉 First Stable Release

The public API has been unchanged since 0.3.0. There are **no breaking changes** relative to
0.4.0 — upgrading is a drop-in `pip install --upgrade cdse-client`. The 1.0 number states
that the API is stable and from now on follows semantic versioning.

### What changed

This release is about the project's presentation rather than its code:

- The README, the PyPI summary and this documentation site now lead with what the library
  does. The comparison with `sentinelsat` moved to a dedicated
  [migration guide](migration.md).
- The README shrank from 352 to about 125 lines: the API catalogue it carried duplicated
  this site, so it now links here instead.
- `Development Status` is now `5 - Production/Stable`, and the package declares
  `Typing :: Typed` and `Environment :: Console`.
- The version number is single-sourced from `cdse.__version__`.

### Fixed

- The `calculate_ndvi` example in the [processing guide](user-guide/processing.md) was
  missing the required `output_path` argument and raised `TypeError` as written.
- The README no longer claims `.env` files are loaded automatically — they are not; set
  `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` in the environment, or pass them to
  `CDSEClient()` directly.

### Removed

- The 2.7 MB `notebooks/test_cdse_client.ipynb`, which was unreferenced, still labelled
  v0.3.0, and accounted for 92% of the repository's tracked bytes. Everything it covered
  lives in the [user guide](user-guide/search.md) and in the runnable `examples/` scripts.
- The unused Read the Docs configuration; documentation is published here, on GitHub Pages.

---

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
