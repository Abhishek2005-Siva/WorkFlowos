import pytest

from backend.agents.capacity_agent import CapacityAgent


@pytest.mark.asyncio
async def test_report_returns_low_load_with_no_tasks():
    agent = CapacityAgent()
    result = await agent.report()

    assert result["open_tasks"] == 0
    assert result["overdue"] == 0
    assert result["load"] in ("low", "medium", "high")
    assert 0 <= result["busy_pct"] <= 100


@pytest.mark.asyncio
async def test_report_flags_high_load_with_many_overdue_tasks():
    agent = CapacityAgent()
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for i in range(4):
        task = await agent.todoist_client.create_task({"content": f"Overdue task {i}"})
        agent.todoist_client.mock_tasks[task["id"]]["due"] = {"date": past}

    result = await agent.report()

    assert result["overdue"] == 4
    assert result["load"] == "high"
