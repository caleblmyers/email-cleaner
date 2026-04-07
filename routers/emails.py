"""Email management endpoints: fetch, classify, list, and bulk actions."""

import json
import os
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

import ai_classifier
import config
import database
import gmail_client

log = config.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/emails", tags=["emails"])


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

def _validate_non_empty_ids(v: list[str]) -> list[str]:
    if not v:
        raise ValueError("email_ids must not be empty")
    return v


class FetchRequest(BaseModel):
    max_results: int = Field(default=config.EMAILS_PER_PAGE, ge=1, le=500)
    page_token: Optional[str] = None
    fetch_all: bool = False


class ClassifyRequest(BaseModel):
    email_ids: Optional[list[str]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=500)


class ActionRequest(BaseModel):
    email_ids: list[str] = Field(min_length=1)
    _val = field_validator("email_ids")(_validate_non_empty_ids)


class MoveRequest(BaseModel):
    email_ids: list[str] = Field(min_length=1)
    label_id: str = Field(min_length=1)
    _val = field_validator("email_ids")(_validate_non_empty_ids)


class MarkRequest(BaseModel):
    email_ids: list[str] = Field(min_length=1)
    read: bool
    _val = field_validator("email_ids")(_validate_non_empty_ids)


class SaveRequest(BaseModel):
    email_ids: list[str] = Field(min_length=1)
    _val = field_validator("email_ids")(_validate_non_empty_ids)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_auth():
    if not gmail_client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


def _validate_email_ids(conn, email_ids: list[str]) -> list[str]:
    existing = database.get_emails_by_ids(conn, email_ids)
    existing_ids = {e["id"] for e in existing}
    invalid = [eid for eid in email_ids if eid not in existing_ids]
    if invalid:
        log.warning("Ignoring %d unknown email IDs", len(invalid))
    return [eid for eid in email_ids if eid in existing_ids]


