# Contributing to cdse-client

First off, thank you for considering contributing to cdse-client! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- A clear and descriptive title
- Steps to reproduce the behavior
- Expected behavior
- Actual behavior
- Python version and OS
- Full error traceback

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- Use a clear and descriptive title
- Provide a detailed description of the suggested enhancement
- Explain why this enhancement would be useful

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linters (`black src tests` and `ruff check src tests`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/cdse-client.git
cd cdse-client

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
ruff check src tests --fix
```

## Code Style

- We use [Black](https://black.readthedocs.io/) for code formatting
- We use [Ruff](https://docs.astral.sh/ruff/) for linting
- We use [mypy](https://mypy.readthedocs.io/) for type checking
- All public functions must have docstrings (Google style)
- All new features must have tests

## Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep the first line under 72 characters
- Reference issues and pull requests when relevant

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
