"""0010_portfolio_alerts — create portfolio_alerts table.

Revision ID: 0010_portfolio_alerts
Revises: 0009_portfolio_quotes
Create Date: 2026-05-04

User-defined price alerts. When the instrument price crosses `threshold`
in the given `direction` (above/below), a webhook is fired. Each alert
is one-shot: `triggered` flips to TRUE after the first fire.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_portfolio_alerts"
down_revision: str | None = "0009_portfolio_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("ticker_exchange", sa.String(32), nullable=True),
        sa.Column("threshold", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column(
            "triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        "ix_alerts_user_triggered",
        "portfolio_alerts",
        ["user_id", "triggered"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_user_triggered", table_name="portfolio_alerts")
    op.drop_table("portfolio_alerts")
