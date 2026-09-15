import pytest

from backend.core.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_full_workflow_negotiates_conflict_and_schedules_meeting():
    orch = Orchestrator()

    seed = await orch.seed_demo_conflict()
    assert seed["seeded"] is True

    email_result = await orch.email_agent.execute({"max_results": 1})
    action = email_result["actions"][0]
    assert action["intent"]["action"] == "schedule_meeting"

    final_state = await orch.run_action(action)

    assert "calendar_event" in final_state
    assert final_state["negotiation_result"]["status"] == "resolved"
    assert "Meet" in final_state["summary"] or "meet" in final_state["summary"].lower()
    assert final_state["task_result"]["main_task"] is not None

    # scheduled time must differ from the original conflicting slot
    assert final_state["chosen_slot"]["start"] != seed["top_slot"]["start"]


@pytest.mark.asyncio
async def test_create_task_workflow_without_conflict():
    orch = Orchestrator()
    orch.email_agent.gmail_client.reset_mock_cursor()

    email_result = await orch.email_agent.execute({"max_results": 2})
    task_action = next(a for a in email_result["actions"] if a["intent"]["action"] == "create_task")

    final_state = await orch.run_action(task_action)

    assert final_state["approved"] is True
    assert final_state["task_result"]["main_task"]["content"] == task_action["intent"]["topic"]


@pytest.mark.asyncio
async def test_urgency_flag_workflow_files_github_issue():
    orch = Orchestrator()
    orch.email_agent.gmail_client.reset_mock_cursor()

    email_result = await orch.email_agent.execute({"max_results": 3})
    urgent_action = next(a for a in email_result["actions"] if a["intent"]["action"] == "urgency_flag")

    final_state = await orch.run_action(urgent_action)

    assert "🚨" in final_state["summary"]
