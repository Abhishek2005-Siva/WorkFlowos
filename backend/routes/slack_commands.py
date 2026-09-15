"""Slack slash commands — /standup, /capacity, /commits, /notes, /meeting,
/assign. Registered manually in the Slack app config (api.slack.com —
Slack has no API for registering a slash command, only for using one
once it exists) pointing at POST /slack/commands on this backend.

Slack requires an ack within 3 seconds; anything that takes longer
(standup generation, LLM calls) acks immediately and posts the real
result to the command's `response_url` afterward.
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from backend.agents.capacity_agent import CapacityAgent
from backend.agents.notes_agent import NotesAgent
from backend.agents.reporting_agent import ReportingAgent
from backend.config import get_settings
from backend.core.orchestrator import orchestrator
from backend.integrations.github import GitHubClient
from backend.utils.logging import get_logger
from backend.utils.webhooks import verify_slack_signature

router = APIRouter(prefix="/slack", tags=["slack-commands"])
logger = get_logger(__name__)


async def _respond_later(response_url: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(response_url, json={"response_type": "in_channel", "text": text})
    except Exception as exc:
        logger.warning("slack_commands.response_url_failed", error=str(exc))


async def _run_standup(response_url: str) -> None:
    result = await ReportingAgent().generate("standup")
    await _respond_later(response_url, f"✅ Standup posted.\n\n{result['summary']}")


async def _run_capacity(response_url: str) -> None:
    result = await CapacityAgent().report()
    await _respond_later(
        response_url,
        f"📊 {result['load'].upper()} load — {result['open_tasks']} open tasks "
        f"({result['overdue']} overdue), {result['busy_pct']}% of next 48h booked.",
    )


async def _run_commits(response_url: str) -> None:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    commits = await GitHubClient().list_recent_commits(since)
    if not commits:
        await _respond_later(response_url, "No commits in the last 24h.")
        return
    lines = [f"- {c.get('commit', {}).get('message', '').splitlines()[0]}" for c in commits[:10]]
    await _respond_later(response_url, "🔧 **Last 24h commits:**\n" + "\n".join(lines))


async def _run_meeting(text: str, response_url: str) -> None:
    try:
        duration = int(text.strip()) if text.strip().isdigit() else 30
    except ValueError:
        duration = 30
    slots = await orchestrator.calendar_agent.check_availability(duration)
    if not slots:
        await _respond_later(response_url, "No available slots found in the next 48h.")
        return
    top = slots[0]
    await _respond_later(response_url, f"📅 Next available {duration}min slot: {top['start']} — {top['reason']}")


async def _run_notes(text: str, response_url: str) -> None:
    if "|" in text:
        title, notes = text.split("|", 1)
    else:
        title, notes = "Untitled meeting", text
    result = await NotesAgent().process(title.strip(), notes.strip())
    items = ", ".join(result["action_items"]) or "none"
    await _respond_later(response_url, f"📝 Logged notes for \"{title.strip()}\". Action items: {items}")


async def _run_assign(text: str, response_url: str) -> None:
    if not text.strip():
        await _respond_later(response_url, "Usage: `/assign <task description>`")
        return
    task = await orchestrator.task_agent.todoist_client.create_task({"content": text.strip()})
    await _respond_later(response_url, f"✅ Created task: {task['content']}")


@router.post("/commands")
async def slack_command(request: Request, background_tasks: BackgroundTasks):
    settings = get_settings()
    body = await request.body()

    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    if not verify_slack_signature(body, timestamp, signature, settings.slack_signing_secret):
        return JSONResponse(status_code=401, content={"error": "invalid signature"})

    form = urllib.parse.parse_qs(body.decode())
    command = form.get("command", [""])[0]
    text = form.get("text", [""])[0]
    response_url = form.get("response_url", [""])[0]

    handlers = {
        "/standup": lambda: _run_standup(response_url),
        "/capacity": lambda: _run_capacity(response_url),
        "/commits": lambda: _run_commits(response_url),
        "/meeting": lambda: _run_meeting(text, response_url),
        "/notes": lambda: _run_notes(text, response_url),
        "/assign": lambda: _run_assign(text, response_url),
    }

    handler = handlers.get(command)
    if not handler:
        return {"response_type": "ephemeral", "text": f"Unknown command {command}"}

    background_tasks.add_task(handler)
    return {"response_type": "ephemeral", "text": "⏳ Working on it…"}
