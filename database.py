import sqlite3
import json
import time
from typing import Optional

import config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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
        """)
        conn.commit()
    finally:
        conn.close()


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
    grouped: dict[str, list[dict]] = {cat: [] for cat in config.CATEGORIES}
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
