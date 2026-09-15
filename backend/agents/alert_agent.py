"""Alert Agent (bonus) — lightweight Telegram notifications for escalations
that need a human's attention outside of Slack (e.g. on mobile)."""
from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.types import AgentStatus
from backend.integrations.telegram import TelegramClient


class AlertAgent(BaseAgent):
    def __init__(self, telegram_client: TelegramClient | None = None):
        super().__init__("Alert Agent", "notifier")
        self.telegram_client = telegram_client or TelegramClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.send_alert(context["text"])

    async def send_alert(self, text: str) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        result = await self.run_with_fallback("send_message", lambda: self.telegram_client.send_message(text))
        await self.set_status(AgentStatus.IDLE)
        return result
