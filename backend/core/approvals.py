"""Tracks decisions awaiting human approval (a Slack button click, or a
click in the dashboard). The orchestrator awaits `wait_for(decision_id)`
after posting to Slack; `resolve()` is called either by the Slack
interactivity webhook, the dashboard's approve/reject endpoint, or — in
MOCK_MODE — an auto-approve timer so the whole pipeline can be demoed
without a human in the loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingApproval:
    decision_id: str
    payload: dict[str, Any]
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool | None = None


class ApprovalStore:
    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def create(self, decision_id: str, payload: dict[str, Any]) -> PendingApproval:
        pending = PendingApproval(decision_id=decision_id, payload=payload)
        self._pending[decision_id] = pending
        return pending

    def resolve(self, decision_id: str, approved: bool) -> bool:
        pending = self._pending.get(decision_id)
        if pending is None:
            return False
        pending.approved = approved
        pending.event.set()
        return True

    async def wait_for(self, decision_id: str, timeout: float = 120.0) -> bool:
        pending = self._pending.get(decision_id)
        if pending is None:
            return False
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        return bool(pending.approved)

    def get(self, decision_id: str) -> PendingApproval | None:
        return self._pending.get(decision_id)

    def list_pending(self) -> list[dict[str, Any]]:
        return [
            {"decision_id": p.decision_id, "payload": p.payload, "resolved": p.event.is_set()}
            for p in self._pending.values()
        ]


approval_store = ApprovalStore()
