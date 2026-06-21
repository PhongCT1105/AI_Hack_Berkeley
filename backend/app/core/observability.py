"""Observability: Sentry (errors) + Arize AX or Phoenix (traces/evals).

All three are OPTIONAL and import-guarded. With no keys / missing packages we
return a no-op tracer so pipeline code can call
`with tracer.start_as_current_span(...)` unconditionally. Arize AX
(arize-otel / ARIZE_SPACE_ID + ARIZE_API_KEY) is the preferred tracer when
configured; it falls back to Phoenix (phoenix.otel / PHOENIX_API_KEY), then
the no-op tracer. Only one tracer provider is ever registered at a time.
"""
from __future__ import annotations

import contextlib
import logging

from app.core.config import settings

logger = logging.getLogger("captain_ddoski.observability")

_initialized = False
_tracer = None


class _NoOpSpan:
    def set_attribute(self, *_args, **_kwargs):
        pass

    def record_exception(self, *_args, **_kwargs):
        pass


class _NoOpTracer:
    @contextlib.contextmanager
    def start_as_current_span(self, _name, *_args, **_kwargs):
        yield _NoOpSpan()


def init_observability() -> None:
    """Call once at startup (FastAPI lifespan). Safe to call with no keys."""
    global _initialized, _tracer
    if _initialized:
        return
    _initialized = True

    # --- Sentry: five lines, only if a DSN is configured ---
    if settings.has_sentry:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=1.0)
            logger.info("Sentry initialized")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Sentry init failed, continuing without it: %s", exc)

    # --- Tracing: Arize AX preferred, Phoenix as fallback. Both register a
    # global OTel tracer provider, so only attempt one. ---
    tracer_provider = None
    if settings.has_arize:
        try:
            from arize.otel import register

            tracer_provider = register(
                space_id=settings.arize_space_id,
                api_key=settings.arize_api_key,
                project_name=settings.arize_project_name,
                # Picks up any installed OpenInference instrumentor (anthropic) by
                # entry point. Generic OTel instrumentors (httpx, fastapi) are NOT
                # covered by this flag and are instrumented explicitly below.
                auto_instrument=True,
            )
            _tracer = tracer_provider.get_tracer("captain_ddoski.pipeline")
            logger.info("Arize AX tracing initialized (project=%s)", settings.arize_project_name)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Arize init failed, continuing without it: %s", exc)
    elif settings.has_phoenix:
        try:
            import os

            # phoenix.otel.register reads these env vars.
            os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", settings.phoenix_collector_endpoint)
            if settings.phoenix_api_key:
                os.environ.setdefault("PHOENIX_API_KEY", settings.phoenix_api_key)

            from phoenix.otel import register

            tracer_provider = register(
                project_name="Captain Ddoski",
                auto_instrument=True,  # picks up anthropic instrumentation if installed
            )
            _tracer = tracer_provider.get_tracer("captain_ddoski.pipeline")
            logger.info("Phoenix tracing initialized")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Phoenix init failed, continuing without it: %s", exc)

    # --- Generic OTel instrumentation: client-side httpx (propagates W3C
    # trace context so the mcp_server.py -> FastAPI hop joins one trace) and
    # server-side FastAPI (extracts that context on the inbound request). Both
    # are no-ops with an unset tracer provider, but only worth the import cost
    # when a real provider is registered. ---
    if tracer_provider is not None:
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("httpx OTel instrumentation failed: %s", exc)


def instrument_fastapi_app(app) -> None:
    """Call once on the FastAPI app instance so inbound request context
    (e.g. a traceparent header forwarded by mcp_server.py) becomes the parent
    of the pipeline spans created inside the request, joining them into one
    trace in Arize. Safe to call even with no tracer configured."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("FastAPI OTel instrumentation failed: %s", exc)


def get_tracer():
    """Return a real OTel tracer when Arize/Phoenix is live, else a no-op shim."""
    return _tracer if _tracer is not None else _NoOpTracer()


def capture_exception(exc: Exception) -> None:
    """Forward to Sentry if available; always also log."""
    logger.exception("captured exception", exc_info=exc)
    if settings.has_sentry:
        with contextlib.suppress(Exception):
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
