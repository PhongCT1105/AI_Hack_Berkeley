"""Score history and threat feed endpoints."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.history import response_from_history_item

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/results")
def list_results(request: Request) -> list[dict[str, Any]]:
    history = request.app.state.score_history
    return history.list()


@router.get("/results/{trace_id}")
def get_result(trace_id: str, request: Request) -> dict[str, Any]:
    history = request.app.state.score_history
    item = history.get(trace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return item


@router.get("/threats")
def list_threats(request: Request) -> dict[str, Any]:
    history = request.app.state.score_history
    grouped: dict[str, dict[str, Any]] = {}
    risk_counts: Counter[str] = Counter()
    flagged_count = 0

    for item in history.list():
        response = response_from_history_item(item)
        if response is None or response.recommendation.value != "AVOID":
            continue

        flagged_count += 1
        domain = response.domain or "unknown domain"
        received_at = item.get("received_at")
        existing = grouped.get(domain)
        if existing is None:
            existing = {
                "domain": domain,
                "risk_tags": set(),
                "trust_scores": [],
                "times_seen": 0,
                "first_seen": received_at,
                "last_seen": received_at,
                "callers": set(),
            }
            grouped[domain] = existing

        existing["times_seen"] += 1
        existing["risk_tags"].update(response.risk_tags or [])
        existing["trust_scores"].append(response.trust_score)
        existing["callers"].add(item.get("caller", "api"))
        existing["first_seen"] = _oldest(existing["first_seen"], received_at)
        existing["last_seen"] = _newest(existing["last_seen"], received_at)
        risk_counts.update(response.risk_tags or [])

    threats = []
    for threat in grouped.values():
        scores = threat.pop("trust_scores")
        threat["risk_tags"] = sorted(threat["risk_tags"])
        threat["callers"] = sorted(threat["callers"])
        threat["trust_score"] = round(sum(scores) / len(scores)) if scores else None
        threats.append(threat)

    threats.sort(key=lambda t: (-t["times_seen"], t["domain"]))
    common_patterns = [
        {
            "tag": tag,
            "count": count,
            "percent": round((count / flagged_count) * 100) if flagged_count else 0,
        }
        for tag, count in risk_counts.most_common(5)
    ]

    return {
        "flagged_count": flagged_count,
        "threats": threats,
        "common_patterns": common_patterns,
    }


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _oldest(a: Any, b: Any) -> Any:
    parsed_a = _parse_time(a)
    parsed_b = _parse_time(b)
    if parsed_a is None:
        return b
    if parsed_b is None:
        return a
    return a if parsed_a <= parsed_b else b


def _newest(a: Any, b: Any) -> Any:
    parsed_a = _parse_time(a)
    parsed_b = _parse_time(b)
    if parsed_a is None:
        return b
    if parsed_b is None:
        return a
    return a if parsed_a >= parsed_b else b
