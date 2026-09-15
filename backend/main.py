"""FastAPI entry point."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.core.orchestrator import orchestrator
from backend.models.db import init_db
from backend.routes import agents, events, knowledge, webhooks, workflow, ws
from backend.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_poll_task: asyncio.Task | None = None


async def _poll_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.poll_interval_seconds)
        try:
            await orchestrator.run_cycle()
        except Exception as exc:
            logger.error("poll_loop.run_cycle_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    logger.info("startup", mock_mode=settings.mock_mode, database_url=settings.database_url)

    global _poll_task
    if settings.enable_auto_poll:
        _poll_task = asyncio.create_task(_poll_loop())

    yield

    if _poll_task:
        _poll_task.cancel()


app = FastAPI(title="WorkflowOS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(events.router)
app.include_router(knowledge.router)
app.include_router(webhooks.router)
app.include_router(workflow.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "mock_mode": settings.mock_mode}
