"""0012_portfolio_quotes_index — minimal migration, index already created in 0009.

Revision ID: 0012_portfolio_quotes_index
Revises: 0011_portfolio_news
Create Date: 2026-05-04

The composite index on (ticker_symbol, ticker_exchange, time DESC) was
created inline in 0009_portfolio_quotes. This migration is a no-op
placeholder to keep the chain contiguous and reserve the slot for any
future index additions (e.g. GIST on ticker_symbol for full-text search,
or BRIN on time for large-scale compression).

No downgrade needed — nothing was created.
"""
from typing import Sequence, Union

revision: str = "0012_portfolio_quotes_index"
down_revision: str | None = "0011_portfolio_news"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reserved for future index additions on portfolio_quotes or related tables.
    # Current indexes are already covered in 0009 (hypertable composite index)
    # and 0011 (news dedup + processed_at).
    pass


def downgrade() -> None:
    pass
