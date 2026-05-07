"""FastAPI dependencies — DB sessions, auth, rate limiting."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.repositories import (
    RefreshTokenRepositoryPort,
    UserRepositoryPort,
)
from stonks_backend.application.use_cases.auth.auth_service import AuthUseCases
from stonks_backend.domain.user import User
from stonks_backend.infrastructure.config import get_settings
from stonks_backend.infrastructure.database import get_session
from stonks_backend.infrastructure.persistence.refresh_token_repo import RefreshTokenRepository
from stonks_backend.infrastructure.persistence.user_repo import UserRepository
from stonks_backend.infrastructure.security.jwt_service import JWTService


async def get_user_repo(session: AsyncSession = Depends(get_session)) -> UserRepositoryPort:
    return UserRepository(session)


async def get_refresh_repo(request: Request) -> RefreshTokenRepositoryPort:
    from redis.asyncio import from_url

    settings = get_settings()
    redis_client = from_url(settings.redis_url, decode_responses=False)  # type: ignore[no-untyped-call]
    return RefreshTokenRepository(redis_client)


async def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService.from_settings(settings)


async def get_auth_use_cases(
    user_repo: UserRepositoryPort = Depends(get_user_repo),
    refresh_repo: RefreshTokenRepositoryPort = Depends(get_refresh_repo),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> AuthUseCases:
    return AuthUseCases(user_repo, refresh_repo, jwt_service)


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    auth_use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> User | None:
    """FastAPI dependency: extract and validate the current user.

    Auth desactivee temporairement — retourne None au lieu de 401.
    Pour reactiver, retablir les HTTPException ci-dessous.
    """
    if not access_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
    if not access_token:
        return None

    try:
        user = await auth_use_cases.get_current_user(access_token)
        return user
    except ValueError:
        return None
