"""Binance WebSocket adapter — Phase 3 stub.

This module is a placeholder for real-time crypto price streaming via
Binance WebSocket (wss://stream.binance.com:9443/ws).

Planned for Phase 3:
    - Subscribe to ticker streams: wss://stream.binance.com:9443/ws/<symbol>@ticker
    - Parse JSON frames into Quote objects
    - Dispatch via callback/handler pattern
    - Reconnection with exponential backoff
    - Heartbeat / ping-pong keepalive

For now, this class simply logs that WebSocket streaming is not yet
implemented and provides the expected interface shape so that callers
can be coded against it without runtime errors.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from stonks_backend.application.ports.portfolio import PriceFeedPort
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Ticker
from stonks_backend.infrastructure.config import Settings

logger = structlog.get_logger(__name__)


class BinanceWebSocketAdapter(PriceFeedPort):
    """Stub adapter for Binance WebSocket real-time price streaming.

    Phase 3 — not yet implemented. All methods are no-ops that log a
    warning and return empty/sentinel values.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the Binance WebSocket adapter stub.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        logger.warning(
            "binance_ws_phase3_stub",
            message="Binance WebSocket adapter is a Phase 3 stub — "
            "real-time streaming not yet implemented.",
        )

    # ── PriceFeedPort implementation (stubs) ─────────────────────────────

    async def get_current(self, ticker: Ticker) -> Quote:
        """REST fallback — not supported by WebSocket adapter.

        Raises:
            NotImplementedError: Always; use CoinGeckoAdapter or YahooFinanceAdapter
                for REST-based quotes.
        """
        raise NotImplementedError(
            "BinanceWebSocketAdapter does not support REST get_current. "
            "Use CoinGeckoAdapter or YahooFinanceAdapter."
        )

    async def get_historical(
        self, ticker: Ticker, since: datetime, until: datetime
    ) -> list[Quote]:
        """Historical data — not supported by WebSocket adapter.

        Raises:
            NotImplementedError: Always; use CoinGeckoAdapter or YahooFinanceAdapter
                for historical data.
        """
        raise NotImplementedError(
            "BinanceWebSocketAdapter does not support historical data. "
            "Use CoinGeckoAdapter or YahooFinanceAdapter."
        )

    async def subscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Subscribe to real-time Binance WebSocket streams.

        Phase 3 stub — logs a warning that WebSocket is not yet implemented.

        Args:
            tickers: The instruments to subscribe to.
        """
        logger.warning(
            "binance_ws_subscribe_not_implemented",
            phase="3",
            tickers=[str(t) for t in tickers],
        )

    async def unsubscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Unsubscribe from real-time Binance WebSocket streams.

        Phase 3 stub — logs a warning that WebSocket is not yet implemented.

        Args:
            tickers: The instruments to unsubscribe from.
        """
        logger.warning(
            "binance_ws_unsubscribe_not_implemented",
            phase="3",
            tickers=[str(t) for t in tickers],
        )
