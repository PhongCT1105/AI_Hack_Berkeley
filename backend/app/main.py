"""AgentShield FastAPI entrypoint.

Credibility infrastructure for AI agents (finance domain). Boots and serves a
valid heuristic verdict with zero API keys; every integration degrades gracefully.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.crawl import router as crawl_router
from app.api import history, score, terac
from app.core.cache import Cache
from app.core.config import settings
from app.core.observability import init_observability
from app.ml import model_registry
from app.services.collector import Collector
from app.services.extractor import Extractor
from app.services.history import ScoreHistory
from app.services.pipeline import Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    cache = Cache()
    app.state.cache = cache
    app.state.score_history = ScoreHistory(settings.score_history_path)
    app.state.pipeline = Pipeline(Collector(), Extractor(), cache)
    model_registry.load()  # silent if no trained model exists (UI-only Terac build)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_router)
app.include_router(score.router)
app.include_router(terac.router)
app.include_router(history.router)


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok"}


@app.get("/api/health")
def health():
    """Reports which integrations are live — great for demoing graceful degradation."""
    return {
        "status": "healthy",
        "capabilities": {
            "anthropic": settings.has_anthropic,
            "browserbase": settings.has_browserbase,
            "redis": settings.has_redis,
            "sentry": settings.has_sentry,
            "phoenix": settings.has_phoenix,
            "terac": settings.has_terac,
            "model_loaded": model_registry.is_loaded(),
        },
        "cache_backend": getattr(getattr(app.state, "cache", None), "backend", "memory"),
    }


@app.get("/api/sentry-debug")
def sentry_debug():
    """Raise a test exception so Sentry setup can be verified in development."""
    if not settings.debug:
        return {"enabled": False, "reason": "Only available when DEBUG=true"}
    raise RuntimeError("AgentShield Sentry debug event")
