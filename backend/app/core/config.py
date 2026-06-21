"""Application settings, loaded from environment / .env file.

Every external integration is OPTIONAL. The app must boot and return a valid
heuristic ScoreResponse with zero keys set. Each service checks a `has_*`
capability flag (never a raw key) and falls back to an in-process path.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    app_name: str = "AgentShield API"
    debug: bool = True

    # Comma-separated list of allowed CORS origins (frontend dev server, etc.)
    cors_origins: str = "http://localhost:3000"

    # --- External services (all optional; absence triggers graceful fallback) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"

    browserbase_api_key: str | None = None
    browserbase_project_id: str | None = None
    browserbase_page_timeout_ms: int = 60000
    browserbase_max_text_chars: int = 12000

    redis_url: str | None = None              # absent -> in-memory cache

    sentry_dsn: str | None = None             # absent -> Sentry disabled
    sentry_traces_sample_rate: float = 1.0
    sentry_send_default_pii: bool = False
    phoenix_collector_endpoint: str | None = None
    phoenix_api_key: str | None = None        # absent -> tracing no-op

    terac_api_key: str | None = None          # absent -> local-only stub arena

    # --- Tunables ---
    cache_ttl_seconds: int = 86400
    capsule_token_budget: int = 220
    ml_model_path: str = "data/terac_model.joblib"
    terac_store_path: str = "data/terac_store.json"
    score_history_path: str = "data/score_history.json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Capability flags: services check these, never the raw keys ---
    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_browserbase(self) -> bool:
        return bool(self.browserbase_api_key and self.browserbase_project_id)

    @property
    def has_redis(self) -> bool:
        return bool(self.redis_url)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)

    @property
    def has_phoenix(self) -> bool:
        return bool(self.phoenix_collector_endpoint)

    @property
    def has_terac(self) -> bool:
        return bool(self.terac_api_key)


settings = Settings()
