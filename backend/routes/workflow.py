"""Manual workflow controls used by the dashboard's "Run Demo" button and
by the approve/reject UI (an alternative to clicking in Slack)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks

from backend.config import get_settings
from backend.core.approvals import approval_store
from backend.core.orchestrator import orchestrator
from backend.core.system_state import system_state
from backend.utils.logging import get_logger

router = APIRouter(prefix="/workflow", tags=["workflow"])
logger = get_logger(__name__)


def _real_gmail_blocked() -> bool:
    """True when Gmail is connected for real but the Live switch is off.

    "Run Demo" / "Process Inbox" are safe, repeatable no-op-risk buttons
    while Gmail is mock — but once real credentials exist they'd read (and
    act on) your actual inbox. Requiring Live for those too, not just the
    push webhook, is what this guards: an accidental click (or, as
    happened once during development, an API call made without stopping
    to think it through) should not be able to take real-world action
    while the dashboard says "Stopped"."""
    return not orchestrator.email_agent.gmail_client.is_mock and not system_state.is_live


@router.post("/trigger")
async def trigger_cycle(background_tasks: BackgroundTasks, max_emails: int = 3):
    if _real_gmail_blocked():
        return {"status": "blocked", "reason": "Real Gmail is connected but the system is Stopped — click Go Live first."}
    background_tasks.add_task(orchestrator.run_cycle, max_emails)
    return {"status": "started"}


async def _seed_then_run() -> None:
    await orchestrator.seed_demo_conflict()
    await orchestrator.run_cycle(1)


@router.post("/demo")
async def trigger_conflict_demo(background_tasks: BackgroundTasks):
    """Deterministically reproduces the flagship scenario: a meeting
    request that collides with a task deadline, forcing the Calendar and
    Task agents to negotiate a new time live on the dashboard.

    Both the seeding step and the workflow run in the background — in
    real mode (real LLM + calendar calls) seeding alone can take tens of
    seconds, and this endpoint should return immediately so the dashboard
    isn't left hanging on the click. Progress streams over /ws/events
    regardless of how long it takes.
    """
    if _real_gmail_blocked():
        return {"status": "blocked", "reason": "Real Gmail is connected but the system is Stopped — click Go Live first."}
    background_tasks.add_task(_seed_then_run)
    return {"status": "started"}


@router.get("/approvals/pending")
async def pending_approvals():
    return {"pending": approval_store.list_pending()}


@router.post("/approvals/{decision_id}")
async def resolve_approval(decision_id: str, approved: bool):
    ok = approval_store.resolve(decision_id, approved)
    return {"resolved": ok}


@router.get("/completed")
async def completed_workflows(limit: int = 20):
    return {"workflows": orchestrator.completed_workflows[-limit:]}


@router.get("/live-status")
async def live_status():
    settings = get_settings()
    return {"live": system_state.is_live, "gmail_watch_configured": bool(settings.gmail_watch_topic)}


@router.post("/live-status")
async def set_live_status(live: bool, background_tasks: BackgroundTasks):
    settings = get_settings()
    gmail = orchestrator.email_agent.gmail_client

    if live:
        if settings.gmail_watch_topic and not gmail.is_mock:
            try:
                await gmail.start_watch(settings.gmail_watch_topic)
                system_state.last_watch_renewal = asyncio.get_event_loop().time()
            except Exception as exc:
                logger.error("live_status.start_watch_failed", error=str(exc))
                return {"live": system_state.is_live, "error": str(exc)}
        system_state.is_live = True
        # Going live also catches up on whatever's already sitting unread,
        # not just future changes — otherwise "Live" would silently do
        # nothing until the next new email arrives.
        background_tasks.add_task(orchestrator.run_cycle)
    else:
        system_state.is_live = False
        if settings.gmail_watch_topic and not gmail.is_mock:
            try:
                await gmail.stop_watch()
            except Exception as exc:
                logger.warning("live_status.stop_watch_failed", error=str(exc))

    return {"live": system_state.is_live}
