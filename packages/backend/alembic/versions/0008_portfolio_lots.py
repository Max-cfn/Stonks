"""0008_portfolio_lots — create portfolio_lots table.

Revision ID: 0008_portfolio_lots
Revises: 0007_portfolio_holdings
Create Date: 2026-05-04

Individual buy/sell/dividend lots that make up a holding. Each lot is
linked to a portfolio_holdings row. Tracks trade price, fees, and
optional dividend amounts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_portfolio_lots"
down_revision: str | None = "0007_portfolio_holdings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "holding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolio_holdings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "fees",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dividend_amount", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_lots_holding_date",
        "portfolio_lots",
        ["holding_id", sa.text("date")],
    )


def downgrade() -> None:
    op.drop_index("ix_lots_holding_date", table_name="portfolio_lots")
    op.drop_table("portfolio_lots")
