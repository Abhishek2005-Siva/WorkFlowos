import pytest

from backend.agents.notes_agent import NotesAgent


@pytest.mark.asyncio
async def test_process_creates_task_per_action_item():
    agent = NotesAgent()
    raw_notes = (
        "Discussed Q3 roadmap.\n"
        "- Send agenda to the team\n"
        "- Review the budget doc\n"
        "General notes not an action item.\n"
    )

    result = await agent.process("Q3 Planning Sync", raw_notes)

    assert result["meeting"] == "Q3 Planning Sync"
    assert result["action_items"] == ["Send agenda to the team", "Review the budget doc"]


@pytest.mark.asyncio
async def test_process_with_no_action_items_creates_no_tasks():
    agent = NotesAgent()
    result = await agent.process("Casual chat", "Just talked, nothing concrete.")

    assert result["action_items"] == []
