"""0004_cashflow_transactions — create cashflow_transactions hypertable (TimescaleDB).

Revision ID: 0004_cashflow_transactions
Revises: 0003_cashflow_accounts
Create Date: 2026-05-02

Note: FK to cashflow_categories is added in 0005 (table created after this one).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_cashflow_transactions"
down_revision: str | None = "0003_cashflow_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cashflow_transactions",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cashflow_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("bank_tx_id", sa.String(128), nullable=True, index=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_label_encrypted", sa.Text(), nullable=True),
        sa.Column("booking_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="booked"),
        sa.Column("source", sa.String(16), nullable=False, server_default="psd2"),
        sa.Column("creditor_name", sa.String(256), nullable=True),
        sa.Column("creditor_iban", sa.String(34), nullable=True),
        sa.Column("debtor_name", sa.String(256), nullable=True),
        sa.Column("debtor_iban", sa.String(34), nullable=True),
        # category_id FK added in 0005 via ALTER TABLE
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Deduplication: one bank_tx_id per account (where bank_tx_id is not null)
        sa.UniqueConstraint("account_id", "bank_tx_id", "created_at", name="uq_account_bank_tx"),
        # TimescaleDB: partition column must be in PK
        sa.PrimaryKeyConstraint("id", "created_at"),
    )
    # Convert to TimescaleDB hypertable on created_at
    op.execute(
        "SELECT create_hypertable('cashflow_transactions', 'created_at', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("cashflow_transactions")
