"""Read-only Sentry issue feed for the home page's System Health panel.

Separate credential from observability.py's SENTRY_DSN: that one lets the SDK
*send* events, this one (an org-level Auth Token) lets the backend *read*
recent issues back out of Sentry's REST API. Absent either capability, the
endpoint reports configured=False so the frontend can fall back honestly
instead of showing fake data.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["system-health"])

_SENTRY_API_BASE = "https://sentry.io/api/0"
_PROJECTS = ["python-fastapi", "captain-ddoski-frontend"]


@router.get("/system-health")
async def system_health() -> dict:
    if not settings.has_sentry_api:
        return {"configured": False, "issues": []}

    headers = {"Authorization": f"Bearer {settings.sentry_auth_token}"}
    issues: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for project in _PROJECTS:
            try:
                resp = await client.get(
                    f"{_SENTRY_API_BASE}/projects/{settings.sentry_org_slug}/{project}/issues/",
                    headers=headers,
                    params={"statsPeriod": "24h", "sort": "date", "limit": 5},
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                continue

            for item in resp.json():
                issues.append(
                    {
                        "project": project,
                        "title": item.get("title"),
                        "level": item.get("level"),
                        "status": item.get("status"),
                        "culprit": item.get("culprit"),
                        "count": item.get("count"),
                        "last_seen": item.get("lastSeen"),
                        "permalink": item.get("permalink"),
                    }
                )

    issues.sort(key=lambda i: i["last_seen"] or "", reverse=True)
    return {
        "configured": True,
        "org_slug": settings.sentry_org_slug,
        "issues": issues[:6],
    }
