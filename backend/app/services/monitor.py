"""Degradation-triggered retrain loop.

Arize AX doesn't do drift-triggered automation (confirmed against their docs)
— it just gives us the traces. This module is the part we own: scan recent
score history per domain, queue degraded domains for fresh Terac annotation,
and retrain/promote a ranker once enough labels exist. Every run is itself
traced so the loop is visible in Arize too.
"""
from __future__ import annotations

import logging

from app.core.observability import get_tracer
from app.ml import model_registry, retrain_queue, trainer
from app.services import degradation
from app.services.pairing import build_pair
from app.services.pipeline import Pipeline

logger = logging.getLogger("captain_ddoski.monitor")

# Same trusted reference source used elsewhere in the demo (mcp_server.py,
# api/demo.py) — the known-good anchor an auto-queued pair compares against.
TRUSTED_BASELINE_URL = "https://www.sec.gov/investor/pubs/assetallocation.htm"


async def run_check(pipeline: Pipeline, history) -> dict:
    tracer = get_tracer()
    with tracer.start_as_current_span("captain_ddoski.monitor.run") as span:
        reports = degradation.scan_all_domains(history)
        flagged = [r for r in reports if r.triggered]

        queued = 0
        for report in flagged:
            retrain_queue.enqueue(report.domain, report.reasons)
            if report.most_recent_low_scoring_url:
                try:
                    await build_pair(
                        pipeline,
                        task=f"Re-evaluate {report.domain} after a degradation finding: {'; '.join(report.reasons)}",
                        url_a=TRUSTED_BASELINE_URL,
                        url_b=report.most_recent_low_scoring_url,
                        auto_queued_reason="; ".join(report.reasons),
                    )
                    queued += 1
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning("Failed to auto-queue pair for domain %s: %s", report.domain, exc)
            retrain_queue.mark_processed(report.domain)

        retrained = False
        train_result = None
        can_train, _ = trainer.can_train()
        if can_train:
            train_result = trainer.train()
            if train_result.get("trained"):
                model_registry.load()
                retrained = True

        span.set_attribute("monitor.domains_checked", len(reports))
        span.set_attribute("monitor.domains_flagged", len(flagged))
        span.set_attribute("monitor.pairs_queued", queued)
        span.set_attribute("monitor.retrained", retrained)

        return {
            "domains_checked": len(reports),
            "domains_flagged": [r.domain for r in flagged],
            "pairs_queued": queued,
            "retrained": retrained,
            "train_result": train_result,
            "reports": [r.__dict__ for r in reports],
        }
