from fastapi import APIRouter, Query

from backend.core.orchestrator import orchestrator

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/graph")
async def get_graph():
    return await orchestrator.knowledge_graph_agent.graph_snapshot()


@router.get("/query")
async def query_context(entity: str = Query(...), type: str = Query("person")):
    return await orchestrator.knowledge_graph_agent.query_context(entity, type)
