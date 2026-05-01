"""Unit tests for UserRepository — SQLAlchemy adapter with mocked AsyncSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.domain.user import Email, User
from stonks_backend.infrastructure.persistence.models import UserModel
from stonks_backend.infrastructure.persistence.user_repo import UserRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return an AsyncMock that mimics AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session: AsyncMock) -> UserRepository:
    return UserRepository(mock_session)


@pytest.fixture
def sample_user() -> User:
    return User.register(email="test@stonks.com", password="StrongPass1")


@pytest.fixture
def sample_user_model(sample_user: User) -> UserModel:
    return UserModel(
        id=sample_user.id,
        email=sample_user.email.address,
        hashed_password=str(sample_user.hashed_password),
        is_active=True,
        created_at=sample_user.created_at,
        updated_at=sample_user.updated_at,
    )


# ── get_by_id ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_id_found(
    repo: UserRepository, mock_session: AsyncMock, sample_user_model: UserModel
) -> None:
    """Returns User when model exists."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user_model
    mock_session.execute.return_value = mock_result

    user = await repo.get_by_id(sample_user_model.id)
    assert user is not None
    assert user.email.address == "test@stonks.com"


@pytest.mark.asyncio
async def test_get_by_id_not_found(repo: UserRepository, mock_session: AsyncMock) -> None:
    """Returns None when user not in DB."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    user = await repo.get_by_id(uuid4())
    assert user is None


# ── get_by_email ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_email_found(
    repo: UserRepository, mock_session: AsyncMock, sample_user_model: UserModel
) -> None:
    """Returns User when email matches."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user_model
    mock_session.execute.return_value = mock_result

    user = await repo.get_by_email(Email("test@stonks.com"))
    assert user is not None
    assert str(user.id) == str(sample_user_model.id)


@pytest.mark.asyncio
async def test_get_by_email_not_found(repo: UserRepository, mock_session: AsyncMock) -> None:
    """Returns None when email not in DB."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    user = await repo.get_by_email(Email("ghost@stonks.com"))
    assert user is None


# ── save ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_new_user(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """save calls merge + flush."""
    mock_session.merge = AsyncMock()
    mock_session.flush = AsyncMock()

    await repo.save(sample_user)
    mock_session.merge.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_save_existing_user(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """save updates existing user (merge + flush)."""
    mock_session.merge = AsyncMock()
    mock_session.flush = AsyncMock()

    await repo.save(sample_user)
    await repo.save(sample_user)  # second save also works
    assert mock_session.merge.call_count == 2
    assert mock_session.flush.call_count == 2


# ── delete ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_existing_user(
    repo: UserRepository, mock_session: AsyncMock, sample_user_model: UserModel
) -> None:
    """delete removes the user and flushes."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user_model
    mock_session.execute.return_value = mock_result
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    await repo.delete(sample_user_model.id)
    mock_session.delete.assert_called_once_with(sample_user_model)
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_nonexistent_user(repo: UserRepository, mock_session: AsyncMock) -> None:
    """delete on non-existing user is a no-op (no delete/flush)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    await repo.delete(uuid4())
    mock_session.delete.assert_not_called()
    mock_session.flush.assert_not_called()


# ── _to_domain ───────────────────────────────────────────────────────


def test_to_domain_roundtrip(sample_user: User) -> None:
    """_to_domain reconstructs User from UserModel correctly."""
    model = UserModel(
        id=sample_user.id,
        email=sample_user.email.address,
        hashed_password=str(sample_user.hashed_password),
        is_active=sample_user.is_active,
        created_at=sample_user.created_at,
        updated_at=sample_user.updated_at,
    )
    user = UserRepository._to_domain(model)
    assert user.id == sample_user.id
    assert user.email == sample_user.email
    assert user.is_active == sample_user.is_active
