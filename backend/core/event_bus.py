"""In-process async pub/sub event bus.

Every agent action, status change, negotiation step and decision flows
through here. Routes subscribe a queue per WebSocket connection; the bus
also persists every event so the dashboard's timeline/replay survives a
reconnect or restart.
"""
from __future__ import annotations

import asyncio
import itertools
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.models.db import EventLog, get_session_factory

_id_counter = itertools.count(1)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._recent: list[dict[str, Any]] = []
        self._recent_max = 200

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._recent[-limit:]

    async def publish(
        self,
        *,
        type: str,
        agent_name: str = "System",
        message: str = "",
        data: dict | None = None,
        category: str = "default",
        thread_id: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        event = {
            "id": next(_id_counter),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": type,
            "category": category,
            "agent_name": agent_name,
            "message": message,
            "data": data or {},
            "thread_id": thread_id,
        }

        self._recent.append(event)
        if len(self._recent) > self._recent_max:
            self._recent = self._recent[-self._recent_max :]

        if persist:
            try:
                async with get_session_factory()() as session:
                    session.add(
                        EventLog(
                            type=type,
                            category=category,
                            agent_name=agent_name,
                            message=message,
                            data=data or {},
                            thread_id=thread_id,
                        )
                    )
                    await session.commit()
            except Exception:
                # Persistence is best-effort; never let logging break a workflow.
                pass

        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

        return event


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


event_bus = EventBus()
