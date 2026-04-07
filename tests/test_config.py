
import config


class TestConfigDefaults:
    def test_app_port_default(self):
        assert isinstance(config.APP_PORT, int)

    def test_emails_per_page_default(self):
        assert config.EMAILS_PER_PAGE == 50

    def test_classifier_batch_size_default(self):
        assert config.CLASSIFIER_BATCH_SIZE == 20

    def test_categories(self):
        assert len(config.CATEGORIES) == 7
        assert "Newsletters" in config.CATEGORIES
        assert "Uncategorized" in config.CATEGORIES

    def test_gmail_scopes(self):
        assert len(config.GMAIL_SCOPES) == 1
        assert "gmail.modify" in config.GMAIL_SCOPES[0]

    def test_get_logger(self):
        logger = config.get_logger("test")
        assert logger.name == "test"

    def test_session_max_age_default(self):
        assert isinstance(config.SESSION_MAX_AGE, int)
        assert config.SESSION_MAX_AGE > 0
