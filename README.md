# Email Cleaner

A Python web app that connects to Gmail, categorizes your inbox with Claude AI, and lets you bulk delete, archive, move, save, and mark emails.

## Prerequisites

- Python 3.10+
- A Google account with Gmail
- An [Anthropic API key](https://console.anthropic.com/)

## Setup

### 1. GCP / Gmail credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a new project.
2. Navigate to **APIs & Services > Library**, search for **Gmail API**, and enable it.
3. Go to **APIs & Services > OAuth consent screen**:
   - Choose **External** user type.
   - Fill in the app name (e.g. "Email Cleaner"), support email, and developer contact.
   - Add the scope: `https://www.googleapis.com/auth/gmail.modify`
   - Under **Test users**, add your Gmail address.
4. Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/auth/callback`
   - Click **Create**, then download the JSON file.
5. Save the downloaded file as `credentials.json` in the project root.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...your-key...
SESSION_SECRET_KEY=any-long-random-string-here
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Usage

1. Click **Connect Gmail Account** and complete the Google OAuth flow.
2. Click **Fetch Emails** — this loads emails from your inbox and runs Claude AI to categorize them.
3. Emails are grouped into 7 categories: **Newsletters, Receipts, Work, Social, Notifications, Spam, Uncategorized**.
4. Select emails using checkboxes (or use **Select All** per category) and apply bulk actions:
   - **Delete** — moves to Gmail trash (recoverable)
   - **Archive** — removes from inbox, keeps in All Mail
   - **Move to...** — moves to a Gmail label of your choice
   - **Save to File** — exports email content as `.txt` files to `./saved_emails/`
   - **Mark Read / Unread**
5. Click **Fetch Emails** again to load more, or **Re-classify** to re-run AI on all cached emails.

## Configuration

All settings are in `.env` (defaults shown):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required. Your Anthropic API key. |
| `SESSION_SECRET_KEY` | — | Required. Random string for session signing. |
| `APP_PORT` | `8000` | Port the server listens on. |
| `EMAILS_PER_PAGE` | `50` | Emails fetched per "Fetch" call. |
| `CLASSIFIER_BATCH_SIZE` | `20` | Emails sent to Claude per API call. |
| `SAVE_DIR` | `./saved_emails` | Directory for saved email files. |

## File structure

```
email-cleaner/
├── main.py            # App entry point
├── config.py          # Settings
├── database.py        # SQLite cache
├── gmail_client.py    # Gmail API + OAuth2
├── ai_classifier.py   # Claude classification
├── routers/           # FastAPI route handlers
├── templates/         # Jinja2 HTML templates
├── static/            # CSS + JS
├── credentials.json   # Your GCP credentials (gitignored)
├── .env               # Your secrets (gitignored)
└── requirements.txt
```
