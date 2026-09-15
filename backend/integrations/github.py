"""GitHub REST API wrapper — backs the bonus DevOps agent."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.errors import IntegrationError
from backend.utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.github.com"


class GitHubClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock_issues: dict[int, dict[str, Any]] = {}
        self._mock_next_id = 1001

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
        }

    async def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.github_token:
            await asyncio.sleep(0.15)
            issue_id = self._mock_next_id
            self._mock_next_id += 1
            issue = {
                "number": issue_id,
                "title": title,
                "body": body,
                "labels": [{"name": l} for l in (labels or [])],
                "html_url": f"https://github.com/mock/repo/issues/{issue_id}",
                "state": "open",
            }
            self.mock_issues[issue_id] = issue
            return issue

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BASE_URL}/repos/{self.settings.github_repo}/issues",
                    headers=self._headers(),
                    json={"title": title, "body": body, "labels": labels or []},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("github.create_issue_failed", error=str(exc))
            raise IntegrationError("github", str(exc)) from exc

    async def comment_issue(self, issue_number: int, comment: str) -> dict[str, Any]:
        if self.settings.mock_mode or not self.settings.github_token:
            await asyncio.sleep(0.1)
            return {"id": f"comment_{uuid.uuid4().hex[:8]}", "body": comment}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BASE_URL}/repos/{self.settings.github_repo}/issues/{issue_number}/comments",
                    headers=self._headers(),
                    json={"body": comment},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("github.comment_issue_failed", error=str(exc))
            raise IntegrationError("github", str(exc)) from exc
