"""SQLite database layer for caching emails and sync state."""

import datetime
import json
import sqlite3
import time
from collections import OrderedDict
from typing import Optional

import config

log = config.get_logger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    log.info("Initializing database at %s", config.DB_PATH)
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS emails (
                id            TEXT PRIMARY KEY,
                thread_id     TEXT,
                sender        TEXT,
                sender_email  TEXT,
                subject       TEXT,
                snippet       TEXT,
                date          INTEGER,
                size_estimate INTEGER,
                is_read       INTEGER DEFAULT 0,
                label_ids     TEXT,
                fetched_at    INTEGER,
                category      TEXT,
                confidence    REAL,
                reasoning     TEXT,
                classified_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_usage (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     INTEGER NOT NULL,
                emails_count  INTEGER NOT NULL,
                input_tokens  INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_cost    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                color      TEXT NOT NULL DEFAULT '#718096',
                sort_order INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()
        _seed_default_categories(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Default category definitions
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES = [
    {"name": "Newsletters", "description": "marketing emails, digests, subscriptions, blog updates, promotional content", "color": "#805ad5", "sort_order": 0},
    {"name": "Receipts", "description": "order confirmations, invoices, payment confirmations, shipping notices, purchase records", "color": "#d69e2e", "sort_order": 1},
    {"name": "Work", "description": "work-related communication, meetings, tasks, colleagues, clients, job applications", "color": "#3182ce", "sort_order": 2},
    {"name": "Social", "description": "personal messages, social network notifications (Facebook, LinkedIn, Twitter, Instagram), dating apps", "color": "#38a169", "sort_order": 3},
    {"name": "Notifications", "description": "automated alerts, account notifications, security alerts, system messages, app updates", "color": "#dd6b20", "sort_order": 4},
    {"name": "Spam", "description": "unsolicited, suspicious, phishing attempts, or clearly unwanted email", "color": "#e53e3e", "sort_order": 5},
    {"name": "Uncategorized", "description": "anything that does not fit the above categories", "color": "#718096", "sort_order": 6},
]


def _seed_default_categories(conn: sqlite3.Connection):
    """Insert default categories if the table is empty."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM categories").fetchone()
    if row["cnt"] > 0:
        return
    for cat in DEFAULT_CATEGORIES:
        conn.execute(
            "INSERT INTO categories (name, description, color, sort_order) VALUES (?, ?, ?, ?)",
            (cat["name"], cat["description"], cat["color"], cat["sort_order"]),
        )
    conn.commit()
    log.info("Seeded %d default categories", len(DEFAULT_CATEGORIES))


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------

def get_categories(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
    return [dict(r) for r in rows]


def get_category_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM categories ORDER BY sort_order, id").fetchall()
    return [r["name"] for r in rows]


def create_category(conn: sqlite3.Connection, name: str, description: str = "", color: str = "#718096") -> dict:
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM categories").fetchone()["m"]
    conn.execute(
        "INSERT INTO categories (name, description, color, sort_order) VALUES (?, ?, ?, ?)",
        (name.strip(), description.strip(), color.strip(), max_order + 1),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM categories WHERE name = ?", (name.strip(),)).fetchone()
    return dict(row)


def update_category(conn: sqlite3.Connection, category_id: int, **fields) -> dict | None:
    allowed = {"name", "description", "color", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return None
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [category_id]
    conn.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return dict(row) if row else None


def delete_category(conn: sqlite3.Connection, category_id: int) -> bool:
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
    if not row:
        return False
    old_name = row["name"]
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    # Reassign emails with this category to Uncategorized
    conn.execute("UPDATE emails SET category = 'Uncategorized' WHERE category = ?", (old_name,))
    conn.commit()
    return True


def upsert_emails(conn: sqlite3.Connection, emails: list[dict]):
    now = int(time.time())
    conn.executemany(
        """
        INSERT INTO emails
            (id, thread_id, sender, sender_email, subject, snippet,
             date, size_estimate, is_read, label_ids, fetched_at)
        VALUES
            (:id, :thread_id, :sender, :sender_email, :subject, :snippet,
             :date, :size_estimate, :is_read, :label_ids, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            sender        = excluded.sender,
            sender_email  = excluded.sender_email,
            subject       = excluded.subject,
            snippet       = excluded.snippet,
            date          = excluded.date,
            size_estimate = excluded.size_estimate,
            is_read       = excluded.is_read,
            label_ids     = excluded.label_ids,
            fetched_at    = excluded.fetched_at
        """,
        [
            {
                "id": e["id"],
                "thread_id": e.get("thread_id"),
                "sender": e.get("sender"),
                "sender_email": e.get("sender_email"),
                "subject": e.get("subject"),
                "snippet": e.get("snippet"),
                "date": e.get("date"),
                "size_estimate": e.get("size_estimate", 0),
                "is_read": 1 if e.get("is_read") else 0,
                "label_ids": json.dumps(e.get("label_ids", [])),
                "fetched_at": now,
            }
            for e in emails
        ],
    )
    conn.commit()


def get_emails_by_category(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    page: int = 1,
    per_page: int = 100,
) -> list[dict]:
    offset = (page - 1) * per_page
    if category:
        rows = conn.execute(
            "SELECT * FROM emails WHERE category = ? ORDER BY date DESC LIMIT ? OFFSET ?",
            (category, per_page, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM emails ORDER BY date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_emails_grouped(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    rows = conn.execute(
        "SELECT * FROM emails ORDER BY date DESC"
    ).fetchall()
    cat_names = get_category_names(conn)
    grouped: dict[str, list[dict]] = {cat: [] for cat in cat_names}
    if "Uncategorized" not in grouped:
        grouped["Uncategorized"] = []
    for r in rows:
        d = dict(r)
        cat = d.get("category") or "Uncategorized"
        if cat not in grouped:
            cat = "Uncategorized"
        grouped[cat].append(d)
    return grouped


def get_unclassified_emails(conn: sqlite3.Connection, limit: int = 200) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM emails WHERE category IS NULL ORDER BY date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_classification(
    conn: sqlite3.Connection,
    email_id: str,
    category: str,
    confidence: float,
    reasoning: str,
):
    conn.execute(
        """
        UPDATE emails
        SET category = ?, confidence = ?, reasoning = ?, classified_at = ?
        WHERE id = ?
        """,
        (category, confidence, reasoning, int(time.time()), email_id),
    )
    conn.commit()


def delete_emails(conn: sqlite3.Connection, email_ids: list[str]):
    placeholders = ",".join("?" * len(email_ids))
    conn.execute(f"DELETE FROM emails WHERE id IN ({placeholders})", email_ids)
    conn.commit()


def update_labels(conn: sqlite3.Connection, email_id: str, label_ids: list[str]):
    conn.execute(
        "UPDATE emails SET label_ids = ? WHERE id = ?",
        (json.dumps(label_ids), email_id),
    )
    conn.commit()


def update_read_status(conn: sqlite3.Connection, email_id: str, is_read: bool):
    conn.execute(
        "UPDATE emails SET is_read = ? WHERE id = ?",
        (1 if is_read else 0, email_id),
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT
            COALESCE(category, 'Uncategorized') AS cat,
            COUNT(*) AS cnt,
            SUM(size_estimate) AS total_bytes
        FROM emails
        GROUP BY cat
        """
    ).fetchall()
    result = {}
    for r in rows:
        result[r["cat"]] = {
            "count": r["cnt"],
            "total_mb": round((r["total_bytes"] or 0) / (1024 * 1024), 2),
        }
    return result


def get_sync_cursor(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute(
        "SELECT value FROM sync_state WHERE key = 'next_page_token'"
    ).fetchone()
    return row["value"] if row else None


def set_sync_cursor(conn: sqlite3.Connection, token: Optional[str]):
    if token:
        conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES ('next_page_token', ?)",
            (token,),
        )
    else:
        conn.execute("DELETE FROM sync_state WHERE key = 'next_page_token'")
    conn.commit()


def get_total_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()
    return row["cnt"] if row else 0


def insert_ai_usage(conn: sqlite3.Connection, emails_count: int, input_tokens: int, output_tokens: int, total_cost: float):
    conn.execute(
        "INSERT INTO ai_usage (timestamp, emails_count, input_tokens, output_tokens, total_cost) VALUES (?, ?, ?, ?, ?)",
        (int(time.time()), emails_count, input_tokens, output_tokens, total_cost),
    )
    conn.commit()


def get_ai_usage_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
            COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
            COALESCE(SUM(total_cost), 0) AS total_cost,
            COALESCE(SUM(emails_count), 0) AS total_emails_classified,
            COUNT(*) AS total_runs
        FROM ai_usage
        """
    ).fetchone()
    return dict(row)


def get_emails_by_ids(conn: sqlite3.Connection, email_ids: list[str]) -> list[dict]:
    if not email_ids:
        return []
    placeholders = ",".join("?" * len(email_ids))
    rows = conn.execute(
        f"SELECT * FROM emails WHERE id IN ({placeholders})",
        email_ids,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Grouping functions — all return dict[str, list[dict]]
# ---------------------------------------------------------------------------

def _fetch_all_emails(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM emails ORDER BY date DESC").fetchall()
    return [dict(r) for r in rows]


def group_by_sender_domain(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    emails = _fetch_all_emails(conn)
    groups: dict[str, list[dict]] = {}
    for e in emails:
        addr = e.get("sender_email") or ""
        domain = addr.split("@")[-1].lower() if "@" in addr else "(unknown)"
        groups.setdefault(domain, []).append(e)
    # Sort by count desc, cap at 20, rest in "Other"
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    result = OrderedDict()
    other = []
    for i, (name, emails_list) in enumerate(sorted_groups):
        if i < 50:
            result[name] = emails_list
        else:
            other.extend(emails_list)
    if other:
        result["Other"] = other
    return result


def group_by_date_range(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    emails = _fetch_all_emails(conn)
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    week_start = (now - datetime.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    six_months_ago = (now - datetime.timedelta(days=180)).timestamp()
    one_year_ago = (now - datetime.timedelta(days=365)).timestamp()

    buckets = OrderedDict([
        ("Today", []),
        ("This Week", []),
        ("This Month", []),
        ("This Year", []),
        ("Older than 6 Months", []),
        ("Older than 1 Year", []),
    ])
    for e in emails:
        ts = e.get("date") or 0
        if ts >= today_start:
            buckets["Today"].append(e)
        elif ts >= week_start:
            buckets["This Week"].append(e)
        elif ts >= month_start:
            buckets["This Month"].append(e)
        elif ts >= six_months_ago:
            buckets["This Year"].append(e)
        elif ts >= one_year_ago:
            buckets["Older than 6 Months"].append(e)
        else:
            buckets["Older than 1 Year"].append(e)
    return buckets


def group_by_read_status(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    emails = _fetch_all_emails(conn)
    groups = OrderedDict([("Unread", []), ("Read", [])])
    for e in emails:
        if e.get("is_read"):
            groups["Read"].append(e)
        else:
            groups["Unread"].append(e)
    return groups


def group_by_size(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    emails = _fetch_all_emails(conn)
    groups = OrderedDict([
        ("Small (< 10 KB)", []),
        ("Medium (10 KB - 100 KB)", []),
        ("Large (> 100 KB)", []),
    ])
    for e in emails:
        size = e.get("size_estimate") or 0
        if size < 10240:
            groups["Small (< 10 KB)"].append(e)
        elif size < 102400:
            groups["Medium (10 KB - 100 KB)"].append(e)
        else:
            groups["Large (> 100 KB)"].append(e)
    return groups


def group_by_label(conn: sqlite3.Connection, label_map: dict[str, str] | None = None) -> dict[str, list[dict]]:
    """Group emails by Gmail label. If label_map is provided (id->name),
    resolve IDs to display names and skip labels that no longer exist."""
    emails = _fetch_all_emails(conn)
    groups: dict[str, list[dict]] = {}
    for e in emails:
        label_ids = json.loads(e.get("label_ids") or "[]")
        if not label_ids:
            groups.setdefault("(no labels)", []).append(e)
        else:
            for lid in label_ids:
                if label_map is not None:
                    name = label_map.get(lid)
                    if name is None:
                        continue  # label no longer exists, skip
                else:
                    name = lid
                groups.setdefault(name, []).append(e)
    return OrderedDict(sorted(groups.items(), key=lambda x: x[0]))


def group_by_frequency(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    emails = _fetch_all_emails(conn)
    groups: dict[str, list[dict]] = {}
    for e in emails:
        sender = e.get("sender_email") or "(unknown)"
        groups.setdefault(sender, []).append(e)
    # Sort by count desc, cap at 20
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    result = OrderedDict()
    other = []
    for i, (name, emails_list) in enumerate(sorted_groups):
        if i < 50:
            result[name] = emails_list
        else:
            other.extend(emails_list)
    if other:
        result["Other"] = other
    return result


def get_stats_for_groups(grouped: dict[str, list[dict]]) -> dict:
    result = {}
    for name, emails in grouped.items():
        total_bytes = sum(e.get("size_estimate", 0) for e in emails)
        result[name] = {
            "count": len(emails),
            "total_mb": round(total_bytes / (1024 * 1024), 2),
        }
    return result


GROUPING_FUNCTIONS = {
    "category": get_all_emails_grouped,
    "sender": group_by_sender_domain,
    "date": group_by_date_range,
    "read_status": group_by_read_status,
    "size": group_by_size,
    "label": group_by_label,
    "frequency": group_by_frequency,
}
