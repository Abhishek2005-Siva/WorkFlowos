"""Minimal async cron scheduler — no APScheduler dependency needed for a
handful of daily/weekly jobs. Each job is a coroutine run once at (or
just after) its target time every day; weekly jobs additionally check
the weekday. Missed windows (server was down) are simply skipped, not
caught up — these are reporting jobs, not critical-path work.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from backend.utils.logging import get_logger

logger = get_logger(__name__)

Job = Callable[[], Awaitable[None]]


@dataclass
class ScheduledJob:
    name: str
    hour: int
    minute: int
    func: Job
    weekday: int | None = None  # 0=Monday ... 6=Sunday; None = every day


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []
        self._task: asyncio.Task | None = None
        self._last_run: dict[str, str] = {}  # job name -> ISO date last fired

    def register(self, name: str, hour: int, minute: int, func: Job, weekday: int | None = None) -> None:
        self._jobs.append(ScheduledJob(name, hour, minute, func, weekday))

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        today_key = now.date().isoformat()
        for job in self._jobs:
            if job.weekday is not None and now.weekday() != job.weekday:
                continue
            target = now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)
            if now < target or now > target + timedelta(minutes=5):
                continue
            if self._last_run.get(job.name) == today_key:
                continue
            self._last_run[job.name] = today_key
            logger.info("scheduler.running_job", job=job.name)
            try:
                await job.func()
            except Exception as exc:
                logger.error("scheduler.job_failed", job=job.name, error=str(exc))

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self._tick()
            except Exception as exc:
                logger.error("scheduler.tick_failed", error=str(exc))

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None


scheduler = Scheduler()
