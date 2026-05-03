"""Push notification token registration endpoint — POST /users/push-token."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.domain.user import User
from stonks_backend.infrastructure.database import get_session
from stonks_backend.infrastructure.persistence.push_token_repo import PushTokenRepository
from stonks_backend.interfaces.api.dependencies.auth import get_current_user
from stonks_backend.interfaces.api.schemas import ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


class PushTokenRequest(BaseModel):
    token: str = Field(..., description="Expo push token")
    platform: str = Field(default="expo", description="Push platform (expo)")


class PushTokenResponse(BaseModel):
    status: str = "registered"
    token: str


@router.post(
    "/push-token",
    response_model=PushTokenResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
)
async def register_push_token(
    body: PushTokenRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushTokenResponse:
    """Register or update the Expo push token for the authenticated user."""
    repo = PushTokenRepository(session)
    await repo.upsert(
        user_id=current_user.id,
        token=body.token,
        platform=body.platform,
    )
    await session.commit()

    logger.info(
        "Push token registered for user %s: platform=%s token_trunc=%s...",
        current_user.id,
        body.platform,
        body.token[:12],
    )

    return PushTokenResponse(status="registered", token=body.token)
