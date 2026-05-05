"""0011_portfolio_news — create portfolio_news_digests table.

Revision ID: 0011_portfolio_news
Revises: 0010_portfolio_alerts
Create Date: 2026-05-04

Aggregated financial news digests with sentiment scoring. Linked to
instruments via `affected_tickers` array. Deduplicated by `guid` (source-
provided unique identifier).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_portfolio_news"
down_revision: str | None = "0010_portfolio_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_news_digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sentiment_label", sa.String(16), nullable=False),
        sa.Column("sentiment_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "affected_tickers",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column("guid", sa.String(256), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_news_guid",
        "portfolio_news_digests",
        ["guid"],
        unique=True,
    )
    op.create_index(
        "ix_news_processed_at",
        "portfolio_news_digests",
        [sa.text("processed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_news_processed_at", table_name="portfolio_news_digests")
    op.drop_index("ix_news_guid", table_name="portfolio_news_digests")
    op.drop_table("portfolio_news_digests")
