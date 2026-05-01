"""Unit tests for RefreshTokenRepository — Redis adapter with mocked aioredis."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stonks_backend.infrastructure.persistence.refresh_token_repo import RefreshTokenRepository


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return an AsyncMock mimicking redis.asyncio.Redis."""
    return AsyncMock()


@pytest.fixture
def repo(mock_redis: AsyncMock) -> RefreshTokenRepository:
    return RefreshTokenRepository(mock_redis)


# ── store ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_happy_path(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """store sets key with user_id:token_hash and TTL."""
    user_id = uuid4()
    token_hash = "abc123hash"
    future_ts = 9999999999  # far future

    mock_redis.set = AsyncMock()
    await repo.store(user_id, token_hash, future_ts)
    expected_key = f"stonks:refresh:{user_id}:{token_hash}"
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args[0][0] == expected_key
    assert call_args[0][1] == "1"
    assert "ex" in call_args[1]


@pytest.mark.asyncio
async def test_store_past_expiry_raises(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """store with expires_at_ts in the past should raise ValueError."""
    user_id = uuid4()
    token_hash = "expiredhash"
    past_ts = 100  # way in the past

    with pytest.raises(ValueError, match="expires_at_ts is in the past"):
        await repo.store(user_id, token_hash, past_ts)

    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_store_different_users_separate_keys(
    repo: RefreshTokenRepository, mock_redis: AsyncMock
) -> None:
    """Two different users get different Redis keys."""
    user_a = uuid4()
    user_b = uuid4()
    future_ts = 9999999999
    mock_redis.set = AsyncMock()

    await repo.store(user_a, "hashA", future_ts)
    await repo.store(user_b, "hashB", future_ts)

    assert mock_redis.set.call_count == 2
    key_a = mock_redis.set.call_args_list[0][0][0]
    key_b = mock_redis.set.call_args_list[1][0][0]
    assert key_a != key_b
    assert str(user_a) in key_a
    assert str(user_b) in key_b


# ── is_valid ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_valid_true(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """is_valid returns True when key exists."""
    user_id = uuid4()
    mock_redis.exists = AsyncMock(return_value=1)

    valid = await repo.is_valid(user_id, "valid-hash")
    assert valid is True
    mock_redis.exists.assert_called_once_with(f"stonks:refresh:{user_id}:valid-hash")


@pytest.mark.asyncio
async def test_is_valid_false(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """is_valid returns False when key doesn't exist."""
    user_id = uuid4()
    mock_redis.exists = AsyncMock(return_value=0)

    valid = await repo.is_valid(user_id, "stale-hash")
    assert valid is False


# ── revoke_all ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_all_deletes_matching_keys(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """revoke_all uses SCAN to find and delete all keys for user."""
    user_id = uuid4()
    mock_redis.scan = AsyncMock(return_value=(0, [f"stonks:refresh:{user_id}:h1", f"stonks:refresh:{user_id}:h2"]))
    mock_redis.delete = AsyncMock(return_value=2)

    await repo.revoke_all(user_id)
    mock_redis.scan.assert_called_once()
    mock_redis.delete.assert_called_once_with(
        f"stonks:refresh:{user_id}:h1", f"stonks:refresh:{user_id}:h2"
    )


@pytest.mark.asyncio
async def test_revoke_all_no_keys(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """revoke_all when user has no tokens → no delete call."""
    user_id = uuid4()
    mock_redis.scan = AsyncMock(return_value=(0, []))
    mock_redis.delete = AsyncMock()

    await repo.revoke_all(user_id)
    mock_redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_all_multi_scan(repo: RefreshTokenRepository, mock_redis: AsyncMock) -> None:
    """revoke_all handles SCAN cursor pagination."""
    user_id = uuid4()
    # First SCAN returns non-zero cursor, second returns zero
    mock_redis.scan = AsyncMock(
        side_effect=[
            (1, [f"stonks:refresh:{user_id}:a"]),
            (0, [f"stonks:refresh:{user_id}:b"]),
        ]
    )
    mock_redis.delete = AsyncMock(return_value=1)

    await repo.revoke_all(user_id)
    assert mock_redis.scan.call_count == 2
    assert mock_redis.delete.call_count == 2
