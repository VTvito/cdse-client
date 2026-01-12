# Release checklist

This page is a practical checklist to get `cdse-client` ready for a clean PyPI release.

## Before you tag

- Version bump
  - Update `__version__` in `src/cdse/__init__.py`.
  - Update `version` in `pyproject.toml`.
  - Add a new entry to `CHANGELOG.md`.

- Quality gates (local)
  - Run tests: `pytest -q`
  - Run lint + format: `ruff format src/ tests/ && ruff check src/ tests/`
  - Optional typing: `mypy src/cdse`
  - Security scan: `bandit -r src -q`

- Packaging
  - Build: `python -m build`
  - Verify metadata: `twine check dist/*`

## CI / automation expectations

- CI runs on PRs and pushes:
  - Ruff format check + lint
  - pytest (Python 3.9–3.13)
  - MkDocs build in strict mode
  - Bandit scan
  - Build + `twine check`

## GitHub Pages (docs)

If you use the provided workflow, set repository Pages to build from GitHub Actions.

- GitHub repo settings → **Pages** → **Build and deployment** → **Source**: GitHub Actions
- Push to `main` to trigger docs deployment

## PyPI Trusted Publishing (OIDC)

The workflow publishes on tags matching `v*`.

One-time setup on PyPI:

- Create (or open) the project on PyPI.
- Add a **Trusted Publisher** for this GitHub repository.
  - Provider: GitHub Actions
  - Repository: `<owner>/<repo>`
  - Workflow: `.github/workflows/publish.yml`
  - Environment: (leave empty unless you explicitly use one)

Then release by tagging:

- `git tag vX.Y.Z`
- `git push --tags`

## After you tag

- Verify on PyPI
  - Project page renders correctly.
  - Wheels + sdist are present.
  - `pip install cdse-client` works on a clean env.

- Verify docs
  - The GitHub Pages site updates successfully.
  - `mkdocs build --strict` stays green in CI.
