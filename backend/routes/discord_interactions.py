"""Discord slash commands via the HTTP Interactions model (no persistent
gateway connection needed, unlike discord.py's usual bot pattern — this
fits the existing FastAPI webhook style). Commands are registered once
via scripts/discord_commands_setup.py; Discord's Interactions Endpoint
URL is set once in the Developer Portal (no API for that field — Discord
PINGs it live to verify before letting you save it).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from backend.agents.reporting_agent import ReportingAgent
from backend.config import get_settings
from backend.integrations.github import GitHubClient
from backend.integrations.todoist import TodoistClient
from backend.utils.logging import get_logger
from backend.utils.webhooks import verify_discord_signature

router = APIRouter(prefix="/discord", tags=["discord-commands"])
logger = get_logger(__name__)

PING = 1
APPLICATION_COMMAND = 2
PONG = 1
DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5


async def _followup(interaction_token: str, content: str) -> None:
    settings = get_settings()
    url = f"https://discord.com/api/v10/webhooks/{settings.discord_application_id}/{interaction_token}/messages/@original"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.patch(url, json={"content": content})
    except Exception as exc:
        logger.warning("discord_commands.followup_failed", error=str(exc))


async def _run_github(interaction_token: str) -> None:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    commits = await GitHubClient().list_recent_commits(since)
    lines = [f"- {c.get('commit', {}).get('message', '').splitlines()[0]}" for c in commits[:10]]
    text = "🔧 **Recent activity (7d):**\n" + ("\n".join(lines) if lines else "No commits this week.")
    await _followup(interaction_token, text)


async def _run_tasks(interaction_token: str) -> None:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    completed = await TodoistClient().get_completed_tasks(since.isoformat(), now.isoformat())
    lines = [f"- {t.get('content', '')}" for t in completed[:10]]
    text = "✅ **Completed this week:**\n" + ("\n".join(lines) if lines else "Nothing logged this week.")
    await _followup(interaction_token, text)


async def _run_weekly(interaction_token: str) -> None:
    result = await ReportingAgent().generate("weekly")
    await _followup(interaction_token, f"📈 **Weekly report:**\n\n{result['summary']}")


COMMAND_HANDLERS = {"github": _run_github, "tasks": _run_tasks, "weekly": _run_weekly}


@router.post("/interactions")
async def discord_interactions(request: Request, background_tasks: BackgroundTasks):
    settings = get_settings()
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")

    if not verify_discord_signature(body, signature, timestamp, settings.discord_public_key):
        return JSONResponse(status_code=401, content={"error": "invalid request signature"})

    payload = await request.json()

    if payload.get("type") == PING:
        return {"type": PONG}

    if payload.get("type") == APPLICATION_COMMAND:
        command_name = payload["data"]["name"]
        interaction_token = payload["token"]
        handler = COMMAND_HANDLERS.get(command_name)
        if handler:
            background_tasks.add_task(handler, interaction_token)
            return {"type": DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
        return {"type": 4, "data": {"content": f"Unknown command: {command_name}"}}

    return {"status": "ignored"}
