"""OAuth2 authentication routes for Google/Gmail login."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

import config
import database
import gmail_client

log = config.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _frontend_url(request: Request, path: str) -> str:
    """Build a redirect URL that goes back to the frontend origin.
    In dev, Vite proxies API calls from :5173 → :8000, so the Referer/Origin
    header or saved session origin tells us where the browser actually is."""
    origin = request.session.get("frontend_origin", "")
    if not origin:
        referer = request.headers.get("referer", "")
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin:
        return f"{origin}{path}"
    return path


@router.get("/login", summary="Start OAuth2 login")
async def login(request: Request):
    """Redirect the user to Google's OAuth2 consent screen."""
    auth_url, state = gmail_client.build_auth_url()
    request.session["oauth_state"] = state
    request.session["frontend_origin"] = _frontend_url(request, "")
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
    return RedirectResponse(url=_frontend_url(request, "/"))


@router.get("/logout", summary="Log out")
async def logout(request: Request):
    """Clear tokens and session, redirecting to login."""
    log.info("User logged out — clearing local cache")
    gmail_client.logout()
    request.session.clear()
    conn = database.get_connection()
    try:
        conn.executescript("""
            DELETE FROM emails;
            DELETE FROM sync_state;
        """)
    finally:
        conn.close()
    return RedirectResponse(url=_frontend_url(request, "/login"))
