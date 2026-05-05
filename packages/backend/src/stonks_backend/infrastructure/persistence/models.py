"""SQLAlchemy declarative Base and core models.

Importing this module ensures all ORM models are registered on Base.metadata
— required for Alembic autogenerate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


class UserModel(Base):
    """SQLAlchemy model for the 'users' table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserModel id={self.id} email={self.email}>"


class AuditLogModel(Base):
    """SQLAlchemy model for the audit_log hypertable (TimescaleDB)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} ts={self.ts}>"


# ── Lazy model registration (avoids circular imports) ────────────────────
# Import the module (not individual symbols) so that all models are
# registered on Base.metadata — required for Alembic autogenerate.
# Using `import module` instead of `from module import Symbol` avoids
# circular import errors between models.py ↔ portfolio_models.py.

import stonks_backend.infrastructure.persistence.cashflow_models  # noqa: E402, F401
import stonks_backend.infrastructure.persistence.portfolio_models  # noqa: E402, F401
