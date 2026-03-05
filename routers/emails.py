import os
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import ai_classifier
import config
import database
import gmail_client

router = APIRouter(prefix="/emails", tags=["emails"])


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class FetchRequest(BaseModel):
    max_results: int = config.EMAILS_PER_PAGE
    page_token: Optional[str] = None


class ClassifyRequest(BaseModel):
    email_ids: Optional[list[str]] = None


class ActionRequest(BaseModel):
    email_ids: list[str]


class MoveRequest(BaseModel):
    email_ids: list[str]
    label_id: str


class MarkRequest(BaseModel):
    email_ids: list[str]
    read: bool


class SaveRequest(BaseModel):
    email_ids: list[str]


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def _require_auth():
    if not gmail_client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/fetch")
async def fetch_emails(body: FetchRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    conn = database.get_connection()
    try:
        page_token = body.page_token or database.get_sync_cursor(conn)
        result = gmail_client.list_messages(
            service,
            page_token=page_token,
            max_results=body.max_results,
        )
        stubs = result.get("messages", [])
        if not stubs:
            return {"fetched": 0, "next_page_token": None}

        messages = gmail_client.batch_get_messages(service, [s["id"] for s in stubs])
        database.upsert_emails(conn, messages)
        next_token = result.get("nextPageToken")
        database.set_sync_cursor(conn, next_token)
        return {"fetched": len(messages), "next_page_token": next_token}
    finally:
        conn.close()


@router.post("/classify")
async def classify_emails(body: ClassifyRequest):
    _require_auth()
    conn = database.get_connection()
    try:
        if body.email_ids:
            all_emails = database.get_emails_by_category(conn)
            emails = [e for e in all_emails if e["id"] in set(body.email_ids)]
        else:
            emails = database.get_unclassified_emails(conn, limit=500)

        if not emails:
            return {"classified": 0}

        results = ai_classifier.classify_emails(emails)
        for r in results:
            database.update_classification(
                conn,
                r["id"],
                r["category"],
                r["confidence"],
                r["reasoning"],
            )
        return {"classified": len(results)}
    finally:
        conn.close()


@router.get("/stats")
async def get_stats():
    conn = database.get_connection()
    try:
        return database.get_stats(conn)
    finally:
        conn.close()


@router.get("/labels")
async def get_labels():
    _require_auth()
    service = gmail_client.build_gmail_service()
    labels = gmail_client.get_labels(service)
    return [l for l in labels if l.get("type") == "user"]


@router.get("/")
async def list_emails(category: Optional[str] = None, page: int = 1, per_page: int = 50):
    conn = database.get_connection()
    try:
        emails = database.get_emails_by_category(conn, category, page, per_page)
        return {"emails": emails, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.post("/actions/delete")
async def delete_emails(body: ActionRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    result = gmail_client.bulk_action(service, body.email_ids, gmail_client.delete_message)
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            database.delete_emails(conn, result["succeeded_ids"])
        finally:
            conn.close()
    return result


@router.post("/actions/archive")
async def archive_emails(body: ActionRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()

    def _archive(svc, msg_id):
        gmail_client.archive_message(svc, msg_id)

    result = gmail_client.bulk_action(service, body.email_ids, _archive)
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                # Reflect label change in DB
                row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
                if row:
                    import json
                    ids = json.loads(row["label_ids"] or "[]")
                    ids = [l for l in ids if l != "INBOX"]
                    database.update_labels(conn, mid, ids)
        finally:
            conn.close()
    return result


@router.post("/actions/move")
async def move_emails(body: MoveRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()

    def _move(svc, msg_id):
        gmail_client.move_to_label(svc, msg_id, body.label_id)

    result = gmail_client.bulk_action(service, body.email_ids, _move)
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                row = conn.execute("SELECT label_ids FROM emails WHERE id=?", (mid,)).fetchone()
                if row:
                    import json
                    ids = json.loads(row["label_ids"] or "[]")
                    ids = [l for l in ids if l != "INBOX"]
                    if body.label_id not in ids:
                        ids.append(body.label_id)
                    database.update_labels(conn, mid, ids)
        finally:
            conn.close()
    return result


@router.post("/actions/mark")
async def mark_emails(body: MarkRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    fn = gmail_client.mark_read if body.read else gmail_client.mark_unread
    result = gmail_client.bulk_action(service, body.email_ids, fn)
    if result["succeeded_ids"]:
        conn = database.get_connection()
        try:
            for mid in result["succeeded_ids"]:
                database.update_read_status(conn, mid, body.read)
        finally:
            conn.close()
    return result


@router.post("/actions/save")
async def save_emails(body: SaveRequest):
    _require_auth()
    service = gmail_client.build_gmail_service()
    os.makedirs(config.SAVE_DIR, exist_ok=True)

    saved = []
    failed = []
    for msg_id in body.email_ids:
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
