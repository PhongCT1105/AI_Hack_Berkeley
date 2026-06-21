"""Pipeline orchestrator — runs collector -> extractor -> features -> ranker
-> capsule, each in its own trace span, and assembles the ScoreResponse.

Per-stage failures become `degradations` entries rather than 500s wherever
possible, so a calling agent always gets a usable verdict.
"""
from __future__ import annotations

import hashlib
import time
import uuid

from app.core.cache import Cache
from app.core.observability import capture_exception, get_tracer
from app.schemas.score import (
    Claim,
    EvidenceCapsule,
    Recommendation,
    ScoreRequest,
    ScoreResponse,
    SourceFeatures,
)
from app.services import features as features_mod
from app.services import ranker, reputation
from app.services.capsule import compress
from app.services.collector import Collector
from app.services.extractor import Extractor


class Pipeline:
    def __init__(self, collector: Collector, extractor: Extractor, cache: Cache) -> None:
        self.collector = collector
        self.extractor = extractor
        self.cache = cache

    async def score_source(self, req: ScoreRequest) -> ScoreResponse:
        tracer = get_tracer()
        trace_id = uuid.uuid4().hex
        started = time.perf_counter()
        degradations: list[str] = []

        cache_key = "score:" + hashlib.sha256(f"{req.url}|{req.task}".encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached:
            cached["trace_id"] = trace_id
            cached["degradations"] = list(cached.get("degradations", [])) + ["served from cache"]
            return ScoreResponse(**cached)

        with tracer.start_as_current_span("agentshield.score_source") as root:
            root.set_attribute("agentshield.url", req.url)
            root.set_attribute("agentshield.task", req.task)

            # Stage 1: collect
            with tracer.start_as_current_span("stage.collector") as span:
                collected = await self.collector.collect(req.url)
                span.set_attribute("collector.mode", collected.mode)
                if collected.mode != "browserbase":
                    degradations.append(f"collector: {collected.mode}")
                if collected.error:
                    degradations.append(f"collector error: {collected.error}")

            # Stage 2: extract
            with tracer.start_as_current_span("stage.extractor") as span:
                extracted = await self.extractor.extract(collected, req.task)
                span.set_attribute("extractor.mode", extracted.mode)
                if extracted.mode != "claude":
                    degradations.append(f"extractor: {extracted.mode}")

            # Reputation + features
            with tracer.start_as_current_span("stage.features"):
                rep, listed, domain = await reputation.lookup(collected.final_url, self.cache)
                feats: SourceFeatures = features_mod.build_features(collected, extracted, rep, listed)

            # Stage 4: rank
            with tracer.start_as_current_span("stage.ranker") as span:
                trust_score, contributions, verdicts, risk_tags, scorer_mode = ranker.score(feats)
                recommendation = ranker.recommend(trust_score)
                span.set_attribute("ranker.trust_score", trust_score)
                span.set_attribute("ranker.scorer_mode", scorer_mode)
                if scorer_mode == "heuristic":
                    degradations.append("ranker: heuristic (no Terac-trained model)")

            top_reasons = [c.detail for c in sorted(verdicts, key=lambda v: -v.weight)[:5]]

            # Stage 5: compress
            with tracer.start_as_current_span("stage.capsule") as span:
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
                if capsule.method != "claude":
                    degradations.append(f"capsule: {capsule.method}")

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
                evidence_capsule=capsule,
                source_features=feats,
                contributions=contributions,
                scorer_mode=scorer_mode,
                degradations=degradations,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
            root.set_attribute("agentshield.recommendation", recommendation.value)

        await self.cache.set(cache_key, response.model_dump(mode="json"))
        await reputation.record_observation(domain, trust_score, self.cache)
        return response
