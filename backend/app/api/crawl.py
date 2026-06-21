"""API routes for Firecrawl-backed crawling with an HTTP fallback."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.crawl import CrawlBatchResponse, CrawlRequest
from app.services.crawler import Crawler

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


@router.post("", response_model=CrawlBatchResponse)
async def crawl_urls(payload: CrawlRequest) -> CrawlBatchResponse:
    try:
        return await Crawler().crawl(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Crawl failed: {exc}") from exc
