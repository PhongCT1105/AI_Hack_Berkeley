"""Side-by-side showcase: the deployed heuristic ranker with no compression
("weak") vs. our full pipeline — TTC-compressed extraction + our own
FinanceCredibilityCompressor capsule + a freshly-fit candidate trained model
("better") — scored on the SAME collected page so the only variables that
change are compression and ranking, not the input data.

The candidate model is fit fresh via trainer.fit_candidate() and used here
regardless of whether it would clear the production promotion bar — this
view exists to show real numbers (including "not better yet"), not to
pretend a promoted model exists when it doesn't.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator

from app.core.config import settings
from app.ml import model_registry, trainer
from app.services import features as features_mod
from app.services import ranker, reputation
from app.services.capsule import compress
from app.services.collector import CollectResult, Collector
from app.services.extractor import Extractor
from app.services.research_agent import ResearchAgent


def _event(type_: str, **kwargs: Any) -> dict:
    return {"type": type_, **kwargs}


@dataclass
class SideResult:
    label: str                     # "weak" | "better"
    domain: str
    trust_score: int
    recommendation: str
    risk_tags: list[str]
    scorer_mode: str
    input_tokens: int
    output_tokens: int
    compression: dict | None       # TTC compression stats, None on the weak side
    evidence_preview: str
    evidence_chars: int
    latency_ms: int


async def _score_weak(collected: CollectResult, task: str, cache) -> SideResult:
    """Heuristic ranker, no TTC compression: extraction goes through a bare
    AsyncAnthropic client (TTC's wrapper never touches it), and the evidence
    handed to a downstream agent is the raw collected text, uncompressed."""
    t0 = time.perf_counter()
    bare_client = None
    if settings.has_anthropic:
        from anthropic import AsyncAnthropic

        bare_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    extracted = await Extractor().extract(collected, task, client=bare_client)
    rep, listed, domain = await reputation.lookup(collected.final_url, cache)
    feats = features_mod.build_features(collected, extracted, rep, listed)
    trust_score, _contributions, _verdicts, risk_tags = ranker.score_heuristic(feats)
    recommendation = ranker.recommend(trust_score)
    usage = extracted.usage or {"input_tokens": 0, "output_tokens": 0}
    evidence_preview = (collected.text or "")[:400]

    return SideResult(
        label="weak",
        domain=domain,
        trust_score=trust_score,
        recommendation=recommendation.value,
        risk_tags=sorted(set(risk_tags)),
        scorer_mode="heuristic",
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        compression=None,
        evidence_preview=evidence_preview,
        evidence_chars=len(collected.text or ""),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def _score_better(
    collected: CollectResult, task: str, cache, candidate_model: Any | None
) -> SideResult:
    """TTC-compressed extraction (default client), our FinanceCredibilityCompressor
    capsule, and — when enough Terac labels exist — our freshly-fit candidate
    model instead of the heuristic. Falls back to the heuristic, clearly
    labeled, when there's no usable candidate yet."""
    t0 = time.perf_counter()
    extracted = await Extractor().extract(collected, task)
    rep, listed, domain = await reputation.lookup(collected.final_url, cache)
    feats = features_mod.build_features(collected, extracted, rep, listed)
    h_score, _contributions, verdicts, risk_tags = ranker.score_heuristic(feats)

    if candidate_model is not None:
        prob = float(candidate_model.predict_proba([model_registry.feature_vector(feats)])[0][1])
        trust_score = int(max(0, min(100, round(prob * 100))))
        scorer_mode = "candidate_model"
    else:
        trust_score = h_score
        scorer_mode = "heuristic (no candidate model yet)"
    recommendation = ranker.recommend(trust_score)

    top_reasons = [v.detail for v in sorted(verdicts, key=lambda v: -v.weight)[:5]]
    capsule = await compress(collected, extracted, feats, top_reasons)
    usage = extracted.usage or {"input_tokens": 0, "output_tokens": 0}

    return SideResult(
        label="better",
        domain=domain,
        trust_score=trust_score,
        recommendation=recommendation.value,
        risk_tags=sorted(set(risk_tags)),
        scorer_mode=scorer_mode,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        compression=extracted.compression,
        evidence_preview=capsule.compressed_text,
        evidence_chars=len(capsule.compressed_text),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def _compare_one(
    collector: Collector, cache, url: str, task: str, candidate_model: Any | None
) -> tuple[str, SideResult, SideResult]:
    collected = await collector.collect(url)
    weak, better = await asyncio.gather(
        _score_weak(collected, task, cache),
        _score_better(collected, task, cache, candidate_model),
    )
    return url, weak, better


async def stream_comparison(pipeline, prompt: str, max_sources: int) -> AsyncIterator[dict]:
    agent = ResearchAgent(pipeline)

    yield _event("narrative", text=f'Planning a broad financial-source search for: "{prompt}"')
    query, planner_mode, _plan_compression = await agent.plan(prompt)
    yield _event("tool_result", tool="claude_plan_search", output={"search_query": query, "planner_mode": planner_mode})

    cap = min(max_sources, settings.research_max_sources)
    discovery = await pipeline.collector.search(query, cap)
    yield _event(
        "tool_result",
        tool="firecrawl_search",
        output={"urls": discovery.urls, "mode": discovery.mode, "error": discovery.error},
    )
    if discovery.error and not discovery.urls:
        yield _event("narrative", text=f"Search discovery failed: {discovery.error}")
        yield _event("summary", output=_empty_summary(discovery.error))
        return

    yield _event(
        "narrative",
        text=(
            "Fitting a candidate model on the current Terac labels for the 'better' "
            "column — not promoted to production, used here only for this comparison."
        ),
    )
    candidate_model, candidate_meta = trainer.fit_candidate()
    yield _event("tool_result", tool="fit_candidate_model", output=candidate_meta)

    totals = {"weak_input_tokens": 0, "weak_output_tokens": 0, "better_input_tokens": 0, "better_output_tokens": 0}
    disagreements: list[dict] = []
    compared = 0

    for url in discovery.urls:
        yield _event("narrative", text=f"Scoring {url} through both pipelines...")
        try:
            _, weak, better = await _compare_one(pipeline.collector, pipeline.cache, url, prompt, candidate_model)
        except Exception as exc:  # pragma: no cover - surfaced to the transcript, not raised
            yield _event("row_error", url=url, error=str(exc))
            continue

        compared += 1
        totals["weak_input_tokens"] += weak.input_tokens
        totals["weak_output_tokens"] += weak.output_tokens
        totals["better_input_tokens"] += better.input_tokens
        totals["better_output_tokens"] += better.output_tokens
        if weak.recommendation != better.recommendation:
            disagreements.append({
                "url": url,
                "domain": weak.domain,
                "weak": weak.recommendation,
                "better": better.recommendation,
            })

        yield _event("row", url=url, domain=weak.domain, weak=asdict(weak), better=asdict(better))

    weak_total_tokens = totals["weak_input_tokens"] + totals["weak_output_tokens"]
    better_total_tokens = totals["better_input_tokens"] + totals["better_output_tokens"]
    yield _event(
        "summary",
        output={
            "sources_compared": compared,
            "totals": totals,
            "weak_total_tokens": weak_total_tokens,
            "better_total_tokens": better_total_tokens,
            "tokens_saved": weak_total_tokens - better_total_tokens,
            "disagreements": disagreements,
            "candidate_model": candidate_meta,
        },
    )


def _empty_summary(error: str | None) -> dict:
    return {
        "sources_compared": 0,
        "totals": {"weak_input_tokens": 0, "weak_output_tokens": 0, "better_input_tokens": 0, "better_output_tokens": 0},
        "weak_total_tokens": 0,
        "better_total_tokens": 0,
        "tokens_saved": 0,
        "disagreements": [],
        "candidate_model": {"trained": False, "note": "discovery failed before scoring started"},
        "discovery_error": error,
    }
