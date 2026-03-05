from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import time

import database
import gmail_client

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="templates")


def _fmt_date(ts):
    if not ts:
        return ""
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%I:%M %p")
    elif dt.year == now.year:
        return dt.strftime("%b %d")
    return dt.strftime("%b %d, %Y")


def _fmt_size(bytes_val):
    if not bytes_val:
        return ""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val // 1024} KB"
    return f"{bytes_val / (1024 * 1024):.1f} MB"


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not gmail_client.is_authenticated():
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error},
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not gmail_client.is_authenticated():
        return RedirectResponse(url="/login")

    conn = database.get_connection()
    try:
        grouped = database.get_all_emails_grouped(conn)
        stats = database.get_stats(conn)
        total = database.get_total_count(conn)
        labels = []
        try:
            service = gmail_client.build_gmail_service()
            labels = gmail_client.get_labels(service)
            # Filter to user-created labels only for the "move to" dropdown
            labels = [l for l in labels if l.get("type") == "user"]
        except Exception:
            pass
    finally:
        conn.close()

    # Add display helpers to each email
    import config
    for cat in config.CATEGORIES:
        for email in grouped.get(cat, []):
            email["_date_fmt"] = _fmt_date(email.get("date"))
            email["_size_fmt"] = _fmt_size(email.get("size_estimate"))
            email["_confidence_pct"] = int((email.get("confidence") or 0) * 100)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "grouped": grouped,
            "stats": stats,
            "total": total,
            "labels": labels,
            "categories": config.CATEGORIES,
        },
    )
