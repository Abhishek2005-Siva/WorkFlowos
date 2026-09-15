"""Google Calendar API wrapper.

This is a thin data layer only: it returns raw busy blocks and creates
events. All the "reasoning" (finding gaps, scoring slots, deciding what's
optimal) lives in agents/calendar_agent.py so that logic stays testable
independent of the Google API.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import get_settings
from backend.utils.errors import AuthenticationError, IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._service = None

    def _build_service(self):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover
            raise IntegrationError("calendar", f"google client libs missing: {exc}") from exc

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
                        "calendar",
                        "No OAuth credentials found. Run scripts/google_auth_setup.py first.",
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.settings.google_credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def _mock_busy_blocks(self, time_min: datetime, time_max: datetime) -> list[dict[str, Any]]:
        """A fixed, realistic busy schedule anchored to `time_min`'s day so
        demos and tests are deterministic regardless of what day it is."""
        day0 = time_min.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = [
            {
                "summary": "Daily standup",
                "start": day0 + timedelta(days=1, hours=9),
                "end": day0 + timedelta(days=1, hours=9, minutes=30),
                "calendar_id": "primary",
            },
            {
                "summary": "1:1 with manager",
                "start": day0 + timedelta(days=1, hours=15),
                "end": day0 + timedelta(days=1, hours=17),
                "calendar_id": "primary",
            },
            {
                "summary": "All-hands (fully booked day)",
                "start": day0 + timedelta(days=2, hours=9),
                "end": day0 + timedelta(days=2, hours=17),
                "calendar_id": "work",
            },
        ]
        return [c for c in candidates if c["start"] < time_max and c["end"] > time_min]

    def _use_mock(self) -> bool:
        return self.settings.mock_mode or not os.path.exists(self.settings.google_token_path)

    @property
    def is_mock(self) -> bool:
        return self._use_mock()

    async def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        calendar_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if self._use_mock():
            await asyncio.sleep(0.2)
            return self._mock_busy_blocks(time_min, time_max)

        calendar_ids = calendar_ids or self.settings.calendar_id_list
        try:
            service = self._build_service()
            events: list[dict[str, Any]] = []
            for cal_id in calendar_ids:
                result = await asyncio.to_thread(
                    lambda cid=cal_id: service.events()
                    .list(
                        calendarId=cid,
                        timeMin=time_min.isoformat(),
                        timeMax=time_max.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                for item in result.get("items", []):
                    start = item["start"].get("dateTime", item["start"].get("date"))
                    end = item["end"].get("dateTime", item["end"].get("date"))
                    events.append(
                        {
                            "summary": item.get("summary", "(busy)"),
                            "start": datetime.fromisoformat(start),
                            "end": datetime.fromisoformat(end),
                            "calendar_id": cal_id,
                        }
                    )
            return events
        except Exception as exc:
            logger.error("calendar.list_events_failed", error=str(exc))
            raise IntegrationError("calendar", str(exc)) from exc

    async def create_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        if self._use_mock():
            await asyncio.sleep(0.25)
            event_id = f"event_{uuid.uuid4().hex[:10]}"
            meet_code = "-".join(uuid.uuid4().hex[i : i + 3] for i in (0, 3, 6))
            return {
                "id": event_id,
                "html_link": f"https://calendar.google.com/event?eid={event_id}",
                "meet_link": f"https://meet.google.com/{meet_code}",
            }

        try:
            service = self._build_service()
            body = {
                "summary": event_data["title"],
                "description": event_data.get("description", ""),
                "start": {"dateTime": event_data["start_time"]},
                "end": {"dateTime": event_data["end_time"]},
                "attendees": [{"email": a} for a in event_data.get("attendees", [])],
                "conferenceData": {
                    "createRequest": {
                        "requestId": uuid.uuid4().hex,
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }
            created = await asyncio.to_thread(
                lambda: service.events()
                .insert(
                    calendarId=event_data.get("calendar_id", "primary"),
                    body=body,
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute()
            )
            meet_link = ""
            for ep in created.get("conferenceData", {}).get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri", "")
            return {
                "id": created["id"],
                "html_link": created.get("htmlLink", ""),
                "meet_link": meet_link,
            }
        except Exception as exc:
            logger.error("calendar.create_event_failed", error=str(exc))
            raise IntegrationError("calendar", str(exc)) from exc

    async def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        if self._use_mock():
            await asyncio.sleep(0.05)
            return
        try:
            service = self._build_service()
            await asyncio.to_thread(
                lambda: service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            )
        except Exception as exc:
            logger.error("calendar.delete_event_failed", error=str(exc))
            raise IntegrationError("calendar", str(exc)) from exc
