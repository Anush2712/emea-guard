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
    # Public URL of the web app, used to build password reset links in emails.
    app_base_url: str = "http://localhost:8080"
    password_reset_minutes: int = 30
    # SMTP for password reset emails. If smtp_host is empty, emails are not sent: the reset link is
    # logged, and (outside production) returned in the API response so local setups stay usable.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "EMEA Guard <no-reply@emea-guard.local>"
    smtp_starttls: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
