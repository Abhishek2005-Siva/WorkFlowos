"""GitHub DevOps Agent (bonus) — auto-files issues from escalations/errors
and comments on them as they're triaged."""
from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.github import GitHubClient


class GitHubAgent(BaseAgent):
    def __init__(self, github_client: GitHubClient | None = None):
        super().__init__("GitHub Agent", "devops")
        self.github_client = github_client or GitHubClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.file_bug(context["title"], context["body"], context.get("severity", "medium"))

    async def file_bug(self, title: str, body: str, severity: str = "medium") -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        await self.log_reasoning(f"Filing GitHub issue for: {title} (severity={severity})")

        labels = ["auto-filed", f"severity:{severity}"]
        issue = await self.run_with_fallback(
            "create_issue", lambda: self.github_client.create_issue(title, body, labels)
        )

        await event_bus.publish(
            type=EventType.API_CALL,
            agent_name=self.name,
            message=f"🐙 Filed issue #{issue['number']}: {title}",
            data=issue,
        )

        await self.set_status(AgentStatus.IDLE)
        return issue
