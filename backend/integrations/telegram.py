"""Telegram Bot API wrapper — backs the bonus lightweight alert agent."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class TelegramClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock_messages: list[str] = []

    async def send_message(self, text: str, chat_id: str | None = None) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.telegram_bot_token:
            await asyncio.sleep(0.05)
            self.mock_messages.append(text)
            logger.info("telegram.mock_send", text=text[:120])
            return {"ok": True, "mock": True}

        try:
            url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, json={"chat_id": chat_id or self.settings.telegram_chat_id, "text": text}
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("telegram.send_message_failed", error=str(exc), body=exc.response.text)
            raise IntegrationError("telegram", exc.response.text, exc.response.status_code) from exc
        except Exception as exc:
            logger.error("telegram.send_message_failed", error=str(exc))
            raise IntegrationError("telegram", str(exc)) from exc
