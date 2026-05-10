"""Auth routes — /auth/register, /auth/login, /auth/refresh, /auth/me, /auth/logout."""

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
        samesite="lax",
        secure=False,  # True in production with HTTPS
        max_age=900,  # 15 minutes
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=604800,  # 7 days
        path="/auth/refresh",
    )


def _delete_token_cookies(response: Response) -> None:
    """Clear JWT token cookies to log the user out."""
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/auth/refresh",
        httponly=True,
        samesite="lax",
        secure=False,
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
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    auth_use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> TokenResponse:
    """Rotate refresh token and return a new token pair.

    Accepte le refresh_token depuis le body JSON OU le cookie HttpOnly.
    """
    # Lire depuis le cookie d'abord (le frontend envoie credentials:include)
    refresh_token = request.cookies.get("refresh_token")
    # Sinon depuis le body
    if not refresh_token and body and body.refresh_token:
        refresh_token = body.refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing (provide in body or cookie)",
        )

    try:
        tokens = await auth_use_cases.refresh(refresh_token=refresh_token)
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


@router.post(
    "/logout",
    responses={401: {"model": ErrorResponse}},
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clear authentication cookies to log the user out.

    Requires authentication. The access and refresh token cookies
    are deleted, which effectively terminates the session.
    """
    logger.info("User %s logging out", current_user.id)
    _delete_token_cookies(response)
    return {"status": "ok"}
