"""Pipeline orchestrator — runs collector -> extractor -> features -> ranker
-> capsule, each in its own trace span, and assembles the ScoreResponse.

Per-stage failures become `degradations` entries rather than 500s wherever
possible, so a calling agent always gets a usable verdict.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Callable

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.cache import Cache
from app.core.config import settings
from app.core.observability import capture_exception, get_tracer
from app.ml import citation_model_registry
from app.schemas.score import (
    Claim,
    CitationAssessment,
    EvidenceCapsule,
    FeatureContribution,
    Recommendation,
    ScoreRequest,
    ScoreResponse,
    SourceFeatures,
    Verdict,
)
from app.services import features as features_mod
from app.services import ranker, reputation, terac_auto_launch
from app.services.capsule import compress
from app.services.collector import Collector
from app.ml.citation_classifier import inference_text
from app.services.extractor import Extractor


class Pipeline:
    def __init__(self, collector: Collector, extractor: Extractor, cache: Cache) -> None:
        self.collector = collector
        self.extractor = extractor
        self.cache = cache

    async def score_source(
        self, req: ScoreRequest, on_step: Callable[[dict], None] | None = None
    ) -> ScoreResponse:
        """on_step is an optional sink for internal-stage events (collector,
        extractor + TTC compression, ranker, citation classifier, capsule
        compression) — every production caller omits it and behavior is
        unchanged. app/services/workflow_demo.py passes one so the showcase
        transcript can show these normally-internal stages as their own
        tool calls instead of one opaque captain_america_score_source call."""
        def emit(event: dict) -> None:
            if on_step is not None:
                on_step(event)

        tracer = get_tracer()
        trace_id = uuid.uuid4().hex
        started = time.perf_counter()
        degradations: list[str] = []

        cache_key = "score:v2:" + hashlib.sha256(
            f"{req.url}|{req.task}|{citation_model_registry.cache_fingerprint()}".encode()
        ).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached:
            cached["trace_id"] = trace_id
            cached["degradations"] = list(cached.get("degradations", [])) + ["served from cache"]
            emit({"type": "tool_result", "tool": "cache_lookup", "output": {"hit": True}})
            return ScoreResponse(**cached)

        with tracer.start_as_current_span("captain_america.score_source") as root:
            # OpenInference span kind: this is the TOOL boundary an agent calls
            # (directly or via the MCP server) before trusting a URL — Arize
            # groups/filters on this so the whole pipeline shows up as one
            # tool invocation rather than an unlabeled trace.
            root.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
            root.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps({"url": req.url, "task": req.task}))
            root.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
            root.set_attribute("captain_america.url", req.url)
            root.set_attribute("captain_america.task", req.task)

            # Stage 1: collect
            emit({"type": "tool_call", "tool": "firecrawl_collect", "input": {"url": req.url}})
            with tracer.start_as_current_span("stage.collector") as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
                collected = await self.collector.collect(req.url)
                span.set_attribute("collector.mode", collected.mode)
                if collected.mode != "firecrawl":
                    degradations.append(f"collector: {collected.mode}")
                if collected.error:
                    degradations.append(f"collector error: {collected.error}")
            emit({
                "type": "tool_result",
                "tool": "firecrawl_collect",
                "output": {
                    "final_url": collected.final_url,
                    "mode": collected.mode,
                    "title": collected.title,
                    "text_chars": len(collected.text or ""),
                    "error": collected.error,
                },
            })

            # Stage 2: extract
            emit({"type": "tool_call", "tool": "claude_extract_claims", "input": {"url": collected.final_url, "task": req.task}})
            with tracer.start_as_current_span("stage.extractor") as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
                extracted = await self.extractor.extract(collected, req.task)
                span.set_attribute("extractor.mode", extracted.mode)
                if extracted.mode != "claude":
                    degradations.append(f"extractor: {extracted.mode}")
            emit({
                "type": "tool_result",
                "tool": "claude_extract_claims",
                "output": {
                    "mode": extracted.mode,
                    "has_author": extracted.has_author,
                    "has_citations": extracted.has_citations,
                    "citation_count": extracted.citation_count,
                    "claims_found": len(extracted.claims),
                },
            })
            if extracted.compression:
                emit({
                    "type": "tool_call",
                    "tool": "ttc_compress_prompt",
                    "input": {"page_chars": extracted.compression.get("page_chars_sent"), "model": settings.ttc_compression_model},
                })
                emit({"type": "tool_result", "tool": "ttc_compress_prompt", "output": extracted.compression})

            # Reputation + features
            with tracer.start_as_current_span("stage.features") as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
                rep, listed, domain = await reputation.lookup(collected.final_url, self.cache)
                feats: SourceFeatures = features_mod.build_features(collected, extracted, rep, listed)

            root.set_attribute("captain_america.domain", domain)

            # Stage 4: rank
            emit({"type": "tool_call", "tool": "credibility_ranker", "input": {"domain": domain}})
            with tracer.start_as_current_span("stage.ranker") as span:
                # EVALUATOR, not CHAIN: this is the score/confidence Arize
                # watches per call, and that degradation.py later compares
                # against a baseline window to decide whether to re-queue
                # Terac annotation and retrain.
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.EVALUATOR.value)
                trust_score, contributions, verdicts, risk_tags, scorer_mode = ranker.score(feats)
                recommendation = ranker.recommend(trust_score)
                confidence = ranker.confidence(trust_score)
                span.set_attribute("ranker.trust_score", trust_score)
                span.set_attribute("ranker.scorer_mode", scorer_mode)
                span.set_attribute("ranker.confidence", confidence)
                span.set_attribute("ranker.risk_tag_count", len(risk_tags))
                if scorer_mode == "heuristic":
                    degradations.append("ranker: heuristic (no Terac-trained model)")
            emit({
                "type": "tool_result",
                "tool": "credibility_ranker",
                "output": {"trust_score": trust_score, "scorer_mode": scorer_mode, "confidence": confidence, "risk_tags": risk_tags},
            })

            # Stage 4b: citation gate. This can only downgrade a source that
            # otherwise qualified for citation; it never upgrades weak sources.
            emit({"type": "tool_call", "tool": "citation_usability_classifier", "input": {"domain": domain, "threshold": settings.citation_model_min_probability}})
            with tracer.start_as_current_span("stage.citation_classifier") as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.EVALUATOR.value)
                document = inference_text(
                    task=req.task,
                    title=collected.title,
                    url=collected.final_url,
                    author=extracted.author_name,
                    claims=extracted.claims,
                )
                prediction = citation_model_registry.assess(
                    document, settings.citation_model_min_probability
                )
                citation_assessment = CitationAssessment(**prediction.__dict__)
                span.set_attribute("citation_classifier.available", citation_assessment.available)
                if citation_assessment.usable_probability is not None:
                    span.set_attribute(
                        "citation_classifier.usable_probability",
                        citation_assessment.usable_probability,
                    )
                if citation_assessment.error:
                    degradations.append(f"citation classifier: {citation_assessment.error}")
                elif not citation_assessment.available:
                    degradations.append("citation classifier: unavailable")
                elif citation_assessment.eligible is False:
                    contributions.append(FeatureContribution(
                        feature="citation_classifier",
                        value=citation_assessment.usable_probability,
                        points=0,
                    ))
                    verdicts.append(Verdict(
                        dimension="citation-usability",
                        passed=False,
                        detail=(
                            "Citation classifier confidence "
                            f"{citation_assessment.usable_probability:.2f} is below the "
                            f"required {citation_assessment.threshold:.2f}"
                        ),
                        weight=20,
                    ))
                    risk_tags.append("citation classifier rejected")
                    if recommendation == Recommendation.USE:
                        recommendation = Recommendation.CAUTION
                else:
                    contributions.append(FeatureContribution(
                        feature="citation_classifier",
                        value=citation_assessment.usable_probability,
                        points=0,
                    ))
                    verdicts.append(Verdict(
                        dimension="citation-usability",
                        passed=True,
                        detail=(
                            "Citation classifier confidence "
                            f"{citation_assessment.usable_probability:.2f} meets the "
                            f"required {citation_assessment.threshold:.2f}"
                        ),
                        weight=20,
                    ))

            emit({
                "type": "tool_result",
                "tool": "citation_usability_classifier",
                "output": {
                    "available": citation_assessment.available,
                    "usable_probability": citation_assessment.usable_probability,
                    "eligible": citation_assessment.eligible,
                },
            })

            top_reasons = [c.detail for c in sorted(verdicts, key=lambda v: -v.weight)[:5]]

            # Stage 5: compress
            emit({"type": "tool_call", "tool": "finance_capsule_compress", "input": {"token_budget": settings.capsule_token_budget}})
            with tracer.start_as_current_span("stage.capsule") as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
                try:
                    capsule: EvidenceCapsule = await compress(collected, extracted, feats, top_reasons)
                except Exception as exc:
                    capture_exception(exc)
                    capsule = EvidenceCapsule(
                        compressed_text=(collected.title or req.url)[:400],
                        key_reasons=top_reasons,
                        method="extractive_fallback",
                    )
                    degradations.append("capsule: minimal fallback")
                span.set_attribute("capsule.method", capsule.method)
                if capsule.method != "finance_credibility":
                    degradations.append(f"capsule: {capsule.method}")
            emit({
                "type": "tool_result",
                "tool": "finance_capsule_compress",
                "output": {
                    "method": capsule.method,
                    "tokens_before": capsule.token_estimate_before,
                    "tokens_after": capsule.token_estimate_after,
                    "compressed_text": capsule.compressed_text,
                },
            })

            claims = [
                Claim(
                    text=c.get("text", ""),
                    supported=bool(c.get("supported")),
                    evidence_snippet=c.get("evidence_snippet"),
                    confidence=float(c.get("confidence") or 0.5),
                )
                for c in extracted.claims
            ]

            latency_ms = int((time.perf_counter() - started) * 1000)
            response = ScoreResponse(
                url=collected.final_url,
                task=req.task,
                domain=domain,
                trust_score=trust_score,
                recommendation=recommendation,
                risk_tags=sorted(set(risk_tags)),
                verdicts=verdicts,
                claims=claims,
                citation_assessment=citation_assessment,
                evidence_capsule=capsule,
                source_features=feats,
                contributions=contributions,
                scorer_mode=scorer_mode,
                degradations=degradations,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
            root.set_attribute("captain_america.recommendation", recommendation.value)
            root.set_attribute("captain_america.trust_score", trust_score)
            root.set_attribute("ranker.confidence", confidence)
            root.set_attribute(
                SpanAttributes.OUTPUT_VALUE,
                json.dumps({
                    "trust_score": trust_score,
                    "recommendation": recommendation.value,
                    "confidence": confidence,
                    "scorer_mode": scorer_mode,
                    "risk_tags": sorted(set(risk_tags)),
                }),
            )
            root.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")

        await self.cache.set(cache_key, response.model_dump(mode="json"))
        await reputation.record_observation(domain, trust_score, self.cache)
        terac_auto_launch.fire_and_forget(self, response)
        return response
