"""API routes for Browserbase crawling."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.crawl import CrawlBatchResponse, CrawlRequest
from app.services.browserbase_crawler import BrowserbaseCrawler

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


@router.post("", response_model=CrawlBatchResponse)
def crawl_urls(payload: CrawlRequest) -> CrawlBatchResponse:
    try:
        return BrowserbaseCrawler().crawl(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Browserbase crawl failed: {exc}") from exc