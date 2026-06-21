"""Streams the same work ResearchAgent.run() does, one step at a time.

This is not a scripted replay: every event below comes from a real call —
the same Claude planner, the same Firecrawl search, the same score_source
pipeline (collector/extractor/ranker/citation/capsule), and the same Terac
auto-launch check that fires in production. The only difference from a
plain POST /api/research call is that each sub-step is yielded as it
completes instead of being collected into one final JSON response, so the
frontend can render it as an AI-native transcript (tool call -> result ->
narrative) rather than a step-progress bar.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.core.config import settings
from app.schemas.score import ScoreRequest, ScoreResponse
from app.services import monitor, terac_auto_launch
from app.services.pipeline import Pipeline
from app.services.research_agent import ResearchAgent


def _event(type_: str, **kwargs: Any) -> dict:
    return {"type": type_, **kwargs}


async def _score_one(
    pipeline: Pipeline, url: str, task: str
) -> tuple[str, ScoreResponse | None, str | None, list[dict]]:
    """Scores one URL and also collects every internal pipeline stage
    (collector, extractor, TTC prompt compression, ranker, citation
    classifier, finance capsule compression) via Pipeline.score_source's
    on_step hook, so the transcript can show them individually instead of
    one opaque score_source call. Each concurrent call gets its own list,
    so interleaved scoring of multiple URLs never mixes up which stage
    belongs to which URL."""
    steps: list[dict] = []
    try:
        resp = await pipeline.score_source(ScoreRequest(url=url, task=task), on_step=steps.append)
        return url, resp, None, steps
    except Exception as exc:  # pragma: no cover - surfaced to the transcript, not raised
        return url, None, str(exc), steps


async def stream_workflow(pipeline: Pipeline, history, prompt: str, max_sources: int) -> AsyncIterator[dict]:
    agent = ResearchAgent(pipeline)

    yield _event("narrative", text=f'Planning a web search for: "{prompt}"')
    yield _event("tool_call", tool="claude_plan_search", input={"prompt": prompt})
    query, planner_mode, plan_compression = await agent.plan(prompt)
    yield _event("tool_result", tool="claude_plan_search", output={"search_query": query, "planner_mode": planner_mode})
    if plan_compression:
        yield _event("tool_call", tool="ttc_compress_prompt", input={"note": "compressing the planning prompt"})
        yield _event("tool_result", tool="ttc_compress_prompt", output=plan_compression)

    cap = min(max_sources, settings.research_max_sources)
    yield _event("tool_call", tool="firecrawl_search", input={"query": query, "limit": cap})
    discovery = await pipeline.collector.search(query, cap)
    yield _event(
        "tool_result",
        tool="firecrawl_search",
        output={"urls": discovery.urls, "mode": discovery.mode, "error": discovery.error},
    )
    if discovery.error and not discovery.urls:
        yield _event("narrative", text=f"Search discovery failed: {discovery.error}")
        yield _event("final", output=_empty_final(prompt, query, discovery.mode, discovery.error))
        return

    semaphore = asyncio.Semaphore(settings.research_concurrency)

    async def bounded_score(url: str):
        async with semaphore:
            return await _score_one(pipeline, url, prompt)

    scored: list[ScoreResponse] = []
    for coro in asyncio.as_completed([bounded_score(u) for u in discovery.urls]):
        url, resp, error, steps = await coro
        yield _event("narrative", text=f"Scoring candidate source: {url}")
        yield _event("tool_call", tool="captain_ddoski_score_source", input={"url": url, "task": prompt})
        for step in steps:
            yield step
        if resp is None:
            yield _event("tool_result", tool="captain_ddoski_score_source", output={"url": url, "error": error})
            continue

        scored.append(resp)
        yield _event(
            "tool_result",
            tool="captain_ddoski_score_source",
            output={
                "url": resp.url,
                "domain": resp.domain,
                "trust_score": resp.trust_score,
                "recommendation": resp.recommendation.value,
                "risk_tags": resp.risk_tags,
                "scorer_mode": resp.scorer_mode,
                "citation_eligible": resp.citation_assessment.eligible,
            },
        )

        if terac_auto_launch.missed_threshold(resp):
            yield _event(
                "narrative",
                text=(
                    f"{resp.domain} scored {resp.recommendation.value} ({resp.trust_score}/100) — "
                    "checking whether this needs a fresh human label."
                ),
            )
            yield _event(
                "tool_call",
                tool="terac_auto_launch",
                input={"domain": resp.domain, "mode": settings.terac_auto_launch_mode},
            )
            launch_result = await terac_auto_launch.evaluate(pipeline, resp)
            yield _event("tool_result", tool="terac_auto_launch", output=launch_result or {"skipped": True, "reason": "not configured"})
        else:
            yield _event(
                "narrative",
                text=f"{resp.domain} cleared the trust threshold ({resp.trust_score}/100) — eligible to cite.",
            )

    scored.sort(key=lambda item: item.trust_score, reverse=True)
    cited = [item for item in scored if item.recommendation.value == "USE"][:8]
    rejected = [item for item in scored if item.recommendation.value == "AVOID"][:8]

    yield _event(
        "narrative",
        text="Checking recent score history for signs the ranker's confidence has degraded...",
    )
    yield _event("tool_call", tool="degradation_monitor", input={"domains_scored": sorted({s.domain for s in scored})})
    monitor_result = await monitor.run_check(pipeline, history)
    yield _event("tool_result", tool="degradation_monitor", output=monitor_result)
    if monitor_result.get("domains_flagged"):
        if monitor_result.get("retrained"):
            train_result = monitor_result.get("train_result") or {}
            yield _event(
                "narrative",
                text=(
                    f"Model updated: the ranker was retrained and promoted — holdout accuracy "
                    f"{train_result.get('holdout_accuracy')} beat the heuristic baseline "
                    f"{train_result.get('baseline_accuracy')}."
                ),
            )
        else:
            note = (monitor_result.get("train_result") or {}).get("note", "not enough fresh labels yet")
            yield _event(
                "narrative",
                text=(
                    f"Degradation flagged on {', '.join(monitor_result['domains_flagged'])}, queued for fresh "
                    f"Terac annotation, but the ranker was not retrained: {note}"
                ),
            )
    else:
        yield _event("narrative", text="No degradation detected across recent calls — ranker confidence holding steady.")

    yield _event(
        "tool_call",
        tool="claude_synthesize",
        input={"prompt": prompt, "cited_sources": [s.domain for s in cited]},
    )
    answer, writer_mode, synth_compression = await agent.synthesize(prompt, cited)
    yield _event("tool_result", tool="claude_synthesize", output={"answer": answer, "writer_mode": writer_mode})
    if synth_compression:
        yield _event("tool_call", tool="ttc_compress_prompt", input={"note": "compressing the cited-evidence prompt"})
        yield _event("tool_result", tool="ttc_compress_prompt", output=synth_compression)

    yield _event(
        "final",
        output={
            "prompt": prompt,
            "search_query": query,
            "search_mode": discovery.mode,
            "discovered_count": len(discovery.urls),
            "inspected_count": len(scored),
            "agent_mode": f"{planner_mode} + {writer_mode}",
            "answer": answer,
            "discovery_error": discovery.error,
            "cited_sources": [s.model_dump(mode="json") for s in cited],
            "rejected_sources": [s.model_dump(mode="json") for s in rejected],
        },
    )


def _empty_final(prompt: str, query: str, search_mode: str, error: str | None) -> dict:
    return {
        "prompt": prompt,
        "search_query": query,
        "search_mode": search_mode,
        "discovered_count": 0,
        "inspected_count": 0,
        "agent_mode": "",
        "answer": "I could not discover any sources to verify for this request.",
        "discovery_error": error,
        "cited_sources": [],
        "rejected_sources": [],
    }
