"""Yahoo Finance market data adapter — implements PriceFeedPort.

Primary path: uses yfinance library via asyncio.to_thread (sync lib).
Fallback: direct httpx calls to Yahoo Finance v8 chart API.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog

from stonks_backend.application.ports.portfolio import PriceFeedPort
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Ticker
from stonks_backend.infrastructure.config import Settings

logger = structlog.get_logger(__name__)

# ── Feature flag: attempt yfinance import ─────────────────────────────────
try:
    import yfinance as yf  # type: ignore[import-untyped]

    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False
    logger.warning(
        "yfinance_not_installed_fallback_httpx",
        hint="pip install yfinance for better Yahoo coverage",
    )


class YahooFinanceError(Exception):
    """Raised when Yahoo Finance API calls fail."""


class YahooFinanceAdapter(PriceFeedPort):
    """Yahoo Finance price feed adapter.

    Two execution paths:
    1. yfinance library (if installed) — richer data, especially for stocks.
    2. httpx → Yahoo v8 chart API — lightweight, no extra dependencies.

    Attributes:
        _timeout: httpx timeout in seconds.
    """

    _base_url: str = "https://query1.finance.yahoo.com/v8/finance/chart"
    _timeout: float = 10.0

    def __init__(self, settings: Settings) -> None:
        """Initialize the Yahoo Finance adapter.

        Args:
            settings: Application settings (unused for free API but kept for
                consistency with other adapters).
        """
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"User-Agent": "Stonks/0.1 (market-data-aggregator)"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── PriceFeedPort implementation ──────────────────────────────────────

    async def get_current(self, ticker: Ticker) -> Quote:
        """Retrieve the latest quote for a ticker.

        Args:
            ticker: The instrument identifier.

        Returns:
            A Quote with price, bid, ask, volume.

        Raises:
            YahooFinanceError: If the ticker is unknown or the API fails.
        """
        symbol = self._to_yahoo_symbol(ticker)

        if _YFINANCE_AVAILABLE:
            return await self._get_current_yfinance(symbol, ticker)
        return await self._get_current_httpx(symbol, ticker)

    async def get_historical(self, ticker: Ticker, since: datetime, until: datetime) -> list[Quote]:
        """Retrieve historical quotes from Yahoo Finance.

        Args:
            ticker: The instrument identifier.
            since: Start of the range (inclusive, UTC).
            until: End of the range (inclusive, UTC).

        Returns:
            Chronologically ordered list of Quotes (oldest first).

        Raises:
            YahooFinanceError: If the API is unreachable or returns no data.
        """
        symbol = self._to_yahoo_symbol(ticker)

        if _YFINANCE_AVAILABLE:
            return await self._get_historical_yfinance(symbol, ticker, since, until)
        return await self._get_historical_httpx(symbol, ticker, since, until)

    async def subscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Yahoo Finance free tier does not support WebSocket streaming.

        Args:
            tickers: The instruments to subscribe to (ignored).
        """
        logger.warning(
            "yahoo_subscribe_realtime_not_supported",
            count=len(tickers),
        )

    async def unsubscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Yahoo Finance free tier does not support WebSocket streaming.

        Args:
            tickers: The instruments to unsubscribe from (ignored).
        """
        logger.warning(
            "yahoo_unsubscribe_realtime_not_supported",
            count=len(tickers),
        )

    # ── yfinance path (sync, wrapped in asyncio.to_thread) ────────────────

    async def _get_current_yfinance(self, symbol: str, ticker: Ticker) -> Quote:
        """Fetch current quote via yfinance library in a thread."""
        try:
            info = await asyncio.to_thread(self._yf_fetch_info, symbol)
        except Exception as exc:
            logger.error("yfinance_info_error", symbol=symbol, error=str(exc))
            raise YahooFinanceError(f"yfinance failed to fetch info for {symbol}: {exc}") from exc

        price_raw = info.get("regularMarketPrice") or info.get("currentPrice") or 0
        bid_raw = info.get("bid")
        ask_raw = info.get("ask")
        volume_raw = info.get("regularMarketVolume") or info.get("volume")

        price = Decimal(str(price_raw))
        if price <= 0:
            raise YahooFinanceError(f"yfinance returned zero price for {symbol}")

        quote = Quote(
            ticker=ticker,
            price=price,
            currency=info.get("currency", "USD"),
            timestamp=datetime.now(UTC),
            source="yahoo",
            bid=Decimal(str(bid_raw)) if bid_raw else None,
            ask=Decimal(str(ask_raw)) if ask_raw else None,
            volume=Decimal(str(volume_raw)) if volume_raw else None,
        )

        logger.info("yfinance_current", ticker=str(ticker), price=str(price))
        return quote

    @staticmethod
    def _yf_fetch_info(symbol: str) -> dict[str, Any]:
        """Sync method to fetch yfinance Ticker info (called via to_thread)."""
        tk = yf.Ticker(symbol)
        return tk.info  # type: ignore[no-any-return]

    async def _get_historical_yfinance(
        self, symbol: str, ticker: Ticker, since: datetime, until: datetime
    ) -> list[Quote]:
        """Fetch historical quotes via yfinance library in a thread."""
        try:
            df = await asyncio.to_thread(self._yf_fetch_history, symbol, since, until)
        except Exception as exc:
            logger.error("yfinance_history_error", symbol=symbol, error=str(exc))
            raise YahooFinanceError(
                f"yfinance failed to fetch history for {symbol}: {exc}"
            ) from exc

        if df is None or df.empty:
            logger.warning("yfinance_no_history", symbol=symbol)
            return []

        quotes: list[Quote] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime().replace(tzinfo=UTC)
            price = Decimal(str(row["Close"]))
            quotes.append(
                Quote(
                    ticker=ticker,
                    price=price,
                    currency="USD",
                    timestamp=ts,
                    source="yahoo",
                )
            )

        logger.info(
            "yfinance_historical",
            ticker=str(ticker),
            count=len(quotes),
        )
        return quotes

    @staticmethod
    def _yf_fetch_history(symbol: str, since: datetime, until: datetime) -> Any:
        """Sync method to fetch yfinance history (called via to_thread)."""
        tk = yf.Ticker(symbol)
        return tk.history(start=since, end=until)  # type: ignore[no-any-return]

    # ── httpx fallback path (Yahoo v8 chart API) ──────────────────────────

    async def _get_current_httpx(self, symbol: str, ticker: Ticker) -> Quote:
        """Fetch current quote via Yahoo v8 chart API."""
        url = f"{self._base_url}/{symbol}"
        params: dict[str, str] = {"interval": "1d", "range": "1d"}

        try:
            client = await self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise YahooFinanceError(f"Yahoo v8 timeout for {symbol}") from None
        except httpx.HTTPStatusError as exc:
            raise YahooFinanceError(
                f"Yahoo v8 HTTP {exc.response.status_code} for {symbol}"
            ) from exc
        except Exception as exc:
            raise YahooFinanceError(f"Yahoo v8 unexpected error for {symbol}: {exc}") from exc

        result = data.get("chart", {}).get("result", [])
        if not result:
            raise YahooFinanceError(f"Yahoo v8 returned no data for {symbol}")

        meta = result[0].get("meta", {})
        price = Decimal(str(meta.get("regularMarketPrice", 0)))
        if price <= 0:
            raise YahooFinanceError(f"Yahoo v8 returned zero price for {symbol}")

        logger.info(
            "yahoo_v8_current",
            ticker=str(ticker),
            price=str(price),
        )

        return Quote(
            ticker=ticker,
            price=price,
            currency=meta.get("currency", "USD"),
            timestamp=datetime.now(UTC),
            source="yahoo",
            bid=Decimal(str(meta["bid"])) if meta.get("bid") else None,
            ask=Decimal(str(meta["ask"])) if meta.get("ask") else None,
            volume=(
                Decimal(str(meta["regularMarketVolume"]))
                if meta.get("regularMarketVolume")
                else None
            ),
        )

    async def _get_historical_httpx(
        self,
        symbol: str,
        ticker: Ticker,
        since: datetime,
        until: datetime,
    ) -> list[Quote]:
        """Fetch historical quotes via Yahoo v8 chart API."""
        url = f"{self._base_url}/{symbol}"
        params = {
            "interval": "1d",
            "period1": str(int(since.timestamp())),
            "period2": str(int(until.timestamp())),
        }

        try:
            client = await self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise YahooFinanceError(f"Yahoo v8 historical timeout for {symbol}") from None
        except httpx.HTTPStatusError as exc:
            raise YahooFinanceError(
                f"Yahoo v8 historical HTTP {exc.response.status_code} for {symbol}"
            ) from exc
        except Exception as exc:
            raise YahooFinanceError(
                f"Yahoo v8 historical unexpected error for {symbol}: {exc}"
            ) from exc

        result = data.get("chart", {}).get("result", [])
        if not result:
            logger.warning("yahoo_v8_no_historical", symbol=symbol)
            return []

        timestamps = result[0].get("timestamp", [])
        quotes_data = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = quotes_data.get("close", [])

        quotes: list[Quote] = []
        for i, ts_unix in enumerate(timestamps):
            ts = datetime.fromtimestamp(ts_unix, tz=UTC)
            close_val = closes[i] if i < len(closes) else None
            if close_val is None:
                continue
            price = Decimal(str(close_val))
            quotes.append(
                Quote(
                    ticker=ticker,
                    price=price,
                    currency="USD",
                    timestamp=ts,
                    source="yahoo",
                )
            )

        logger.info(
            "yahoo_v8_historical",
            ticker=str(ticker),
            count=len(quotes),
        )
        return quotes

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_yahoo_symbol(ticker: Ticker) -> str:
        """Convert a Ticker to a Yahoo Finance symbol.

        Examples:
            Ticker('AAPL', NASDAQ) → 'AAPL'
            Ticker('BTC', CRYPTO)  → 'BTC-USD'

        Args:
            ticker: The instrument identifier.

        Returns:
            The Yahoo Finance symbol string.
        """
        symbol = ticker.symbol
        if ticker.is_crypto:
            return f"{symbol}-USD"
        return symbol
