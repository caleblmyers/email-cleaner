"""Gmail API client: OAuth2 authentication, message fetching, and actions."""

import base64
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

log = config.get_logger(__name__)


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


def batch_get_messages(service, msg_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Fetch metadata for multiple messages using the Gmail Batch API.

    Falls back to sequential fetching if the batch API fails.
    Returns (results, skipped).
    """
    results = []
    skipped = []

    BATCH_LIMIT = 20

    def _callback(request_id, response, exception):
        if exception is not None:
            log.error("Batch fetch failed for %s: %s", request_id, exception)
            skipped.append({"id": request_id, "error": str(exception)})
        else:
            try:
                results.append(_parse_message(response))
            except Exception as e:
                log.error("Failed to parse message %s: %s", request_id, e)
                skipped.append({"id": request_id, "error": str(e)})

    try:
        for i in range(0, len(msg_ids), BATCH_LIMIT):
            if i > 0:
                time.sleep(1)
            chunk = msg_ids[i : i + BATCH_LIMIT]
            batch = service.new_batch_http_request()
            for msg_id in chunk:
                batch.add(
                    service.users().messages().get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    ),
                    request_id=msg_id,
                    callback=_callback,
                )
            batch.execute()

        # Retry any that were rate-limited, sequentially
        rate_limited = [s for s in skipped if "429" in str(s.get("error", "")) or "rate" in str(s.get("error", "")).lower()]
        if rate_limited:
            retry_ids = [s["id"] for s in rate_limited]
            for s in rate_limited:
                skipped.remove(s)
            log.info("Retrying %d rate-limited messages sequentially", len(retry_ids))
            time.sleep(3)
            retry_results, retry_skipped = _sequential_get_messages(service, retry_ids)
            results.extend(retry_results)
            skipped.extend(retry_skipped)

        log.info("Batch API fetched %d messages (%d skipped)", len(results), len(skipped))
    except Exception as e:
        log.warning("Batch API failed, falling back to sequential: %s", e)
        results, skipped = _sequential_get_messages(service, msg_ids)

    return results, skipped


def _sequential_get_messages(service, msg_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Fallback sequential fetch when batch API is unavailable."""
    results = []
    skipped = []
    for i, msg_id in enumerate(msg_ids):
        if i > 0 and i % 10 == 0:
            time.sleep(1)
        try:
            results.append(get_message_metadata(service, msg_id))
        except HttpError as e:
            if e.resp.status == 429:
                log.warning("Rate limited on message %s, retrying after 3s", msg_id)
                time.sleep(3)
                try:
                    results.append(get_message_metadata(service, msg_id))
                except Exception as retry_err:
                    log.error("Retry failed for message %s: %s", msg_id, retry_err)
                    skipped.append({"id": msg_id, "error": str(retry_err)})
            else:
                log.error("Failed to fetch message %s: HTTP %d – %s", msg_id, e.resp.status, e)
                skipped.append({"id": msg_id, "error": f"HTTP {e.resp.status}"})
        except Exception as e:
            log.error("Unexpected error fetching message %s: %s", msg_id, e)
            skipped.append({"id": msg_id, "error": str(e)})
    return results, skipped


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


def create_label(service, name: str) -> dict:
    """Create a new user label in Gmail. Returns the created label resource."""
    body = {
        "name": name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    return service.users().labels().create(userId="me", body=body).execute()


def update_label(service, label_id: str, name: str) -> dict:
    """Rename a Gmail label. Returns the updated label resource."""
    body = {"name": name}
    return service.users().labels().update(userId="me", id=label_id, body=body).execute()


def delete_label(service, label_id: str) -> None:
    """Permanently delete a Gmail label. Messages are not deleted."""
    service.users().labels().delete(userId="me", id=label_id).execute()


def bulk_trash(service, msg_ids: list[str]) -> dict:
    """Trash emails in bulk using Gmail's batchModify (up to 1000 per call)."""
    BATCH_LIMIT = 1000
    succeeded = []
    failed = []
    for i in range(0, len(msg_ids), BATCH_LIMIT):
        if i > 0:
            time.sleep(2)
        chunk = msg_ids[i : i + BATCH_LIMIT]
        try:
            service.users().messages().batchModify(
                userId="me",
                body={"ids": chunk, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
            ).execute()
            succeeded.extend(chunk)
        except HttpError as e:
            if e.resp.status == 429:
                log.warning("Rate limited on bulk trash, retrying chunk after 5s")
                time.sleep(5)
                try:
                    service.users().messages().batchModify(
                        userId="me",
                        body={"ids": chunk, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
                    ).execute()
                    succeeded.extend(chunk)
                except Exception as retry_err:
                    log.error("Bulk trash retry failed: %s", retry_err)
                    failed.extend({"id": mid, "error": str(retry_err)} for mid in chunk)
            else:
                log.error("Bulk trash failed: %s", e)
                failed.extend({"id": mid, "error": str(e)} for mid in chunk)
    return {
        "success": len(succeeded),
        "failed": len(failed),
        "succeeded_ids": succeeded,
        "errors": failed,
    }


def bulk_modify(service, msg_ids: list[str], add_labels: list[str] = None, remove_labels: list[str] = None) -> dict:
    """Modify labels in bulk using Gmail's batchModify (up to 1000 per call)."""
    BATCH_LIMIT = 1000
    succeeded = []
    failed = []
    body = {"ids": [], "addLabelIds": add_labels or [], "removeLabelIds": remove_labels or []}
    for i in range(0, len(msg_ids), BATCH_LIMIT):
        if i > 0:
            time.sleep(2)
        chunk = msg_ids[i : i + BATCH_LIMIT]
        body["ids"] = chunk
        try:
            service.users().messages().batchModify(userId="me", body=body).execute()
            succeeded.extend(chunk)
        except HttpError as e:
            if e.resp.status == 429:
                log.warning("Rate limited on bulk modify, retrying chunk after 5s")
                time.sleep(5)
                try:
                    service.users().messages().batchModify(userId="me", body=body).execute()
                    succeeded.extend(chunk)
                except Exception as retry_err:
                    log.error("Bulk modify retry failed: %s", retry_err)
                    failed.extend({"id": mid, "error": str(retry_err)} for mid in chunk)
            else:
                log.error("Bulk modify failed: %s", e)
                failed.extend({"id": mid, "error": str(e)} for mid in chunk)
    return {
        "success": len(succeeded),
        "failed": len(failed),
        "succeeded_ids": succeeded,
        "errors": failed,
    }


def bulk_action(service, msg_ids: list[str], action_fn) -> dict:
    """Run action_fn(service, id) for each id with throttling and retry."""
    succeeded = []
    failed = []
    for i, msg_id in enumerate(msg_ids):
        if i > 0 and i % 10 == 0:
            time.sleep(1)
        try:
            action_fn(service, msg_id)
            succeeded.append(msg_id)
        except HttpError as e:
            if e.resp.status == 429:
                log.warning("Rate limited on %s, retrying after 3s", msg_id)
                time.sleep(3)
                try:
                    action_fn(service, msg_id)
                    succeeded.append(msg_id)
                except Exception as retry_err:
                    failed.append({"id": msg_id, "error": str(retry_err)})
            else:
                failed.append({"id": msg_id, "error": str(e)})
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
