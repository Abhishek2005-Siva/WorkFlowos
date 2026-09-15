from datetime import datetime, timedelta, timezone

import pytest

from backend.agents.task_agent import TaskAgent


@pytest.mark.asyncio
async def test_create_task_hierarchy_with_subtasks():
    agent = TaskAgent()
    result = await agent.create_task_hierarchy(
        {
            "title": "Main task",
            "description": "desc",
            "subtasks": [{"title": "Subtask A"}, {"title": "Subtask B"}],
        }
    )

    assert len(result["task_ids"]) == 3
    assert result["main_task"]["content"] == "Main task"
    assert len(result["subtasks"]) == 2


@pytest.mark.asyncio
async def test_check_deadline_conflicts_detects_seeded_deadline():
    agent = TaskAgent()
    due = datetime.now(timezone.utc) + timedelta(days=1)
    await agent.seed_mock_deadline("Quarterly planning doc", due)

    conflict = await agent.check_deadline_conflicts(
        due - timedelta(minutes=5), due + timedelta(minutes=25)
    )

    assert conflict is not None
    assert conflict["content"] == "Quarterly planning doc"


@pytest.mark.asyncio
async def test_check_deadline_conflicts_returns_none_when_clear():
    agent = TaskAgent()
    window_start = datetime.now(timezone.utc) + timedelta(days=5)
    conflict = await agent.check_deadline_conflicts(window_start, window_start + timedelta(minutes=30))
    assert conflict is None


@pytest.mark.asyncio
async def test_evaluate_counter_proposal_accepts_when_clear():
    agent = TaskAgent()
    proposed = datetime.now(timezone.utc) + timedelta(days=3)
    evaluation = await agent.evaluate_counter_proposal(proposed, proposed + timedelta(minutes=30))
    assert evaluation["status"] == "accept"
