import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import config
import database
from routers import auth, dashboard, emails

app = FastAPI(title="Email Cleaner")

app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def startup():
    database.init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=config.APP_PORT, reload=True)
