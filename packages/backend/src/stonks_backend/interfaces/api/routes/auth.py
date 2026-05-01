"""Auth routes — /auth/register, /auth/login, /auth/refresh, /auth/me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from stonks_backend.application.use_cases.auth.auth_service import AuthUseCases
from stonks_backend.domain.user import User
from stonks_backend.infrastructure.security.jwt_service import TokenPair
from stonks_backend.interfaces.api.dependencies.auth import (
    get_auth_use_cases,
    get_current_user,
)
from stonks_backend.interfaces.api.schemas import (
    ErrorResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_token_cookies(response: Response, tokens: TokenPair) -> None:
    """Set JWT tokens as HttpOnly cookies."""
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        samesite="strict",
        secure=False,  # True in production with HTTPS
        max_age=900,  # 15 minutes
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=604800,  # 7 days
        path="/auth/refresh",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def register(
    body: RegisterRequest,
    auth_use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> UserResponse:
    """Register a new user account."""
    try:
        user = await auth_use_cases.register(email=body.email, password=body.password)
        return UserResponse(
            id=str(user.id),
            email=user.email.address,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    auth_use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> TokenResponse:
    """Authenticate and return token pair (set as HttpOnly cookies + JSON body)."""
    try:
        tokens = await auth_use_cases.login(email=body.email, password=body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_token_cookies(response, tokens)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def refresh(
    body: RefreshRequest,
    response: Response,
    auth_use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> TokenResponse:
    """Rotate refresh token and return a new token pair."""
    try:
        tokens = await auth_use_cases.refresh(refresh_token=body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_token_cookies(response, tokens)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the current authenticated user."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email.address,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )
