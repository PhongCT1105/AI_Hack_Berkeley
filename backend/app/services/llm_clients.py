"""Provider clients with optional, transparent prompt compression."""
from __future__ import annotations

from typing import Any

from opentelemetry import trace

from app.core.config import settings


def get_compression_stats(client: Any) -> dict[str, Any] | None:
    """Return TTC's per-client compression stats as a plain dict, or None
    when TTC isn't wired in — ``client.compression`` only exists on the
    wrapper `with_compression()` returns, never on a bare Anthropic client.
    Used both for the Arize span attributes below and for surfacing the
    compression step explicitly in the workflow showcase transcript."""
    stats = getattr(client, "compression", None)
    if stats is None:
        return None
    return {
        "compression_ratio": stats.ratio,
        "total_tokens_saved": stats.total_tokens_saved,
        "total_input_tokens": stats.total_input_tokens,
        "total_output_tokens": stats.total_output_tokens,
        "calls": stats.calls,
    }


def record_compression_stats(client: Any, span: Any | None = None) -> None:
    """Attach TTC's per-client compression stats to the current (or given) span."""
    stats = get_compression_stats(client)
    if stats is None:
        return
    target = span or trace.get_current_span()
    target.set_attribute("ttc.compression_ratio", stats["compression_ratio"])
    target.set_attribute("ttc.total_tokens_saved", stats["total_tokens_saved"])
    target.set_attribute("ttc.total_input_tokens", stats["total_input_tokens"])
    target.set_attribute("ttc.total_output_tokens", stats["total_output_tokens"])
    target.set_attribute("ttc.calls", stats["calls"])


def create_anthropic_client() -> Any:
    """Return the existing async Anthropic client, optionally wrapped by TTC.

    The wrapper intercepts ``messages.create``. Call sites keep their existing
    Claude request shape and work normally when ``TTC_API_KEY`` is not set.
    """

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    if not settings.has_ttc:
        return client

    from thetokencompany.anthropic import with_compression

    return with_compression(
        client,
        compression_api_key=settings.ttc_api_key,
        model=settings.ttc_compression_model,
        aggressiveness=settings.ttc_aggressiveness,
        app_id=settings.ttc_app_id,
    )
