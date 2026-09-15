"""Discord wrapper — backs the bonus alternative coordination agent.

Supports two ways of posting, tried in this order:
  1. Bot token + channel ID (Discord REST API) — more flexible, works for
     any channel the bot has been added to.
  2. A fixed incoming webhook URL — simpler, one URL per channel.
Falls back to a mock (logged, not sent) if neither is configured.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock_messages: list[str] = []

    def _configured(self) -> bool:
        return bool(
            (self.settings.discord_bot_token and self.settings.discord_channel_id)
            or self.settings.discord_webhook_url
        )

    async def send_message(self, content: str) -> dict[str, Any]:
        if self.settings.mock_mode or not self._configured():
            await asyncio.sleep(0.05)
            self.mock_messages.append(content)
            logger.info("discord.mock_send", content=content[:120])
            return {"ok": True, "mock": True}

        if self.settings.discord_bot_token and self.settings.discord_channel_id:
            return await self._send_via_bot(content)
        return await self._send_via_webhook(content)

    async def _send_via_bot(self, content: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{DISCORD_API_BASE}/channels/{self.settings.discord_channel_id}/messages",
                    headers={
                        "Authorization": f"Bot {self.settings.discord_bot_token}",
                        "Content-Type": "application/json",
                    },
                    json={"content": content},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("discord.send_via_bot_failed", error=str(exc), body=exc.response.text)
            raise IntegrationError("discord", str(exc), exc.response.status_code) from exc
        except Exception as exc:
            logger.error("discord.send_via_bot_failed", error=str(exc))
            raise IntegrationError("discord", str(exc)) from exc

    async def _send_via_webhook(self, content: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.settings.discord_webhook_url, json={"content": content})
                resp.raise_for_status()
                return {"ok": True}
        except Exception as exc:
            logger.error("discord.send_via_webhook_failed", error=str(exc))
            raise IntegrationError("discord", str(exc)) from exc
