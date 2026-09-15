"""Google Sheets API wrapper — backs the bonus audit-log agent."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from backend.config import get_settings
from backend.utils.errors import AuthenticationError, IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._service = None
        self.mock_rows: list[list[Any]] = []

    def _build_service(self):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover
            raise IntegrationError("sheets", f"google client libs missing: {exc}") from exc

        creds = None
        token_path = self.settings.google_token_path
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.settings.google_credentials_path):
                    raise AuthenticationError("sheets", "No OAuth credentials found.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.settings.google_credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    async def append_row(self, values: list[Any], sheet_range: str = "Sheet1!A1") -> dict[str, Any]:
        if (
            self.settings.mock_mode
            or not self.settings.google_sheets_spreadsheet_id
            or not os.path.exists(self.settings.google_token_path)
        ):
            await asyncio.sleep(0.1)
            self.mock_rows.append(values)
            return {"updates": {"updatedRange": sheet_range, "updatedRows": 1}}

        try:
            service = self._build_service()
            result = await asyncio.to_thread(
                lambda: service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.settings.google_sheets_spreadsheet_id,
                    range=sheet_range,
                    valueInputOption="USER_ENTERED",
                    body={"values": [values]},
                )
                .execute()
            )
            return result
        except Exception as exc:
            logger.error("sheets.append_row_failed", error=str(exc))
            raise IntegrationError("sheets", str(exc)) from exc
