"""PushToken SQLAlchemy model — stores Expo push notification tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stonks_backend.infrastructure.persistence.models import Base


class PushTokenModel(Base):
    """Stores Expo push tokens for push notification delivery."""

    __tablename__ = "push_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_push_token_user_platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(
        String(32), default="expo", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PushTokenModel id={self.id} user_id={self.user_id} "
            f"platform={self.platform}>"
        )
