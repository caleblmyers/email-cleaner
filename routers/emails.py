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

class FetchRequest(BaseModel):
    """Parameters for fetching emails from Gmail."""
    max_results: int = Field(default=config.EMAILS_PER_PAGE, ge=1, le=500, description="Max emails to fetch per page")
    page_token: Optional[str] = Field(default=None, description="Gmail pagination token")
    fetch_all: bool = Field(default=False, description="Fetch all emails by paginating through the entire inbox")


class FetchResponse(BaseModel):
    """Result of a fetch operation."""
    fetched: int = Field(description="Number of emails fetched")
    next_page_token: Optional[str] = Field(description="Token for fetching the next page")
    skipped: Optional[list[dict]] = Field(default=None, description="Messages that failed to fetch")


class ClassifyRequest(BaseModel):
    """Parameters for classifying emails. Omit email_ids to classify all unclassified."""
    email_ids: Optional[list[str]] = Field(default=None, description="Specific email IDs to classify (omit for all unclassified)")
    limit: Optional[int] = Field(default=None, ge=1, le=500, description="Max unclassified emails to classify (ignored if email_ids is set)")


class UsageInfo(BaseModel):
    """Token usage and cost from AI classification."""
    input_tokens: int = Field(description="Input tokens consumed")
    output_tokens: int = Field(description="Output tokens consumed")
    total_cost: float = Field(description="Estimated cost in USD")


class ClassifyResponse(BaseModel):
    """Result of a classification operation."""
    classified: int = Field(description="Number of emails classified")
    usage: UsageInfo = Field(description="AI token usage and cost")


class ActionRequest(BaseModel):
    """Request body for delete and archive actions."""
    email_ids: list[str] = Field(min_length=1, description="Email IDs to act on")

    @field_validator("email_ids")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("email_ids must not be empty")
        return v


class MoveRequest(BaseModel):
    """Request body for moving emails to a label."""
    email_ids: list[str] = Field(min_length=1, description="Email IDs to move")
    label_id: str = Field(description="Target Gmail label ID")

    @field_validator("email_ids")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("email_ids must not be empty")
        return v

    @field_validator("label_id")
    @classmethod
    def label_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label_id must not be empty")
        return v


class MarkRequest(BaseModel):
    """Request body for marking emails as read or unread."""
    email_ids: list[str] = Field(min_length=1, description="Email IDs to mark")
    read: bool = Field(description="True to mark read, False to mark unread")

    @field_validator("email_ids")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("email_ids must not be empty")
        return v


class SaveRequest(BaseModel):
    """Request body for saving emails to files."""
    email_ids: list[str] = Field(min_length=1, description="Email IDs to save")

    @field_validator("email_ids")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("email_ids must not be empty")
        return v


class BulkActionResponse(BaseModel):
    """Result of a bulk action (delete, archive, move, mark)."""
    success: int = Field(description="Number of emails successfully processed")
    failed: int = Field(description="Number of emails that failed")
    succeeded_ids: list[str] = Field(description="IDs of successfully processed emails")
    errors: list[dict] = Field(description="Details of failed operations")


class SaveResponse(BulkActionResponse):
    """Result of a save-to-file action."""
    saved_to: str = Field(description="Directory where files were saved")


class EmailListResponse(BaseModel):
    """Paginated list of emails."""
    emails: list[dict] = Field(description="Email objects")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Emails per page")


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def _require_auth():
    if not gmail_client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


def _validate_email_ids(conn, email_ids: list[str]) -> list[str]:
    """Return only email IDs that exist in the local database."""
    existing = database.get_emails_by_ids(conn, email_ids)
    existing_ids = {e["id"] for e in existing}
    invalid = [eid for eid in email_ids if eid not in existing_ids]
    if invalid:
        log.warning("Ignoring %d unknown email IDs", len(invalid))
    return [eid for eid in email_ids if eid in existing_ids]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/fetch", response_model=FetchResponse, summary="Fetch emails from Gmail")
