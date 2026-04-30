"""Configuration via Pydantic Settings — lit .env + fallback Vault en production."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file() -> str:
    """Détermine le fichier .env selon STONKS_ENV."""
    env = os.getenv("STONKS_ENV", "dev")
    candidates = [
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[3] / f".env.{env}",
        Path("/opt/stonks/.env"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return ".env"


class Settings(BaseSettings):
    """Configuration centralisée — env vars + fichier .env."""

    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        env_prefix="STONKS_",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    app_name: str = "stonks-backend"
    app_env: str = Field(default="dev", alias="ENV")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")  # "console" | "json"

    # ── Server ─────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database ───────────────────────────────────────────────────
    database_url: SecretStr = Field(
        default=SecretStr(
            "postgresql+asyncpg://stonks:stonks_dev@localhost:5432/stonks_dev"
        ),
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # ── Redis ──────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Vault ──────────────────────────────────────────────────────
    vault_url: str = "http://localhost:8200"
    vault_token: SecretStr = Field(default=SecretStr("dev-token"))
    vault_mount_point: str = "secret"
    vault_enabled: bool = True

    # ── JWT ────────────────────────────────────────────────────────
    jwt_secret: SecretStr = Field(
        default=SecretStr("dev-secret-change-me-in-production"),
        description="Clé HS256 pour signer les tokens JWT. En prod, vient de Vault.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "stonks-backend"

    # ── AES-256-GCM ────────────────────────────────────────────────
    aes_key: SecretStr = Field(
        default=SecretStr("dev-aes-key-32-bytes-change-me!!"),
        description="Clé maîtresse AES-256-GCM (32 octets). En prod, vient de Vault.",
    )

    # ── Rate Limiting ──────────────────────────────────────────────
    rate_limit_auth_login: str = "5/minute"
    rate_limit_global: str = "100/minute"

    # ── CORS ───────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        if v not in ("console", "json"):
            raise ValueError("log_format must be 'console' or 'json'")
        return v

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    def dict_no_secrets(self) -> dict[str, Any]:
        """Représentation safe pour les logs (masque les secrets)."""
        d = self.model_dump()
        for k, v in d.items():
            if isinstance(v, SecretStr):
                d[k] = "***"
        return d


@lru_cache
def get_settings() -> Settings:
    """Factory singleton pour Settings."""
    return Settings()