def _get_gmail_label_info() -> tuple[dict[str, str], set[str]]:
    """Fetch Gmail labels and return (label_map, user_label_ids)."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    all_labels = gmail_client.get_labels(service)
    label_map = {lbl["id"]: lbl["name"] for lbl in all_labels}
    user_label_ids = {lbl["id"] for lbl in all_labels if lbl.get("type") == "user"}
    return label_map, user_label_ids


def _apply_grouping(emails: list[dict], group_by: str, conn=None) -> dict[str, list[dict]]:
    """Apply a grouping function, handling label/category special cases."""
    grouping_fn = database.GROUPING_FUNCTIONS[group_by]
    if group_by == "label":
        label_map, user_label_ids = _get_gmail_label_info()
        return grouping_fn(emails, label_map=label_map, user_label_ids=user_label_ids)
    elif group_by == "category":
        return grouping_fn(emails, conn=conn)
    else:
        return grouping_fn(emails)


def _fmt_emails(emails: list[dict]) -> list[dict]:
    """Add display-formatted fields to email dicts."""
    for e in emails:
        ts = e.get("date")
        if ts:
            d = datetime.fromtimestamp(ts)
            now = datetime.now()
            if d.date() == now.date():
                e["_date_fmt"] = d.strftime("%I:%M %p")
            elif d.year == now.year:
                e["_date_fmt"] = d.strftime("%b %d")
            else:
                e["_date_fmt"] = d.strftime("%b %d, %Y")
        else:
            e["_date_fmt"] = ""
        b = e.get("size_estimate") or 0
        e["_size_fmt"] = f"{b} B" if b < 1024 else f"{b // 1024} KB" if b < 1024 * 1024 else f"{b / (1024 * 1024):.1f} MB"
        e["_confidence_pct"] = int((e.get("confidence") or 0) * 100)
    return emails


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/fetch", summary="Fetch emails from Gmail")
@limiter.limit("10/minute")
async def fetch_emails(request: Request, body: FetchRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        total_fetched = 0
        all_skipped = []
        page_token = body.page_token or database.get_sync_cursor(conn)

        while True:
            log.info("Fetching emails (max_results=%d, page_token=%s)", body.max_results, bool(page_token))
            result = gmail_client.list_messages(service, page_token=page_token, max_results=body.max_results)
            stubs = result.get("messages", [])
            if not stubs:
                break

            messages, skipped = gmail_client.batch_get_messages(service, [s["id"] for s in stubs])
            database.upsert_emails(conn, messages)
            total_fetched += len(messages)
            all_skipped.extend(skipped)

            next_token = result.get("nextPageToken")
            database.set_sync_cursor(conn, next_token)

            if not body.fetch_all or not next_token:
                break
            page_token = next_token
            time.sleep(2)

        log.info("Fetched %d messages total (%d skipped)", total_fetched, len(all_skipped))
        resp = {"fetched": total_fetched, "next_page_token": next_token if not body.fetch_all else None}
        if all_skipped:
            resp["skipped"] = all_skipped
        return resp
    finally:
        conn.close()


@router.post("/classify", summary="Classify emails with AI")
@limiter.limit("10/minute")
async def classify_emails(request: Request, body: ClassifyRequest):
    _require_auth()
    conn = database.get_connection()
    try:
        if body.email_ids:
            emails = database.get_emails_by_ids(conn, body.email_ids)
        else:
            emails = database.get_unclassified_emails(conn, limit=body.limit or 500)

        if not emails:
            return {"classified": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "total_cost": 0}}

        log.info("Classifying %d emails", len(emails))
        output = ai_classifier.classify_emails(emails)
        for r in output["results"]:
            database.update_classification(conn, r["id"], r["category"], r["confidence"], r["reasoning"])
        database.insert_ai_usage(conn, len(output["results"]), output["usage"]["input_tokens"], output["usage"]["output_tokens"], output["usage"]["total_cost"])
        return {"classified": len(output["results"]), "usage": output["usage"]}
    finally:
        conn.close()


@router.get("/dashboard", summary="Get dashboard data")
async def get_dashboard_data(group_by: str = "category", then_by: Optional[str] = None):
    if group_by not in database.GROUPING_FUNCTIONS:
        group_by = "category"
    if then_by and (then_by not in database.GROUPING_FUNCTIONS or then_by == group_by):
        then_by = None

    conn = database.get_connection()
    try:
        emails = database._fetch_all_emails(conn)
        grouped = _apply_grouping(emails, group_by, conn=conn)
        stats = database.get_stats_for_groups(grouped)

        return {
            "stats": stats,
            "total": database.get_total_count(conn),
            "unclassified_count": conn.execute("SELECT COUNT(*) AS cnt FROM emails WHERE category IS NULL").fetchone()["cnt"],
            "ai_usage": database.get_ai_usage_summary(conn),
            "group_summaries": [{"name": n, "count": len(e)} for n, e in grouped.items() if e],
            "categories": database.get_categories(conn),
        }
    finally:
        conn.close()


@router.get("/group", summary="Get emails for a specific group")
async def get_group_emails(group_by: str = "category", group_name: str = ""):
    if group_by not in database.GROUPING_FUNCTIONS:
        raise HTTPException(status_code=400, detail="Invalid group_by value")
    conn = database.get_connection()
    try:
        emails = database._fetch_all_emails(conn)
        grouped = _apply_grouping(emails, group_by, conn=conn)
        result = grouped.get(group_name, [])
    finally:
        conn.close()
    return {"emails": _fmt_emails(result), "count": len(result)}


@router.get("/subgroup", summary="Get emails for a sub-group")
async def get_subgroup_emails(
    group_by: str = "category",
    group_name: str = "",
    then_by: str = "",
    subgroup_name: str = "",
):
    if group_by not in database.GROUPING_FUNCTIONS or then_by not in database.GROUPING_FUNCTIONS:
        raise HTTPException(status_code=400, detail="Invalid group_by or then_by value")

    conn = database.get_connection()
    try:
        # Get parent group
        all_emails = database._fetch_all_emails(conn)
        parent_grouped = _apply_grouping(all_emails, group_by, conn=conn)
        parent_emails = parent_grouped.get(group_name, [])
        # Sub-group
        sub_grouped = _apply_grouping(parent_emails, then_by, conn=conn)
        result = sub_grouped.get(subgroup_name, [])
    finally:
        conn.close()
    return {"emails": _fmt_emails(result), "count": len(result)}


@router.get("/stats", summary="Get email statistics")
async def get_stats():
    conn = database.get_connection()
    try:
        return database.get_stats(conn)
    finally:
        conn.close()


@router.get("/ai-usage", summary="Get AI usage summary")
async def get_ai_usage():
    conn = database.get_connection()
    try:
        return database.get_ai_usage_summary(conn)
    finally:
        conn.close()


@router.get("/labels", summary="List user-created Gmail labels")
async def get_labels():
    _require_auth()
    service = gmail_client.build_gmail_service()
    labels = gmail_client.get_labels(service)
    return [lbl for lbl in labels if lbl.get("type") == "user"]


@router.get("/", summary="List cached emails")
async def list_emails(category: Optional[str] = None, page: int = 1, per_page: int = 50):
    conn = database.get_connection()
    try:
        emails = database.get_emails_by_category(conn, category, page, per_page)
        return {"emails": emails, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------

@router.post("/actions/delete", summary="Delete emails")
async def delete_emails(body: ActionRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
        if not validated_ids:
            raise HTTPException(status_code=400, detail="No valid email IDs provided")
        log.info("Deleting %d emails", len(validated_ids))
        result = gmail_client.bulk_trash(service, validated_ids)
        if result["succeeded_ids"]:
            database.delete_emails(conn, result["succeeded_ids"])
        return result
    finally:
        conn.close()


@router.post("/actions/archive", summary="Archive emails")
async def archive_emails(body: ActionRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
        if not validated_ids:
            raise HTTPException(status_code=400, detail="No valid email IDs provided")
        log.info("Archiving %d emails", len(validated_ids))
        result = gmail_client.bulk_modify(service, validated_ids, remove_labels=["INBOX"])
        for mid in result["succeeded_ids"]:
            row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
            if row:
                ids = [lid for lid in json.loads(row["label_ids"] or "[]") if lid != "INBOX"]
                database.update_labels(conn, mid, ids)
        return result
    finally:
        conn.close()


@router.post("/actions/move", summary="Move emails to label")
async def move_emails(body: MoveRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
        if not validated_ids:
            raise HTTPException(status_code=400, detail="No valid email IDs provided")
        log.info("Moving %d emails to label %s", len(validated_ids), body.label_id)
        result = gmail_client.bulk_modify(service, validated_ids, add_labels=[body.label_id], remove_labels=["INBOX"])
        for mid in result["succeeded_ids"]:
            row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
            if row:
                ids = [lid for lid in json.loads(row["label_ids"] or "[]") if lid != "INBOX"]
                if body.label_id not in ids:
                    ids.append(body.label_id)
                database.update_labels(conn, mid, ids)
        return result
    finally:
        conn.close()


@router.post("/actions/mark", summary="Mark emails read/unread")
async def mark_emails(body: MarkRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
        if not validated_ids:
            raise HTTPException(status_code=400, detail="No valid email IDs provided")
        if body.read:
            result = gmail_client.bulk_modify(service, validated_ids, remove_labels=["UNREAD"])
        else:
            result = gmail_client.bulk_modify(service, validated_ids, add_labels=["UNREAD"])
        for mid in result["succeeded_ids"]:
            database.update_read_status(conn, mid, body.read)
        return result
    finally:
        conn.close()


@router.post("/actions/save", summary="Save emails to files")
async def save_emails(body: SaveRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
    finally:
        conn.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    os.makedirs(config.SAVE_DIR, exist_ok=True)

    saved, failed = [], []
    for msg_id in validated_ids:
        try:
            msg = gmail_client.get_message_full(service, msg_id)
            filename = _make_filename(msg)
            path = os.path.join(config.SAVE_DIR, filename)
            _write_email_file(path, msg)
            saved.append(msg_id)
        except Exception as e:
            failed.append({"id": msg_id, "error": str(e)})

    return {"success": len(saved), "failed": len(failed), "succeeded_ids": saved, "errors": failed, "saved_to": os.path.abspath(config.SAVE_DIR)}


def _make_filename(msg: dict) -> str:
    date_str = datetime.fromtimestamp(msg.get("date") or time.time()).strftime("%Y%m%d")
    sender = re.sub(r"[^\w.-]", "_", msg.get("sender_email", "unknown"))
    subject = re.sub(r"\s+", "_", re.sub(r"[^\w\s-]", "", msg.get("subject", "no_subject")).strip())[:50]
    return f"{date_str}_{sender}_{subject}.txt"


def _write_email_file(path: str, msg: dict):
    date_fmt = datetime.fromtimestamp(msg.get("date") or time.time()).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"From: {msg.get('sender', '')} <{msg.get('sender_email', '')}>",
        f"Date: {date_fmt}",
        f"Subject: {msg.get('subject', '')}",
        f"Category: {msg.get('category', 'Uncategorized')}",
        "-" * 60, "",
        msg.get("body", msg.get("snippet", "")),
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
