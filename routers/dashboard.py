"""Dashboard and login page routes (server-rendered HTML)."""


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
async def dashboard(request: Request, group_by: str = "category"):
    if not gmail_client.is_authenticated():
        return RedirectResponse(url="/login")

    if group_by not in database.GROUPING_FUNCTIONS:
        group_by = "category"

    conn = database.get_connection()
    try:
        # Fetch Gmail labels (needed for label grouping and move-to dropdown)
        all_gmail_labels = []
        try:
            service = gmail_client.build_gmail_service()
            all_gmail_labels = gmail_client.get_labels(service)
        except Exception:
            pass

        if group_by == "label":
            label_map = {lbl["id"]: lbl["name"] for lbl in all_gmail_labels}
            grouped = database.group_by_label(conn, label_map)
        else:
            grouping_fn = database.GROUPING_FUNCTIONS[group_by]
            grouped = grouping_fn(conn)

        stats = database.get_stats_for_groups(grouped)
        total = database.get_total_count(conn)
        unclassified_count = conn.execute("SELECT COUNT(*) AS cnt FROM emails WHERE category IS NULL").fetchone()["cnt"]
        ai_usage = database.get_ai_usage_summary(conn)
        user_categories = database.get_categories(conn)
        labels = [lbl for lbl in all_gmail_labels if lbl.get("type") == "user"]
    finally:
        conn.close()

    # Build group summaries (name + count only, no email data)
    group_summaries = [
        {"name": name, "count": len(emails)}
        for name, emails in grouped.items()
        if emails
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "total": total,
            "unclassified_count": unclassified_count,
            "ai_usage": ai_usage,
            "labels": labels,
            "group_summaries": group_summaries,
            "group_by": group_by,
            "group_modes": GROUP_MODE_LABELS,
            "user_categories": user_categories,
        },
    )
