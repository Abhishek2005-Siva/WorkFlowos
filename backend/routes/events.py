from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.core.event_bus import event_bus
from backend.models.db import ConflictRecord, DecisionTrace, EventLog, get_session_factory

router = APIRouter(tags=["events"])


@router.get("/events/recent")
async def get_recent_events(limit: int = Query(50, le=200)):
    live = event_bus.recent(limit)
    if live:
        return {"events": live[-limit:]}

    async with get_session_factory()() as session:
        result = await session.execute(select(EventLog).order_by(EventLog.id.desc()).limit(limit))
        rows = result.scalars().all()
    return {
        "events": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "type": r.type,
                "category": r.category,
                "agent_name": r.agent_name,
                "message": r.message,
                "data": r.data,
                "thread_id": r.thread_id,
            }
            for r in reversed(rows)
        ]
    }


@router.get("/decisions")
async def list_decisions(limit: int = Query(20, le=100)):
    async with get_session_factory()() as session:
        result = await session.execute(select(DecisionTrace).order_by(DecisionTrace.id.desc()).limit(limit))
        rows = result.scalars().all()
    return {
        "decisions": [
            {
                "decision_id": r.decision_id,
                "timestamp": r.timestamp.isoformat(),
                "agent": r.agent,
                "type": r.decision_type,
                "title": r.title,
                "data": r.data,
            }
            for r in rows
        ]
    }


@router.get("/decisions/{decision_id}")
async def replay_decision(decision_id: str):
    async with get_session_factory()() as session:
        result = await session.execute(select(DecisionTrace).where(DecisionTrace.decision_id == decision_id))
        row = result.scalar_one_or_none()
    if row is None:
        return {"error": "not found"}
    return {
        "decision_id": row.decision_id,
        "timestamp": row.timestamp.isoformat(),
        "agent": row.agent,
        "type": row.decision_type,
        "title": row.title,
        "reasoning_trace": row.reasoning_trace,
        "data": row.data,
        "notion_page_id": row.notion_page_id,
    }


@router.get("/conflicts")
async def list_conflicts(limit: int = Query(20, le=100)):
    async with get_session_factory()() as session:
        result = await session.execute(select(ConflictRecord).order_by(ConflictRecord.id.desc()).limit(limit))
        rows = result.scalars().all()
    return {
        "conflicts": [
            {
                "conflict_id": r.conflict_id,
                "timestamp": r.timestamp.isoformat(),
                "agent1": r.agent1,
                "agent2": r.agent2,
                "description": r.description,
                "negotiation_log": r.negotiation_log,
                "status": r.status,
                "resolution": r.resolution,
            }
            for r in rows
        ]
    }
