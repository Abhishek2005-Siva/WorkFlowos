"""Slack Coordination Hub.

Every agent's decisions, negotiations, and conflicts get posted here. In
MOCK_MODE (no bot token) it still fully operates — messages are logged and
stored in-memory rather than sent to a real workspace — so the rest of the
system never has to special-case "no Slack yet".

Slack is a *notification* channel, not a dependency the workflow should
die on: if a real post fails (wrong channel, bot not invited, etc.) that's
logged as a warning event and the workflow keeps going. Approvals still
get created in `approval_store` regardless, so the dashboard's own
approve/reject controls work as a complete fallback to Slack's buttons —
which matters in particular because Slack's interactivity webhook needs a
public HTTPS URL that a local dev server doesn't have.
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.approvals import approval_store
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.slack import SlackClient
from backend.utils.logging import get_logger

logger = get_logger(__name__)

AGENT_EMOJI = {
    "Email Agent": "📧",
    "Calendar Agent": "📅",
    "Task Agent": "✅",
    "Knowledge Graph Agent": "📊",
    "Slack Coordination Hub": "🤖",
    "GitHub Agent": "🐙",
}


class SlackAgent(BaseAgent):
    def __init__(self, slack_client: SlackClient | None = None):
        super().__init__("Slack Coordination Hub", "coordinator")
        self.slack_client = slack_client or SlackClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.post_agent_message(context.get("agent_name", "System"), context.get("message", ""))

    async def _safe_send(self, channel: str, text: str, blocks: list[dict] | None = None) -> dict | None:
        """Post to Slack; on failure, log a warning event instead of
        raising, so a Slack misconfiguration never breaks a workflow that
        otherwise succeeded."""
        try:
            return await self.slack_client.send_message(channel=channel, text=text, blocks=blocks)
        except Exception as exc:
            logger.warning("slack_agent.post_failed_non_fatal", channel=channel, error=str(exc))
            await event_bus.publish(
                type=EventType.ERROR,
                agent_name=self.name,
                message=f"Slack post to {channel} failed (continuing anyway): {exc}",
                category="warning",
            )
            return None

    async def post_decision_for_approval(
        self, decision_id: str, agent_name: str, title: str, description: str
    ) -> str | None:
        await self.set_status(AgentStatus.WAITING)
        blocks = SlackClient.build_approval_blocks(decision_id, f"{agent_name} needs approval", title)
        result = await self._safe_send(self.settings.slack_approvals_channel, f"{title}\n{description}", blocks)

        approval_store.create(decision_id, {"agent": agent_name, "title": title, "description": description})

        await event_bus.publish(
            type=EventType.APPROVAL_REQUESTED,
            agent_name=agent_name,
            message=f"📅 {title} — awaiting approval (Slack ✅/❌ or the dashboard's Approvals panel)",
            data={"decision_id": decision_id, "description": description},
        )

        if self.settings.mock_mode:
            asyncio.create_task(self._auto_approve_after_delay(decision_id))

        await self.set_status(AgentStatus.IDLE)
        return result["ts"] if result else None

    async def _auto_approve_after_delay(self, decision_id: str, delay: float = 1.5) -> None:
        await asyncio.sleep(delay)
        approval_store.resolve(decision_id, approved=True)
        await event_bus.publish(
            type=EventType.APPROVAL_GRANTED,
            agent_name=self.name,
            message="✅ Approved (mock auto-approval — reacted with ✅ in Slack)",
            data={"decision_id": decision_id},
        )

    async def post_agent_message(self, agent_name: str, message: str, thread_ts: str | None = None) -> None:
        emoji = AGENT_EMOJI.get(agent_name, "🤖")
        await self._safe_send(self.settings.slack_activity_channel, f"{emoji} *{agent_name}*: {message}")

    async def notify_conflict(self, conflict_data: dict[str, Any]) -> None:
        message = (
            f"⚠️ *Conflict Detected*\n"
            f"*Agents:* {conflict_data['agent1']} ↔️ {conflict_data['agent2']}\n"
            f"*Issue:* {conflict_data['description']}\n"
            f"*Status:* {conflict_data['status']}"
        )
        await self._safe_send(self.settings.slack_conflicts_channel, message)

    async def notify_completion(self, summary: str) -> None:
        await self._safe_send(self.settings.slack_activity_channel, summary)
        await event_bus.publish(
            type=EventType.SLACK_NOTIFICATION,
            agent_name=self.name,
            message=summary,
        )
