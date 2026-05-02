"""0003_cashflow_accounts — create cashflow_accounts table.

Revision ID: 0003_cashflow_accounts
Revises: 0002_audit_log
Create Date: 2026-05-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_cashflow_accounts"
down_revision: str | None = "0002_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cashflow_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("bank_connector", sa.String(64), nullable=False),
        sa.Column("bank_id", sa.String(128), nullable=False),
        sa.Column("iban_encrypted", sa.Text(), nullable=True),
        sa.Column("holder_name_encrypted", sa.Text(), nullable=True),
        sa.Column("account_type", sa.String(32), nullable=False, server_default="checking"),
        sa.Column("account_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("current_balance_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("current_balance_currency", sa.String(3), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
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
        sa.UniqueConstraint("user_id", "bank_connector", "bank_id", name="uq_user_bank_account"),
    )


def downgrade() -> None:
    op.drop_table("cashflow_accounts")
