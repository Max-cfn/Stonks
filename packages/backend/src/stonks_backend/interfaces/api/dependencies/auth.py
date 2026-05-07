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
) -> User:
    """FastAPI dependency: extract and validate the current user.

    Reads token from:
      1. HttpOnly cookie (access_token)
      2. Authorization: Bearer <token> header

    Raises 401 if no valid token is found.
    """
    if not access_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            return None  # Auth desactivee — retourne None au lieu de 401
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await auth_use_cases.get_current_user(access_token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
