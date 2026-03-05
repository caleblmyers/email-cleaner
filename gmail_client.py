import base64
import email as email_lib
import json
import os
import re
import time
from email.header import decode_header
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def build_auth_url() -> tuple[str, str]:
    """Returns (authorization_url, state)."""
    flow = _build_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return url, state


def exchange_code(code: str) -> None:
    """Exchange authorization code for tokens and save to token.json."""
    flow = _build_flow()
    flow.fetch_token(code=code)
    _save_credentials(flow.credentials)


def get_credentials() -> Credentials:
    """Load credentials from token.json, refresh if expired."""
    if not os.path.exists(config.TOKEN_FILE):
        raise FileNotFoundError("Not authenticated. Please log in first.")
    creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
    return creds


def is_authenticated() -> bool:
    try:
        get_credentials()
        return True
    except Exception:
        return False


def logout() -> None:
    if os.path.exists(config.TOKEN_FILE):
        os.remove(config.TOKEN_FILE)


def build_gmail_service():
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def list_messages(
    service,
    page_token: Optional[str] = None,
    max_results: int = 50,
    label_ids: Optional[list[str]] = None,
) -> dict:
    """Returns {'messages': [...], 'nextPageToken': ..., 'resultSizeEstimate': ...}"""
    params = {
        "userId": "me",
        "maxResults": max_results,
        "labelIds": label_ids or ["INBOX"],
    }
    if page_token:
        params["pageToken"] = page_token
    return service.users().messages().list(**params).execute()


def get_message_metadata(service, msg_id: str) -> dict:
    """Fetch message metadata and parse into a flat dict."""
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ).execute()
    return _parse_message(msg)


def batch_get_messages(service, msg_ids: list[str]) -> list[dict]:
    """Fetch metadata for multiple messages. Falls back to sequential on error."""
    results = []
    # Use sequential fetches with a small delay to avoid rate limits
    for msg_id in msg_ids:
        try:
            results.append(get_message_metadata(service, msg_id))
        except HttpError as e:
            if e.resp.status == 429:
                time.sleep(1)
                results.append(get_message_metadata(service, msg_id))
            else:
                pass  # Skip messages that can't be fetched
    return results


def get_message_full(service, msg_id: str) -> dict:
    """Fetch full message including body."""
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full",
    ).execute()
    parsed = _parse_message(msg)
    parsed["body"] = _extract_body(msg)
    return parsed


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

def delete_message(service, msg_id: str) -> None:
    """Move to trash (recoverable)."""
    service.users().messages().trash(userId="me", id=msg_id).execute()


def archive_message(service, msg_id: str) -> None:
    """Remove from INBOX (moves to All Mail)."""
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()


def move_to_label(service, msg_id: str, label_id: str) -> None:
    """Add label and remove from INBOX."""
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [label_id], "removeLabelIds": ["INBOX"]},
    ).execute()


def mark_read(service, msg_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def mark_unread(service, msg_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": ["UNREAD"]},
    ).execute()


def get_labels(service) -> list[dict]:
    result = service.users().labels().list(userId="me").execute()
    return result.get("labels", [])


def bulk_action(service, msg_ids: list[str], action_fn) -> dict:
    """Run action_fn(service, id) for each id. Returns success/failed counts."""
    succeeded = []
    failed = []
    for msg_id in msg_ids:
        try:
            action_fn(service, msg_id)
            succeeded.append(msg_id)
        except Exception as e:
            failed.append({"id": msg_id, "error": str(e)})
    return {
        "success": len(succeeded),
        "failed": len(failed),
        "succeeded_ids": succeeded,
        "errors": failed,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_flow() -> Flow:
    flow = Flow.from_client_secrets_file(
        config.CREDENTIALS_FILE,
        scopes=config.GMAIL_SCOPES,
        redirect_uri=config.REDIRECT_URI,
    )
    return flow


def _save_credentials(creds: Credentials) -> None:
    with open(config.TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def _parse_message(msg: dict) -> dict:
    headers = {
        h["name"].lower(): h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }
    raw_from = headers.get("from", "")
    sender, sender_email = _parse_from(raw_from)
    subject = _decode_header_value(headers.get("subject", "(no subject)"))
    date_str = headers.get("date", "")
    date_ts = _parse_date(date_str)
    label_ids = msg.get("labelIds", [])
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "sender": sender,
        "sender_email": sender_email,
        "subject": subject,
        "snippet": msg.get("snippet", ""),
        "date": date_ts,
        "size_estimate": msg.get("sizeEstimate", 0),
        "is_read": "UNREAD" not in label_ids,
        "label_ids": label_ids,
    }


def _parse_from(raw: str) -> tuple[str, str]:
    """Parse 'Name <email@example.com>' or 'email@example.com'."""
    match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', raw.strip())
    if match:
        name = match.group(1).strip() or match.group(2)
        addr = match.group(2).strip()
        return _decode_header_value(name), addr
    return raw.strip(), raw.strip()


def _decode_header_value(value: str) -> str:
    """Decode RFC2047 encoded header values."""
    try:
        parts = decode_header(value)
        decoded = []
        for text, charset in parts:
            if isinstance(text, bytes):
                decoded.append(text.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(text)
        return "".join(decoded)
    except Exception:
        return value


def _parse_date(date_str: str) -> int:
    """Parse email Date header to Unix timestamp."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return int(dt.timestamp())
    except Exception:
        return int(time.time())


def _extract_body(msg: dict) -> str:
    """Recursively extract plain text body from a message payload."""
    payload = msg.get("payload", {})
    return _decode_part(payload)


def _decode_part(part: dict) -> str:
    mime_type = part.get("mimeType", "")
    if mime_type == "text/plain":
        data = part.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime_type == "text/html":
        data = part.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            return _strip_html(html)
    elif mime_type.startswith("multipart/"):
        parts = part.get("parts", [])
        # Prefer plain text parts
        for p in parts:
            if p.get("mimeType") == "text/plain":
                result = _decode_part(p)
                if result:
                    return result
        # Fall back to any part
        for p in parts:
            result = _decode_part(p)
            if result:
                return result
    return ""


def _strip_html(html: str) -> str:
    """Simple HTML tag stripper."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
