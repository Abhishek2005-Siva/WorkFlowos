"""PR Review Agent — analyzes new pull requests and posts review comments.

Triggered by a real GitHub webhook (pull_request opened/synchronize), not
polling. Honest scope note: "cross-references team standards in Notion"
and "auto-assigns reviewers based on code areas" from the original idea
need a standards database and a team roster this single-user setup
doesn't have — this posts a genuine LLM code review plus logs metrics,
which is the part that's actually verifiable and useful without inventing
data that doesn't exist.
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
from backend.utils.llm import llm_review_code
from backend.utils.notify import safe_notify

SHEET_TAB = "PRReviews"
SHEET_HEADER = ["timestamp", "pr_number", "title", "author", "verdict_snippet"]


class PRReviewAgent(BaseAgent):
    def __init__(
        self,
        github_client: GitHubClient | None = None,
        sheets_client: SheetsClient | None = None,
        slack_client: SlackClient | None = None,
    ):
        super().__init__("PR Review Agent", "code_reviewer")
        self.github_client = github_client or GitHubClient()
        self.sheets_client = sheets_client or SheetsClient()
        self.slack_client = slack_client or SlackClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.review(context["pr_number"], context["title"], context["author"], context["html_url"])

    async def review(self, pr_number: int, title: str, author: str, html_url: str) -> dict[str, Any]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning(f"Fetching diff for PR #{pr_number}: {title}")

        diff = await self.run_with_fallback("get_pr_diff", lambda: self.github_client.get_pr_diff(pr_number))

        await self.log_reasoning("Analyzing diff")
        review_text = await llm_review_code(diff, title)

        await self.set_status(AgentStatus.ACTING)
        await self.github_client.comment_issue(pr_number, f"🤖 **Automated review**\n\n{review_text}")

        await safe_notify(
            self.name,
            "Slack",
            self.slack_client.send_message(
                channel=self.settings.standup_slack_channel,
                text=f"🔍 Reviewed PR #{pr_number} *{title}* by {author}\n{html_url}\n\n{review_text[:300]}",
            ),
        )

        await safe_notify(self.name, "Sheets", self.sheets_client.ensure_tab_exists(SHEET_TAB, header=SHEET_HEADER))
        await safe_notify(
            self.name,
            "Sheets",
            self.sheets_client.append_row(
                [datetime.now(timezone.utc).isoformat(), pr_number, title, author, review_text[:200]],
                sheet_range=f"{SHEET_TAB}!A1",
            ),
        )

        await event_bus.publish(
            type=EventType.API_CALL,
            agent_name=self.name,
            message=f"🔍 Reviewed PR #{pr_number}: {title}",
            data={"pr_number": pr_number, "review": review_text},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"pr_number": pr_number, "review": review_text}
