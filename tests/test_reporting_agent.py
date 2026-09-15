import pytest

from backend.agents.reporting_agent import ReportingAgent


@pytest.mark.asyncio
async def test_generate_standup_returns_summary_and_activity():
    agent = ReportingAgent()
    result = await agent.generate("standup")

    assert result["kind"] == "standup"
    assert "summary" in result and result["summary"]
    assert "task_titles" in result["activity"]
    assert "commit_messages" in result["activity"]


@pytest.mark.asyncio
async def test_generate_weekly_uses_seven_day_window():
    agent = ReportingAgent()
    result = await agent.generate("weekly")

    assert result["kind"] == "weekly"
    assert result["summary"]
