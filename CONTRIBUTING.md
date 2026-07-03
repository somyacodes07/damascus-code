# Contributing to Damascus

First off, thank you for considering contributing to Damascus! It's people like you that make Damascus such a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](https://github.com/your-username/damascus/issues) if one already exists. If not, go ahead and create one!

## Development Setup

The project uses Python 3.12 and Poetry for dependency management.

### Backend

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Run the development server (or use Docker if preferred):
   ```bash
   poetry run uvicorn damascus.main:app --reload
   ```

### CLI

1. Navigate to the `cli` directory:
   ```bash
   cd cli
   ```
2. Install dependencies:
   ```bash
   poetry install
   ```

### Tests & Linting

We use `pytest` for testing and `ruff` for linting/formatting. Please ensure all tests pass and code is formatted before submitting a PR.

To run linting:
```bash
poetry run ruff check .
poetry run ruff format .
```

To run tests:
```bash
poetry run pytest
```

## Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Code of Conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
