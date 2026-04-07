"""Dashboard and login page routes (server-rendered HTML)."""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

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


GROUP_MODE_LABELS = {
    "category": "AI Category",
    "sender": "Sender Domain",
    "date": "Date Range",
    "read_status": "Read / Unread",
    "size": "Size",
    "label": "Labels",
    "frequency": "Top Senders",
}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    group_by: str = "category",
    then_by: Optional[str] = None,
):
    if not gmail_client.is_authenticated():
        return RedirectResponse(url="/login")

    if group_by not in database.GROUPING_FUNCTIONS:
        group_by = "category"
    if then_by and then_by not in database.GROUPING_FUNCTIONS:
        then_by = None
    if then_by == group_by:
        then_by = None

    conn = database.get_connection()
    try:
        # Fetch Gmail labels
        all_gmail_labels = []
        try:
            service = gmail_client.build_gmail_service()
            all_gmail_labels = gmail_client.get_labels(service)
        except Exception:
            pass

        label_map = {lbl["id"]: lbl["name"] for lbl in all_gmail_labels}
        user_labels = [lbl for lbl in all_gmail_labels if lbl.get("type") == "user"]

        # Fetch all emails and group
        emails = database._fetch_all_emails(conn)
        grouping_fn = database.GROUPING_FUNCTIONS[group_by]
        user_label_ids = {lbl["id"] for lbl in user_labels}
        if group_by == "label":
            grouped = grouping_fn(emails, label_map=label_map, user_label_ids=user_label_ids)
        elif group_by == "category":
            grouped = grouping_fn(emails, conn=conn)
        else:
            grouped = grouping_fn(emails)

        stats = database.get_stats_for_groups(grouped)
        total = database.get_total_count(conn)
        unclassified_count = conn.execute("SELECT COUNT(*) AS cnt FROM emails WHERE category IS NULL").fetchone()["cnt"]
        ai_usage = database.get_ai_usage_summary(conn)
        user_categories = database.get_categories(conn)
    finally:
        conn.close()

    # Build group summaries
    group_summaries = [
        {"name": name, "count": len(group_emails)}
        for name, group_emails in grouped.items()
        if group_emails
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "total": total,
            "unclassified_count": unclassified_count,
            "ai_usage": ai_usage,
            "labels": user_labels,
            "group_summaries": group_summaries,
            "group_by": group_by,
            "then_by": then_by or "",
            "group_modes": GROUP_MODE_LABELS,
            "user_categories": user_categories,
        },
    )
