"""Configuration safety tests."""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="dev-secret-change-me",
            auto_seed=False,
        )


def test_production_rejects_auto_seed():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="x" * 64,
            auto_seed=True,
        )


def test_production_accepts_explicit_safe_settings():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="x" * 64,
        auto_seed=False,
    )

    assert settings.is_production is True


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_timezone="Not/A_Real_Timezone")