@limiter.limit("10/minute")
async def fetch_emails(request: Request, body: FetchRequest):
    """Fetch a page of emails from the Gmail inbox and store them in the local cache."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        total_fetched = 0
        all_skipped = []
        page_token = body.page_token or database.get_sync_cursor(conn)

        while True:
            log.info("Fetching emails (max_results=%d, page_token=%s)", body.max_results, bool(page_token))
            result = gmail_client.list_messages(
                service,
                page_token=page_token,
                max_results=body.max_results,
            )
            stubs = result.get("messages", [])
            if not stubs:
                log.info("No new messages found")
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


@router.post("/classify", response_model=ClassifyResponse, summary="Classify emails with AI")
@limiter.limit("10/minute")
async def classify_emails(request: Request, body: ClassifyRequest):
    """Run Claude AI classification on unclassified emails, or re-classify specific emails by ID."""
    _require_auth()
    conn = database.get_connection()
    try:
        if body.email_ids:
            emails = database.get_emails_by_ids(conn, body.email_ids)
        else:
            fetch_limit = body.limit or 500
            emails = database.get_unclassified_emails(conn, limit=fetch_limit)

        if not emails:
            log.info("No emails to classify")
            return {"classified": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "total_cost": 0}}

        log.info("Classifying %d emails", len(emails))
        output = ai_classifier.classify_emails(emails)
        results = output["results"]
        usage = output["usage"]
        for r in results:
            database.update_classification(
                conn,
                r["id"],
                r["category"],
                r["confidence"],
                r["reasoning"],
            )
        database.insert_ai_usage(conn, len(results), usage["input_tokens"], usage["output_tokens"], usage["total_cost"])
        log.info("Classification complete: %d emails, cost=$%.4f", len(results), usage["total_cost"])
        return {"classified": len(results), "usage": usage}
    finally:
        conn.close()


@router.get("/stats", summary="Get email statistics")
async def get_stats():
    """Return email counts and total sizes grouped by category."""
    conn = database.get_connection()
    try:
        return database.get_stats(conn)
    finally:
        conn.close()


@router.get("/group", summary="Get emails for a specific group")
async def get_group_emails(group_by: str = "category", group_name: str = ""):
    """Return emails belonging to a specific group, with display formatting applied."""
    if group_by not in database.GROUPING_FUNCTIONS:
        raise HTTPException(status_code=400, detail="Invalid group_by value")
    conn = database.get_connection()
    try:
        if group_by == "label":
            _require_auth()
            service = gmail_client.build_gmail_service()
            all_labels = gmail_client.get_labels(service)
            label_map = {lbl["id"]: lbl["name"] for lbl in all_labels}
            grouped = database.group_by_label(conn, label_map)
        else:
            grouping_fn = database.GROUPING_FUNCTIONS[group_by]
            grouped = grouping_fn(conn)
        emails = grouped.get(group_name, [])
    finally:
        conn.close()

    # Apply display formatting
    from routers.dashboard import _fmt_date, _fmt_size
    for email in emails:
        email["_date_fmt"] = _fmt_date(email.get("date"))
        email["_size_fmt"] = _fmt_size(email.get("size_estimate"))
        email["_confidence_pct"] = int((email.get("confidence") or 0) * 100)

    return {"emails": emails, "count": len(emails)}


@router.get("/ai-usage", summary="Get AI usage summary")
async def get_ai_usage():
    """Return cumulative AI token usage and cost."""
    conn = database.get_connection()
    try:
        return database.get_ai_usage_summary(conn)
    finally:
        conn.close()


@router.get("/labels", summary="List user-created Gmail labels")
async def get_labels():
    """Return all user-created Gmail labels (for the move-to dropdown)."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    labels = gmail_client.get_labels(service)
    return [lbl for lbl in labels if lbl.get("type") == "user"]


