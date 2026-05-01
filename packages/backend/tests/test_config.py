"""Tests for configuration module."""

import pytest

from stonks_backend.infrastructure.config import Settings, get_settings


class TestSettings:
    def test_default_settings(self) -> None:
        s = Settings()
        assert s.app_name == "stonks-backend"
        assert s.app_env == "dev"
        assert s.is_dev is True
        assert s.is_prod is False

    def test_is_dev_from_constructor(self) -> None:
        s = Settings(app_env="dev")
        assert s.is_dev is True

    def test_dict_no_secrets(self) -> None:
        s = Settings()
        d = s.dict_no_secrets()
        assert d["jwt_secret"] == "***"
        assert d["database_url"] == "***"

    def test_get_settings_is_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_log_format_validation(self) -> None:
        with pytest.raises(ValueError, match="log_format"):
            Settings(log_format="xml")

    def test_log_level_configurable(self) -> None:
        s = Settings(log_level="DEBUG")
        assert s.log_level == "DEBUG"

    def test_cors_origins_default(self) -> None:
        s = Settings()
        assert s.cors_origins == ["http://localhost:3000"]

    def test_jwt_defaults(self) -> None:
        s = Settings()
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_access_token_expire_minutes == 15
        assert s.jwt_refresh_token_expire_days == 7

    def test_rate_limit_config(self) -> None:
        s = Settings()
        assert s.rate_limit_auth_login == "5/minute"
        assert s.rate_limit_global == "100/minute"
