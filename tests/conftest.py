import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret-key-for-testing-only")

import config
import database


@pytest.fixture()
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    original = config.DB_PATH
    config.DB_PATH = db_path
    database.init_db()
    yield db_path
    config.DB_PATH = original


@pytest.fixture()
def db_conn(tmp_db):
    conn = database.get_connection()
    yield conn
    conn.close()


SAMPLE_EMAILS = [
    {
        "id": "msg_001",
        "thread_id": "thread_001",
        "sender": "Alice",
        "sender_email": "alice@example.com",
        "subject": "Hello World",
        "snippet": "This is a test email",
        "date": 1700000000,
        "size_estimate": 1024,
        "is_read": True,
        "label_ids": ["INBOX"],
    },
    {
        "id": "msg_002",
        "thread_id": "thread_002",
        "sender": "Bob",
        "sender_email": "bob@example.com",
        "subject": "Newsletter Update",
        "snippet": "Weekly digest...",
        "date": 1700001000,
        "size_estimate": 2048,
        "is_read": False,
        "label_ids": ["INBOX", "UNREAD"],
    },
    {
        "id": "msg_003",
        "thread_id": "thread_003",
        "sender": "Noreply",
        "sender_email": "noreply@shop.com",
        "subject": "Order Confirmation",
        "snippet": "Your order #1234 has been confirmed",
        "date": 1700002000,
        "size_estimate": 512,
        "is_read": True,
        "label_ids": ["INBOX"],
    },
]
