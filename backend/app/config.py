"""Application settings, loaded from environment variables (12-factor style)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EMEA_GUARD_", extra="ignore")

    app_name: str = "EMEA Guard"
    environment: str = "development"
    # PostgreSQL is the primary database. SQLite is supported for tests and the static demo export.
    database_url: str = "postgresql+psycopg://emea_guard:emea_guard@localhost:5432/emea_guard"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480
    cors_origins: str = "*"
    seed_on_startup: bool = True
    random_seed: int = 2712


@lru_cache
def get_settings() -> Settings:
    return Settings()
