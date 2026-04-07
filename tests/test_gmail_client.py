from unittest.mock import MagicMock, patch

import gmail_client


class TestParseMessage:
    def test_basic_message(self):
        msg = {
            "id": "abc123",
            "threadId": "thread1",
            "snippet": "Hello there",
            "sizeEstimate": 2048,
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice Smith <alice@example.com>"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
                ],
            },
        }
        result = gmail_client._parse_message(msg)
        assert result["id"] == "abc123"
        assert result["thread_id"] == "thread1"
        assert result["sender"] == "Alice Smith"
        assert result["sender_email"] == "alice@example.com"
        assert result["subject"] == "Test Subject"
        assert result["snippet"] == "Hello there"
        assert result["size_estimate"] == 2048
        assert result["is_read"] is False

    def test_read_message(self):
        msg = {
            "id": "abc123",
            "labelIds": ["INBOX"],
            "payload": {"headers": []},
        }
        result = gmail_client._parse_message(msg)
        assert result["is_read"] is True

    def test_missing_headers(self):
        msg = {
            "id": "abc123",
            "labelIds": [],
            "payload": {"headers": []},
        }
        result = gmail_client._parse_message(msg)
        assert result["sender"] == ""
        assert result["sender_email"] == ""
        assert result["subject"] == "(no subject)"


class TestParseFrom:
    def test_name_and_email(self):
        name, email = gmail_client._parse_from("John Doe <john@example.com>")
        assert name == "John Doe"
        assert email == "john@example.com"

    def test_email_only(self):
        name, email = gmail_client._parse_from("john@example.com")
        assert name == "john@example.com"
        assert email == "john@example.com"

    def test_quoted_name(self):
        name, email = gmail_client._parse_from('"Jane Doe" <jane@example.com>')
        assert name == "Jane Doe"
        assert email == "jane@example.com"


class TestDecodeHeaderValue:
    def test_plain_text(self):
        assert gmail_client._decode_header_value("Hello World") == "Hello World"

    def test_encoded(self):
        result = gmail_client._decode_header_value("=?UTF-8?B?SGVsbG8=?=")
        assert result == "Hello"


class TestStripHtml:
    def test_removes_tags(self):
        html = "<p>Hello <b>World</b></p>"
        assert "Hello" in gmail_client._strip_html(html)
        assert "World" in gmail_client._strip_html(html)
        assert "<" not in gmail_client._strip_html(html)

    def test_removes_style_and_script(self):
        html = "<style>body{color:red}</style><script>alert(1)</script><p>Content</p>"
        result = gmail_client._strip_html(html)
        assert "Content" in result
        assert "color" not in result
        assert "alert" not in result

    def test_decodes_entities(self):
        html = "&amp; &lt; &gt; &nbsp;"
        result = gmail_client._strip_html(html)
        assert "&" in result
        assert "<" in result
        assert ">" in result


class TestBatchGetMessages:
    def test_batch_api_success(self):
        service = MagicMock()
        batch_obj = MagicMock()
        service.new_batch_http_request.return_value = batch_obj

        def mock_execute():
            for call in batch_obj.add.call_args_list:
                callback = call[1]["callback"]
                request_id = call[1]["request_id"]
                response = {
                    "id": request_id,
                    "threadId": "t1",
                    "snippet": "test",
                    "sizeEstimate": 100,
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "test@example.com"},
                            {"name": "Subject", "value": "Test"},
                            {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
                        ]
                    },
                }
                callback(request_id, response, None)

        batch_obj.execute.side_effect = mock_execute
        results, skipped = gmail_client.batch_get_messages(service, ["m1", "m2"])
        assert len(results) == 2
        assert len(skipped) == 0

    def test_batch_api_partial_failure(self):
        service = MagicMock()
        batch_obj = MagicMock()
        service.new_batch_http_request.return_value = batch_obj

        def mock_execute():
            calls = batch_obj.add.call_args_list
            cb0 = calls[0][1]["callback"]
            cb1 = calls[1][1]["callback"]
            cb0("m1", None, Exception("not found"))
            cb1("m2", {
                "id": "m2", "threadId": "t1", "snippet": "", "sizeEstimate": 0,
                "labelIds": [], "payload": {"headers": []},
            }, None)

        batch_obj.execute.side_effect = mock_execute
        results, skipped = gmail_client.batch_get_messages(service, ["m1", "m2"])
        assert len(results) == 1
        assert len(skipped) == 1
        assert skipped[0]["id"] == "m1"

    @patch.object(gmail_client, "_sequential_get_messages")
    def test_falls_back_to_sequential(self, mock_seq):
        service = MagicMock()
        service.new_batch_http_request.side_effect = Exception("batch not supported")
        mock_seq.return_value = ([{"id": "m1"}], [])
        results, skipped = gmail_client.batch_get_messages(service, ["m1"])
        mock_seq.assert_called_once()
        assert len(results) == 1


class TestSequentialGetMessages:
    @patch.object(gmail_client, "get_message_metadata")
    def test_success(self, mock_get):
        mock_get.side_effect = [
            {"id": "m1", "subject": "A"},
            {"id": "m2", "subject": "B"},
        ]
        results, skipped = gmail_client._sequential_get_messages(MagicMock(), ["m1", "m2"])
        assert len(results) == 2
        assert len(skipped) == 0

    @patch.object(gmail_client, "get_message_metadata")
    def test_non_429_error_skips(self, mock_get):
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 404
        mock_get.side_effect = [
            HttpError(resp, b"not found"),
            {"id": "m2", "subject": "B"},
        ]
        results, skipped = gmail_client._sequential_get_messages(MagicMock(), ["m1", "m2"])
        assert len(results) == 1
        assert len(skipped) == 1

    @patch("time.sleep")
    @patch.object(gmail_client, "get_message_metadata")
    def test_429_retry_succeeds(self, mock_get, mock_sleep):
        from googleapiclient.errors import HttpError

        resp_429 = MagicMock()
        resp_429.status = 429
        mock_get.side_effect = [
            HttpError(resp_429, b"rate limited"),
            {"id": "m1", "subject": "A"},
        ]
        results, skipped = gmail_client._sequential_get_messages(MagicMock(), ["m1"])
        assert len(results) == 1
        assert len(skipped) == 0
        mock_sleep.assert_called_once_with(1)


class TestBulkAction:
    def test_all_succeed(self):
        service = MagicMock()
        action = MagicMock()
        result = gmail_client.bulk_action(service, ["m1", "m2"], action)
        assert result["success"] == 2
        assert result["failed"] == 0
        assert action.call_count == 2

    def test_partial_failure(self):
        service = MagicMock()
        action = MagicMock(side_effect=[None, Exception("fail")])
        result = gmail_client.bulk_action(service, ["m1", "m2"], action)
        assert result["success"] == 1
        assert result["failed"] == 1
        assert result["errors"][0]["id"] == "m2"


class TestIsAuthenticated:
    @patch.object(gmail_client, "get_credentials")
    def test_true_when_valid(self, mock_creds):
        mock_creds.return_value = MagicMock()
        assert gmail_client.is_authenticated() is True

    @patch.object(gmail_client, "get_credentials")
    def test_false_on_exception(self, mock_creds):
        mock_creds.side_effect = FileNotFoundError()
        assert gmail_client.is_authenticated() is False
