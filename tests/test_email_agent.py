import pytest

from backend.agents.email_agent import EmailAgent
from backend.core.types import AgentStatus


@pytest.mark.asyncio
async def test_email_agent_extracts_intent():
    agent = EmailAgent()
    agent.gmail_client.reset_mock_cursor()

    result = await agent.execute({"max_results": 3})

    assert result["agent"] == "Email Agent"
    assert result["actions_found"] == 3
    assert agent.status == AgentStatus.IDLE

    first = result["actions"][0]
    assert first["intent"]["action"] == "schedule_meeting"
    assert first["requires_approval"] is True
    assert "Alex" in first["intent"]["requester"]


@pytest.mark.asyncio
async def test_email_agent_flags_urgency():
    agent = EmailAgent()
    agent.gmail_client.reset_mock_cursor()

    result = await agent.execute({"max_results": 3})
    urgent_actions = [a for a in result["actions"] if a["intent"]["action"] == "urgency_flag"]

    assert len(urgent_actions) >= 1
    assert urgent_actions[0]["intent"]["urgency"] == "high"
