"""HTTP MCP server for Captain Ddoski compression tools."""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI
from fastmcp import FastMCP

from app.core.config import settings
from app.services.prompt_compressor import CompressionConfig, PromptCompressor
from app.services.semantic_ir_compressor import SemanticIRCompressor


CompressionMethod = Literal["semantic_ir", "sentence_selector"]

mcp = FastMCP(
    name="captain_ddoski",
    instructions=(
        "Tools for compressing source context into smaller evidence capsules for "
        "AI agents. Prefer semantic_ir for structured capsules and "
        "sentence_selector for query-aware sentence reduction."
    ),
)


@mcp.tool(
    name="compress_context",
    description=(
        "Compress source or prompt context while preserving the facts needed for "
        "an agent task."
    ),
)
def compress_context(
    text: str,
    query: str | None = None,
    method: CompressionMethod = "semantic_ir",
) -> dict[str, object]:
    if method == "sentence_selector":
        result = PromptCompressor(CompressionConfig(use_llmlingua2=False)).compress(
            text,
            query=query,
        )
        original_tokens = _token_estimate(result.normalized_text)
        compressed_tokens = _token_estimate(result.compressed_text)
        preserved, missing = _preservation_items(result.compressed_text, query)
        return {
            "method": method,
            "original_text": result.original_text,
            "compressed_text": result.compressed_text,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "compression_ratio": compressed_tokens / original_tokens if original_tokens else 0.0,
            "token_savings_percent": _savings(original_tokens, compressed_tokens),
            "preservation_score": _preservation_score(preserved, missing),
            "preserved_items": preserved,
            "missing_items": missing,
            "notes": list(result.notes),
        }

    result = SemanticIRCompressor().compress(text)
    preserved, missing = _preservation_items(
        "\n".join([result.compact_language, result.reconstructed_prompt]),
        query,
    )
    return {
        "method": method,
        "original_text": result.original_text,
        "compressed_text": result.compact_language,
        "reconstructed_prompt": result.reconstructed_prompt,
        "original_tokens": result.original_token_estimate,
        "compressed_tokens": result.compact_token_estimate,
        "compression_ratio": result.compression_ratio,
        "token_savings_percent": _savings(
            result.original_token_estimate,
            result.compact_token_estimate,
        ),
        "preservation_score": _preservation_score(preserved, missing),
        "preserved_items": preserved,
        "missing_items": missing,
        "semantic_ir": asdict(result.semantic_ir),
        "notes": list(result.notes),
    }


@mcp.tool(
    name="server_status",
    description="Return basic deployment status and capability flags for Captain Ddoski.",
)
def server_status() -> dict[str, object]:
    return {
        "service": settings.app_name,
        "mcp_server": "captain_ddoski",
        "status": "ok",
        "capabilities": {
            "anthropic": settings.has_anthropic,
            "firecrawl": settings.has_firecrawl,
            "supabase": bool(settings.supabase_url and settings.supabase_key),
        },
    }


mcp_app = mcp.http_app(path="/", transport="streamable-http")
app = FastAPI(title="Captain Ddoski MCP", debug=settings.debug, lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "Captain Ddoski MCP", "status": "ok"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


def _token_estimate(text: str) -> int:
    return max(1, round(len(text) / 4))


def _savings(original_tokens: int, compressed_tokens: int) -> int:
    if original_tokens <= 0:
        return 0
    return max(0, round((1 - compressed_tokens / original_tokens) * 100))


def _preservation_items(text: str, query: str | None) -> tuple[list[str], list[str]]:
    if not query:
        return [], []
    required = [item.strip() for item in query.split(",") if item.strip()]
    lowered = text.casefold()
    preserved = [item for item in required if item.casefold() in lowered]
    missing = [item for item in required if item.casefold() not in lowered]
    return preserved, missing


def _preservation_score(preserved: list[str], missing: list[str]) -> float | None:
    total = len(preserved) + len(missing)
    if total == 0:
        return None
    return round(len(preserved) / total, 3)
