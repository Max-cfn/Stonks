"""0007_portfolio_holdings — create portfolio_holdings table.

Revision ID: 0007_portfolio_holdings
Revises: 0006_cashflow_balance_snapshots
Create Date: 2026-05-04

Stores current holdings: which instruments a user owns, quantity, and
average cost basis. One row per user/ticker/exchange tuple (unique).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_portfolio_holdings"
down_revision: str | None = "0006_cashflow_balance_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("ticker_exchange", sa.String(32), nullable=True),
        sa.Column("instrument_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("avg_cost", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "ticker_symbol",
            "ticker_exchange",
            name="uq_holding_user_ticker_exchange",
        ),
    )


def downgrade() -> None:
    op.drop_table("portfolio_holdings")
