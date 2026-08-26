# Contributing to cdse-client

Thanks for contributing!

## Reporting bugs

Check the existing issues first. When opening one, include:

- A clear and descriptive title
- Steps to reproduce
- What you expected, and what actually happened
- Python version and OS
- The full traceback

Security vulnerabilities go through [SECURITY.md](SECURITY.md) instead — not a public issue.

## Suggesting enhancements

Enhancement suggestions are tracked as GitHub issues. Say what you want to be able to do and
why the current API makes it awkward; that is more useful than a proposed signature.

## Development setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/cdse-client.git
cd cdse-client

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows (PowerShell): .\.venv\Scripts\Activate.ps1

# Fast loop: linting and the tests that need no optional dependencies
pip install -e ".[dev]"
```

### Running the whole test suite

`.[dev]` is enough for a quick loop, but it does **not** install rasterio, aiohttp, pandas,
geopandas or geopy — and the tests that need them skip silently rather than fail. That is
around 50 of them, covering `processing.py`, `async_client.py`, the dataframe converters and
geocoding. A green run against `.[dev]` alone does not mean you have tested a change to any of
those.

If you are touching them, install the extras too:

```bash
pip install -e ".[dev,processing,geo,dataframe,async]"
pytest
```

The count tells you which one you ran: around 136 tests with `.[dev]`, around 188 with the
extras.

## Before opening a pull request

CI runs five jobs, and passing `pytest` locally only satisfies one of them. Run all five:

```bash
ruff format --check src/ tests/     # lint job
ruff check src/ tests/              # lint job
pytest                              # test job (3.9 through 3.14 in CI)
bandit -r src -q                    # security job
mkdocs build --strict               # docs job, needs .[docs]
python -m build && twine check --strict dist/*   # build job
```

Two of these bite people:

- **bandit exits 1 on any finding**, not only high-severity ones. Its output prints a table by
  severity *and* a table by confidence, which are easy to confuse — read the severity one.
- **`mkdocs build --strict`** fails on a broken internal link, so a renamed page or a typo in a
  relative path turns the docs job red.

`ruff format src/ tests/` and `ruff check src/ tests/ --fix` will fix most lint findings for
you.

Type checking with `mypy src/cdse` is worth running but is not a CI gate.

## Pull requests

1. Fork the repository
2. Branch from `main` (`git checkout -b fix/short-description`)
3. Make your changes, with a test that fails before them and passes after
4. Run the checks above
5. Push and open a pull request against `main`

CI runs on pull requests targeting `main` and on pushes to `main` — so the matrix does not see
your work until the PR exists.

## Code style

- [Ruff](https://docs.astral.sh/ruff/) for formatting and linting; line length 100
- Google-style docstrings on every public function
- Type annotations on public signatures — the package ships `py.typed`
- New behaviour comes with a test

## Commit messages

The history uses a `type: summary` first line — `fix:`, `docs:`, `ci:`, `test:`, `release:`,
optionally scoped as `fix(processing):`. Keep that first line under 72 characters, in the
imperative ("Add feature", not "Added feature").

The body is where the value is: say what the behaviour was, what it is now, and why the change
is shaped the way it is. Reference issues and pull requests where relevant.

## Where the project's state is written down

- [CHANGELOG.md](CHANGELOG.md) — what changed in each release
- [docs/audit.md](docs/audit.md) — known defects, fixed and open, and the reasoning behind each
  fix. Worth a look before starting on something: it may already be described there.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
