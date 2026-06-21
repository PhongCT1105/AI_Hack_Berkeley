"""Application settings, loaded from environment / .env file.

Every external integration is OPTIONAL. The app must boot and return a valid
heuristic ScoreResponse with zero keys set. Each service checks a `has_*`
capability flag (never a raw key) and falls back to an in-process path.
"""
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    app_name: str = "Captain America API"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_environment(cls, value: object) -> object:
        """Accept conventional deployment names in addition to boolean strings."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"development", "dev", "debug"}:
                return True
            if normalized in {"production", "prod", "release"}:
                return False
        return value

    # Comma-separated list of allowed CORS origins (frontend dev server, etc.)
    cors_origins: str = "http://localhost:3000"

    # --- External services (all optional; absence triggers graceful fallback) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"

    firecrawl_api_key: str | None = None
    firecrawl_api_url: str = "https://api.firecrawl.dev"
    firecrawl_page_timeout_ms: int = 60000
    firecrawl_max_text_chars: int = 12000
    research_max_sources: int = 100
    research_concurrency: int = 6

    redis_url: str | None = None              # absent -> in-memory cache

    sentry_dsn: str | None = None             # absent -> Sentry disabled
    phoenix_collector_endpoint: str | None = None
    phoenix_api_key: str | None = None        # absent -> tracing no-op

    terac_api_key: str | None = None          # absent -> local-only stub arena

    # Supabase labeled-task export.  Use the publishable/anon key only when RLS
    # permits the intended read; otherwise use a server-side service-role key.
    # Keep this key in backend/.env, never in the frontend.
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_table: str = "tasks"
    supabase_label_column: str = "can_ai_cite"
    # Labels live in a separate annotations table (many rows per task, majority
    # vote needed) rather than inline on the task row.
    supabase_tasks_table: str = "source_claim_tasks"
    supabase_annotations_table: str = "simple_claim_annotations"
    supabase_join_key: str = "task_id"

    # --- Tunables ---
    cache_ttl_seconds: int = 86400
    capsule_token_budget: int = 220
    ml_model_path: str = "data/terac_model.joblib"
    citation_model_path: str = "data/sourceguard_citation_classifier.joblib"
    # Match the trained classifier's decision boundary. Raise only after
    # calibration on a held-out deployment-like citation set.
    citation_model_min_probability: float = Field(default=0.50, ge=0.5, le=0.95)
    supabase_export_path: str = "data/supabase_labeled_tasks.jsonl"
    terac_store_path: str = "data/terac_store.json"
    score_history_path: str = "data/captain_america_history.json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Capability flags: services check these, never the raw keys ---
    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_firecrawl(self) -> bool:
        return bool(self.firecrawl_api_key)

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
