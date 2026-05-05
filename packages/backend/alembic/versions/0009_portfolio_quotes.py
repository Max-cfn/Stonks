"""0009_portfolio_quotes — create portfolio_quotes hypertable (TimescaleDB).

Revision ID: 0009_portfolio_quotes
Revises: 0008_portfolio_lots
Create Date: 2026-05-04

Time-series table for instrument price quotes (OHLC, bid/ask, volume).
Converted to a TimescaleDB hypertable on `time` with 1-day chunks.
Composite index on (ticker_symbol, ticker_exchange, time DESC) for
efficient latest-price lookups per ticker.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_portfolio_quotes"
down_revision: str | None = "0008_portfolio_lots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No PK — TimescaleDB hypertables work best without a traditional PK
    op.create_table(
        "portfolio_quotes",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("ticker_exchange", sa.String(32), nullable=True),
        sa.Column("price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("bid", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("ask", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("volume", sa.Numeric(precision=30, scale=8), nullable=True),
    )
    # Convert to TimescaleDB hypertable on `time`, 1-day chunks
    op.execute(
        "SELECT create_hypertable('portfolio_quotes', 'time', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )
    # Composite index for efficient latest-price lookups per ticker
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_quotes_ticker_time "
        "ON portfolio_quotes (ticker_symbol, ticker_exchange, time DESC)"
    )


def downgrade() -> None:
    op.drop_table("portfolio_quotes")
