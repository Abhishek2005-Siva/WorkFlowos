import pytest

from backend.agents.issue_triage_agent import IssueTriageAgent


@pytest.mark.asyncio
async def test_triage_critical_issue_by_keyword():
    agent = IssueTriageAgent()
    result = await agent.triage(
        issue_number=7,
        title="Production down: data loss on checkout",
        body="Customers are seeing errors and orders are being dropped.",
        html_url="https://github.com/mock/repo/issues/7",
    )

    assert result["issue_number"] == 7
    assert result["priority"] == "critical"


@pytest.mark.asyncio
async def test_triage_feature_request_is_low_priority():
    agent = IssueTriageAgent()
    result = await agent.triage(
        issue_number=8,
        title="Feature idea: dark mode",
        body="Would be nice to have an enhancement for dark mode.",
        html_url="https://github.com/mock/repo/issues/8",
    )

    assert result["priority"] == "low"
