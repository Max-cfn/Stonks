"""Auth use cases — register, login, refresh_token."""

from __future__ import annotations

import hashlib
from uuid import UUID

import structlog

from stonks_backend.application.ports.repositories import (
    RefreshTokenRepositoryPort,
    UserRepositoryPort,
)
from stonks_backend.domain.user import Email, User
from stonks_backend.infrastructure.security.jwt_service import JWTService, TokenPair

logger = structlog.get_logger(__name__)


class AuthUseCases:
    """Orchestrates authentication: register, login, refresh."""

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        refresh_repo: RefreshTokenRepositoryPort,
        jwt_service: JWTService,
    ) -> None:
        self._users = user_repo
        self._refresh = refresh_repo
        self._jwt = jwt_service

    async def register(self, email: str, password: str) -> User:
        """Register a new user. Raises ValueError if email already exists."""
        email_vo = Email(email)
        existing = await self._users.get_by_email(email_vo)
        if existing is not None:
            raise ValueError("Email already registered")

        user = User.register(email, password)
        await self._users.save(user)
        logger.info("user registered", user_id=str(user.id), email=email)
        return user

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate user and return token pair.

        Raises ValueError on invalid credentials.
        """
        email_vo = Email(email)
        user = await self._users.get_by_email(email_vo)
        if user is None or not user.is_active:
            raise ValueError("Invalid email or password")

        if not user.verify_password(password):
            raise ValueError("Invalid email or password")

        token_pair = self._jwt.create_token_pair(user.id, user.email.address)

        # Store refresh token hash
        token_hash = _hash_token(token_pair.refresh_token)
        payload = self._jwt.decode_refresh_token(token_pair.refresh_token)
        await self._refresh.store(user.id, token_hash, payload.exp)

        logger.info("user logged in", user_id=str(user.id))
        return token_pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate tokens using a valid refresh token.

        Revokes the old refresh token and issues a new pair.
        """
        payload = self._jwt.decode_refresh_token(refresh_token)
        user_id = UUID(payload.sub)

        if not await self._refresh.is_valid(user_id, _hash_token(refresh_token)):
            # Token reuse detected — revoke all tokens for this user
            await self._refresh.revoke_all(user_id)
            logger.warning("refresh token reuse detected", user_id=str(user_id))
            raise ValueError("Refresh token revoked")

        # Revoke old, issue new
        await self._refresh.revoke_all(user_id)

        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")

        token_pair = self._jwt.create_token_pair(user.id, user.email.address)
        payload = self._jwt.decode_refresh_token(token_pair.refresh_token)
        await self._refresh.store(user.id, _hash_token(token_pair.refresh_token), payload.exp)

        logger.info("tokens refreshed", user_id=str(user_id))
        return token_pair

    async def get_current_user(self, access_token: str) -> User:
        """Validate access token and return the current user."""
        payload = self._jwt.decode_access_token(access_token)
        user_id = UUID(payload.sub)
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")
        return user


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
