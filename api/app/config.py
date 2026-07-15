"""Application configuration loaded from environment variables."""
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
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
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost,http://localhost:5173,http://localhost:3000"

    # Behaviour
    # Preferred seed switch: none, users, or demo. Empty means use legacy AUTO_SEED.
    seed_mode: str = ""
    auto_seed: bool = False
    reports_dir: str = "/app/generated_reports"
    app_timezone: str = "Asia/Jakarta"
    metric_retention_days: int = Field(30, ge=1, le=3650)
    metric_cleanup_interval_seconds: int = Field(3600, ge=60, le=86400)
    metric_cleanup_batch_size: int = Field(10000, ge=100, le=100000)

    @property
    def is_production(self) -> bool:
        """Whether the app is running with production safety checks enabled."""
        return self.app_env in {"prod", "production"}

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, trimming whitespace and empties."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_seed_mode(self) -> str:
        """Resolved seed behavior, with AUTO_SEED kept as legacy fallback."""
        if self.seed_mode:
            return self.seed_mode
        return "demo" if self.auto_seed else "none"

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        """Keep environment names predictable for safety checks."""
        return value.strip().lower()

    @field_validator("seed_mode")
    @classmethod
    def normalize_seed_mode(cls, value: str) -> str:
        """Validate explicit seed mode while allowing empty legacy fallback."""
        normalized = value.strip().lower()
        if normalized not in {"", "none", "users", "demo"}:
            raise ValueError("SEED_MODE must be one of: none, users, demo")
        return normalized

    @field_validator("app_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        """Fail early if APP_TIMEZONE is not a valid IANA timezone."""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid IANA timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def production_must_be_explicitly_safe(self) -> "Settings":
        """Prevent common demo defaults from accidentally reaching production."""
        weak_secrets = {
            "dev-secret-change-me",
            "dev-secret-change-me-in-production-0123456789abcdef",
            "your_super_secret_jwt_key_here",
        }
        if self.is_production:
            if self.effective_seed_mode == "demo":
                raise ValueError("SEED_MODE=demo/AUTO_SEED=true is not allowed when APP_ENV=production")
            if self.jwt_secret_key in weak_secrets or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be a strong non-default secret when APP_ENV=production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
