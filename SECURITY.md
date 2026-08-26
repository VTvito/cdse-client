# Security Policy

## Supported versions

Fixes go into the **latest release line**. The current one is on
[PyPI](https://pypi.org/project/cdse-client/) and in
[the releases](https://github.com/VTvito/cdse-client/releases); the public API has been stable
since 0.3.0, so upgrading is a drop-in `pip install --upgrade cdse-client`.

Older lines are not backported. This is stated as a policy rather than a version table on
purpose: a table has to be edited on every release, and the one this file used to carry sat at
`0.3.x` long after that stopped being true.

## Reporting a vulnerability

**Do not open a public issue.** Use one of these instead:

1. [Report a vulnerability privately](https://github.com/VTvito/cdse-client/security/advisories/new)
   through GitHub. This is the preferred route: it gives you a tracked, private thread and lets
   the fix be prepared without disclosing it first.
2. Failing that, email 75219756+VTvito@users.noreply.github.com.

Please include what you found, how to reproduce it, what an attacker gets out of it, and — if
you have one — a suggested fix.

## What to expect

This is a single-maintainer project worked on outside of a job, so what follows is an honest
description rather than a service commitment: reports are usually acknowledged within a week,
and a fix for something exploitable is prioritised over everything else in the queue.

If two weeks pass with no reply at all, open a public issue saying only that you are waiting on
a security report — no details — so it is visible that one is outstanding.

Credit is given in the release notes unless you would rather it were not.

## Scope

In scope: anything in this library that mishandles your credentials, weakens the transport to
CDSE, writes outside the directory you asked it to write to, or executes data it should only be
parsing.

Out of scope: the Copernicus Data Space Ecosystem service itself, and the contents of the
products it serves. Those belong to [CDSE](https://dataspace.copernicus.eu/), not here.

## For users

1. **Never commit credentials.** Use the `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` environment
   variables.
2. **Use a `.env` file** kept out of version control for local development.
3. **Rotate credentials** periodically in your CDSE account.
4. **Keep the package current**: `pip install --upgrade cdse-client`.

## Dependencies

The required dependency set is deliberately small:

- `requests` — HTTP, with TLS
- `requests-oauthlib` and `oauthlib` — OAuth2 client-credentials flow
- `tqdm` — progress bars, no network access
- `python-dateutil` — timestamp parsing

Everything else — rasterio, shapely, geopandas, pandas, aiohttp, matplotlib — lives behind an
optional extra and is imported lazily, inside the functions that need it. Installing the base
package does not pull them in, and not calling those functions does not load them.
