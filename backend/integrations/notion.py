"""Notion API wrapper — backs the Knowledge Graph Agent's memory store."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock_pages: dict[str, dict[str, Any]] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.notion_api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def create_page(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.notion_api_key:
            await asyncio.sleep(0.15)
            page_id = f"page_{uuid.uuid4().hex[:12]}"
            page = {"id": page_id, "database_id": database_id, "properties": properties}
            self.mock_pages[page_id] = page
            return page

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BASE_URL}/pages",
                    headers=self._headers(),
                    json={"parent": {"database_id": database_id}, "properties": properties},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("notion.create_page_failed", error=str(exc), body=exc.response.text)
            raise IntegrationError("notion", str(exc), exc.response.status_code) from exc
        except Exception as exc:
            logger.error("notion.create_page_failed", error=str(exc))
            raise IntegrationError("notion", str(exc)) from exc

    async def query_database(
        self, database_id: str, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if self.settings.mock_mode or not self.settings.notion_api_key:
            await asyncio.sleep(0.1)
            return [p for p in self.mock_pages.values() if p["database_id"] == database_id]

        try:
            body: dict[str, Any] = {}
            if filter:
                body["filter"] = filter
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BASE_URL}/databases/{database_id}/query", headers=self._headers(), json=body
                )
                resp.raise_for_status()
                return resp.json().get("results", [])
        except Exception as exc:
            logger.error("notion.query_database_failed", error=str(exc))
            raise IntegrationError("notion", str(exc)) from exc

    async def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.notion_api_key:
            await asyncio.sleep(0.1)
            if page_id in self.mock_pages:
                self.mock_pages[page_id]["properties"].update(properties)
                return self.mock_pages[page_id]
            return {"id": page_id, "properties": properties}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.patch(
                    f"{BASE_URL}/pages/{page_id}", headers=self._headers(), json={"properties": properties}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("notion.update_page_failed", error=str(exc))
            raise IntegrationError("notion", str(exc)) from exc
