"""Abstract ports — interfaces that infrastructure adapters must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from stonks_backend.domain.user import Email, User


class UserRepositoryPort(ABC):
    """Abstract interface for user persistence."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: Email) -> User | None: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None: ...


class RefreshTokenRepositoryPort(ABC):
    """Abstract interface for refresh token persistence."""

    @abstractmethod
    async def store(self, user_id: UUID, token_hash: str, expires_at_ts: int) -> None: ...

    @abstractmethod
    async def is_valid(self, user_id: UUID, token_hash: str) -> bool: ...

    @abstractmethod
    async def revoke_all(self, user_id: UUID) -> None: ...
