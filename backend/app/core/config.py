"""Application settings, loaded from environment / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    app_name: str = "AIHackBerk API"
    debug: bool = True

    # Comma-separated list of allowed CORS origins (frontend dev server, etc.)
    cors_origins: str = "http://localhost:3000"

    # Browserbase session settings.
    browserbase_api_key: str | None = None
    browserbase_project_id: str | None = None
    browserbase_page_timeout_ms: int = 60000
    browserbase_max_text_chars: int = 12000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
