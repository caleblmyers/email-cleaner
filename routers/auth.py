from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

import gmail_client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    auth_url, state = gmail_client.build_auth_url()
    request.session["oauth_state"] = state
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(url="/?error=" + error)

    stored_state = request.session.get("oauth_state")
    if stored_state and stored_state != state:
        return RedirectResponse(url="/?error=state_mismatch")

    gmail_client.exchange_code(code)
    request.session["logged_in"] = True
    request.session.pop("oauth_state", None)
    return RedirectResponse(url="/dashboard")


@router.get("/logout")
async def logout(request: Request):
    gmail_client.logout()
    request.session.clear()
    return RedirectResponse(url="/")
