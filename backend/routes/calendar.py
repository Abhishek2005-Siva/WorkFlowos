"""Read-only calendar view for the dashboard — separate from the Calendar
Agent's own availability-checking logic, this just lists what's already
on the calendar(s) so you can see everything in one place, not just what
the pipeline itself created."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from backend.core.orchestrator import orchestrator

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
async def list_calendar_events(days_back: int = Query(1, ge=0), days_forward: int = Query(14, ge=1, le=90)):
    calendar_client = orchestrator.calendar_agent.calendar_client
    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=days_back)
    time_max = now + timedelta(days=days_forward)

    events = await calendar_client.list_events(time_min, time_max)
    events.sort(key=lambda e: e["start"])

    return {
        "events": [
            {
                "summary": e["summary"],
                "start": e["start"].isoformat(),
                "end": e["end"].isoformat(),
                "calendar_id": e.get("calendar_id", "primary"),
            }
            for e in events
        ],
        "mock": calendar_client.is_mock,
    }
