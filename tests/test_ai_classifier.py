import json
from unittest.mock import MagicMock, patch

import ai_classifier
import config
from tests.conftest import SAMPLE_EMAILS


def _mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


class TestClassifyEmails:
    @patch.object(ai_classifier, "_get_client")
    def test_single_batch(self, mock_get_client):
        response_data = [
            {"id": "msg_001", "category": "Work", "confidence": 0.9, "reasoning": "work related"},
        ]
        client = MagicMock()
        client.messages.create.return_value = _mock_response(json.dumps(response_data))
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert len(results) == 1
        assert results[0]["category"] == "Work"
        assert results[0]["confidence"] == 0.9

    @patch.object(ai_classifier, "_get_client")
    def test_multiple_batches(self, mock_get_client):
        original_batch_size = config.CLASSIFIER_BATCH_SIZE
        config.CLASSIFIER_BATCH_SIZE = 2

        responses = [
            json.dumps([
                {"id": "msg_001", "category": "Work", "confidence": 0.9, "reasoning": "work"},
                {"id": "msg_002", "category": "Newsletters", "confidence": 0.8, "reasoning": "news"},
            ]),
            json.dumps([
                {"id": "msg_003", "category": "Receipts", "confidence": 0.95, "reasoning": "receipt"},
            ]),
        ]
        client = MagicMock()
        client.messages.create.side_effect = [_mock_response(r) for r in responses]
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS)
        config.CLASSIFIER_BATCH_SIZE = original_batch_size

        assert len(results) == 3
        assert results[0]["category"] == "Work"
        assert results[1]["category"] == "Newsletters"
        assert results[2]["category"] == "Receipts"

    @patch.object(ai_classifier, "_get_client")
    def test_invalid_category_defaults_to_uncategorized(self, mock_get_client):
        response_data = [
            {"id": "msg_001", "category": "InvalidCategory", "confidence": 0.9, "reasoning": "test"},
        ]
        client = MagicMock()
        client.messages.create.return_value = _mock_response(json.dumps(response_data))
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert results[0]["category"] == "Uncategorized"

    @patch.object(ai_classifier, "_get_client")
    def test_confidence_clamped(self, mock_get_client):
        response_data = [
            {"id": "msg_001", "category": "Work", "confidence": 1.5, "reasoning": "test"},
        ]
        client = MagicMock()
        client.messages.create.return_value = _mock_response(json.dumps(response_data))
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert results[0]["confidence"] == 1.0

    @patch.object(ai_classifier, "_get_client")
    def test_api_error_returns_fallback(self, mock_get_client):
        client = MagicMock()
        client.messages.create.side_effect = Exception("API Error")
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert len(results) == 1
        assert results[0]["category"] == "Uncategorized"
        assert results[0]["confidence"] == 0.0

    @patch.object(ai_classifier, "_get_client")
    def test_json_parse_error_returns_fallback(self, mock_get_client):
        client = MagicMock()
        client.messages.create.return_value = _mock_response("not valid json {{{")
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:2])
        assert len(results) == 2
        assert all(r["category"] == "Uncategorized" for r in results)

    @patch.object(ai_classifier, "_get_client")
    def test_strips_markdown_fences(self, mock_get_client):
        response_data = [
            {"id": "msg_001", "category": "Spam", "confidence": 0.99, "reasoning": "spam"},
        ]
        fenced = f"```json\n{json.dumps(response_data)}\n```"
        client = MagicMock()
        client.messages.create.return_value = _mock_response(fenced)
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert results[0]["category"] == "Spam"

    @patch.object(ai_classifier, "_get_client")
    def test_missing_email_in_response_defaults(self, mock_get_client):
        response_data = []
        client = MagicMock()
        client.messages.create.return_value = _mock_response(json.dumps(response_data))
        mock_get_client.return_value = client

        results = ai_classifier.classify_emails(SAMPLE_EMAILS[:1])
        assert results[0]["category"] == "Uncategorized"
        assert results[0]["confidence"] == 0.5


class TestFallbackResults:
    def test_returns_uncategorized(self):
        results = ai_classifier._fallback_results(SAMPLE_EMAILS)
        assert len(results) == 3
        for r in results:
            assert r["category"] == "Uncategorized"
            assert r["confidence"] == 0.0
            assert r["reasoning"] == "Classification failed"
