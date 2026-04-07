from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from tests.conftest import SAMPLE_EMAILS


@pytest.fixture()
def client(tmp_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def authed_client(client):
    """Client with mocked authentication."""
    with patch("gmail_client.is_authenticated", return_value=True):
        yield client


@pytest.fixture()
def seeded_db(tmp_db):
    conn = database.get_connection()
    database.upsert_emails(conn, SAMPLE_EMAILS)
    database.update_classification(conn, "msg_001", "Work", 0.9, "work email")
    database.update_classification(conn, "msg_002", "Newsletters", 0.8, "newsletter")
    conn.close()


class TestDashboardRoutes:
    def test_index_redirects_to_login_when_not_authed(self, client):
        with patch("gmail_client.is_authenticated", return_value=False):
            resp = client.get("/", follow_redirects=False)
            assert resp.status_code == 307
            assert "/login" in resp.headers["location"]

    def test_index_redirects_to_dashboard_when_authed(self, client):
        with patch("gmail_client.is_authenticated", return_value=True):
            resp = client.get("/", follow_redirects=False)
            assert resp.status_code == 307
            assert "/dashboard" in resp.headers["location"]

    def test_login_page_renders(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "Email Cleaner" in resp.text

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.get_labels", return_value=[])
    def test_dashboard_renders(self, mock_labels, mock_service, authed_client, seeded_db):
        resp = authed_client.get("/dashboard")
        assert resp.status_code == 200
        assert "Work" in resp.text
        assert "Newsletters" in resp.text


class TestAuthRoutes:
    @patch("gmail_client.build_auth_url", return_value=("https://accounts.google.com/auth", "state123"))
    def test_login_redirects_to_google(self, mock_auth, client):
        resp = client.get("/auth/login", follow_redirects=False)
        assert resp.status_code == 307
        assert "accounts.google.com" in resp.headers["location"]

    @patch("gmail_client.exchange_code")
    @patch("gmail_client.build_auth_url", return_value=("https://accounts.google.com/auth", "state123"))
    def test_callback_success(self, mock_auth, mock_exchange, client):
        client.get("/auth/login", follow_redirects=False)
        resp = client.get("/auth/callback?code=testcode&state=state123", follow_redirects=False)
        assert resp.status_code == 307
        assert "/dashboard" in resp.headers["location"]

    def test_callback_error(self, client):
        resp = client.get("/auth/callback?error=access_denied", follow_redirects=False)
        assert resp.status_code == 307
        assert "error" in resp.headers["location"]

    @patch("gmail_client.logout")
    def test_logout(self, mock_logout, client):
        resp = client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 307
        mock_logout.assert_called_once()


class TestEmailRoutes:
    def test_fetch_requires_auth(self, client):
        with patch("gmail_client.is_authenticated", return_value=False):
            resp = client.post("/emails/fetch", json={})
            assert resp.status_code == 401

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.list_messages")
    @patch("gmail_client.batch_get_messages")
    def test_fetch_emails(self, mock_batch, mock_list, mock_service, authed_client, tmp_db):
        mock_list.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}],
            "nextPageToken": "token123",
        }
        mock_batch.return_value = (SAMPLE_EMAILS[:2], [])
        resp = authed_client.post("/emails/fetch", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched"] == 2
        assert data["next_page_token"] == "token123"

    @patch("ai_classifier.classify_emails")
    def test_classify_emails(self, mock_classify, authed_client, seeded_db):
        mock_classify.return_value = [
            {"id": "msg_003", "category": "Receipts", "confidence": 0.95, "reasoning": "receipt"},
        ]
        resp = authed_client.post("/emails/classify", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["classified"] == 1

    @patch("ai_classifier.classify_emails")
    def test_classify_specific_ids(self, mock_classify, authed_client, seeded_db):
        mock_classify.return_value = [
            {"id": "msg_001", "category": "Social", "confidence": 0.7, "reasoning": "social"},
        ]
        resp = authed_client.post("/emails/classify", json={"email_ids": ["msg_001"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["classified"] == 1

    def test_get_stats(self, authed_client, seeded_db):
        resp = authed_client.get("/emails/stats")
        assert resp.status_code == 200

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.get_labels", return_value=[{"id": "L1", "name": "Test", "type": "user"}])
    def test_get_labels(self, mock_labels, mock_service, authed_client):
        resp = authed_client.get("/emails/labels")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_emails(self, authed_client, seeded_db):
        resp = authed_client.get("/emails/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["emails"]) == 3

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.bulk_action")
    def test_delete_action(self, mock_bulk, mock_service, authed_client, seeded_db):
        mock_bulk.return_value = {
            "success": 1, "failed": 0,
            "succeeded_ids": ["msg_001"], "errors": [],
        }
        resp = authed_client.post("/emails/actions/delete", json={"email_ids": ["msg_001"]})
        assert resp.status_code == 200
        assert resp.json()["success"] == 1

    def test_delete_empty_ids_rejected(self, authed_client, seeded_db):
        resp = authed_client.post("/emails/actions/delete", json={"email_ids": []})
        assert resp.status_code == 422

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.bulk_action")
    def test_archive_action(self, mock_bulk, mock_service, authed_client, seeded_db):
        mock_bulk.return_value = {
            "success": 1, "failed": 0,
            "succeeded_ids": ["msg_001"], "errors": [],
        }
        resp = authed_client.post("/emails/actions/archive", json={"email_ids": ["msg_001"]})
        assert resp.status_code == 200

    @patch("gmail_client.build_gmail_service")
    @patch("gmail_client.bulk_action")
    def test_mark_read(self, mock_bulk, mock_service, authed_client, seeded_db):
        mock_bulk.return_value = {
            "success": 1, "failed": 0,
            "succeeded_ids": ["msg_002"], "errors": [],
        }
        resp = authed_client.post(
            "/emails/actions/mark",
            json={"email_ids": ["msg_002"], "read": True},
        )
        assert resp.status_code == 200

    def test_move_requires_label(self, authed_client, seeded_db):
        resp = authed_client.post(
            "/emails/actions/move",
            json={"email_ids": ["msg_001"], "label_id": ""},
        )
        assert resp.status_code == 422

    @patch("gmail_client.build_gmail_service")
    def test_delete_nonexistent_ids_rejected(self, mock_service, authed_client, seeded_db):
        resp = authed_client.post(
            "/emails/actions/delete",
            json={"email_ids": ["nonexistent_id"]},
        )
        assert resp.status_code == 400
