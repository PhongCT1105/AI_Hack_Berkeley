"""Degradation detector — the piece Arize AX itself doesn't provide.

Arize gives us traces with `captain_ddoski.trust_score` / `ranker.confidence`
on every call (see pipeline.py); this module is what actually decides "source
quality or model confidence degraded" by comparing a recent window of
ScoreHistory against an older baseline window, per domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.history import ScoreHistory

MIN_SAMPLES_PER_DOMAIN = 6
SCORE_DROP_THRESHOLD = 15.0
CONFIDENCE_DROP_THRESHOLD = 0.2
AVOID_RATE_INCREASE_THRESHOLD = 0.3


@dataclass
class DegradationReport:
    domain: str
    triggered: bool
    reasons: list[str] = field(default_factory=list)
    baseline_avg_score: float | None = None
    recent_avg_score: float | None = None
    recent_avg_confidence: float | None = None
    sample_count: int = 0
    most_recent_low_scoring_url: str | None = None


def _domain_groups(history: ScoreHistory) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for item in history.list():
        response = item.get("response", {})
        domain = response.get("domain")
        if not domain:
            continue
        groups.setdefault(domain, []).append(item)
    return groups


def evaluate_domain(domain: str, items: list[dict]) -> DegradationReport:
    """`items` is assumed newest-first (ScoreHistory.list() order)."""
    if len(items) < MIN_SAMPLES_PER_DOMAIN:
        return DegradationReport(domain=domain, triggered=False, sample_count=len(items))

    mid = len(items) // 2
    recent, baseline = items[:mid], items[mid:]

    def avg_score(rows: list[dict]) -> float:
        return sum(r["response"]["trust_score"] for r in rows) / len(rows)

    def avg_confidence(rows: list[dict]) -> float:
        scores = [r["response"]["trust_score"] for r in rows]
        return sum(min(abs(s - 40), abs(s - 70)) / 30.0 for s in scores) / len(scores)

    def avoid_rate(rows: list[dict]) -> float:
        return sum(1 for r in rows if r["response"]["recommendation"] == "AVOID") / len(rows)

    baseline_avg = avg_score(baseline)
    recent_avg = avg_score(recent)
    baseline_conf = avg_confidence(baseline)
    recent_conf = avg_confidence(recent)
    baseline_avoid = avoid_rate(baseline)
    recent_avoid = avoid_rate(recent)

    reasons: list[str] = []
    if baseline_avg - recent_avg >= SCORE_DROP_THRESHOLD:
        reasons.append(f"avg trust_score dropped {baseline_avg:.1f} -> {recent_avg:.1f}")
    if baseline_conf - recent_conf >= CONFIDENCE_DROP_THRESHOLD:
        reasons.append(f"avg confidence dropped {baseline_conf:.2f} -> {recent_conf:.2f}")
    if recent_avoid - baseline_avoid >= AVOID_RATE_INCREASE_THRESHOLD:
        reasons.append(f"AVOID rate rose {baseline_avoid:.0%} -> {recent_avoid:.0%}")

    low_scoring = min(recent, key=lambda r: r["response"]["trust_score"])

    return DegradationReport(
        domain=domain,
        triggered=bool(reasons),
        reasons=reasons,
        baseline_avg_score=round(baseline_avg, 1),
        recent_avg_score=round(recent_avg, 1),
        recent_avg_confidence=round(recent_conf, 3),
        sample_count=len(items),
        most_recent_low_scoring_url=low_scoring["response"]["url"],
    )


def scan_all_domains(history: ScoreHistory) -> list[DegradationReport]:
    return [evaluate_domain(domain, items) for domain, items in _domain_groups(history).items()]
