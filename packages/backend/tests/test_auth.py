"""Auth integration tests — full flow: register → login → refresh → /me."""
import pytest
from httpx import ASGITransport, AsyncClient

from stonks_backend.app import create_app
from stonks_backend.domain.user import User
from stonks_backend.application.ports.repositories import (
    RefreshTokenRepositoryPort,
    UserRepositoryPort,
)
from stonks_backend.infrastructure.security.jwt_service import JWTService
from stonks_backend.infrastructure.config import Settings


# ── Test doubles (in-memory repos) ────────────────────────────────────


class InMemoryUserRepo(UserRepositoryPort):
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def get_by_id(self, user_id):
        return self._users.get(str(user_id))

    async def get_by_email(self, email):
        for u in self._users.values():
            if u.email.address == email.address:
                return u
        return None

    async def save(self, user):
        self._users[str(user.id)] = user

    async def delete(self, user_id):
        self._users.pop(str(user_id), None)


class InMemoryRefreshRepo(RefreshTokenRepositoryPort):
    def __init__(self) -> None:
        self._tokens: set[str] = set()

    async def store(self, user_id, token_hash, expires_at_ts):
        self._tokens.add(f"{user_id}:{token_hash}")

    async def is_valid(self, user_id, token_hash):
        return f"{user_id}:{token_hash}" in self._tokens

    async def revoke_all(self, user_id):
        prefix = f"{user_id}:"
        self._tokens = {t for t in self._tokens if not t.startswith(prefix)}


# ── App override fixture ──────────────────────────────────────────────


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-at-least-32-chars-for-testing",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        jwt_issuer="stonks-test",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncClient:
    """Create a test client with in-memory repos injected."""
    app = create_app()

    user_repo = InMemoryUserRepo()
    refresh_repo = InMemoryRefreshRepo()
    jwt_svc = JWTService.from_settings(test_settings)

    from stonks_backend.application.use_cases.auth.auth_service import AuthUseCases
    from stonks_backend.interfaces.api.dependencies.auth import (
        get_auth_use_cases,
        get_user_repo,
        get_refresh_repo,
        get_jwt_service,
    )

    auth_uc = AuthUseCases(user_repo, refresh_repo, jwt_svc)

    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_refresh_repo] = lambda: refresh_repo
    app.dependency_overrides[get_jwt_service] = lambda: jwt_svc
    app.dependency_overrides[get_auth_use_cases] = lambda: auth_uc

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_auth_flow(client: AsyncClient) -> None:
    """Register → Login → /me → Refresh → /me."""
    resp = await client.post(
        "/auth/register",
        json={"email": "flow@stonks.com", "password": "password123"},
    )
    assert resp.status_code == 201
    user_data = resp.json()
    user_id = user_data["id"]

    resp = await client.post(
        "/auth/login",
        json={"email": "flow@stonks.com", "password": "password123"},
    )
    assert resp.status_code == 200
    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id

    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "dup@stonks.com", "password": "password123"},
    )
    resp = await client.post(
        "/auth/register",
        json={"email": "dup@stonks.com", "password": "another123"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "wrong@stonks.com", "password": "correct12"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "wrong@stonks.com", "password": "wrongpass1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "noone@stonks.com", "password": "anything12"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid-refresh-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_flow(client: AsyncClient) -> None:
    """Happy path: login → refresh → verify new tokens work."""
    await client.post(
        "/auth/register",
        json={"email": "rf@stonks.com", "password": "password123"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": "rf@stonks.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_tokens = resp.json()

    # Verify new access token works
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "rf@stonks.com"
