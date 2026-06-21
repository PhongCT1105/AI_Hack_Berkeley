"""Prompt-driven web research orchestrated by Claude tool use and Firecrawl."""
from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.schemas.research import ResearchRequest, ResearchResponse
from app.schemas.score import ScoreRequest, ScoreResponse
from app.services.llm_clients import create_anthropic_client, get_compression_stats


class ResearchAgent:
    def __init__(self, pipeline) -> None:
        self.pipeline = pipeline

    async def run(self, request: ResearchRequest) -> ResearchResponse:
        query, planner, _ = await self.plan(request.prompt)
        cap = min(request.max_sources, settings.research_max_sources)
        discovery = await self.pipeline.collector.search(query, cap)
        urls, search_mode = discovery.urls, discovery.mode
        semaphore = asyncio.Semaphore(settings.research_concurrency)

        async def score(url: str) -> ScoreResponse | None:
            async with semaphore:
                try:
                    return await self.pipeline.score_source(ScoreRequest(url=url, task=request.prompt))
                except Exception:
                    return None

        scored = [item for item in await asyncio.gather(*(score(url) for url in urls)) if item is not None]
        scored.sort(key=lambda item: item.trust_score, reverse=True)
        cited = [item for item in scored if item.recommendation.value == "USE"][:8]
        rejected = [item for item in scored if item.recommendation.value == "AVOID"][:8]
        answer, writer, _ = await self.synthesize(request.prompt, cited)
        return ResearchResponse(
            prompt=request.prompt, search_query=query, discovered_count=len(urls), inspected_count=len(scored),
            agent_mode=f"{planner} + {writer}", search_mode=search_mode, answer=answer,
            discovery_error=discovery.error,
            cited_sources=cited, rejected_sources=rejected,
        )

    async def plan(self, prompt: str) -> tuple[str, str, dict | None]:
        """Returns (search_query, planner_mode, ttc_compression_stats).
        The third element is None unless TTC_API_KEY is set — this call goes
        through the same with_compression-wrapped client as the extractor,
        so the page-planning prompt is compressed too, not just extraction."""
        if not settings.has_anthropic:
            return prompt, "deterministic planner", None
        client = create_anthropic_client()
        message = await client.messages.create(
            model=settings.anthropic_model, max_tokens=300,
            system=(
                "You are a web research planner. Use the web_search tool once with a concise "
                "current-web search query. Preserve the user's requested source mix. When they "
                "ask to compare credible and questionable material, include terms that can find "
                "both authoritative reporting and promotional, anonymous, or guaranteed-return "
                "investment claims. Do not assume every result is trustworthy."
            ),
            tools=[{"name": "web_search", "description": "Search the public web for sources.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}],
            messages=[{"role": "user", "content": prompt}],
        )
        compression = get_compression_stats(client)
        for block in message.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "web_search":
                return str(block.input.get("query") or prompt), "claude tool-use planner", compression
        return prompt, "claude planner fallback", compression

    async def synthesize(self, prompt: str, sources: list[ScoreResponse]) -> tuple[str, str, dict | None]:
        """Returns (answer, writer_mode, ttc_compression_stats) — see plan()."""
        if not sources:
            return "I could not verify a sufficient set of credible public sources for this request.", "evidence guard", None
        evidence = "\n\n".join(f"SOURCE: {s.domain}\nURL: {s.url}\nEVIDENCE: {s.evidence_capsule.compressed_text}" for s in sources[:8])
        if not settings.has_anthropic:
            return f"Validated research for: {prompt}\n\n" + "\n".join(f"• {s.domain}: {s.evidence_capsule.compressed_text}" for s in sources[:4]), "extractive synthesis", None
        client = create_anthropic_client()
        message = await client.messages.create(
            model=settings.anthropic_model, max_tokens=1000,
            system="Answer only from the supplied validated evidence. State uncertainty. Cite domains in brackets. Do not use any source not provided.",
            messages=[{"role": "user", "content": f"QUESTION: {prompt}\n\nVALIDATED EVIDENCE:\n{evidence}"}],
        )
        compression = get_compression_stats(client)
        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text").strip()
        return text or "No grounded answer was produced.", "claude grounded synthesis", compression
