"""Domain reputation lookup.

Order of precedence: Redis learned reputation (if present) -> static finance
allow/blocklist -> neutral 0.5. `record_observation` lets the system build a
rolling reputation when Redis is available (no-op otherwise).
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.core.cache import Cache
from app.data.finance_domains import classify_domain

logger = logging.getLogger("captain_america.reputation")

_REDIS_KEY = "captain_america:reputation"


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url if "://" in url else f"https://{url}").netloc
        return netloc.lower() or url.lower()
    except Exception:
        return url.lower()


async def lookup(url: str, cache: Cache | None = None) -> tuple[float, str | None, str]:
    """Return (reputation 0..1, listed "allow"|"block"|None, domain)."""
    domain = domain_of(url)
    static_rep, listed = classify_domain(domain)

    # A learned reputation (from prior observations) refines the static prior.
    if cache is not None and cache.backend == "redis" and cache._redis is not None:
        try:
            learned = await cache._redis.hget(_REDIS_KEY, domain)
            if learned is not None:
                # blend learned signal with the static prior
                blended = 0.5 * static_rep + 0.5 * float(learned)
                return max(0.0, min(1.0, blended)), listed, domain
        except Exception as exc:  # pragma: no cover
            logger.debug("reputation hget failed: %s", exc)

    return static_rep, listed, domain


async def record_observation(domain: str, trust_score: int, cache: Cache | None = None) -> None:
    """Persist a rolling reputation when Redis is available; no-op otherwise."""
    if cache is None or cache.backend != "redis" or cache._redis is None:
        return
    try:
        prev = await cache._redis.hget(_REDIS_KEY, domain)
        observed = trust_score / 100.0
        new = observed if prev is None else (0.7 * float(prev) + 0.3 * observed)
        await cache._redis.hset(_REDIS_KEY, domain, round(new, 4))
    except Exception as exc:  # pragma: no cover
        logger.debug("reputation hset failed: %s", exc)
