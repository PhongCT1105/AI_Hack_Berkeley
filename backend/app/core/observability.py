"""Observability: Sentry (errors) + Arize Phoenix (traces/evals).

Both are OPTIONAL and import-guarded. With no keys / missing packages we return
a no-op tracer so pipeline code can call `with tracer.start_as_current_span(...)`
unconditionally. This is the Phoenix product (phoenix.otel / PHOENIX_API_KEY),
NOT Arize AX.
"""
from __future__ import annotations

import contextlib
import logging

from app.core.config import settings

logger = logging.getLogger("agentshield.observability")

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
    """Initialize Sentry before FastAPI app creation; Phoenix can follow at startup."""
    global _initialized, _tracer
    if _initialized:
        return
    _initialized = True

    # --- Sentry: only if a DSN is configured ---
    if settings.has_sentry:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                send_default_pii=settings.sentry_send_default_pii,
            )
            logger.info("Sentry initialized")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Sentry init failed, continuing without it: %s", exc)

    # --- Phoenix tracing: only if a collector endpoint is configured ---
    if settings.has_phoenix:
        try:
            import os

            # phoenix.otel.register reads these env vars.
            os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", settings.phoenix_collector_endpoint)
            if settings.phoenix_api_key:
                os.environ.setdefault("PHOENIX_API_KEY", settings.phoenix_api_key)

            from phoenix.otel import register

            tracer_provider = register(
                project_name="AgentShield",
                auto_instrument=True,  # picks up anthropic + httpx instrumentation if installed
            )
            _tracer = tracer_provider.get_tracer("agentshield.pipeline")
            logger.info("Phoenix tracing initialized")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Phoenix init failed, continuing without it: %s", exc)


def get_tracer():
    """Return a real OTel tracer when Phoenix is live, else a no-op shim."""
    return _tracer if _tracer is not None else _NoOpTracer()


def capture_exception(exc: Exception) -> None:
    """Forward to Sentry if available; always also log."""
    logger.exception("captured exception", exc_info=exc)
    if settings.has_sentry:
        with contextlib.suppress(Exception):
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
