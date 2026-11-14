"""App settings, read from environment variables (or a .env file in dev).

Defaults match docker-compose.yml, so local dev works with no .env at all.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://vyayam:vyayam@localhost:5433/vyayam"
    environment: str = "development"

    # Auth
    session_cookie_name: str = "vy_session"
    session_ttl_days: int = 30
    cookie_secure: bool = True  # browsers treat http://localhost as secure, so dev still works
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 20
    login_window_seconds: int = 15 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
