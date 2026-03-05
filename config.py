import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-to-a-random-32-char-string")
APP_PORT = int(os.getenv("APP_PORT", 8000))
EMAILS_PER_PAGE = int(os.getenv("EMAILS_PER_PAGE", 50))
CLASSIFIER_BATCH_SIZE = int(os.getenv("CLASSIFIER_BATCH_SIZE", 20))
SAVE_DIR = os.getenv("SAVE_DIR", "./saved_emails")

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
DB_PATH = "email_cleaner.db"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
REDIRECT_URI = f"http://localhost:{APP_PORT}/auth/callback"

CATEGORIES = [
    "Newsletters",
    "Receipts",
    "Work",
    "Social",
    "Notifications",
    "Spam",
    "Uncategorized",
]
