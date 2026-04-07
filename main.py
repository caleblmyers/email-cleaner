"""Email Cleaner application entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

import config
import database
from routers import auth, categories, dashboard, emails, labels

log = config.get_logger(__name__)

app = FastAPI(title="Email Cleaner")

app.state.limiter = emails.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    max_age=config.SESSION_MAX_AGE,
)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(labels.router)
app.include_router(emails.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def startup():
    log.info("Starting Email Cleaner on port %d", config.APP_PORT)
    database.init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=config.APP_PORT, reload=True)
