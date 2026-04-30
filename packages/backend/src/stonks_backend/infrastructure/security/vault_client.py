"""Vault client adapter — hvac with .env fallback in dev mode."""
from __future__ import annotations

import logging

import hvac

from stonks_backend.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Raised when Vault operations fail."""


class VaultClient:
    """Async-friendly Vault client wrapping hvac.

    En mode dev, les secrets sont lus depuis les Settings (fallback .env).
    En production, hvac contacte le serveur Vault.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: hvac.Client | None = None
        self._dev_fallback: dict[str, str] = {}  # cache .env fallback

    @classmethod
    def from_settings(cls, settings: Settings) -> VaultClient:
        return cls(settings)

    # ── Lifecycle ──────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Connect to Vault (or init dev fallback)."""
        settings = self._settings
        if not settings.vault_enabled:
            logger.info("vault disabled, using .env fallback")
            self._populate_dev_fallback(settings)
            return

        try:
            self._client = hvac.Client(
                url=settings.vault_url,
                token=settings.vault_token.get_secret_value(),
            )
            if not self._client.is_authenticated():
                raise VaultError("Vault authentication failed")
            logger.info("vault connected", url=settings.vault_url)
        except Exception as exc:
            if settings.is_dev:
                logger.warning("vault unreachable, falling back to .env", error=str(exc))
                self._populate_dev_fallback(settings)
                self._client = None
            else:
                raise VaultError(f"Vault is required in production: {exc}") from exc

    async def health_check(self) -> bool:
        """Return True if Vault (or fallback) is healthy."""
        if self._client is None:
            return True  # dev fallback always healthy
        try:
            return self._client.is_authenticated()
        except Exception:
            return False

    def _populate_dev_fallback(self, settings: Settings) -> None:
        """Pre-load secrets from Settings for dev mode."""
        self._dev_fallback = {
            "jwt_secret": settings.jwt_secret.get_secret_value(),
            "aes_key": settings.aes_key.get_secret_value(),
        }

    # ── Secrets API ────────────────────────────────────────────────

    async def read_secret(self, path: str, key: str) -> str | None:
        """Read a secret from Vault or dev fallback."""
        # Dev fallback: secrets stored flat
        if self._client is None:
            return self._dev_fallback.get(key)

        try:
            mount_point = self._settings.vault_mount_point
            full_path = f"{mount_point}/data/{path}"
            response = self._client.secrets.kv.v2.read_secret_version(
                path=full_path.replace(f"{mount_point}/data/", ""),
                mount_point=mount_point,
            )
            data = response["data"]["data"]
            return data.get(key)
        except Exception as exc:
            logger.error("vault read_secret failed", path=path, key=key, error=str(exc))
            return None

    async def write_secret(self, path: str, data: dict[str, str]) -> bool:
        """Write a secret to Vault (dev mode: store in fallback cache)."""
        if self._client is None:
            self._dev_fallback.update(data)
            return True

        try:
            mount_point = self._settings.vault_mount_point
            self._client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=mount_point,
            )
            return True
        except Exception as exc:
            logger.error("vault write_secret failed", path=path, error=str(exc))
            return False

    # ── Convenience methods ────────────────────────────────────────

    async def get_jwt_secret(self) -> str:
        secret = await self.read_secret("stonks/jwt", "jwt_secret")
        if secret is None:
            raise VaultError("jwt_secret not found in Vault or settings")
        return secret

    async def get_aes_key(self) -> str:
        key = await self.read_secret("stonks/aes", "aes_key")
        if key is None:
            raise VaultError("aes_key not found in Vault or settings")
        return key

    async def close(self) -> None:
        if self._client is not None:
            self._client.adapter.close()
