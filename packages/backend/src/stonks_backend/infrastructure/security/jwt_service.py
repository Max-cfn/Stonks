"""JWT service — HS256 access + refresh tokens, Vault-backed secret."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt  # type: ignore[import-untyped]

from stonks_backend.infrastructure.config import Settings
from stonks_backend.infrastructure.security.vault_client import VaultClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class TokenPayload:
    sub: str  # user_id as string
    exp: int
    iat: int
    iss: str
    type: str  # "access" | "refresh"
    email: str | None = None


class JWTService:
    """Create and verify JWT tokens (HS256)."""

    def __init__(self, settings: Settings, secret: str) -> None:
        self._settings = settings
        self._secret = secret
        self._algorithm = settings.jwt_algorithm
        self._issuer = settings.jwt_issuer
        self._access_ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.jwt_refresh_token_expire_days)

    @classmethod
    async def from_vault(cls, settings: Settings, vault: VaultClient) -> JWTService:
        secret = await vault.get_jwt_secret()
        return cls(settings, secret)

    @classmethod
    def from_settings(cls, settings: Settings) -> JWTService:
        """Convenience factory using the JWT secret directly from settings (dev)."""
        return cls(settings, settings.jwt_secret.get_secret_value())

    # ── Token creation ────────────────────────────────────────────

    def create_access_token(self, user_id: UUID, email: str) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
            "iss": self._issuer,
            "type": "access",
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)  # type: ignore[no-any-return]

    def create_refresh_token(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + self._refresh_ttl).timestamp()),
            "iss": self._issuer,
            "type": "refresh",
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)  # type: ignore[no-any-return]

    def create_token_pair(self, user_id: UUID, email: str) -> TokenPair:
        return TokenPair(
            access_token=self.create_access_token(user_id, email),
            refresh_token=self.create_refresh_token(user_id),
        )

    # ── Token verification ────────────────────────────────────────

    def decode_access_token(self, token: str) -> TokenPayload:
        """Decode and validate an access token. Raises ValueError on any failure."""
        payload = self._decode(token)
        if payload.type != "access":
            raise ValueError("Token is not an access token")
        return payload

    def decode_refresh_token(self, token: str) -> TokenPayload:
        """Decode and validate a refresh token. Raises ValueError on any failure."""
        payload = self._decode(token)
        if payload.type != "refresh":
            raise ValueError("Token is not a refresh token")
        return payload

    def _decode(self, token: str) -> TokenPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
            )
            return TokenPayload(
                sub=claims["sub"],
                exp=int(claims["exp"]),
                iat=int(claims["iat"]),
                iss=claims["iss"],
                type=claims["type"],
                email=claims.get("email"),
            )
        except JWTError as exc:
            raise ValueError(f"Invalid token: {exc}") from exc
