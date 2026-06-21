"""Auto-launch: when a scored source misses the trust/citation threshold,
fetch a fresh candidate and stage it in Supabase + Terac — closing the loop
described in the monitored-MCP pitch without waiting for the periodic
degradation monitor.

The Supabase insert happens regardless of mode, so the new task is
immediately labelable by anyone hitting /annotate organically — that alone
is often enough to get a fresh label without spending anything. Terac's
side is gated by TERAC_AUTO_LAUNCH_MODE:
  - "draft" (default): create the opportunity only. Free, no recruitment;
    a human reviews and calls terac_launch_draft_opportunity later once
    they've decided it's worth scaling up paid labeling.
  - "launch": also launch it immediately — real money, real recruitment.

Fired as a background task from Pipeline.score_source (see fire_and_forget)
so it never adds latency to, or can fail, the calling agent's request.
Bounded by app/ml/terac_auto_launch_store.py's per-domain cooldown and
global cap either way, so a noisy domain can't spam drafts or spend.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.config import settings
from app.core.observability import capture_exception, get_tracer
from app.ml import terac_auto_launch_store as store
from app.ml import terac_mcp_client
from app.ml.terac_mcp_client import TeracMCPError
from app.schemas.score import Recommendation, ScoreResponse
from app.services.supabase_writer import insert_task_row

if TYPE_CHECKING:
    from app.services.pipeline import Pipeline

logger = logging.getLogger("captain_ddoski.terac_auto_launch")

# Matches the research_task wording already used across the 200 existing
# labeled rows in Supabase (see data/supabase_labeled_tasks.jsonl) so new
# rows are indistinguishable from the original training data to an annotator.
RESEARCH_TASK_PROMPT = (
    "An AI financial research agent is deciding whether it can cite this "
    "claim/source. Judge whether the claim is trustworthy enough to use."
)

_background_tasks: set[asyncio.Task] = set()


def fire_and_forget(pipeline: "Pipeline", response: ScoreResponse) -> None:
    """Schedule the auto-launch check without blocking the caller. Keeps a
    strong reference to the task so it isn't garbage-collected mid-flight."""
    task = asyncio.create_task(evaluate(pipeline, response))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def missed_threshold(response: ScoreResponse) -> bool:
    if response.recommendation != Recommendation.USE:
        return True
    return response.citation_assessment.eligible is False


async def evaluate(pipeline: "Pipeline", response: ScoreResponse) -> dict | None:
    """Run the auto-launch check and, if it fires, return what happened
    (candidate URL, Supabase task id, Terac opportunity id, mode). Returns
    None when nothing fired (threshold met, not configured, or
    cooldown/cap). Public and awaitable — fire_and_forget wraps this for
    the normal scoring path; app/services/workflow_demo.py awaits it
    directly so the showcase transcript can display the real result."""
    try:
        if not missed_threshold(response):
            return None
        if not (settings.terac_api_url and settings.terac_api_key and settings.terac_project_id):
            logger.info("Auto-launch skipped: Terac MCP not fully configured")
            return None

        ok, reason = store.can_launch(response.domain)
        if not ok:
            logger.info("Auto-launch skipped for domain=%s: %s", response.domain, reason)
            return {"skipped": True, "reason": reason}

        tracer = get_tracer()
        with tracer.start_as_current_span("captain_ddoski.terac_auto_launch.run") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            span.set_attribute("auto_launch.domain", response.domain)
            span.set_attribute("auto_launch.original_url", response.url)
            span.set_attribute("auto_launch.recommendation", response.recommendation.value)

            candidate_url = await _find_fresh_candidate(pipeline, response, span)
            task_id = f"auto_{uuid.uuid4().hex[:10]}"

            supabase_task_id = await insert_task_row(_build_supabase_row(task_id, candidate_url, response))
            span.set_attribute("auto_launch.supabase_task_id", supabase_task_id or "")

            launched = False
            error: str | None = None
            try:
                opportunity_id = await _create_opportunity(candidate_url, response)
                if settings.terac_auto_launch_mode == "launch":
                    await terac_mcp_client.call_tool(
                        "terac_launch_draft_opportunity", {"opportunityId": opportunity_id}
                    )
                    launched = True
            except TeracMCPError as exc:
                logger.warning("Auto-launch: Terac opportunity step failed: %s", exc)
                span.record_exception(exc)
                opportunity_id = None
                error = str(exc)

            span.set_attribute("auto_launch.opportunity_id", opportunity_id or "")
            span.set_attribute("auto_launch.launched", launched)
            store.record_launch(response.domain, candidate_url, opportunity_id, supabase_task_id, launched)
            return {
                "skipped": False,
                "domain": response.domain,
                "candidate_url": candidate_url,
                "supabase_task_id": supabase_task_id,
                "opportunity_id": opportunity_id,
                "mode": settings.terac_auto_launch_mode,
                "launched": launched,
                "error": error,
            }
    except Exception as exc:  # pragma: no cover - never propagate to the caller
        capture_exception(exc)
        return {"skipped": True, "reason": str(exc)}


async def _find_fresh_candidate(pipeline: "Pipeline", response: ScoreResponse, span) -> str:
    """Best-effort Firecrawl search for an alternative source on the same
    task; falls back to the original (failing) URL when search is
    unavailable or empty, so the labeling job still has something to grade."""
    result = await pipeline.collector.search(response.task, limit=5)
    span.set_attribute("auto_launch.search_mode", result.mode)
    fresh = next((u for u in result.urls if u != response.url), None)
    return fresh or response.url


def _build_supabase_row(task_id: str, candidate_url: str, response: ScoreResponse) -> dict:
    top_claim = response.claims[0].text if response.claims else response.task
    return {
        "task_id": task_id,
        "task_type": "financial_claim_credibility",
        "research_task": RESEARCH_TASK_PROMPT,
        "claim": top_claim,
        "author": "",
        "posted_date": "",
        "source": response.domain,
        "evidence_text": "[]",
        "evidence_url": candidate_url,
        "image_url": "",
        "capsule": response.evidence_capsule.compressed_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evidence_text_clean": "",
    }


async def _create_opportunity(candidate_url: str, response: ScoreResponse) -> str:
    payload = {
        "title": f"Verify finance source credibility: {response.domain}",
        "internal_title": f"auto_launch:{response.domain}:{response.trace_id}",
        "description": (
            f"An AI agent scored {candidate_url} as {response.recommendation.value} while "
            f"researching: {response.task}. Read the source and judge whether the claim it "
            "supports is trustworthy enough for an AI agent to cite."
        ),
        "project_id": settings.terac_project_id,
        "num_participants": settings.terac_auto_launch_participants,
        "business_type": "b2c",
        "tasks": [{
            "sequence": 1,
            "task_type": "activity",
            "review_type": "manual_review",
            "task_url": settings.terac_auto_launch_task_url,
            "title": "Judge source credibility",
            "description": "Read the source and judge whether it is trustworthy enough to cite.",
            "duration_minutes": settings.terac_auto_launch_duration_minutes,
        }],
    }
    created = await terac_mcp_client.call_tool("terac_create_opportunity", payload)
    opportunity_id = created.get("opportunityId") or created.get("id")
    if not opportunity_id:
        raise TeracMCPError(f"terac_create_opportunity response had no opportunity id: {created}")
    return opportunity_id
