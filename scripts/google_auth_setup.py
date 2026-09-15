#!/usr/bin/env python3
"""One-time OAuth 2.0 setup for Gmail, Calendar and Sheets.

Run this locally (needs a browser) once you've downloaded your OAuth
"Desktop app" credentials JSON from Google Cloud Console:

    python scripts/google_auth_setup.py

It walks through the consent screen and writes the resulting token to
GOOGLE_TOKEN_PATH (see .env), which gmail.py / google_calendar.py /
google_sheets.py then reuse (and silently refresh) on every subsequent run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow

from backend.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    # Needed only by scripts/gmail_watch_setup.py (Pub/Sub topic/subscription
    # creation for real-time Gmail push) — included here so you don't have
    # to redo consent later if you set that up after this initial run.
    "https://www.googleapis.com/auth/pubsub",
]


def main() -> None:
    settings = get_settings()
    creds_path = Path(settings.google_credentials_path)
    token_path = Path(settings.google_token_path)

    if not creds_path.exists():
        print(f"❌ No credentials file found at {creds_path}")
        print("   1. Go to https://console.cloud.google.com/apis/credentials")
        print("   2. Create an OAuth client ID of type 'Desktop app'")
        print("   3. Download the JSON and save it at that path")
        sys.exit(1)

    token_path.parent.mkdir(parents=True, exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json())
    print(f"✅ Token saved to {token_path}")
    print("   Set MOCK_MODE=false in .env to start using real Gmail/Calendar/Sheets data.")


if __name__ == "__main__":
    main()
