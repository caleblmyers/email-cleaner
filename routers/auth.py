"""OAuth2 authentication routes for Google/Gmail login."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

import config
import gmail_client

log = config.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", summary="Start OAuth2 login")
async def login(request: Request):
    """Redirect the user to Google's OAuth2 consent screen."""
    auth_url, state = gmail_client.build_auth_url()
    request.session["oauth_state"] = state
    return RedirectResponse(url=auth_url)


@router.get("/callback", summary="OAuth2 callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Handle the OAuth2 callback from Google after user consent."""
    if error:
        log.warning("OAuth callback error: %s", error)
        return RedirectResponse(url="/?error=" + error)

    stored_state = request.session.get("oauth_state")
    if stored_state and stored_state != state:
        log.warning("OAuth state mismatch")
        return RedirectResponse(url="/?error=state_mismatch")

    gmail_client.exchange_code(code)
    request.session["logged_in"] = True
    request.session.pop("oauth_state", None)
    log.info("User authenticated successfully")
    return RedirectResponse(url="/dashboard")


@router.get("/logout", summary="Log out")
async def logout(request: Request):
    """Clear tokens and session, redirecting to the home page."""
    log.info("User logged out")
    gmail_client.logout()
    request.session.clear()
    return RedirectResponse(url="/")
