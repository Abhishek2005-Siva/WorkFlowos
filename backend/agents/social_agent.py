"""Social Agent (bonus) — mirrors key coordination messages to Discord as
an alternative channel, for teams that live there instead of Slack."""
from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.types import AgentStatus
from backend.integrations.discord import DiscordClient


class SocialAgent(BaseAgent):
    def __init__(self, discord_client: DiscordClient | None = None):
        super().__init__("Social Agent", "alt_coordinator")
        self.discord_client = discord_client or DiscordClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.post(context["content"])

    async def post(self, content: str) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        result = await self.run_with_fallback("send_message", lambda: self.discord_client.send_message(content))
        await self.set_status(AgentStatus.IDLE)
        return result
