# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Structured logging with configurable `LOG_LEVEL` environment variable
- Rate limiting on `/emails/fetch` and `/emails/classify` endpoints (10/minute)
- Input validation: email IDs verified against local DB before Gmail API calls
- Pydantic field validators for all request models (non-empty checks)
- Session timeout via `SESSION_MAX_AGE` configuration
- Gmail Batch API for faster message fetching (with sequential fallback)
- Confirmation dialog before bulk delete actions
- Keyboard shortcuts: `Ctrl+A` to select all, `Escape` to clear selection/close modals
- Client-side pagination for large category sections (50 emails per page)
- Empty state message when emails are fetched but not yet categorized
- Comprehensive test suite: 83 tests covering database, classifier, Gmail client, and routers
- Docker support: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Production deployment: Caddy reverse proxy config, production compose file, backup script
- CI/CD: GitHub Actions workflow for linting, testing, and Docker build
- API documentation: Pydantic response models, endpoint summaries, and docstrings for OpenAPI
- Architecture documentation (`docs/ARCHITECTURE.md`) with data flow diagrams and schema reference
- `CONTRIBUTING.md` with development setup and code style guidelines
- `pyproject.toml` with Ruff and pytest configuration

### Fixed
- Classify endpoint now correctly filters by provided email IDs instead of loading all emails
- `batch_get_messages` now reports skipped messages instead of silently ignoring errors

### Changed
- `batch_get_messages` returns `(results, skipped)` tuple instead of just results
- All modules now use structured logging instead of implicit print statements
