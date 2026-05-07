"""0006_cashflow_balance_snapshots — create cashflow_balance_snapshots hypertable.

Revision ID: 0006_cashflow_balance_snapshots
Revises: 0005_cashflow_categories
Create Date: 2026-05-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_cashflow_balance_snapshots"
down_revision: str | None = "0005_cashflow_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cashflow_balance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cashflow_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("balance_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("balance_currency", sa.String(3), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="psd2"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # TimescaleDB requires partition column in PK
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    # Hypertable on timestamp
    op.execute(
        "SELECT create_hypertable('cashflow_balance_snapshots', 'timestamp', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("cashflow_balance_snapshots")
