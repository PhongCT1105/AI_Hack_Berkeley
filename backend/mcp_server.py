"""AgentShield MCP server (FastMCP, stdio).

Exposes the credibility engine as a single MCP tool so any MCP-capable agent
(Claude Code, Cursor, a FetchAI uAgent bridge) can validate a source. The tool
is a thin client over the FastAPI engine, keeping the pipeline (cache,
observability, scoring) as the single source of truth.

Run:   python mcp_server.py
Register (Claude Code):  claude mcp add agentshield -- python /abs/path/backend/mcp_server.py
Requires the FastAPI engine running:  uvicorn app.main:app --reload

Env:   AGENTSHIELD_API_URL (default http://localhost:8000)
"""
from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

API_URL = os.environ.get("AGENTSHIELD_API_URL", "http://localhost:8000")

mcp = FastMCP("agentshield_mcp")


class ScoreSourceInput(BaseModel):
    url: str = Field(..., description="The finance web source URL to evaluate")
    task: str = Field(..., description="What you intend to do with this source")


@mcp.tool(
    name="agentshield_score_source",
    description=(
        "Validate the credibility of a FINANCE web source before trusting it. "
        "Returns a trust score (0-100), a USE/CAUTION/AVOID recommendation, risk "
        "tags, per-dimension verdicts, extracted claims with evidence, and a "
        "compressed credibility capsule. Use this before relying on any web source "
        "for a finance task."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
)
async def agentshield_score_source(params: ScoreSourceInput) -> dict:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_URL}/api/score-source",
                json={"url": params.url, "task": params.task},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"AgentShield engine unreachable at {API_URL}. Start it with: "
            f"cd backend && uvicorn app.main:app --reload"
        ) from exc


if __name__ == "__main__":
    mcp.run()  # stdio transport
