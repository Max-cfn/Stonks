"""0013_cashflow_account_bank_name — add bank_name column to cashflow_accounts.

Revision ID: 0013_cashflow_account_bank_name
Revises: 0012_portfolio_quotes_index
Create Date: 2026-05-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_cashflow_account_bank_name"
down_revision: str | None = "0012_portfolio_quotes_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cashflow_accounts",
        sa.Column("bank_name", sa.String(128), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("cashflow_accounts", "bank_name")
