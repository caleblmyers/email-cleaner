"""Email Cleaner application entry point."""

import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

import config
import database
from routers import auth, categories, emails, labels

log = config.get_logger(__name__)

app = FastAPI(title="Email Cleaner")

app.state.limiter = emails.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    max_age=config.SESSION_MAX_AGE,
)

# API routers
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(labels.router)
app.include_router(emails.router)

# Serve SvelteKit build if it exists, fall back to old static dir
SPA_DIR = os.path.join(os.path.dirname(__file__), "frontend", "build")
if os.path.isdir(SPA_DIR):
    app.mount("/_app", StaticFiles(directory=os.path.join(SPA_DIR, "_app")), name="spa-assets")

    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """Serve SvelteKit SPA — try static file first, fall back to index.html."""
        file_path = os.path.join(SPA_DIR, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(SPA_DIR, "index.html"))
else:
    log.warning("SvelteKit build not found at %s — run 'npm run build' in frontend/", SPA_DIR)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    # Keep old Jinja2 dashboard as fallback
    from routers import dashboard
    app.include_router(dashboard.router)


@app.on_event("startup")
async def startup():
    log.info("Starting Email Cleaner on port %d", config.APP_PORT)
    database.init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=config.APP_PORT, reload=True)
