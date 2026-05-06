"""Asynchronous background workers — price polling and news sentiment analysis.

Both workers run as asyncio Tasks within the FastAPI lifespan and are fully optional.
If the database is unreachable, they log a warning and the application continues.
"""

from __future__ import annotations

from stonks_backend.infrastructure.workers.news_analyzer import NewsAnalyzer
from stonks_backend.infrastructure.workers.price_poller import PricePoller

__all__ = [
    "NewsAnalyzer",
    "PricePoller",
]
