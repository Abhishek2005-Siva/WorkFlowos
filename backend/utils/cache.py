"""Redis-backed cache with an in-memory fallback.

Used for: agent state snapshots, "last known good" data for fallback level 3
(serve cached data when an upstream API is down), and simple rate-limit
bookkeeping. If Redis is unreachable the cache degrades to an in-process
dict so local development never hard-fails on a missing Redis server.
"""
from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from backend.config import get_settings
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class Cache:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._memory: dict[str, tuple[float | None, str]] = {}
        self._redis_available = True

    async def _client(self) -> aioredis.Redis | None:
        if not self._redis_available:
            return None
        if self._redis is None:
            settings = get_settings()
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await self._redis.ping()
            return self._redis
        except Exception as exc:
            logger.warning("cache.redis_unavailable_falling_back_to_memory", error=str(exc))
            self._redis_available = False
            return None

    async def get(self, key: str) -> Any | None:
        client = await self._client()
        if client is not None:
            try:
                raw = await client.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                pass
        entry = self._memory.get(key)
        if entry is None:
            return None
        expires_at, raw = entry
        if expires_at is not None and expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        raw = json.dumps(value, default=str)
        client = await self._client()
        if client is not None:
            try:
                await client.set(key, raw, ex=ttl_seconds)
                return
            except Exception:
                pass
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._memory[key] = (expires_at, raw)


cache = Cache()
