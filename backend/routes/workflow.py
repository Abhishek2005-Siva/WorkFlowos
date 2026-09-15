"""Manual workflow controls used by the dashboard's "Run Demo" button and
by the approve/reject UI (an alternative to clicking in Slack)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from backend.core.approvals import approval_store
from backend.core.orchestrator import orchestrator

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("/trigger")
async def trigger_cycle(background_tasks: BackgroundTasks, max_emails: int = 3):
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
