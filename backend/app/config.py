"""App settings, read from environment variables (or a .env file in dev).

Defaults match docker-compose.yml, so local dev works with no .env at all.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://vyayam:vyayam@localhost:5433/vyayam"
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
