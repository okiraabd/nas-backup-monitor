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


def test_production_rejects_demo_seed_mode():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="x" * 64,
            seed_mode="demo",
        )


def test_production_accepts_users_seed_mode():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="x" * 64,
        seed_mode="users",
    )

    assert settings.effective_seed_mode == "users"


def test_seed_mode_overrides_legacy_auto_seed():
    settings = Settings(_env_file=None, seed_mode="users", auto_seed=True)

    assert settings.effective_seed_mode == "users"


def test_invalid_seed_mode_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, seed_mode="everything")


def test_production_accepts_explicit_safe_settings():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="x" * 64,
        auto_seed=False,
    )

    assert settings.is_production is True
    assert settings.effective_seed_mode == "none"


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_timezone="Not/A_Real_Timezone")
