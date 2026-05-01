"""0002_audit_log — create audit_log hypertable (TimescaleDB).

Revision ID: 0002_audit_log
Revises: 0001_users
Create Date: 2026-04-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_audit_log"
down_revision: str | None = "0001_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the table first
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
    )
    # Convert to TimescaleDB hypertable
    op.execute("SELECT create_hypertable('audit_log', 'ts', if_not_exists => TRUE)")


def downgrade() -> None:
    op.drop_table("audit_log")
