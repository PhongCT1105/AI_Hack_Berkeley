"""Captain America MCP server (FastMCP, stdio).

Exposes the credibility engine as a single MCP tool so any MCP-capable agent
(Claude Code, Cursor, a FetchAI uAgent bridge) can validate a source. The tool
is a thin client over the FastAPI engine, keeping the pipeline (cache,
observability, scoring) as the single source of truth.

Run:   python mcp_server.py
Register (Claude Code):  claude mcp add captain-america -- python /abs/path/backend/mcp_server.py
Requires the FastAPI engine running:  uvicorn app.main:app --reload

Env:   CAPTAIN_AMERICA_API_URL (default http://localhost:8000)
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from pydantic import Field

# AGENTSHIELD_* remains a migration fallback for existing local MCP configs.
API_URL = os.environ.get("CAPTAIN_AMERICA_API_URL") or os.environ.get("AGENTSHIELD_API_URL", "http://localhost:8000")

logging.basicConfig(
    level=os.environ.get("CAPTAIN_AMERICA_MCP_LOG_LEVEL") or os.environ.get("AGENTSHIELD_MCP_LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s [captain_america.mcp] %(message)s",
)
logger = logging.getLogger("captain_america.mcp")

mcp = FastMCP("captain_america_mcp")


@mcp.tool(
    name="captain_america_demo_sources",
    description=(
        "Return deterministic finance source URLs for testing Captain America MCP calls. "
        "Use one trusted and one risky URL when you need a quick demo."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def captain_america_demo_sources() -> dict[str, Any]:
    logger.info("tool=captain_america_demo_sources")
    return {
        "task": "Research low-risk retirement investments for a consumer-facing finance agent.",
        "trusted": "https://www.sec.gov/investor/pubs/assetallocation.htm",
        "risky": "https://best-stock-picks-now.com/double-your-money",
    }


@mcp.tool(
    name="captain_america_score_source",
    description=(
        "Validate the credibility of a FINANCE web source before trusting it. "
        "Returns a trust score (0-100), a USE/CAUTION/AVOID recommendation, risk "
        "tags, per-dimension verdicts, extracted claims with evidence, and a "
        "compressed credibility capsule. Use this before relying on any web source "
        "for a finance task."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
)
async def captain_america_score_source(
    url: Annotated[str, Field(description="The finance web source URL to evaluate")],
    task: Annotated[str, Field(description="What you intend to do with this source")],
) -> dict:
    logger.info("tool=captain_america_score_source url=%s task=%s", url, task)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_URL}/api/score-source",
                headers={"X-Captain-America-Caller": "claude-mcp"},
                json={"url": url, "task": task},
            )
            resp.raise_for_status()
            payload = resp.json()
            logger.info(
                "result trace_id=%s domain=%s score=%s recommendation=%s risk_tags=%s",
                payload.get("trace_id"),
                payload.get("domain"),
                payload.get("trust_score"),
                payload.get("recommendation"),
                payload.get("risk_tags"),
            )
            return payload
    except httpx.ConnectError as exc:
        logger.exception("engine unreachable api_url=%s", API_URL)
        raise RuntimeError(
            f"Captain America engine unreachable at {API_URL}. Start it with: "
            f"cd backend && uvicorn app.main:app --reload"
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("engine returned error status=%s body=%s", exc.response.status_code, exc.response.text)
        raise


if __name__ == "__main__":
    logger.info("starting Captain America MCP server api_url=%s", API_URL)
    mcp.run()  # stdio transport
