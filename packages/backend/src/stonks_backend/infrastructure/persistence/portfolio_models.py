"""Portfolio SQLAlchemy ORM models — mirrors domain entities for portfolio space.

Models for holdings, lots, quotes (hypertable), alerts, and news digests.
All models use async-compatible SQLAlchemy 2.0 Mapped[] style.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stonks_backend.infrastructure.persistence.models import Base


class PortfolioHoldingModel(Base):
    """SQLAlchemy model for the 'portfolio_holdings' table."""

    __tablename__ = "portfolio_holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker_exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    instrument_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
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

    # Relationships
    lots: Mapped[list[PortfolioLotModel]] = relationship(
        "PortfolioLotModel", back_populates="holding", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "ticker_symbol", "ticker_exchange", name="uq_holding_user_ticker_exchange"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioHolding id={self.id} user={self.user_id} "
            f"ticker={self.ticker_symbol}.{self.ticker_exchange} "
            f"qty={self.quantity} avg_cost={self.avg_cost} {self.currency}>"
        )


class PortfolioLotModel(Base):
    """SQLAlchemy model for the 'portfolio_lots' table."""

    __tablename__ = "portfolio_lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolio_holdings.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(precision=24, scale=8), nullable=False, server_default=text("0"), default=Decimal("0")
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dividend_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=24, scale=8), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )

    # Relationship
    holding: Mapped[PortfolioHoldingModel] = relationship(
        "PortfolioHoldingModel", back_populates="lots"
    )

    __table_args__ = (
        Index("ix_lots_holding_date", "holding_id", text("date")),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioLot id={self.id} holding={self.holding_id} "
            f"type={self.trade_type} qty={self.quantity} @ {self.price} {self.currency}>"
        )


class PortfolioQuoteModel(Base):
    """SQLAlchemy model for the 'portfolio_quotes' hypertable (TimescaleDB).

    No primary key — hypertables do not support traditional PKs.
    """

    __tablename__ = "portfolio_quotes"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticker_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker_exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(precision=24, scale=8), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(precision=24, scale=8), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(precision=30, scale=8), nullable=True)

    __table_args__ = (
        Index("ix_quotes_ticker_time", "ticker_symbol", "ticker_exchange", text("time DESC")),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioQuote time={self.time} ticker={self.ticker_symbol}.{self.ticker_exchange} "
            f"price={self.price} {self.currency}>"
        )


class PortfolioAlertModel(Base):
    """SQLAlchemy model for the 'portfolio_alerts' table."""

    __tablename__ = "portfolio_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker_exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    threshold: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=8), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text(), nullable=False)
    triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    __table_args__ = (
        Index("ix_alerts_user_triggered", "user_id", "triggered"),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioAlert id={self.id} user={self.user_id} "
            f"ticker={self.ticker_symbol}.{self.ticker_exchange} "
            f"dir={self.direction} threshold={self.threshold} triggered={self.triggered}>"
        )


class PortfolioNewsDigestModel(Base):
    """SQLAlchemy model for the 'portfolio_news_digests' table."""

    __tablename__ = "portfolio_news_digests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=4), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    affected_tickers: Mapped[list[str] | None] = mapped_column(ARRAY(Text()), nullable=True)
    guid: Mapped[str] = mapped_column(String(256), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_news_guid", "guid", unique=True),
        Index("ix_news_processed_at", text("processed_at DESC")),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioNewsDigest id={self.id} source={self.source} "
            f"sentiment={self.sentiment_label} guid={self.guid}>"
        )
