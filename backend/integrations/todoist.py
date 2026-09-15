"""Todoist REST API v2 wrapper."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Todoist merged the Sync (v9) and REST (v2) APIs into one Unified API v1
# in 2025; the old /rest/v2 endpoints now return 410 Gone.
BASE_URL = "https://api.todoist.com/api/v1"


class TodoistClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock_tasks: dict[str, dict[str, Any]] = {}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.todoist_api_key}", "Content-Type": "application/json"}

    async def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.todoist_api_key:
            await asyncio.sleep(0.1)
            task_id = f"task_{uuid.uuid4().hex[:10]}"
            task = {
                "id": task_id,
                "content": data.get("content"),
                "description": data.get("description", ""),
                "due": {"string": data.get("due_date")} if data.get("due_date") else None,
                "parent_id": data.get("parent_id"),
                "priority": data.get("priority", 1),
                "project_id": data.get("project_id"),
            }
            self.mock_tasks[task_id] = task
            return task

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {"content": data["content"]}
                if data.get("description"):
                    payload["description"] = data["description"]
                if data.get("due_date"):
                    payload["due_string"] = data["due_date"]
                if data.get("parent_id"):
                    payload["parent_id"] = data["parent_id"]
                if data.get("project_id"):
                    payload["project_id"] = data["project_id"]
                if data.get("priority"):
                    payload["priority"] = data["priority"]

                resp = await client.post(f"{BASE_URL}/tasks", headers=self._headers(), json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("todoist.create_task_failed", error=str(exc), body=exc.response.text)
            raise IntegrationError("todoist", str(exc), exc.response.status_code) from exc
        except Exception as exc:
            logger.error("todoist.create_task_failed", error=str(exc))
            raise IntegrationError("todoist", str(exc)) from exc

    async def get_tasks(self, project_id: str | None = None, filter_str: str | None = None) -> list[dict[str, Any]]:
        if self.settings.mock_mode or not self.settings.todoist_api_key:
            await asyncio.sleep(0.1)
            return list(self.mock_tasks.values())

        try:
            params = {}
            if project_id:
                params["project_id"] = project_id
            if filter_str:
                params["filter"] = filter_str
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{BASE_URL}/tasks", headers=self._headers(), params=params)
                resp.raise_for_status()
                body = resp.json()
                # Unified API v1 paginates list endpoints as {"results": [...], "next_cursor": ...}
                return body["results"] if isinstance(body, dict) and "results" in body else body
        except Exception as exc:
            logger.error("todoist.get_tasks_failed", error=str(exc))
            raise IntegrationError("todoist", str(exc)) from exc

    async def close_task(self, task_id: str) -> None:
        if self.settings.mock_mode or not self.settings.todoist_api_key:
            await asyncio.sleep(0.05)
            self.mock_tasks.pop(task_id, None)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{BASE_URL}/tasks/{task_id}/close", headers=self._headers())
                resp.raise_for_status()
        except Exception as exc:
            logger.error("todoist.close_task_failed", error=str(exc))
            raise IntegrationError("todoist", str(exc)) from exc