@router.get("/", response_model=EmailListResponse, summary="List cached emails")
async def list_emails(category: Optional[str] = None, page: int = 1, per_page: int = 50):
    """Return paginated emails from the local cache, optionally filtered by category."""
    conn = database.get_connection()
    try:
        emails = database.get_emails_by_category(conn, category, page, per_page)
        return {"emails": emails, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.post("/actions/delete", response_model=BulkActionResponse, summary="Delete emails")
async def delete_emails(body: ActionRequest):
    """Move selected emails to Gmail trash and remove from local cache."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn, body.email_ids)
    finally:
        conn.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    log.info("Deleting %d emails", len(validated_ids))
    result = gmail_client.bulk_trash(service, validated_ids)
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            database.delete_emails(conn, result["succeeded_ids"])
        finally:
            conn.close()
    return result


@router.post("/actions/archive", response_model=BulkActionResponse, summary="Archive emails")
async def archive_emails(body: ActionRequest):
    """Remove selected emails from the inbox (keep in All Mail)."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn_check = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn_check, body.email_ids)
    finally:
        conn_check.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    log.info("Archiving %d emails", len(validated_ids))
    result = gmail_client.bulk_modify(service, validated_ids, remove_labels=["INBOX"])
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
                if row:
                    ids = json.loads(row["label_ids"] or "[]")
                    ids = [lid for lid in ids if lid != "INBOX"]
                    database.update_labels(conn, mid, ids)
        finally:
            conn.close()
    return result


@router.post("/actions/move", response_model=BulkActionResponse, summary="Move emails to label")
async def move_emails(body: MoveRequest):
    """Move selected emails to a Gmail label and remove from inbox."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn_check = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn_check, body.email_ids)
    finally:
        conn_check.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    log.info("Moving %d emails to label %s", len(validated_ids), body.label_id)
    result = gmail_client.bulk_modify(service, validated_ids, add_labels=[body.label_id], remove_labels=["INBOX"])
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
                if row:
                    ids = json.loads(row["label_ids"] or "[]")
                    ids = [lid for lid in ids if lid != "INBOX"]
                    if body.label_id not in ids:
                        ids.append(body.label_id)
                    database.update_labels(conn, mid, ids)
        finally:
            conn.close()
    return result


@router.post("/actions/mark", response_model=BulkActionResponse, summary="Mark emails read/unread")
async def mark_emails(body: MarkRequest):
    """Mark selected emails as read or unread in Gmail and local cache."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn_check = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn_check, body.email_ids)
    finally:
        conn_check.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    if body.read:
        result = gmail_client.bulk_modify(service, validated_ids, remove_labels=["UNREAD"])
    else:
        result = gmail_client.bulk_modify(service, validated_ids, add_labels=["UNREAD"])
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                database.update_read_status(conn, mid, body.read)
        finally:
            conn.close()
    return result


@router.post("/actions/save", response_model=SaveResponse, summary="Save emails to files")
async def save_emails(body: SaveRequest):
    """Download full email content and save as text files to the configured directory."""
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn_check = database.get_connection()
    try:
        validated_ids = _validate_email_ids(conn_check, body.email_ids)
    finally:
        conn_check.close()
    if not validated_ids:
        raise HTTPException(status_code=400, detail="No valid email IDs provided")
    os.makedirs(config.SAVE_DIR, exist_ok=True)

    saved = []
    failed = []
    for msg_id in validated_ids:
        try:
            msg = gmail_client.get_message_full(service, msg_id)
            filename = _make_filename(msg)
            path = os.path.join(config.SAVE_DIR, filename)
            _write_email_file(path, msg)
            saved.append(msg_id)
        except Exception as e:
            failed.append({"id": msg_id, "error": str(e)})

    return {
        "success": len(saved),
        "failed": len(failed),
        "succeeded_ids": saved,
        "errors": failed,
        "saved_to": os.path.abspath(config.SAVE_DIR),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_filename(msg: dict) -> str:
    date_str = datetime.fromtimestamp(msg.get("date") or time.time()).strftime("%Y%m%d")
    sender = re.sub(r"[^\w.-]", "_", msg.get("sender_email", "unknown"))
    subject = re.sub(r"[^\w\s-]", "", msg.get("subject", "no_subject"))
    subject = re.sub(r"\s+", "_", subject.strip())[:50]
    return f"{date_str}_{sender}_{subject}.txt"


def _write_email_file(path: str, msg: dict):
    date_fmt = datetime.fromtimestamp(msg.get("date") or time.time()).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    lines = [
        f"From: {msg.get('sender', '')} <{msg.get('sender_email', '')}>",
        f"Date: {date_fmt}",
        f"Subject: {msg.get('subject', '')}",
        f"Category: {msg.get('category', 'Uncategorized')}",
        "-" * 60,
        "",
        msg.get("body", msg.get("snippet", "")),
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
