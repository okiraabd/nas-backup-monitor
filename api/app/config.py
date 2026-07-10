"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object. Values come from the environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = (
        "postgresql+psycopg://backup_monitor:backup_monitor_pw@localhost:5432/backup_monitor"
    )

    # JWT / security
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # issuer / audience claims — validated on every token decode
    jwt_issuer: str = "backup-monitor-api"
    jwt_audience: str = "backup-monitor-clients"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost,http://localhost:5173,http://localhost:3000"

    # Behaviour
    auto_seed: bool = False
    reports_dir: str = "/app/generated_reports"
    app_timezone: str = "Asia/Jakarta"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, trimming whitespace and empties."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
