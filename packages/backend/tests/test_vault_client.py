"""Unit tests for VaultClient — cover fallback, errors, caching, convenience methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stonks_backend.infrastructure.config import Settings
from stonks_backend.infrastructure.security.vault_client import VaultClient, VaultError


@pytest.fixture
def dev_settings() -> Settings:
    return Settings(
        vault_enabled=False,
        jwt_secret="dev-jwt-secret-at-least-32-chars!!",
        aes_key="ZYh4xPjRqFzOdLKm2AVFUlIm2BfXpXuMTaoDn5cKt5b+",
    )


@pytest.fixture
def prod_settings() -> Settings:
    return Settings(
        vault_enabled=True,
        vault_url="http://vault:8200",
        vault_token="hvs.test-token-for-ci-00000000",
        vault_mount_point="stonks-kv",
        jwt_secret="prod-jwt-secret-at-least-32-chars",
        aes_key="ZYh4xPjRqFzOdLKm2AVFUlIm2BfXpXuMTaoDn5cKt5b+",
        ENV="production",
    )


# ── Fallback (.env dev mode) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_initialize_vault_disabled_uses_fallback(dev_settings: Settings) -> None:
    """When vault_enabled=False, client uses .env fallback."""
    client = VaultClient(dev_settings)
    await client.initialize()
    assert client._client is None
    assert "jwt_secret" in client._dev_fallback
    assert client._dev_fallback["jwt_secret"] == "dev-jwt-secret-at-least-32-chars!!"


@pytest.mark.asyncio
async def test_initialize_vault_disabled_populates_aes_key(dev_settings: Settings) -> None:
    """Fallback should include aes_key."""
    client = VaultClient(dev_settings)
    await client.initialize()
    assert "aes_key" in client._dev_fallback
    assert client._dev_fallback["aes_key"] == dev_settings.aes_key.get_secret_value()


# ── Vault unreachable in dev → fallback ───────────────────────────────


@pytest.mark.asyncio
async def test_vault_unreachable_dev_falls_back() -> None:
    """In dev mode, Vault connection failure should trigger .env fallback."""
    settings = Settings(
        vault_enabled=True,
        vault_url="http://unreachable:9999",
        vault_token="hvs.fake",
        jwt_secret="fallback-jwt-secret-at-least-32-char",
        aes_key="ZYh4xPjRqFzOdLKm2AVFUlIm2BfXpXuMTaoDn5cKt5b+",
        ENV="dev",
    )
    client = VaultClient(settings)

    with patch("stonks_backend.infrastructure.security.vault_client.hvac.Client") as mock_hvac:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.side_effect = Exception("Connection refused")
        mock_hvac.return_value = mock_instance

        await client.initialize()

        # Should have fallen back to .env
        assert client._client is None
        assert client._dev_fallback["jwt_secret"] == "fallback-jwt-secret-at-least-32-char"


# ── Vault unreachable in prod → raise ─────────────────────────────────


@pytest.mark.asyncio
async def test_vault_unreachable_prod_raises(prod_settings: Settings) -> None:
    """In production, Vault connection failure must raise VaultError."""
    client = VaultClient(prod_settings)

    with patch("stonks_backend.infrastructure.security.vault_client.hvac.Client") as mock_hvac:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.side_effect = Exception("Connection refused")
        mock_hvac.return_value = mock_instance

        with pytest.raises(VaultError, match="Vault is required in production"):
            await client.initialize()


@pytest.mark.asyncio
async def test_vault_auth_failed_prod_raises(prod_settings: Settings) -> None:
    """Vault reachable but not authenticated in prod → VaultError."""
    client = VaultClient(prod_settings)

    with patch("stonks_backend.infrastructure.security.vault_client.hvac.Client") as mock_hvac:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.return_value = False
        mock_hvac.return_value = mock_instance

        with pytest.raises(VaultError, match="Vault authentication failed"):
            await client.initialize()


# ── Health check ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_fallback_always_healthy(dev_settings: Settings) -> None:
    """In dev fallback mode, health_check returns True."""
    client = VaultClient(dev_settings)
    await client.initialize()
    assert await client.health_check() is True


@pytest.mark.asyncio
async def test_health_check_vault_healthy(prod_settings: Settings) -> None:
    """With authenticated Vault client, health_check returns True."""
    client = VaultClient(prod_settings)
    with patch("stonks_backend.infrastructure.security.vault_client.hvac.Client") as mock_hvac:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.return_value = True
        mock_hvac.return_value = mock_instance
        await client.initialize()

        assert await client.health_check() is True


# ── read_secret / write_secret (fallback) ─────────────────────────────


@pytest.mark.asyncio
async def test_read_secret_fallback(dev_settings: Settings) -> None:
    """read_secret returns cached fallback value."""
    client = VaultClient(dev_settings)
    await client.initialize()

    result = await client.read_secret("stonks/jwt", "jwt_secret")
    assert result == "dev-jwt-secret-at-least-32-chars!!"


@pytest.mark.asyncio
async def test_read_secret_missing_key_fallback(dev_settings: Settings) -> None:
    """read_secret returns None for unknown key in fallback mode."""
    client = VaultClient(dev_settings)
    await client.initialize()

    result = await client.read_secret("stonks/unknown", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_write_secret_fallback(dev_settings: Settings) -> None:
    """write_secret populates dev fallback cache."""
    client = VaultClient(dev_settings)
    await client.initialize()

    ok = await client.write_secret("stonks/test", {"my_key": "my_value"})
    assert ok is True
    assert client._dev_fallback["my_key"] == "my_value"


@pytest.mark.asyncio
async def test_read_secret_after_write(dev_settings: Settings) -> None:
    """read_secret returns value previously written via write_secret."""
    client = VaultClient(dev_settings)
    await client.initialize()

    await client.write_secret("stonks/new", {"new_key": "new_secret_value"})
    result = await client.read_secret("stonks/new", "new_key")
    assert result == "new_secret_value"


# ── Convenience methods ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jwt_secret_fallback(dev_settings: Settings) -> None:
    """get_jwt_secret returns the JWT secret from fallback."""
    client = VaultClient(dev_settings)
    await client.initialize()

    secret = await client.get_jwt_secret()
    assert secret == "dev-jwt-secret-at-least-32-chars!!"


@pytest.mark.asyncio
async def test_get_aes_key_fallback(dev_settings: Settings) -> None:
    """get_aes_key returns the AES key from fallback."""
    client = VaultClient(dev_settings)
    await client.initialize()

    key = await client.get_aes_key()
    assert key == dev_settings.aes_key.get_secret_value()


@pytest.mark.asyncio
async def test_get_jwt_secret_missing_raises(dev_settings: Settings) -> None:
    """get_jwt_secret raises VaultError if jwt_secret not in fallback."""
    client = VaultClient(dev_settings)
    await client.initialize()
    client._dev_fallback.pop("jwt_secret", None)

    with pytest.raises(VaultError, match="jwt_secret not found"):
        await client.get_jwt_secret()


@pytest.mark.asyncio
async def test_get_aes_key_missing_raises(dev_settings: Settings) -> None:
    """get_aes_key raises VaultError if aes_key not in fallback."""
    client = VaultClient(dev_settings)
    await client.initialize()
    client._dev_fallback.pop("aes_key", None)

    with pytest.raises(VaultError, match="aes_key not found"):
        await client.get_aes_key()


# ── Close ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_close_with_null_client_does_nothing(dev_settings: Settings) -> None:
    """close() on a fallback-only client should not raise."""
    client = VaultClient(dev_settings)
    await client.initialize()
    # Should not raise
    await client.close()


@pytest.mark.asyncio
async def test_close_with_hvac_client(prod_settings: Settings) -> None:
    """close() calls hvac adapter.close()."""
    client = VaultClient(prod_settings)

    with patch("stonks_backend.infrastructure.security.vault_client.hvac.Client") as mock_hvac:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.return_value = True
        mock_hvac.return_value = mock_instance
        await client.initialize()

        await client.close()
        mock_instance.adapter.close.assert_called_once()


# ── from_settings class method ───────────────────────────────────────


def test_from_settings_creates_client(dev_settings: Settings) -> None:
    """from_settings factory returns a VaultClient."""
    client = VaultClient.from_settings(dev_settings)
    assert isinstance(client, VaultClient)
    assert client._settings == dev_settings
