"""CoinGecko market data adapter — implements PriceFeedPort.

Free tier: ~10-30 calls/min, no API key required for basic endpoints.
Respects rate limits with a cooldown between calls.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

import httpx
import structlog

from stonks_backend.application.ports.portfolio import PriceFeedPort
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Ticker
from stonks_backend.infrastructure.config import Settings

logger = structlog.get_logger(__name__)


class CoinGeckoError(Exception):
    """Raised when CoinGecko API calls fail."""


# ── Mapping Ticker symbol → CoinGecko coin_id ─────────────────────────────
_COINGECKO_ID_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "TRX": "tron",
    "NEAR": "near",
    "ALGO": "algorand",
    "XTZ": "tezos",
    "APT": "aptos",
    "SUI": "sui",
    "SEI": "sei-network",
    "ARB": "arbitrum",
    "OP": "optimism",
    "INJ": "injective-protocol",
    "RNDR": "render-token",
    "FIL": "filecoin",
    "HBAR": "hedera-hashgraph",
    "QNT": "quant-network",
}


class CoinGeckoAdapter(PriceFeedPort):
    """Price feed adapter backed by CoinGecko free API.

    Attributes:
        _base_url: API base URL.
        _timeout: httpx timeout in seconds.
        _cooldown: Minimum delay between calls in seconds.
    """

    _base_url: str = "https://api.coingecko.com/api/v3"
    _timeout: float = 10.0
    _cooldown: float = 1.5
    _last_call: ClassVar[float] = 0.0

    def __init__(self, settings: Settings) -> None:
        """Initialize the CoinGecko adapter.

        Args:
            settings: Application settings (unused for free tier but kept for
                extensibility — API key pro tier would use it).
        """
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    # ── Cooldown management ───────────────────────────────────────────────

    @staticmethod
    async def _respect_rate_limit() -> None:
        """Enforce cooldown between CoinGecko API calls."""
        now = asyncio.get_event_loop().time()
        elapsed = now - CoinGeckoAdapter._last_call
        if elapsed < CoinGeckoAdapter._cooldown:
            wait = CoinGeckoAdapter._cooldown - elapsed
            logger.debug("coingecko_rate_limit_wait", wait_seconds=round(wait, 2))
            await asyncio.sleep(wait)
        CoinGeckoAdapter._last_call = asyncio.get_event_loop().time()

    # ── HTTP client management ────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── PriceFeedPort implementation ──────────────────────────────────────

    async def get_current(self, ticker: Ticker) -> Quote:
        """Retrieve the latest quote for a crypto ticker.

        Args:
            ticker: The instrument identifier (crypto only).

        Returns:
            A Quote with price, bid, ask from CoinGecko.

        Raises:
            CoinGeckoError: If the ticker is unsupported or the API is unreachable.
        """
        coin_id = self._map_ticker(ticker)
        url = f"{self._base_url}/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd,eur"}

        await self._respect_rate_limit()

        try:
            client = await self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            logger.error("coingecko_timeout", coin_id=coin_id, url=url)
            raise CoinGeckoError(f"CoinGecko timeout for {coin_id}") from None
        except httpx.HTTPStatusError as exc:
            logger.error(
                "coingecko_http_error",
                coin_id=coin_id,
                status=exc.response.status_code,
            )
            if exc.response.status_code == 429:
                raise CoinGeckoError(
                    f"CoinGecko rate limited for {coin_id}"
                ) from exc
            raise CoinGeckoError(
                f"CoinGecko HTTP {exc.response.status_code} for {coin_id}"
            ) from exc
        except Exception as exc:
            logger.error("coingecko_unexpected_error", coin_id=coin_id, error=str(exc))
            raise CoinGeckoError(
                f"CoinGecko unexpected error for {coin_id}: {exc}"
            ) from exc

        if coin_id not in data:
            raise CoinGeckoError(
                f"CoinGecko returned no data for coin_id={coin_id}; "
                f"keys={list(data.keys())}"
            )

        coin_data = data[coin_id]
        price_usd = Decimal(str(coin_data.get("usd", 0)))
        price_eur = Decimal(str(coin_data.get("eur", 0)))

        if price_usd <= 0:
            raise CoinGeckoError(f"CoinGecko returned zero/negative price for {coin_id}")

        # CoinGecko simple/price doesn't provide bid/ask — use ±0.05% spread fallback
        bid = (price_usd * Decimal("0.9995")).quantize(Decimal("0.01"))
        ask = (price_usd * Decimal("1.0005")).quantize(Decimal("0.01"))

        logger.info(
            "coingecko_current_price",
            ticker=str(ticker),
            coin_id=coin_id,
            price_usd=str(price_usd),
            price_eur=str(price_eur),
        )

        return Quote(
            ticker=ticker,
            price=price_usd,
            currency="USD",
            timestamp=datetime.now(UTC),
            source="coingecko",
            bid=bid,
            ask=ask,
            volume=None,
        )

    async def get_historical(
        self, ticker: Ticker, since: datetime, until: datetime
    ) -> list[Quote]:
        """Retrieve historical quotes from CoinGecko.

        Args:
            ticker: The instrument identifier (crypto only).
            since: Start of the range (inclusive, UTC).
            until: End of the range (inclusive, UTC).

        Returns:
            Chronologically ordered list of Quotes (oldest first).

        Raises:
            CoinGeckoError: If the API is unreachable or returns no data.
        """
        coin_id = self._map_ticker(ticker)
        url = f"{self._base_url}/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": int(since.timestamp()),
            "to": int(until.timestamp()),
        }

        await self._respect_rate_limit()

        try:
            client = await self._get_client()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            logger.error("coingecko_historical_timeout", coin_id=coin_id)
            raise CoinGeckoError(
                f"CoinGecko historical timeout for {coin_id}"
            ) from None
        except httpx.HTTPStatusError as exc:
            logger.error(
                "coingecko_historical_http_error",
                coin_id=coin_id,
                status=exc.response.status_code,
            )
            raise CoinGeckoError(
                f"CoinGecko historical HTTP {exc.response.status_code} for {coin_id}"
            ) from exc
        except Exception as exc:
            logger.error(
                "coingecko_historical_unexpected_error",
                coin_id=coin_id,
                error=str(exc),
            )
            raise CoinGeckoError(
                f"CoinGecko historical unexpected error for {coin_id}: {exc}"
            ) from exc

        prices = data.get("prices", [])
        if not prices:
            logger.warning("coingecko_no_historical_data", coin_id=coin_id)
            return []

        quotes: list[Quote] = []
        for entry in prices:
            ts_ms, price_val = entry[0], entry[1]
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
            price = Decimal(str(price_val))
            quotes.append(
                Quote(
                    ticker=ticker,
                    price=price,
                    currency="USD",
                    timestamp=ts,
                    source="coingecko",
                )
            )

        logger.info(
            "coingecko_historical",
            ticker=str(ticker),
            coin_id=coin_id,
            count=len(quotes),
        )
        return quotes

    async def subscribe_realtime(self, tickers: list[Ticker]) -> None:
        """CoinGecko free tier does not support WebSocket streams.

        Args:
            tickers: The instruments to subscribe to (ignored).
        """
        logger.warning(
            "coingecko_subscribe_realtime_not_supported",
            count=len(tickers),
        )

    async def unsubscribe_realtime(self, tickers: list[Ticker]) -> None:
        """CoinGecko free tier does not support WebSocket streams.

        Args:
            tickers: The instruments to unsubscribe from (ignored).
        """
        logger.warning(
            "coingecko_unsubscribe_realtime_not_supported",
            count=len(tickers),
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _map_ticker(self, ticker: Ticker) -> str:
        """Resolve a Ticker to a CoinGecko coin_id.

        Args:
            ticker: The instrument identifier.

        Returns:
            The CoinGecko coin_id string.

        Raises:
            CoinGeckoError: If the ticker symbol is not in the mapping.
        """
        coin_id = _COINGECKO_ID_MAP.get(ticker.symbol)
        if coin_id is None:
            raise CoinGeckoError(
                f"Unsupported ticker for CoinGecko: {ticker.symbol}. "
                f"Supported: {sorted(_COINGECKO_ID_MAP.keys())}"
            )
        return coin_id
