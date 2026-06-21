"""FastAPI entrypoint. Minimal scaffold — add routers under app/api/ as the app grows."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compress
from app.core.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compress.router)


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}
