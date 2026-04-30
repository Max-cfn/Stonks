"""Redis adapter for RefreshTokenRepositoryPort."""
from __future__ import annotations

import logging
from datetime import UTC
from uuid import UUID

import redis.asyncio as aioredis

from stonks_backend.application.ports.repositories import RefreshTokenRepositoryPort

logger = logging.getLogger(__name__)

# Redis key prefix
_PREFIX = "stonks:refresh:"


class RefreshTokenRepository(RefreshTokenRepositoryPort):
    """Redis-backed refresh token storage.

    Stores SHA-256 hashes of refresh tokens, not the tokens themselves.
    Keys expire automatically based on the token TTL.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def store(self, user_id: UUID, token_hash: str, expires_at_ts: int) -> None:
        from datetime import datetime

        now_ts = int(datetime.now(UTC).timestamp())
        ttl = expires_at_ts - now_ts
        if ttl <= 0:
            raise ValueError("expires_at_ts is in the past")

        key = f"{_PREFIX}{user_id}:{token_hash}"
        await self._redis.set(key, "1", ex=ttl)
        logger.debug("refresh token stored", user_id=str(user_id))

    async def is_valid(self, user_id: UUID, token_hash: str) -> bool:
        key = f"{_PREFIX}{user_id}:{token_hash}"
        exists = await self._redis.exists(key)
        return bool(exists)

    async def revoke_all(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        pattern = f"{_PREFIX}{user_id}:*"
        cursor: int = 0
        deleted = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += await self._redis.delete(*keys)
            if cursor == 0:
                break
        logger.info("refresh tokens revoked", user_id=str(user_id), count=deleted)
