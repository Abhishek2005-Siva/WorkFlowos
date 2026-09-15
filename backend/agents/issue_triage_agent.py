"""Issue Triage Agent — GitHub Issue Intelligence.

Triggered by a real GitHub webhook (issues opened). Honest scope note:
"assigns to appropriate team member" from the original idea assumes a
team roster that doesn't exist here — this labels by priority, comments
with reasoning, and alerts, which is the single-user-honest version of
"routes the issue to attention."
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.github import GitHubClient
from backend.integrations.google_sheets import SheetsClient
from backend.integrations.slack import SlackClient
from backend.integrations.telegram import TelegramClient
from backend.utils.llm import llm_triage_issue

SHEET_TAB = "GitHubIssues"
SHEET_HEADER = ["timestamp", "issue_number", "title", "priority", "reasoning"]


class IssueTriageAgent(BaseAgent):
    def __init__(
        self,
        github_client: GitHubClient | None = None,
        sheets_client: SheetsClient | None = None,
        slack_client: SlackClient | None = None,
        telegram_client: TelegramClient | None = None,
    ):
        super().__init__("Issue Triage Agent", "issue_triage")
        self.github_client = github_client or GitHubClient()
        self.sheets_client = sheets_client or SheetsClient()
        self.slack_client = slack_client or SlackClient()
        self.telegram_client = telegram_client or TelegramClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.triage(context["issue_number"], context["title"], context["body"], context["html_url"])

    async def triage(self, issue_number: int, title: str, body: str, html_url: str) -> dict[str, Any]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning(f"Triaging issue #{issue_number}: {title}")

        result = await llm_triage_issue(title, body or "")
        priority = result.get("priority", "medium")
        reasoning = result.get("reasoning", "")

        await self.log_reasoning(f"Priority: {priority} — {reasoning}")

        await self.set_status(AgentStatus.ACTING)
        await self.github_client.add_labels(issue_number, [f"priority:{priority}"])
        await self.github_client.comment_issue(
            issue_number, f"🤖 Auto-triaged as **{priority}** priority.\n\n_{reasoning}_"
        )

        await self.slack_client.send_message(
            channel=self.settings.standup_slack_channel,
            text=f"🏷️ Issue #{issue_number} triaged as *{priority}*: {title}\n{html_url}",
        )

        if priority in ("critical", "high"):
            await self.telegram_client.send_message(f"🚨 {priority.upper()} issue: {title}\n{html_url}")

        await self.sheets_client.ensure_tab_exists(SHEET_TAB, header=SHEET_HEADER)
        await self.sheets_client.append_row(
            [datetime.now(timezone.utc).isoformat(), issue_number, title, priority, reasoning],
            sheet_range=f"{SHEET_TAB}!A1",
        )

        await event_bus.publish(
            type=EventType.API_CALL,
            agent_name=self.name,
            message=f"🏷️ Issue #{issue_number} triaged as {priority}: {title}",
            data={"issue_number": issue_number, "priority": priority},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"issue_number": issue_number, "priority": priority}
