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
    # Password reset email delivery. Use ONE of:
    #   resend_api_key  - Resend HTTPS API (port 443; works where outbound SMTP is blocked, e.g. Render free tier)
    #   smtp_host/...   - any SMTP relay
    # With neither configured, links are never returned by the API; in development only they are written
    # to the server log so a local setup stays usable. In any other environment nothing is logged.
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "EMEA Guard <no-reply@emea-guard.local>"
    smtp_starttls: bool = True
    # Number of reverse proxies in front of the API that append to X-Forwarded-For (0 = trust no header).
    trusted_proxy_hops: int = 0

    @property
    def is_development(self) -> bool:
        """Only an explicit development environment may log reset links (fail closed for anything else)."""
        return self.environment.strip().lower() in ("development", "dev", "local", "test")

    @property
    def email_configured(self) -> bool:
        return bool(self.resend_api_key or self.smtp_host)


@lru_cache
def get_settings() -> Settings:
    return Settings()
