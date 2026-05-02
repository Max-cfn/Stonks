"""Cashflow SQLAlchemy ORM models — mirrors domain entities with encrypted columns.

Sensitive columns (iban, holder_name, raw_label) are stored AES-256-GCM encrypted.
All models use async-compatible patterns.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stonks_backend.infrastructure.persistence.models import Base


class CashflowAccountModel(Base):
    """SQLAlchemy model for the 'cashflow_accounts' table."""

    __tablename__ = "cashflow_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_connector: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_id: Mapped[str] = mapped_column(String(128), nullable=False)
    iban_encrypted: Mapped[str | None] = mapped_column(Text(), nullable=True)
    holder_name_encrypted: Mapped[str | None] = mapped_column(Text(), nullable=True)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="checking")
    account_name: Mapped[str] = mapped_column(String(256), nullable=False, server_default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="EUR")
    current_balance_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=4), nullable=True
    )
    current_balance_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    transactions: Mapped[list[CashflowTransactionModel]] = relationship(
        "CashflowTransactionModel", back_populates="account", cascade="all, delete-orphan"
    )
    balance_snapshots: Mapped[list[CashflowBalanceSnapshotModel]] = relationship(
        "CashflowBalanceSnapshotModel", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "bank_connector", "bank_id", name="uq_user_bank_account"),
    )

    def __repr__(self) -> str:
        return f"<CashflowAccount id={self.id} bank={self.bank_connector}:{self.bank_id}>"


class CashflowTransactionModel(Base):
    """SQLAlchemy model for the 'cashflow_transactions' hypertable."""

    __tablename__ = "cashflow_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashflow_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_tx_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default="")
    raw_label_encrypted: Mapped[str | None] = mapped_column(Text(), nullable=True)
    booking_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    value_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="booked")
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="psd2")
    creditor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    creditor_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    debtor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    debtor_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    account: Mapped[CashflowAccountModel] = relationship(
        "CashflowAccountModel", back_populates="transactions"
    )

    __table_args__ = (
        UniqueConstraint("account_id", "bank_tx_id", name="uq_account_bank_tx"),
    )

    def __repr__(self) -> str:
        return f"<CashflowTransaction id={self.id} amount={self.amount} {self.currency}>"


class CashflowCategoryModel(Base):
    """SQLAlchemy model for the 'cashflow_categories' table."""

    __tablename__ = "cashflow_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False, server_default="other")
    icon: Mapped[str] = mapped_column(String(8), nullable=False, server_default="📦")
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#808080")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )

    def __repr__(self) -> str:
        return f"<CashflowCategory id={self.id} name={self.name}>"


class CategorizationRuleModel(Base):
    """SQLAlchemy model for 'categorization_rules' — regex patterns for auto-categorization."""

    __tablename__ = "categorization_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashflow_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    field: Mapped[str] = mapped_column(String(32), nullable=False, server_default="description")
    is_regex: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("category_id", "pattern", name="uq_category_pattern"),
    )

    def __repr__(self) -> str:
        return f"<CategorizationRule id={self.id} field={self.field} pattern={self.pattern}>"


class CashflowBalanceSnapshotModel(Base):
    """SQLAlchemy model for 'cashflow_balance_snapshots' hypertable."""

    __tablename__ = "cashflow_balance_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashflow_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    balance_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=4), nullable=False
    )
    balance_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="psd2")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=text("now()")
    )

    # Relationship
    account: Mapped[CashflowAccountModel] = relationship(
        "CashflowAccountModel", back_populates="balance_snapshots"
    )

    def __repr__(self) -> str:
        return (
            f"<CashflowBalanceSnapshot id={self.id} balance={self.balance_amount} "
            f"{self.balance_currency}>"
        )
