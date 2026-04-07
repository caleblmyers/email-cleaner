# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **SvelteKit SPA frontend** with Svelte 5 runes, shadcn-svelte components, Tailwind CSS, and TypeScript
- **Dynamic category management** — categories stored in DB, not hardcoded; CRUD API with descriptor items that guide the AI classifier
- **Gmail label management** — create, rename, delete Gmail labels from the UI
- **Nested grouping** — group emails by two dimensions (e.g., labels then sender domain)
- **Label name resolution** — Gmail label IDs resolved to display names, system labels filtered out, "Unlabelled" group for emails with no user labels
- **Dashboard JSON API** (`/emails/dashboard`) — single endpoint returning all dashboard data for the SPA
- **Subgroup API** (`/emails/subgroup`) — endpoint for fetching emails within nested groups
- Typed API client (`frontend/src/lib/api/client.ts`) wrapping all backend endpoints
- Reactive Svelte stores for selection state, toast notifications, and loading overlay
- shadcn-svelte UI components: Button, Dialog, Table, Badge, Card, Checkbox, Input, Select
- svelte-sonner for toast notifications
- lucide-svelte for icons
- Root `package.json` with `npm run dev` (concurrent backend + frontend), `npm run build`, `npm run start`
- `CLAUDE.md` project knowledge file for AI-assisted development
- Structured logging with configurable `LOG_LEVEL`
- Rate limiting on fetch/classify endpoints (10/minute)
- Input validation: email IDs verified against local DB before Gmail API calls
- Session timeout via `SESSION_MAX_AGE`
- Gmail Batch API for faster message fetching (with sequential fallback)
- Confirmation dialog with type-to-confirm for large batch actions (100+)
- Keyboard shortcuts: `Ctrl+A` select all, `Escape` close dialog/clear selection
- Comprehensive test suite
- Docker support and production deployment configs
- CI/CD GitHub Actions workflow

### Changed
- AI classifier prompt built dynamically from DB categories instead of hardcoded
- All grouping functions accept pre-fetched email lists for composability
- Backend API routes return JSON only (HTML template endpoints removed)
- Bulk actions use single DB connection instead of opening multiple
- Duplicate Pydantic validators consolidated into shared function

### Removed
- Jinja2 templates (`templates/` directory)
- HTMX and Pico CSS dependencies
- Vanilla JS frontend (`static/app.js`, `static/style.css`)
- `routers/dashboard.py` (server-rendered HTML dashboard)
- Hardcoded `config.CATEGORIES` list (replaced by DB-driven categories)

### Fixed
- Classify endpoint correctly filters by provided email IDs
- `batch_get_messages` reports skipped messages instead of silently ignoring errors
