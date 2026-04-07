import json

import database
from tests.conftest import SAMPLE_EMAILS


class TestInitDb:
    def test_creates_tables(self, tmp_db):
        conn = database.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "emails" in names
        assert "sync_state" in names
        conn.close()

    def test_idempotent(self, tmp_db):
        database.init_db()
        database.init_db()
        conn = database.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables) >= 2
        conn.close()


class TestUpsertEmails:
    def test_insert_new(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        rows = db_conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()
        assert rows["cnt"] == 3

    def test_upsert_updates_existing(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        updated = [{**SAMPLE_EMAILS[0], "subject": "Updated Subject"}]
        database.upsert_emails(db_conn, updated)
        row = db_conn.execute("SELECT subject FROM emails WHERE id='msg_001'").fetchone()
        assert row["subject"] == "Updated Subject"
        total = db_conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()
        assert total["cnt"] == 3

    def test_label_ids_stored_as_json(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS[:1])
        row = db_conn.execute("SELECT label_ids FROM emails WHERE id='msg_001'").fetchone()
        assert json.loads(row["label_ids"]) == ["INBOX"]


class TestGetEmailsByCategory:
    def test_returns_all_when_no_filter(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.update_classification(db_conn, "msg_001", "Work", 0.9, "work email")
        results = database.get_emails_by_category(db_conn)
        assert len(results) == 3

    def test_filters_by_category(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.update_classification(db_conn, "msg_001", "Work", 0.9, "work email")
        database.update_classification(db_conn, "msg_002", "Newsletters", 0.8, "newsletter")
        results = database.get_emails_by_category(db_conn, category="Work")
        assert len(results) == 1
        assert results[0]["id"] == "msg_001"

    def test_pagination(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        page1 = database.get_emails_by_category(db_conn, per_page=2, page=1)
        page2 = database.get_emails_by_category(db_conn, per_page=2, page=2)
        assert len(page1) == 2
        assert len(page2) == 1


class TestGetAllEmailsGrouped:
    def test_groups_by_category(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.update_classification(db_conn, "msg_001", "Work", 0.9, "work")
        database.update_classification(db_conn, "msg_002", "Newsletters", 0.8, "news")
        grouped = database.get_all_emails_grouped(db_conn)
        assert len(grouped["Work"]) == 1
        assert len(grouped["Newsletters"]) == 1
        assert len(grouped["Uncategorized"]) == 1

    def test_unclassified_go_to_uncategorized(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS[:1])
        grouped = database.get_all_emails_grouped(db_conn)
        assert len(grouped["Uncategorized"]) == 1


class TestGetUnclassifiedEmails:
    def test_returns_only_unclassified(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.update_classification(db_conn, "msg_001", "Work", 0.9, "work")
        results = database.get_unclassified_emails(db_conn)
        assert len(results) == 2
        ids = {r["id"] for r in results}
        assert "msg_001" not in ids

    def test_limit(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        results = database.get_unclassified_emails(db_conn, limit=1)
        assert len(results) == 1


class TestUpdateClassification:
    def test_sets_classification(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS[:1])
        database.update_classification(db_conn, "msg_001", "Work", 0.95, "clearly work")
        row = db_conn.execute(
            "SELECT category, confidence, reasoning, classified_at FROM emails WHERE id='msg_001'"
        ).fetchone()
        assert row["category"] == "Work"
        assert row["confidence"] == 0.95
        assert row["reasoning"] == "clearly work"
        assert row["classified_at"] is not None


class TestDeleteEmails:
    def test_deletes_by_ids(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.delete_emails(db_conn, ["msg_001", "msg_002"])
        rows = db_conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()
        assert rows["cnt"] == 1


class TestUpdateLabels:
    def test_updates_labels(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS[:1])
        database.update_labels(db_conn, "msg_001", ["INBOX", "Label_1"])
        row = db_conn.execute("SELECT label_ids FROM emails WHERE id='msg_001'").fetchone()
        assert json.loads(row["label_ids"]) == ["INBOX", "Label_1"]


class TestUpdateReadStatus:
    def test_marks_read(self, db_conn):
        database.upsert_emails(db_conn, [SAMPLE_EMAILS[1]])
        database.update_read_status(db_conn, "msg_002", True)
        row = db_conn.execute("SELECT is_read FROM emails WHERE id='msg_002'").fetchone()
        assert row["is_read"] == 1

    def test_marks_unread(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS[:1])
        database.update_read_status(db_conn, "msg_001", False)
        row = db_conn.execute("SELECT is_read FROM emails WHERE id='msg_001'").fetchone()
        assert row["is_read"] == 0


class TestGetStats:
    def test_returns_stats_per_category(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        database.update_classification(db_conn, "msg_001", "Work", 0.9, "work")
        database.update_classification(db_conn, "msg_002", "Newsletters", 0.8, "news")
        stats = database.get_stats(db_conn)
        assert stats["Work"]["count"] == 1
        assert stats["Newsletters"]["count"] == 1


class TestSyncCursor:
    def test_set_and_get(self, db_conn):
        database.set_sync_cursor(db_conn, "abc123")
        assert database.get_sync_cursor(db_conn) == "abc123"

    def test_clear(self, db_conn):
        database.set_sync_cursor(db_conn, "abc123")
        database.set_sync_cursor(db_conn, None)
        assert database.get_sync_cursor(db_conn) is None

    def test_get_returns_none_initially(self, db_conn):
        assert database.get_sync_cursor(db_conn) is None


class TestGetTotalCount:
    def test_counts(self, db_conn):
        assert database.get_total_count(db_conn) == 0
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        assert database.get_total_count(db_conn) == 3


class TestGetEmailsByIds:
    def test_returns_matching(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        results = database.get_emails_by_ids(db_conn, ["msg_001", "msg_003"])
        ids = {r["id"] for r in results}
        assert ids == {"msg_001", "msg_003"}

    def test_ignores_missing(self, db_conn):
        database.upsert_emails(db_conn, SAMPLE_EMAILS)
        results = database.get_emails_by_ids(db_conn, ["msg_001", "nonexistent"])
        assert len(results) == 1

    def test_empty_list(self, db_conn):
        results = database.get_emails_by_ids(db_conn, [])
        assert results == []
