"""Captain Ddoski FastAPI entrypoint.

Credibility infrastructure for AI agents (finance domain). Boots and serves a
valid heuristic verdict with zero API keys; every integration degrades gracefully.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import comparison, compress
from app.api.crawl import router as crawl_router
from app.api import demo, history, monitor, research, score, system_health, terac, workflow
from app.core.cache import Cache
from app.core.config import settings
from app.core.observability import init_observability, instrument_fastapi_app
from app.ml import citation_model_registry, model_registry
from app.services.collector import Collector
from app.services.extractor import Extractor
from app.services.history import ScoreHistory
from app.services.pipeline import Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    # Must run after init_observability() registers the tracer provider —
    # FastAPIInstrumentor captures the current global provider eagerly.
    instrument_fastapi_app(app)
    cache = Cache()
    app.state.cache = cache
    app.state.score_history = ScoreHistory(settings.score_history_path)
    app.state.pipeline = Pipeline(Collector(), Extractor(), cache)
    model_registry.load()  # silent if no trained model exists (UI-only Terac build)
    citation_model_registry.load()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compress.router)
app.include_router(crawl_router)
app.include_router(score.router)
app.include_router(terac.router)
app.include_router(history.router)
app.include_router(demo.router)
app.include_router(research.router)
app.include_router(monitor.router)
app.include_router(workflow.router)
app.include_router(comparison.router)
app.include_router(system_health.router)


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
            "firecrawl": settings.has_firecrawl,
            "research_discovery": settings.has_firecrawl,
            "redis": settings.has_redis,
            "sentry": settings.has_sentry,
            "phoenix": settings.has_phoenix,
            "arize": settings.has_arize,
            "terac": settings.has_terac,
            "model_loaded": model_registry.is_loaded(),
            "citation_classifier_loaded": citation_model_registry.is_loaded(),
        },
        "cache_backend": getattr(getattr(app.state, "cache", None), "backend", "memory"),
    }
