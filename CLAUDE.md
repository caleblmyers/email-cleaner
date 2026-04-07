# Email Cleaner

A web app that connects to Gmail, categorizes your inbox with Claude AI, and lets you bulk-manage emails. SvelteKit frontend, FastAPI backend, SQLite database.

## Stack

- **Frontend:** SvelteKit + Svelte 5 (runes), shadcn-svelte, Tailwind CSS, TypeScript
- **Backend:** FastAPI (Python), SQLite via raw `sqlite3`
- **AI:** Anthropic Claude (Haiku 4.5) for email classification
- **Gmail:** Google OAuth2 + Gmail API (`google-api-python-client`)
- **Dev tooling:** Vite (frontend), uvicorn (backend), concurrently (both)

## Dev Commands

```bash
npm run dev        # Start both FastAPI (:8000) and Vite dev server (:5173)
npm run build      # Build SvelteKit SPA to frontend/build/
npm run start      # Build + start FastAPI serving the SPA

# Backend only
source venv/bin/activate && python3 main.py

# Frontend only
cd frontend && npm run dev
```

## Architecture

### Backend (FastAPI)

```
main.py                  Entry point — mounts routers, serves SPA build
config.py                Env vars, constants, logging
database.py              SQLite schema, CRUD, grouping functions
ai_classifier.py         Claude API — dynamic prompt from DB categories
gmail_client.py          OAuth2, message fetch, bulk actions, label CRUD
routers/
  auth.py                /auth/* — OAuth2 login/callback/logout
  emails.py              /emails/* — fetch, classify, group, bulk actions, dashboard JSON
  categories.py          /categories/* — AI category CRUD + descriptor items
  labels.py              /labels/* — Gmail label CRUD
```

### Frontend (SvelteKit SPA)

```
frontend/src/
  routes/
    +page.svelte         Dashboard — overview, groups, bulk actions, dialogs
    login/+page.svelte   OAuth login page
  lib/
    api/client.ts        Typed API client wrapping all backend endpoints
    stores/              Svelte 5 reactive stores (selection, toast, loading)
    components/          App components (Toolbar, EmailTable, GroupSection, dialogs)
    components/ui/       shadcn-svelte primitives (Button, Dialog, Table, etc.)
```

### Data Flow

1. **Fetch:** Browser → FastAPI → Gmail API → SQLite cache
2. **Classify:** Browser → FastAPI → Claude AI (batches of 20) → SQLite
3. **Bulk actions:** Browser → FastAPI → Gmail API → SQLite update → SPA reload
4. **Dashboard:** Browser → `/emails/dashboard` JSON → SPA renders

### Key Design Decisions

- **Categories stored in DB**, not hardcoded — users can add/edit/remove, AI prompt is built dynamically
- **Gmail label IDs resolved to names** at display time, system labels filtered out, "Unlabelled" group for emails with no user labels
- **Nested grouping** — primary group (e.g., labels) with secondary sub-groups (e.g., senders within each label)
- **SPA served by FastAPI** — `frontend/build/` is served as static files with SPA fallback routing
- **All mutations trigger full dashboard reload** — simple and correct, avoids stale state

## Database Tables

- `emails` — cached Gmail messages with AI classification fields
- `categories` — user-defined classification labels with descriptions and colors
- `sync_state` — Gmail pagination cursor
- `ai_usage` — token counts and costs per classification run

## API Conventions

- All endpoints return JSON
- Bulk actions accept `{ email_ids: [...] }` and return `{ success, failed, succeeded_ids, errors }`
- Category descriptor items are stored as comma-separated text in the `description` field
- Gmail label operations go directly to the Gmail API (no local cache of labels)

## Interaction Style

- Use AskUserQuestion when requirements are ambiguous
- Caleb is learning Python and Svelte — frame explanations with JS/TS analogies when relevant
- Prefer simple, direct implementations over abstractions
