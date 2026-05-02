"""Push token repository — stores Expo push tokens for notifications."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.infrastructure.persistence.push_token_model import PushTokenModel


class PushTokenRepository:
    """Handles upsert of push notification tokens per user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, user_id: uuid.UUID, token: str, platform: str) -> PushTokenModel:
        """Insert or update a push token for a user+platform combo."""
        stmt = (
            pg_insert(PushTokenModel)
            .values(
                user_id=user_id,
                token=token,
                platform=platform,
            )
            .on_conflict_do_update(
                constraint="uq_push_token_user_platform",
                set_=dict(token=token),
            )
            .returning(PushTokenModel)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_user(self, user_id: uuid.UUID) -> list[PushTokenModel]:
        """Get all push tokens for a user."""
        stmt = (
            select(PushTokenModel)
            .where(PushTokenModel.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
