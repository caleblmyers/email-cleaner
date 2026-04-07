# Contributing to Email Cleaner

## Development Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd email-cleaner
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. Run the app:
   ```bash
   python main.py
   ```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration is in `pyproject.toml`.

```bash
# Check for lint errors
ruff check .

# Auto-fix lint errors
ruff check --fix .

# Format code
ruff format .

# Check formatting without changes
ruff format --check .
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_database.py -v

# Run with coverage (install pytest-cov first)
python -m pytest tests/ --cov=. --cov-report=term-missing
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `routers/` | FastAPI route handlers |
| `templates/` | Jinja2 HTML templates |
| `static/` | CSS and JavaScript |
| `tests/` | Pytest test suite |
| `deploy/` | Production deployment configs |
| `docs/` | Architecture documentation |

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes with clear, atomic commits.
3. Ensure all tests pass: `python -m pytest tests/ -v`
4. Ensure linting passes: `ruff check .`
5. Update documentation if your changes affect the API or user-facing behavior.
6. Open a pull request with a clear description of the changes and why they were made.

## Conventions

- **Python**: Follow PEP 8 (enforced by Ruff). Use type hints for function signatures.
- **Tests**: Each module has a corresponding test file in `tests/`. Use `pytest` fixtures for shared setup.
- **Commits**: Use clear, descriptive commit messages. Prefix with the area of change (e.g., "fix(classify): filter by email IDs").
- **Docstrings**: All public functions and modules should have docstrings.
