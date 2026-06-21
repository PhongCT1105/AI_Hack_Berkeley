"""Shared comparison-pair builder used by the Terac Arena endpoint and the
degradation monitor's auto-queue step. Keeping this in one place means every
pair — human-created or auto-queued — carries the feature vectors trainer.py
needs."""
from __future__ import annotations

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.observability import get_tracer
from app.ml import model_registry, terac_store
from app.schemas.score import ScoreRequest
from app.services.pipeline import Pipeline


async def build_pair(
    pipeline: Pipeline,
    task: str,
    url_a: str,
    url_b: str,
    auto_queued_reason: str | None = None,
) -> dict:
    tracer = get_tracer()
    with tracer.start_as_current_span("captain_ddoski.terac.build_pair") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
        span.set_attribute("terac.task", task)
        span.set_attribute("terac.url_a", url_a)
        span.set_attribute("terac.url_b", url_b)
        span.set_attribute("terac.auto_queued", auto_queued_reason is not None)
        if auto_queued_reason:
            span.set_attribute("terac.auto_queued_reason", auto_queued_reason)

        a = await pipeline.score_source(ScoreRequest(url=url_a, task=task))
        b = await pipeline.score_source(ScoreRequest(url=url_b, task=task))

        pair = terac_store.add_pair({
            "task": task,
            "url_a": a.url, "url_b": b.url,
            "domain_a": a.domain, "domain_b": b.domain,
            "score_a": a.trust_score, "score_b": b.trust_score,
            "reasons_a": [v.detail for v in a.verdicts[:4]],
            "reasons_b": [v.detail for v in b.verdicts[:4]],
            "features_a": model_registry.feature_vector(a.source_features),
            "features_b": model_registry.feature_vector(b.source_features),
            "auto_queued_reason": auto_queued_reason,
        })
        span.set_attribute("terac.pair_id", pair.get("pair_id", ""))
        span.set_attribute("terac.score_a", a.trust_score)
        span.set_attribute("terac.score_b", b.trust_score)
        return pair
