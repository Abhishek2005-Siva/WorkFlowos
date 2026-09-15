from datetime import datetime, timedelta, timezone

import pytest

from backend.agents.calendar_agent import CalendarAgent


@pytest.mark.asyncio
async def test_check_availability_returns_sorted_scored_slots():
    agent = CalendarAgent()
    slots = await agent.check_availability(duration_minutes=30)

    assert len(slots) > 0
    scores = [s["score"] for s in slots]
    assert scores == sorted(scores, reverse=True)
    for slot in slots:
        assert "reason" in slot
        start = datetime.fromisoformat(slot["start"])
        assert 9 <= start.hour < 18


@pytest.mark.asyncio
async def test_check_availability_avoids_explicit_avoid_list():
    agent = CalendarAgent()
    first_pass = await agent.check_availability(duration_minutes=30)
    top = first_pass[0]

    avoid_range = (datetime.fromisoformat(top["start"]), datetime.fromisoformat(top["end"]))
    second_pass = await agent.check_availability(duration_minutes=30, avoid=[avoid_range])

    assert all(s["start"] != top["start"] for s in second_pass)


@pytest.mark.asyncio
async def test_create_event_returns_meet_link():
    agent = CalendarAgent()
    now = datetime.now(timezone.utc)
    event = await agent.create_event(
        {
            "title": "Test Meeting",
            "description": "unit test",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(minutes=30)).isoformat(),
            "attendees": ["alex@company.com"],
        }
    )

    assert event["id"].startswith("event_")
    assert "meet.google.com" in event["meet_link"]
