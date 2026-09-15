"""Capacity Agent — Team Capacity & Workload Balancer, single-user adapted.

Honest scope note: the original idea assumes a team roster to balance
work across (read each member's calendar/tasks/Slack activity, then
reassign). This system has no multi-user data source — Todoist and
Calendar are both scoped to the one connected account. What's real and
useful here instead: your own capacity signal (task load + calendar
busyness) as an early-warning report, which is the single-user-honest
version of "workload balancing." Reassignment logic would need a real
team roster wired in before it could do anything but fabricate data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.google_calendar import CalendarClient
from backend.integrations.google_sheets import SheetsClient
from backend.integrations.slack import SlackClient
from backend.integrations.todoist import TodoistClient

SHEET_TAB = "Capacity"
SHEET_HEADER = ["timestamp", "open_tasks", "overdue_tasks", "calendar_busy_pct", "load_level"]


class CapacityAgent(BaseAgent):
    def __init__(
        self,
        todoist_client: TodoistClient | None = None,
        calendar_client: CalendarClient | None = None,
        sheets_client: SheetsClient | None = None,
        slack_client: SlackClient | None = None,
    ):
        super().__init__("Capacity Agent", "capacity")
        self.todoist_client = todoist_client or TodoistClient()
        self.calendar_client = calendar_client or CalendarClient()
        self.sheets_client = sheets_client or SheetsClient()
        self.slack_client = slack_client or SlackClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.report()

    async def report(self) -> dict[str, Any]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning("Checking open tasks and calendar load")

        tasks = await self.run_with_fallback("get_tasks", lambda: self.todoist_client.get_tasks())
        now = datetime.now(timezone.utc)
        overdue = 0
        for t in tasks:
            due = t.get("due")
            due_dt_str = due.get("datetime") or due.get("date") if isinstance(due, dict) else None
            if due_dt_str:
                try:
                    due_dt = datetime.fromisoformat(due_dt_str.replace("Z", "+00:00"))
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone.utc)
                    if due_dt < now:
                        overdue += 1
                except ValueError:
                    pass

        window_end = now + timedelta(hours=48)
        events = await self.run_with_fallback(
            "list_events", lambda: self.calendar_client.list_events(now, window_end)
        )
        busy_minutes = sum((e["end"] - e["start"]).total_seconds() / 60 for e in events)
        working_minutes = 48 * 60 * (9 / 24)  # rough: 9 working hours/day over 2 days
        busy_pct = min(100, round((busy_minutes / working_minutes) * 100)) if working_minutes else 0

        if overdue >= 3 or busy_pct >= 80:
            load = "high"
        elif overdue >= 1 or busy_pct >= 50:
            load = "medium"
        else:
            load = "low"

        await self.log_reasoning(
            f"{len(tasks)} open task(s), {overdue} overdue, {busy_pct}% of next 48h booked -> {load} load"
        )

        message = (
            f"📊 **Capacity check** — {load.upper()} load\n"
            f"• {len(tasks)} open tasks ({overdue} overdue)\n"
            f"• {busy_pct}% of the next 48h booked"
        )
        await self.slack_client.send_message(channel=self.settings.standup_slack_channel, text=message)

        await self.sheets_client.ensure_tab_exists(SHEET_TAB, header=SHEET_HEADER)
        await self.sheets_client.append_row(
            [now.isoformat(), len(tasks), overdue, busy_pct, load], sheet_range=f"{SHEET_TAB}!A1"
        )

        await event_bus.publish(
            type=EventType.SLACK_NOTIFICATION,
            agent_name=self.name,
            message=message,
            data={"open_tasks": len(tasks), "overdue": overdue, "busy_pct": busy_pct, "load": load},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"open_tasks": len(tasks), "overdue": overdue, "busy_pct": busy_pct, "load": load}
