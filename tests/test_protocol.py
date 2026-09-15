from datetime import datetime, timedelta, timezone

import pytest

from backend.agents.calendar_agent import CalendarAgent
from backend.agents.task_agent import TaskAgent
from backend.core.protocol import AgentNegotiationProtocol


@pytest.mark.asyncio
async def test_negotiation_resolves_by_finding_alternate_slot():
    calendar_agent = CalendarAgent()
    task_agent = TaskAgent()
    protocol = AgentNegotiationProtocol(calendar_agent, task_agent)

    slots = await calendar_agent.check_availability(duration_minutes=30)
    top_slot = slots[0]
    conflicting_deadline = await task_agent.seed_mock_deadline(
        "Quarterly planning doc", datetime.fromisoformat(top_slot["start"])
    )

    result = await protocol.negotiate_meeting_conflict(top_slot, 30, conflicting_deadline)

    assert result["status"] == "resolved"
    assert result["final_slot"] is not None
    assert result["final_slot"]["start"] != top_slot["start"]
    assert len(result["negotiation_log"]) >= 2
    assert any(entry["agent"] == "Calendar Agent" for entry in result["negotiation_log"])
    assert any(entry["agent"] == "Task Agent" for entry in result["negotiation_log"])


@pytest.mark.asyncio
async def test_negotiation_escalates_when_every_slot_is_blocked():
    calendar_agent = CalendarAgent()
    task_agent = TaskAgent()
    protocol = AgentNegotiationProtocol(calendar_agent, task_agent, max_iterations=2)

    all_slots = await calendar_agent.check_availability(duration_minutes=30)
    top_slot = all_slots[0]

    # Seed a deadline on every 30-minute mark across the full 48h window,
    # not just the current top-12 candidates: once negotiation excludes a
    # slot via `avoid`, _find_gaps recomputes and can surface a *new*
    # candidate outside the original top 12 to fill that cap. Only a dense
    # blanket across the whole search space guarantees no gap survives
    # regardless of which slots the algorithm happens to rank highest.
    now = datetime.now(timezone.utc)
    cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    window_end = now + timedelta(hours=48)
    while cursor < window_end:
        await task_agent.seed_mock_deadline("Blocking deadline", cursor)
        cursor += timedelta(minutes=30)

    result = await protocol.negotiate_meeting_conflict(
        top_slot, 30, {"content": "Quarterly planning doc"}
    )

    assert result["status"] == "escalated"
    assert result["final_slot"] is None
