"""SQLAlchemy adapter for UserRepositoryPort."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.repositories import UserRepositoryPort
from stonks_backend.domain.user import Email, User
from stonks_backend.infrastructure.persistence.models import UserModel

logger = structlog.get_logger(__name__)


class UserRepository(UserRepositoryPort):
    """SQLAlchemy implementation of UserRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.address)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def save(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            email=user.email.address,
            hashed_password=str(user.hashed_password),
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        await self._session.merge(model)
        await self._session.flush()
        logger.debug("user saved", user_id=str(user.id))

    async def delete(self, user_id: UUID) -> None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=Email(model.email),
            hashed_password=model.hashed_password,  # type: ignore[arg-type]
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
        )
