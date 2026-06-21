"""Cache abstraction: Redis when REDIS_URL is set, else in-memory dict with TTL.

Same async interface either way so the pipeline never branches on backend.
Used to avoid re-crawling the same URL within the TTL window.
"""
from __future__ import annotations

import json
import logging
import time

from app.core.config import settings

logger = logging.getLogger("captain_america.cache")


class Cache:
    def __init__(self) -> None:
        self._redis = None
        self._mem: dict[str, tuple[float, str]] = {}  # key -> (expires_at, json_value)
        if settings.has_redis:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                logger.info("Cache using Redis")
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis unavailable, falling back to in-memory cache: %s", exc)
                self._redis = None

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    async def get(self, key: str):
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis get failed: %s", exc)
                return None
        entry = self._mem.get(key)
        if not entry:
            return None
        expires_at, raw = entry
        if expires_at < time.monotonic():
            self._mem.pop(key, None)
            return None
        return json.loads(raw)

    async def set(self, key: str, value, ttl: int | None = None) -> None:
        ttl = ttl if ttl is not None else settings.cache_ttl_seconds
        raw = json.dumps(value)
        if self._redis is not None:
            try:
                await self._redis.set(key, raw, ex=ttl)
                return
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis set failed: %s", exc)
                return
        self._mem[key] = (time.monotonic() + ttl, raw)
