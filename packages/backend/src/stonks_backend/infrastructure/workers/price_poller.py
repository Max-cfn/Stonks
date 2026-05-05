"""PricePoller — background worker that periodically fetches market prices.

Polls all active tickers from portfolio holdings, persists quotes, and
checks price alerts. Runs as an asyncio Task in the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog

from stonks_backend.application.ports.portfolio import (
    FxRatePort,
    PortfolioRepositoryPort,
    PriceFeedPort,
)
from stonks_backend.application.use_cases.portfolio.manage_alerts import ManageAlerts

logger = structlog.get_logger(__name__)


class PricePoller:
    """Periodically fetches current prices for all active portfolio tickers.

    On each cycle:
    1. Queries distinct tickers from all active holdings.
    2. Fetches the latest price for each ticker via the price feed.
    3. Persists each quote in the repository.
    4. Checks all pending price alerts and fires webhooks.

    Errors are logged but do not crash the poll loop.

    Args:
        repo_factory: Async callable that returns a fresh repository instance.
            Each cycle opens and closes its own session to avoid stale connections.
        price_feed: Market data port for fetching current prices.
        fx_rate: FX rate port (reserved for future cross-currency valuation).
        interval_seconds: Seconds to sleep between full poll cycles (default 60).
    """

    def __init__(
        self,
        repo_factory: Callable[[], Awaitable[PortfolioRepositoryPort]],
        price_feed: PriceFeedPort,
        fx_rate: FxRatePort,
        interval_seconds: int = 60,
    ) -> None:
        self._repo_factory = repo_factory
        self._price_feed = price_feed
        self._fx_rate = fx_rate
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Launch the polling loop as a background asyncio Task.

        Safe to call multiple times — no-op if already running.
        """
        if self._task is not None and not self._task.done():
            logger.warning("price_poller_already_running")
            return
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("price_poller_started", interval_s=self._interval_seconds)

    async def stop(self) -> None:
        """Cancel the polling loop and wait for graceful shutdown."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("price_poller_stopped")

    # ── Poll loop ─────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Main polling loop — runs until cancelled.

        Each iteration:
        1. Opens a fresh repo session.
        2. Collects distinct tickers and user IDs from active holdings.
        3. Fetches current price for each ticker.
        4. Persists quotes.
        5. Checks pending price alerts.
        6. Sleeps for ``interval_seconds``.
        """
        while True:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                logger.info("price_poller_cancelled")
                raise
            except Exception:
                logger.exception("price_poller_cycle_error")

            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                logger.info("price_poller_cancelled_during_sleep")
                raise

    async def _run_cycle(self) -> None:
        """Execute a single poll cycle: fetch prices → persist → check alerts.

        Opens one repo session for the full cycle to keep transactional
        coherence between quote persistence and alert checking.  Commits
        and closes the session in the ``finally`` block.
        """
        repo = await self._repo_factory()
        try:
            await self._do_cycle(repo)
            await repo.commit_and_close()
        except Exception:
            try:
                await repo.rollback_and_close()
            except Exception:
                logger.exception("price_poller_rollback_close_error")
            raise

    async def _do_cycle(self, repo: PortfolioRepositoryPort) -> None:
        """Core cycle logic with an already-open repository.

        Args:
            repo: An active repository instance (session already open).
        """
        # ── 1. Collect tickers and user IDs ───────────────────────────
        tickers = await repo.get_active_tickers()
        user_ids = await repo.get_active_user_ids()

        if not tickers:
            logger.debug("price_poller_no_tickers")
            return

        logger.info(
            "price_poller_cycle_start",
            ticker_count=len(tickers),
            user_count=len(user_ids),
        )

        # ── 2. Fetch & persist quotes ────────────────────────────────
        saved_count = 0
        error_count = 0
        for ticker in tickers:
            try:
                quote = await self._price_feed.get_current(ticker)
                await repo.save_quote(quote)
                saved_count += 1
                logger.debug(
                    "price_poller_quote_saved",
                    ticker=str(ticker),
                    price=str(quote.price),
                    currency=quote.currency,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error_count += 1
                logger.warning(
                    "price_poller_quote_failed",
                    ticker=str(ticker),
                    error=str(exc),
                )

        logger.info(
            "price_poller_quotes_done",
            saved=saved_count,
            errors=error_count,
        )

        # ── 3. Check alerts ──────────────────────────────────────────
        if user_ids:
            try:
                manage_alerts = ManageAlerts(repo)
                triggered = await manage_alerts.check_and_trigger(
                    self._price_feed, user_ids
                )
                if triggered:
                    logger.info(
                        "price_poller_alerts_triggered",
                        count=len(triggered),
                        alert_ids=[str(a.id) for a in triggered],
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "price_poller_alert_check_failed", error=str(exc)
                )
