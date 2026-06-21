"""Push seam to the real Terac annotation API.

LOCAL-ONLY THIS BUILD. The local terac_store stays authoritative for /pairs,
/pairs/next, and /labels — this module is a best-effort mirror so a queued
pair also becomes a real annotation task once a teammate has the actual Terac
REST contract (see Terac.docx / the $250 hackathon credit). Until
TERAC_API_KEY and TERAC_API_URL are both set, push_pair() is a no-op and the
Arena screen behaves exactly as before.

# TODO(terac): once the real endpoint path is known, POST `pair` (or a mapped
# subset of it) to f"{settings.terac_api_url}/<real-path>" with the API key as
# a bearer/header credential.
"""
from __future__ import annotations

import logging

import httpx
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.config import settings
from app.core.observability import get_tracer

logger = logging.getLogger("captain_ddoski.terac_client")


def push_pair(pair: dict) -> bool:
    """Best-effort mirror of a comparison pair to Terac. Never raises.

    Traced as its own TOOL span (an outbound call to the real Terac API) so a
    silently-failing push — which previously only showed up as a log line —
    is visible in Arize next to the pair/build spans that produced it.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("captain_ddoski.terac.push_pair") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
        span.set_attribute("terac.pair_id", pair.get("pair_id", ""))
        span.set_attribute("terac.configured", bool(settings.has_terac and settings.terac_api_url))

        if not (settings.has_terac and settings.terac_api_url):
            span.set_attribute("terac.pushed", False)
            return False
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{settings.terac_api_url}/tasks",
                    headers={"Authorization": f"Bearer {settings.terac_api_key}"},
                    json=pair,
                )
                resp.raise_for_status()
            logger.info("Pushed pair %s to Terac", pair.get("pair_id"))
            span.set_attribute("terac.pushed", True)
            return True
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Terac push failed for pair %s, staying local-only: %s", pair.get("pair_id"), exc)
            span.set_attribute("terac.pushed", False)
            span.record_exception(exc)
            return False
