"""Reporting Agent — Daily Standup Generator and Weekly Status Report.

Both are the same shape (aggregate recent activity across Todoist/GitHub/
Notion, synthesize with an LLM, publish somewhere, log for history) at
different windows and destinations, so one agent handles both rather than
duplicating the aggregation logic.

Honest scope note: the original idea included "email to team" and
"reads Slack messages for context" — this account's Gmail scope is
read-only (gmail.readonly, not gmail.send), so there's no email-sending
here, and there's no Slack Events API subscription wired up to read
historical channel messages. Both get a Slack post instead, which is
what actually gets seen day to day anyway.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.github import GitHubClient
from backend.integrations.google_sheets import SheetsClient
from backend.integrations.slack import SlackClient
from backend.integrations.todoist import TodoistClient
from backend.utils.llm import llm_synthesize_standup
from backend.utils.notify import safe_notify

STANDUP_SHEET_TAB = "Standups"
WEEKLY_SHEET_TAB = "WeeklyReports"
SHEET_HEADER = ["timestamp", "kind", "window_hours", "tasks_completed", "commits", "summary"]


class ReportingAgent(BaseAgent):
    def __init__(
        self,
        todoist_client: TodoistClient | None = None,
        github_client: GitHubClient | None = None,
        sheets_client: SheetsClient | None = None,
        slack_client: SlackClient | None = None,
    ):
        super().__init__("Reporting Agent", "reporter")
        self.todoist_client = todoist_client or TodoistClient()
        self.github_client = github_client or GitHubClient()
        self.sheets_client = sheets_client or SheetsClient()
        self.slack_client = slack_client or SlackClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.generate(context["kind"])

    async def _gather_activity(self, window_hours: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=window_hours)

        completed = await self.run_with_fallback(
            "get_completed_tasks",
            lambda: self.todoist_client.get_completed_tasks(since.isoformat(), now.isoformat()),
        )
        commits = await self.run_with_fallback(
            "list_recent_commits", lambda: self.github_client.list_recent_commits(since.isoformat())
        )

        task_titles = [t.get("content", "") for t in completed]
        commit_messages = [c.get("commit", {}).get("message", "").split("\n")[0] for c in commits]
        return {"task_titles": task_titles, "commit_messages": commit_messages}

    async def generate(self, kind: str) -> dict[str, Any]:
        """kind: 'standup' (24h window, posts to activity channel) or
        'weekly' (7-day window, posts to activity channel with a weekly
        framing). Both log a row to their own Sheets tab."""
        await self.set_status(AgentStatus.THINKING)
        window_hours = 24 if kind == "standup" else 24 * 7
        await self.log_reasoning(f"Gathering {'daily' if kind == 'standup' else 'weekly'} activity")

        activity = await self._gather_activity(window_hours)

        await self.log_reasoning(
            f"Found {len(activity['task_titles'])} completed task(s), {len(activity['commit_messages'])} commit(s)"
        )

        await self.set_status(AgentStatus.ACTING)
        summary = await llm_synthesize_standup(activity["task_titles"], activity["commit_messages"], notes=[])

        emoji = "☀️" if kind == "standup" else "📈"
        title = "Daily Standup" if kind == "standup" else "Weekly Status Report"
        message = f"{emoji} **{title}**\n\n{summary}"

        await safe_notify(
            self.name, "Slack", self.slack_client.send_message(channel=self.settings.standup_slack_channel, text=message)
        )

        tab = STANDUP_SHEET_TAB if kind == "standup" else WEEKLY_SHEET_TAB
        await safe_notify(self.name, "Sheets", self.sheets_client.ensure_tab_exists(tab, header=SHEET_HEADER))
        await safe_notify(
            self.name,
            "Sheets",
            self.sheets_client.append_row(
                [
                    datetime.now(timezone.utc).isoformat(),
                    kind,
                    window_hours,
                    len(activity["task_titles"]),
                    len(activity["commit_messages"]),
                    summary[:500],
                ],
                sheet_range=f"{tab}!A1",
            ),
        )

        await event_bus.publish(
            type=EventType.SLACK_NOTIFICATION,
            agent_name=self.name,
            message=f"{emoji} Posted {title.lower()} to {self.settings.standup_slack_channel}",
            data={"kind": kind, "summary": summary},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"kind": kind, "summary": summary, "activity": activity}
