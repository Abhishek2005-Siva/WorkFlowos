"""Slack API wrapper (real: slack_sdk async client; mock: logs + fake ts)."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class SlackClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        self.mock_messages: list[dict[str, Any]] = []

    def _get_client(self):
        if self._client is None:
            from slack_sdk.web.async_client import AsyncWebClient

            self._client = AsyncWebClient(token=self.settings.slack_bot_token)
        return self._client

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.slack_bot_token:
            await asyncio.sleep(0.1)
            ts = f"{time.time():.6f}"
            record = {"channel": channel, "text": text, "blocks": blocks, "thread_ts": thread_ts, "ts": ts}
            self.mock_messages.append(record)
            logger.info("slack.mock_send", channel=channel, text=text[:120])
            return {"ts": ts, "channel": channel}

        try:
            client = self._get_client()
            response = await client.chat_postMessage(
                channel=channel, text=text, blocks=blocks, thread_ts=thread_ts
            )
            return {"ts": response["ts"], "channel": response["channel"]}
        except Exception as exc:
            logger.error("slack.send_message_failed", error=str(exc))
            raise IntegrationError("slack", str(exc)) from exc

    async def add_reaction(self, channel: str, timestamp: str, emoji: str) -> None:
        if self.settings.mock_mode or not self.settings.slack_bot_token:
            await asyncio.sleep(0.05)
            return
        try:
            client = self._get_client()
            await client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
        except Exception as exc:
            logger.error("slack.add_reaction_failed", error=str(exc))
            raise IntegrationError("slack", str(exc)) from exc

    @staticmethod
    def build_approval_blocks(decision_id: str, title: str, description: str) -> list[dict[str, Any]]:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n{description}"}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "value": decision_id,
                        "action_id": f"approve_{decision_id}",
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "value": decision_id,
                        "action_id": f"reject_{decision_id}",
                        "style": "danger",
                    },
                ],
            },
        ]
