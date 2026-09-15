from datetime import datetime, timezone

import pytest

from backend.agents.knowledge_graph_agent import KnowledgeGraphAgent


@pytest.mark.asyncio
async def test_log_decision_creates_relationships():
    agent = KnowledgeGraphAgent()
    result = await agent.log_decision(
        {
            "agent": "Calendar Agent",
            "type": "meeting_scheduled",
            "title": "Q4 Sync",
            "person": "Test Person A",
            "event": "Q4 Sync Meeting",
            "reasoning_trace": [{"step": 1, "reasoning": "found a slot"}],
            "related_tasks": ["Prep doc"],
        }
    )

    assert result["decision_id"].startswith("decision_")
    assert len(result["relationships"]) >= 3

    context = await agent.query_context("Test Person A", "person")
    assert context["interactions"] >= 1


@pytest.mark.asyncio
async def test_learn_pattern_detects_morning_preference():
    agent = KnowledgeGraphAgent()
    person = "Pattern Person"

    for day in range(3):
        morning_time = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
        await agent.log_decision(
            {
                "agent": "Calendar Agent",
                "type": "meeting_scheduled",
                "title": f"Sync {day}",
                "person": person,
                "event": f"Sync Meeting {day}",
                "final_time_scheduled": morning_time.isoformat(),
                "reasoning_trace": [],
            }
        )

    pattern = await agent.learn_pattern(person)
    assert pattern is not None
    assert "morning" in pattern.lower()


@pytest.mark.asyncio
async def test_graph_snapshot_returns_entities_and_relationships():
    agent = KnowledgeGraphAgent()
    await agent.log_decision(
        {
            "agent": "Task Agent",
            "type": "task_created",
            "title": "Some task",
            "person": "Snapshot Person",
            "reasoning_trace": [],
        }
    )

    snapshot = await agent.graph_snapshot()
    assert any(e["name"] == "Snapshot Person" for e in snapshot["entities"])
