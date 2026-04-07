"""Application configuration loaded from environment variables."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-to-a-random-32-char-string")
APP_PORT = int(os.getenv("APP_PORT", 8000))
EMAILS_PER_PAGE = int(os.getenv("EMAILS_PER_PAGE", 50))
CLASSIFIER_BATCH_SIZE = int(os.getenv("CLASSIFIER_BATCH_SIZE", 20))
SAVE_DIR = os.getenv("SAVE_DIR", "./saved_emails")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 3600))

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
DB_PATH = "email_cleaner.db"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
REDIRECT_URI = f"http://localhost:{APP_PORT}/auth/callback"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
