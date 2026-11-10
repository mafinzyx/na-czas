"""Application settings, read from environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'commute.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # AI advice is optional: without a key the app uses a rule-based summary.
    anthropic_api_key: str | None = None
    advisor_model: str = "claude-opus-5-5"

    # When true, no external service is called (used by tests and for offline demos).
    offline: bool = False
    http_timeout_seconds: float = 5.0
    transit_timeout_seconds: float = 12.0
    transit_api_url: str = "https://api.transitous.org/api/v1/plan"
    # Sent to the free public services so their operators can tell who is calling.
    user_agent: str = "na-czas-commute-planner/1.0"
    # All times in the app are local to this zone (timetables arrive in UTC).
    timezone: str = "Europe/Warsaw"
    # Address search is limited to these countries (ISO codes, comma separated).
    geocode_countries: str = "pl"
    seed_demo_data: bool = True
    # Folder with the built front-end. When it exists the API serves the UI as well,
    # so the whole app can run as a single container. Unused in local development.
    static_dir: Path = BACKEND_DIR.parent / "frontend" / "dist"
    serve_frontend: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
