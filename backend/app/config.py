"""App settings, read from environment variables (or a .env file in dev).

Defaults match docker-compose.yml, so local dev works with no .env at all.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://vyayam:vyayam@localhost:5433/vyayam"
    environment: str = "development"
    # Built React app. Served by FastAPI when it exists (after `npm run build`).
    frontend_dist: Path = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    # Auth
    session_cookie_name: str = "vy_session"
    session_ttl_days: int = 30
    cookie_secure: bool = True  # HTTPS-only cookie; set COOKIE_SECURE=false in a local .env
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 20
    login_window_seconds: int = 15 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
