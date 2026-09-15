"""Calendar Coordination Agent.

Finds gaps across calendars, scores them by a simple "energy" heuristic,
creates events with auto-generated Google Meet links, and can propose an
alternative slot when the Task Agent raises a deadline conflict during
negotiation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.google_calendar import CalendarClient
from backend.utils.llm import llm_explain_slot_choice

WORKDAY_START_HOUR = 9
WORKDAY_END_HOUR = 18
SLOT_STEP_MINUTES = 30


def _heuristic_reason(hour: int) -> str:
    """Cheap default reason shown for every non-winning slot — only the
    slot that actually gets recommended is worth spending an LLM call on."""
    if 9 <= hour < 11:
        return "high energy morning slot"
    if 11 <= hour < 13:
        return "late morning, good focus window before lunch"
    if 13 <= hour < 15:
        return "early afternoon, post-lunch dip avoided"
    return "available within the requested window"


class CalendarAgent(BaseAgent):
    def __init__(self, calendar_client: CalendarClient | None = None):
        super().__init__("Calendar Agent", "scheduler")
        self.calendar_client = calendar_client or CalendarClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        duration = context.get("duration_minutes", 30)
        slots = await self.check_availability(duration, context.get("time_preferences"))
        return {"agent": self.name, "slots": slots}

    async def check_availability(
        self,
        duration_minutes: int,
        time_preferences: dict[str, Any] | None = None,
        avoid: list[tuple[datetime, datetime]] | None = None,
        window_hours: int = 48,
        explain_top: bool = True,
    ) -> list[dict[str, Any]]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning("Querying all calendars for availability")

        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=window_hours)

        busy_events = await self.run_with_fallback(
            "list_events",
            lambda: self.calendar_client.list_events(now, window_end),
            cache_key="last_calendar_events",
        )

        await self.log_reasoning(f"Found {len(busy_events)} existing event(s) across calendars")

        candidates = self._find_gaps(busy_events, duration_minutes, now, window_end, avoid or [])

        await self.log_reasoning(f"Identified {len(candidates)} candidate slot(s), scoring by preference")
        scored = self._score_slots(candidates, time_preferences)
        scored.sort(key=lambda s: s["score"], reverse=True)

        if scored:
            top = scored[0]
            if explain_top:
                # Only the winning slot's explanation is ever shown, so only
                # it is worth a real LLM call — scoring every candidate here
                # would mean up to a dozen sequential API calls per check.
                # Negotiation rounds skip this (explain_top=False): an
                # intermediate counter-proposal that might get rejected
                # doesn't need a polished explanation, and skipping it keeps
                # each round fast instead of compounding LLM latency.
                top["reason"] = await llm_explain_slot_choice(top, scored[1:4])
            await self.log_reasoning(
                f"Top recommendation: {top['start']} (score {top['score']:.2f}) — {top['reason']}"
            )

        await self.set_status(AgentStatus.IDLE)
        return scored

    def _find_gaps(
        self,
        busy_events: list[dict[str, Any]],
        duration_minutes: int,
        window_start: datetime,
        window_end: datetime,
        avoid: list[tuple[datetime, datetime]],
    ) -> list[dict[str, Any]]:
        busy = sorted(
            [(e["start"], e["end"]) for e in busy_events] + list(avoid),
            key=lambda b: b[0],
        )
        duration = timedelta(minutes=duration_minutes)
        step = timedelta(minutes=SLOT_STEP_MINUTES)

        candidates = []
        cursor = window_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        while cursor + duration <= window_end:
            if WORKDAY_START_HOUR <= cursor.hour < WORKDAY_END_HOUR and cursor.weekday() < 5:
                slot_end = cursor + duration
                overlaps = any(cursor < b_end and slot_end > b_start for b_start, b_end in busy)
                if not overlaps and cursor > window_start:
                    candidates.append({"start": cursor, "end": slot_end})
            cursor += step

        return candidates[:12]

    def _score_slots(
        self, candidates: list[dict[str, Any]], time_preferences: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        scored = []
        for c in candidates:
            hour = c["start"].hour
            if 9 <= hour < 11:
                base_score = 0.95
            elif 11 <= hour < 13:
                base_score = 0.75
            elif 13 <= hour < 15:
                base_score = 0.7
            else:
                base_score = 0.55

            days_out = (c["start"].date() - datetime.now(timezone.utc).date()).days
            recency_bonus = max(0, 0.05 - days_out * 0.02)
            score = round(min(base_score + recency_bonus, 1.0), 2)

            scored.append(
                {
                    "start": c["start"].isoformat(),
                    "end": c["end"].isoformat(),
                    "start_hour": hour,
                    "score": score,
                    "reason": _heuristic_reason(hour),
                }
            )
        return scored

    async def create_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        await self.log_reasoning(f"Creating calendar event: {event_data['title']}")

        result = await self.run_with_fallback(
            "create_event", lambda: self.calendar_client.create_event(event_data)
        )

        await self.log_reasoning(f"Google Meet link generated: {result['meet_link']}")
        await event_bus.publish(
            type=EventType.EVENT_CREATED,
            agent_name=self.name,
            message=f"📅 Created \"{event_data['title']}\" — {result['meet_link']}",
            data={**result, "title": event_data["title"], "start_time": event_data["start_time"]},
        )

        await self.set_status(AgentStatus.IDLE)
        return result

    async def propose_alternative(
        self,
        duration_minutes: int,
        avoid: list[tuple[datetime, datetime]],
    ) -> dict[str, Any] | None:
        """Used during negotiation: find the next-best slot that avoids a
        set of time ranges the other agent flagged as conflicting."""
        await self.set_status(AgentStatus.NEGOTIATING)
        slots = await self.check_availability(duration_minutes, avoid=avoid, explain_top=False)
        await self.set_status(AgentStatus.IDLE)
        return slots[0] if slots else None
