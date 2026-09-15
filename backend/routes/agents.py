from fastapi import APIRouter

from backend.core.orchestrator import orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status")
async def get_agents_status():
    return {"agents": orchestrator.get_agents_status()}
