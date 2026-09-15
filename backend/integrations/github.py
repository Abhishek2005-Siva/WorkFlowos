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

    async def add_labels(self, issue_number: int, labels: list[str]) -> None:
        if self.settings.mock_mode or not self.settings.github_token:
            await asyncio.sleep(0.05)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{BASE_URL}/repos/{self.settings.github_repo}/issues/{issue_number}/labels",
                    headers=self._headers(),
                    json={"labels": labels},
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("github.add_labels_failed", error=str(exc))
            raise IntegrationError("github", str(exc)) from exc

    async def get_pr_diff(self, pr_number: int) -> str:
        """Raw unified diff for a PR — used to feed Claude for review."""
        if self.settings.mock_mode or not self.settings.github_token:
            await asyncio.sleep(0.1)
            return "diff --git a/mock.py b/mock.py\n+print('mock diff — no real PAT configured')\n"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{BASE_URL}/repos/{self.settings.github_repo}/pulls/{pr_number}",
                    headers={**self._headers(), "Accept": "application/vnd.github.v3.diff"},
                )
                resp.raise_for_status()
                return resp.text[:20000]  # cap for LLM context
        except Exception as exc:
            logger.error("github.get_pr_diff_failed", error=str(exc))
            raise IntegrationError("github", str(exc)) from exc

    async def list_recent_commits(self, since_iso: str) -> list[dict[str, Any]]:
        if self.settings.mock_mode or not self.settings.github_token:
            await asyncio.sleep(0.1)
            return [{"sha": "mock123", "commit": {"message": "Mock commit — no real PAT configured"}}]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{BASE_URL}/repos/{self.settings.github_repo}/commits",
                    headers=self._headers(),
                    params={"since": since_iso},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("github.list_recent_commits_failed", error=str(exc))
            raise IntegrationError("github", str(exc)) from exc

    async def create_webhook(self, target_url: str, secret: str, events: list[str]) -> dict[str, Any]:
        """Registers a webhook on github_repo. Idempotent-ish: GitHub
        allows duplicate webhooks to the same URL, so callers should list
        existing hooks first if re-running this matters to them."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BASE_URL}/repos/{self.settings.github_repo}/hooks",
                headers=self._headers(),
                json={
                    "name": "web",
                    "active": True,
                    "events": events,
                    "config": {"url": target_url, "content_type": "json", "secret": secret},
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def list_webhooks(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/repos/{self.settings.github_repo}/hooks", headers=self._headers())
            resp.raise_for_status()
            return resp.json()
