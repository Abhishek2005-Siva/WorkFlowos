"""Notes Agent — Meeting Notes Automaton, slash-command adapted.

Honest scope note: the original idea has notes accumulate in a Slack
thread throughout a meeting, auto-synthesized afterward. That needs a
Slack Events API subscription tracking thread replies over time, which
isn't wired up. The single-endpoint-honest version: a `/notes` slash
command you run once, with everything pasted in — same synthesis and
action-item extraction, without inventing a "was listening the whole
meeting" capability that isn't real.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.event_bus import event_bus
from backend.core.types import AgentStatus, EventType
from backend.integrations.notion import NotionClient
from backend.integrations.todoist import TodoistClient
from backend.utils.llm import llm_extract_action_items


class NotesAgent(BaseAgent):
    def __init__(self, notion_client: NotionClient | None = None, todoist_client: TodoistClient | None = None):
        super().__init__("Notes Agent", "meeting_notes")
        self.notion_client = notion_client or NotionClient()
        self.todoist_client = todoist_client or TodoistClient()
        self.settings = get_settings()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.process(context["meeting_title"], context["raw_notes"])

    async def process(self, meeting_title: str, raw_notes: str) -> dict[str, Any]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning(f"Synthesizing notes for: {meeting_title}")

        action_items = await self._extract_action_items(raw_notes)

        await self.set_status(AgentStatus.ACTING)
        created_tasks = []
        for item in action_items:
            task = await self.todoist_client.create_task({"content": item})
            created_tasks.append(task["content"])

        await self.notion_client.create_page(
            self.settings.notion_decisions_db_id or "mock_decisions_db",
            {
                "Title": {"title": [{"text": {"content": f"Meeting notes: {meeting_title}"}}]},
                "Agent": {"select": {"name": "Notes Agent"}},
                "Decision Type": {"select": {"name": "meeting_notes"}},
                "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Reasoning Trace": {"rich_text": [{"text": {"content": raw_notes[:2000]}}]},
            },
        )

        await event_bus.publish(
            type=EventType.KB_LOGGED,
            agent_name=self.name,
            message=f"📝 Logged notes for \"{meeting_title}\" — {len(created_tasks)} action item(s) created",
            data={"meeting": meeting_title, "action_items": created_tasks},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"meeting": meeting_title, "action_items": created_tasks}

    async def _extract_action_items(self, raw_notes: str) -> list[str]:
        return await llm_extract_action_items(raw_notes)
