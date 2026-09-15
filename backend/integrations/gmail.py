"""Gmail API wrapper.

Real mode uses OAuth 2.0 "installed app" credentials (see
docs/API_INTEGRATIONS.md for the one-time setup). Mock mode returns a
rotating set of realistic sample emails so the Email Agent, and everything
downstream of it, can be built and demoed before credentials exist.
"""
from __future__ import annotations

import asyncio
import base64
import os
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings
from backend.utils.errors import AuthenticationError, IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_MOCK_INBOX: list[dict[str, Any]] = [
    {
        "id": "mock_email_1",
        "from": "Alex Rivera <alex@company.com>",
        "subject": "Quick sync on Q4 strategy",
        "body": (
            "Hey! Could we grab 30 minutes this week to sync on Q4 strategy? "
            "Nothing urgent, just want to align before the planning doc is due."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "mock_email_2",
        "from": "Priya Nair <priya@company.com>",
        "subject": "Please review the vendor contract by Friday",
        "body": (
            "Can you please review the attached vendor contract and send edits "
            "by Friday EOD? Legal is waiting on our sign-off."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "mock_email_3",
        "from": "Sam Okafor <sam@company.com>",
        "subject": "URGENT: production error spike",
        "body": (
            "We're seeing a spike in 500 errors on checkout since 9am. Need eyes "
            "on this ASAP, customers are affected."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
]


class GmailClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._service = None
        self._mock_cursor = 0

    def _build_service(self):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover
            raise IntegrationError("gmail", f"google client libs missing: {exc}") from exc

        creds = None
        token_path = self.settings.google_token_path
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.settings.google_credentials_path):
                    raise AuthenticationError(
                        "gmail",
                        "No OAuth credentials found. Run scripts/google_auth_setup.py first.",
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.settings.google_credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def _use_mock(self) -> bool:
        # No OAuth consent has been completed yet (see scripts/google_auth_setup.py)
        # -> behave like mock mode regardless of the global flag, same as
        # every other integration falls back when its own key is missing.
        return self.settings.mock_mode or not os.path.exists(self.settings.google_token_path)

    async def list_messages(self, query: str = "is:unread", max_results: int = 5) -> list[dict[str, Any]]:
        if self._use_mock():
            await asyncio.sleep(0.15)
            batch = _MOCK_INBOX[self._mock_cursor : self._mock_cursor + max_results]
            if not batch:
                self._mock_cursor = 0
                batch = _MOCK_INBOX[:max_results]
            else:
                self._mock_cursor += len(batch)
            return batch

        try:
            service = self._build_service()
            results = await asyncio.to_thread(
                lambda: service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = []
            for msg_ref in results.get("messages", []):
                full = await asyncio.to_thread(
                    lambda mid=msg_ref["id"]: service.users()
                    .messages()
                    .get(userId="me", id=mid, format="full")
                    .execute()
                )
                messages.append(self._parse_message(full))
            return messages
        except Exception as exc:
            logger.error("gmail.list_messages_failed", error=str(exc))
            raise IntegrationError("gmail", str(exc)) from exc

    def _parse_message(self, raw: dict[str, Any]) -> dict[str, Any]:
        headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}
        body = self._extract_body(raw["payload"])
        return {
            "id": raw["id"],
            "from": headers.get("from", "Unknown"),
            "subject": headers.get("subject", "(no subject)"),
            "body": body,
            "timestamp": headers.get("date", ""),
        }

    def _extract_body(self, payload: dict[str, Any]) -> str:
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []) or []:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []) or []:
            text = self._extract_body(part)
            if text:
                return text
        return ""

    def reset_mock_cursor(self) -> None:
        self._mock_cursor = 0

    async def get_message_content(self, message_id: str) -> str:
        if self._use_mock():
            for m in _MOCK_INBOX:
                if m["id"] == message_id:
                    return m["body"]
            return ""
        service = self._build_service()
        full = await asyncio.to_thread(
            lambda: service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )
        return self._extract_body(full["payload"])
