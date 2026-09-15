"""FastAPI entry point."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.reporting_agent import ReportingAgent
from backend.config import get_settings
from backend.core.orchestrator import orchestrator
from backend.core.scheduler import scheduler
from backend.core.system_state import system_state
from backend.models.db import init_db
from backend.routes import agents, calendar, discord_interactions, events, knowledge, slack_commands, webhooks, workflow, ws
from backend.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_poll_task: asyncio.Task | None = None
_gmail_watch_task: asyncio.Task | None = None


def _materialize_google_credentials() -> None:
    """Write GOOGLE_CREDENTIALS_JSON / GOOGLE_TOKEN_JSON (if set) out to
    disk at the paths the Google clients expect. Needed on platforms like
    Railway where the filesystem is rebuilt from the image on every
    deploy, so a git-ignored credentials/ directory never survives."""
    settings = get_settings()
    pairs = [
        (settings.google_credentials_json, settings.google_credentials_path),
        (settings.google_token_json, settings.google_token_path),
    ]
    for content, path_str in pairs:
        if not content:
            continue
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        logger.info("startup.materialized_google_credential", path=str(path))


GMAIL_WATCH_RENEWAL_SECONDS = 6 * 24 * 60 * 60  # renew a day before the 7-day expiry


async def _poll_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.poll_interval_seconds)
        try:
            await orchestrator.run_cycle()
        except Exception as exc:
            logger.error("poll_loop.run_cycle_failed", error=str(exc))


async def _gmail_watch_renewal_loop() -> None:
    """Checks hourly whether the watch needs (re)starting — only while
    the user has actually flipped the dashboard's Live switch on, and
    only every ~6 days once it has. Does nothing while stopped."""
    settings = get_settings()
    check_interval = 60 * 60
    while True:
        await asyncio.sleep(check_interval)
        if not system_state.is_live:
            continue
        now = asyncio.get_event_loop().time()
        if system_state.last_watch_renewal and now - system_state.last_watch_renewal < GMAIL_WATCH_RENEWAL_SECONDS:
            continue
        try:
            result = await orchestrator.email_agent.gmail_client.start_watch(settings.gmail_watch_topic)
            system_state.last_watch_renewal = now
            logger.info("gmail_watch.renewed", history_id=result.get("historyId"), expiration=result.get("expiration"))
        except Exception as exc:
            logger.error("gmail_watch.renewal_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _materialize_google_credentials()
    await init_db()
    logger.info("startup", mock_mode=settings.mock_mode, database_url=settings.database_url)

    global _poll_task, _gmail_watch_task
    if settings.enable_auto_poll:
        _poll_task = asyncio.create_task(_poll_loop())
    if settings.gmail_watch_topic:
        _gmail_watch_task = asyncio.create_task(_gmail_watch_renewal_loop())

    if settings.enable_daily_standup:
        scheduler.register("daily_standup", hour=8, minute=30, func=lambda: ReportingAgent().generate("standup"))
    if settings.enable_weekly_report:
        scheduler.register(
            "weekly_report", hour=16, minute=0, weekday=4, func=lambda: ReportingAgent().generate("weekly")
        )
    scheduler.start()

    yield

    if _poll_task:
        _poll_task.cancel()
    if _gmail_watch_task:
        _gmail_watch_task.cancel()
    scheduler.stop()


app = FastAPI(title="WorkflowOS", version="1.0.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_origin_regex=_settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(calendar.router)
app.include_router(discord_interactions.router)
app.include_router(events.router)
app.include_router(knowledge.router)
app.include_router(slack_commands.router)
app.include_router(webhooks.router)
app.include_router(workflow.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "mock_mode": settings.mock_mode}
