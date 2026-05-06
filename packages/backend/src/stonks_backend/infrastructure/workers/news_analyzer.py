"""NewsAnalyzer — background worker for periodic RSS news sentiment analysis.

Fetches recent news, classifies sentiment via LLM or keyword fallback,
and persists a NewsDigest. Runs as an asyncio Task in the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog

from stonks_backend.application.ports.portfolio import (
    NewsFeedPort,
    PortfolioRepositoryPort,
)
from stonks_backend.application.use_cases.portfolio.analyze_sentiment import (
    AnalyzeMarketSentiment,
)

logger = structlog.get_logger(__name__)


class NewsAnalyzer:
    """Periodically fetches and analyses financial news sentiment.

    On each cycle:
    1. Fetches recent news articles (last 30 minutes by default).
    2. Analyzes sentiment via LLM Flash or keyword fallback.
    3. Persists a NewsDigest in the repository.

    Errors are logged but do not crash the analyze loop.

    Args:
        news_feed: News aggregation port (RSS, NewsAPI, etc.).
        repo_factory: Async callable that returns a fresh repository instance.
            Each cycle opens and closes its own session.
        interval_minutes: Minutes to wait between analysis cycles (default 15).
    """

    def __init__(
        self,
        news_feed: NewsFeedPort,
        repo_factory: Callable[[], Awaitable[PortfolioRepositoryPort]],
        interval_minutes: int = 15,
    ) -> None:
        self._news_feed = news_feed
        self._repo_factory = repo_factory
        self._interval_minutes = interval_minutes
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Launch the analysis loop as a background asyncio Task.

        Safe to call multiple times — no-op if already running.
        """
        if self._task is not None and not self._task.done():
            logger.warning("news_analyzer_already_running")
            return
        self._task = asyncio.create_task(self._analyze_loop())
        logger.info(
            "news_analyzer_started",
            interval_minutes=self._interval_minutes,
        )

    async def stop(self) -> None:
        """Cancel the analysis loop and wait for graceful shutdown."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("news_analyzer_stopped")

    # ── Analyze loop ──────────────────────────────────────────────────────

    async def _analyze_loop(self) -> None:
        """Main analysis loop — runs until cancelled.

        Each iteration:
        1. Invokes AnalyzeMarketSentiment for the last 30 minutes.
        2. Commits and closes the session.
        3. Sleeps for ``interval_minutes * 60`` seconds.
        """
        while True:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                logger.info("news_analyzer_cancelled")
                raise
            except Exception:
                logger.exception("news_analyzer_cycle_error")

            try:
                await asyncio.sleep(self._interval_minutes * 60)
            except asyncio.CancelledError:
                logger.info("news_analyzer_cancelled_during_sleep")
                raise

    async def _run_cycle(self) -> None:
        """Execute a single analysis cycle: fetch → analyze → persist.

        Uses a 30-minute lookback window. Opens a fresh repo session,
        commits on success, rolls back on failure.
        """
        since = datetime.now(UTC) - timedelta(minutes=30)
        repo = await self._repo_factory()

        try:
            analyzer = AnalyzeMarketSentiment(
                news_feed=self._news_feed,
                repo=repo,
            )
            digest = await analyzer.execute(since=since)

            logger.info(
                "news_analyzer_cycle_done",
                digest_id=str(digest.id),
                overall_label=digest.sentiment_label,
            )
            await repo.commit_and_close()
        except Exception:
            try:
                await repo.rollback_and_close()
            except Exception:
                logger.exception("news_analyzer_rollback_close_error")
            raise
