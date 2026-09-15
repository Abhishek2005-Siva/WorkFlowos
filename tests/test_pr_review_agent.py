import pytest

from backend.agents.pr_review_agent import PRReviewAgent


@pytest.mark.asyncio
async def test_review_returns_pr_number_and_review_text():
    agent = PRReviewAgent()
    result = await agent.review(
        pr_number=42, title="Add retry logic", author="octocat", html_url="https://github.com/mock/repo/pull/42"
    )

    assert result["pr_number"] == 42
    assert "review" in result and result["review"]
