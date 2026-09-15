"""Task Delegation Agent.

Creates hierarchical tasks (main + subtasks) in Todoist, and is the other
half of the negotiation protocol's flagship scenario: it checks whether a
calendar slot the Calendar Agent wants to book collides with an existing
task deadline, and evaluates counter-proposals during negotiation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.todoist import TodoistClient


class TaskAgent(BaseAgent):
    def __init__(self, todoist_client: TodoistClient | None = None):
        super().__init__("Task Agent", "task_coordinator")
        self.todoist_client = todoist_client or TodoistClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.create_task_hierarchy(context["action"])

    async def create_task_hierarchy(self, action: dict[str, Any]) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        await self.log_reasoning(f"Creating task hierarchy for: {action['title']}")

        main_task = await self.run_with_fallback(
            "create_main_task",
            lambda: self.todoist_client.create_task(
                {
                    "content": action["title"],
                    "description": action.get("description", ""),
                    "due_date": action.get("deadline"),
                }
            ),
        )

        task_ids = [main_task["id"]]
        subtasks_created = []

        subtasks = action.get("subtasks", [])
        if subtasks:
            await self.log_reasoning(f"Breaking down into {len(subtasks)} subtask(s)")
            for subtask_data in subtasks:
                subtask = await self.todoist_client.create_task(
                    {
                        "content": subtask_data["title"],
                        "parent_id": main_task["id"],
                        "due_date": subtask_data.get("deadline"),
                    }
                )
                task_ids.append(subtask["id"])
                subtasks_created.append(subtask)

        await event_bus.publish(
            type=EventType.TASK_CREATED,
            agent_name=self.name,
            message=f"📝 Created {len(task_ids)} task(s): {action['title']}",
            data={"main_task": main_task, "subtasks": subtasks_created},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"agent": self.name, "task_ids": task_ids, "main_task": main_task, "subtasks": subtasks_created}

    async def check_deadline_conflicts(
        self, candidate_start: datetime, candidate_end: datetime
    ) -> dict[str, Any] | None:
        """Returns the conflicting task dict if any known task deadline
        falls inside the proposed meeting window, else None."""
        await self.log_reasoning(
            f"Checking whether any task deadline conflicts with {candidate_start.isoformat()}"
        )

        tasks = await self.run_with_fallback("get_tasks", lambda: self.todoist_client.get_tasks())

        for task in tasks:
            due_iso = self._extract_due(task)
            if due_iso is None:
                continue
            due_dt = datetime.fromisoformat(due_iso)
            if candidate_start <= due_dt <= candidate_end:
                await self.log_reasoning(f"⚠️ Conflict: \"{task['content']}\" is due at {due_iso}")
                return task

        await self.log_reasoning("No deadline conflicts found")
        return None

    def _extract_due(self, task: dict[str, Any]) -> str | None:
        due = task.get("due")
        if not due:
            return None
        if isinstance(due, dict):
            return due.get("datetime") or due.get("string")
        return None

    async def evaluate_counter_proposal(
        self, proposed_start: datetime, proposed_end: datetime
    ) -> dict[str, Any]:
        """Called by the negotiation protocol when the Calendar Agent
        counter-proposes a new time. Accepts unless the new slot itself
        collides with another deadline."""
        await self.set_status(AgentStatus.NEGOTIATING)
        conflict = await self.check_deadline_conflicts(proposed_start, proposed_end)
        await self.set_status(AgentStatus.IDLE)

        if conflict is None:
            buffer_ok = True
            await self.log_reasoning(
                f"Counter-proposal {proposed_start.isoformat()} accepted — gives buffer time, no new conflicts"
            )
            return {"status": "accept", "buffer_ok": buffer_ok}

        return {"status": "reject", "reason": f"Still conflicts with \"{conflict['content']}\""}

    async def seed_mock_deadline(self, content: str, due_datetime: datetime) -> dict[str, Any]:
        """Test/demo helper: seed a task with a hard deadline so the
        negotiation scenario has something real to collide with."""
        return await self.todoist_client.create_task(
            {"content": content, "due_date": due_datetime.isoformat()}
        )
