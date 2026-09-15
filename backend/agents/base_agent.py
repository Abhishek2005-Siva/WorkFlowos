"""Base class every agent inherits from.

Provides: status tracking (broadcast live to the dashboard via the event
bus), a reasoning trace (the audit trail every decision can be replayed
from), escalation to Slack, and a generic 5-level fallback wrapper
(immediate retry -> exponential backoff -> cached data -> escalate) used
around every external API call so a single flaky integration never crashes
a workflow.
"""
from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.utils.cache import cache
from backend.utils.errors import AgentExecutionError, IntegrationError
from backend.utils.logging import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


class BaseAgent(ABC):
    def __init__(self, name: str, agent_type: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.agent_type = agent_type
        self._status = AgentStatus.IDLE
        self.last_action_time: str | None = None
        self.error_count = 0
        self.last_error: str | None = None
        self.reasoning_trace: list[dict[str, Any]] = []

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def set_status(self, status: AgentStatus) -> None:
        self._status = status
        self.last_action_time = datetime.now(timezone.utc).isoformat()
        await event_bus.publish(
            type=EventType.AGENT_STATUS,
            agent_name=self.name,
            message=f"{self.name} → {status.value}",
            data={"agent_id": self.id, "agent_type": self.agent_type, "status": status.value},
            category="status",
        )

    async def log_reasoning(self, reasoning: str, step: int | None = None) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step if step is not None else len(self.reasoning_trace) + 1,
            "reasoning": reasoning,
        }
        self.reasoning_trace.append(entry)
        await event_bus.publish(
            type=EventType.AGENT_REASONING,
            agent_name=self.name,
            message=reasoning,
            data=entry,
            category="reasoning",
        )

    async def escalate(self, reason: str, data: dict[str, Any] | None = None) -> None:
        await self.set_status(AgentStatus.ESCALATED)
        await event_bus.publish(
            type=EventType.ERROR,
            agent_name=self.name,
            message=f"⚠️ Escalation: {reason}",
            data=data or {},
            category="error",
        )

    async def run_with_fallback(
        self,
        operation_name: str,
        func: Callable[[], Awaitable[T]],
        *,
        cache_key: str | None = None,
        max_retries: int = 3,
        base_backoff: float = 1.0,
    ) -> T:
        """5-level fallback: retry immediately, then exponential backoff,
        then cached data, then escalate. Raises AgentExecutionError only
        once every level has been exhausted."""
        last_exc: Exception | None = None

        try:
            result = await func()
            if cache_key is not None:
                await cache.set(cache_key, result, ttl_seconds=3600)
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(f"{self.name}.{operation_name}.attempt_failed", attempt=0, error=str(exc))

        for attempt in range(1, max_retries + 1):
            wait_time = base_backoff * (2**attempt)
            await event_bus.publish(
                type=EventType.ERROR,
                agent_name=self.name,
                message=f"{operation_name} failed, retrying in {wait_time:.0f}s (attempt {attempt}/{max_retries})",
                data={"error": str(last_exc)},
                category="warning",
            )
            await asyncio.sleep(min(wait_time, 0.5) if _is_test_mode() else wait_time)
            try:
                result = await func()
                if cache_key is not None:
                    await cache.set(cache_key, result, ttl_seconds=3600)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning(f"{self.name}.{operation_name}.attempt_failed", attempt=attempt, error=str(exc))

        if cache_key is not None:
            cached = await cache.get(cache_key)
            if cached is not None:
                await event_bus.publish(
                    type=EventType.ERROR,
                    agent_name=self.name,
                    message=f"{operation_name} still failing — serving last-known-good cached data",
                    category="warning",
                )
                return cached  # type: ignore[return-value]

        self.error_count += 1
        self.last_error = str(last_exc)
        await self.escalate(
            f"{operation_name} failed after {max_retries} retries and no cache available",
            {"error": str(last_exc)},
        )
        raise AgentExecutionError(self.name, operation_name, last_exc)

    def to_status_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.agent_type,
            "status": self._status.value,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_action_time": self.last_action_time,
            "reasoning_trace": self.reasoning_trace[-10:],
        }

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's core logic."""


def _is_test_mode() -> bool:
    import os

    return os.environ.get("WORKFLOWOS_FAST_RETRY") == "1"
