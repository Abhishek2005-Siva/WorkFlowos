"""Logging Agent (bonus) — appends an audit row to Google Sheets for every
completed workflow, independent of the Notion knowledge graph."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.core.types import AgentStatus
from backend.integrations.google_sheets import SheetsClient


class LoggingAgent(BaseAgent):
    def __init__(self, sheets_client: SheetsClient | None = None):
        super().__init__("Logging Agent", "audit_log")
        self.sheets_client = sheets_client or SheetsClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.log_row(context["summary"])

    async def log_row(self, summary: dict[str, Any]) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        row = [
            datetime.now(timezone.utc).isoformat(),
            summary.get("workflow", ""),
            summary.get("agents_involved", ""),
            summary.get("conflicts_resolved", 0),
            summary.get("result", ""),
        ]
        result = await self.run_with_fallback("append_row", lambda: self.sheets_client.append_row(row))
        await self.set_status(AgentStatus.IDLE)
        return result
