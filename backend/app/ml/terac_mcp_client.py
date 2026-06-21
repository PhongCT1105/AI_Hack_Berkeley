"""MCP client for the real Terac org endpoint.

TERAC_API_URL (https://terac.com/api/mcp) speaks MCP — JSON-RPC tool calls
over streamable HTTP — not a plain REST API, so this opens a short-lived MCP
session per call rather than a simple httpx.post. Used by
app/services/terac_auto_launch.py to create and launch real, paid
opportunities.
"""
from __future__ import annotations

import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.config import settings
from app.core.observability import get_tracer

logger = logging.getLogger("captain_ddoski.terac_mcp_client")


class TeracMCPError(RuntimeError):
    pass


async def call_tool(name: str, arguments: dict) -> dict:
    """Call a Terac MCP tool and return its parsed JSON result.

    Raises TeracMCPError on any failure (unconfigured, transport, or a
    non-JSON / error result) — callers in the auto-launch pipeline catch this
    and downgrade to a logged skip rather than ever 500ing a score request.
    """
    if not (settings.terac_api_url and settings.terac_api_key):
        raise TeracMCPError("TERAC_API_URL / TERAC_API_KEY not configured")

    tracer = get_tracer()
    with tracer.start_as_current_span(f"captain_ddoski.terac_mcp.{name}") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
        span.set_attribute("terac_mcp.tool", name)
        span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(arguments, default=str))
        try:
            async with streamablehttp_client(
                settings.terac_api_url, headers={"x-api-key": settings.terac_api_key}
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
        except Exception as exc:
            span.record_exception(exc)
            raise TeracMCPError(f"Terac MCP call to {name} failed: {exc}") from exc

        text = "".join(getattr(block, "text", "") for block in result.content)
        if result.isError:
            span.set_attribute("terac_mcp.error", True)
            raise TeracMCPError(f"Terac MCP tool {name} returned an error: {text[:500]}")

        parsed = _parse_result(text)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, text[:2000])
        return parsed


def _parse_result(text: str) -> dict:
    """Tool results are usually JSON; terac_get_context returns markdown, so
    fall back to the raw text under a single key rather than raising."""
    try:
        decoded = json.loads(text)
        if isinstance(decoded, dict):
            return decoded
    except json.JSONDecodeError:
        pass
    return {"raw": text}
