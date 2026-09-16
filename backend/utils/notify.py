"""Wraps a notification/logging side effect (Slack, Telegram, Sheets) so a
failure there never crashes an automation whose core action (a label, a
comment, a created task) already succeeded. Mirrors the same philosophy
SlackAgent._safe_send already established for the meeting-orchestration
agents, generalized for the standalone automations that don't go through
SlackAgent.
"""
from __future__ import annotations

from typing import Any, Awaitable, TypeVar

from backend.core.event_bus import event_bus
from backend.core.types import EventType
from backend.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def safe_notify(agent_name: str, channel_desc: str, coro: Awaitable[T]) -> T | None:
    try:
        return await coro
    except Exception as exc:
        logger.warning("notify.failed_non_fatal", agent=agent_name, channel=channel_desc, error=str(exc))
        await event_bus.publish(
            type=EventType.ERROR,
            agent_name=agent_name,
            message=f"{channel_desc} notification failed (continuing anyway): {exc}",
            category="warning",
        )
        return None
