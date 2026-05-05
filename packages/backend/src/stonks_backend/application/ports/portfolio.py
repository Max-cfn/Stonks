"""Portfolio abstract ports — interfaces for market data, FX, news, and persistence.

All adapters in infrastructure/ must implement these interfaces.
This is the "port" side of the ports & adapters architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Ticker
from stonks_backend.domain.portfolio.trade import Trade

# ═══════════════════════════════════════════════════════════════════════════════
# Data contracts (part of the port — adapters produce/consume these shapes)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class NewsItem:
    """A news article related to a financial instrument.

    Attributes:
        guid: Globally unique identifier for deduplication.
        source: Provider or publisher name (e.g. 'bloomberg', 'reuters').
        title: Article headline.
        url: Link to the full article.
        published_at: UTC datetime of publication.
        summary: Optional short summary or excerpt.
    """

    guid: str
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str | None = None


@dataclass
class PriceAlert:
    """A user-defined price alert on a financial instrument.

    Attributes:
        id: Unique alert identifier.
        user_id: Owner's user identifier.
        ticker: The instrument to watch.
        threshold: Price level that triggers the alert.
        direction: 'above' or 'below' — which side of threshold triggers.
        webhook_url: URL to call when the alert fires.
        triggered: Whether the alert has already fired.
        triggered_at: UTC datetime when the alert fired, or None.
        created_at: UTC datetime when the alert was created.
    """

    id: UUID
    user_id: UUID
    ticker: Ticker
    threshold: Decimal
    direction: str
    webhook_url: str
    triggered: bool
    triggered_at: datetime | None
    created_at: datetime


@dataclass
class NewsDigest:
    """A news article enriched with sentiment analysis.

    Attributes:
        id: Unique digest identifier.
        source: Provider or publisher name.
        title: Article headline.
        url: Link to the full article.
        published_at: UTC datetime of publication.
        sentiment_label: Human-readable sentiment (e.g. 'positive', 'neutral', 'negative').
        sentiment_score: Numeric sentiment score (higher = more positive).
        summary: Short summary or excerpt.
        affected_tickers: Ticker symbols mentioned in the article, if any.
        processed_at: UTC datetime when the digest was created.
    """

    id: UUID
    source: str
    title: str
    url: str
    published_at: datetime
    sentiment_label: str
    sentiment_score: Decimal
    summary: str
    affected_tickers: list[str] | None
    processed_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Abstract ports
# ═══════════════════════════════════════════════════════════════════════════════


class PriceFeedPort(ABC):
    """Abstract interface for real-time & historical market data.

    Implementations:
        - YahooFinanceAdapter
        - AlphaVantageAdapter
        - TwelveDataAdapter
    """

    @abstractmethod
    async def get_current(self, ticker: Ticker) -> Quote:
        """Retrieve the latest available quote for a single ticker.

        Args:
            ticker: The instrument identifier.

        Returns:
            The most recent Quote available from the provider.

        Raises:
            PriceFeedError: If the ticker is unknown or the provider is unreachable.
        """
        ...

    @abstractmethod
    async def get_historical(
        self, ticker: Ticker, since: datetime, until: datetime
    ) -> list[Quote]:
        """Retrieve historical quotes for a ticker in a date range.

        Args:
            ticker: The instrument identifier.
            since: Start of the range (inclusive, UTC).
            until: End of the range (inclusive, UTC).

        Returns:
            Chronologically ordered list of Quotes (oldest first).

        Raises:
            PriceFeedError: If the provider is unreachable or the range is invalid.
        """
        ...

    @abstractmethod
    async def subscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Subscribe to real-time streaming updates for a list of tickers.

        After calling, the adapter starts receiving live quotes (e.g. via
        WebSocket or SSE) and should dispatch them to registered listeners.

        Args:
            tickers: The instruments to subscribe to.
        """
        ...

    @abstractmethod
    async def unsubscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Cancel real-time streaming subscriptions for a list of tickers.

        Args:
            tickers: The instruments to unsubscribe from.
        """
        ...


class FxRatePort(ABC):
    """Abstract interface for foreign exchange rate data.

    Implementations:
        - ExchangeRateApiAdapter
        - OpenExchangeRatesAdapter
    """

    @abstractmethod
    async def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        at: datetime | None = None,
    ) -> Decimal:
        """Retrieve the exchange rate between two currencies.

        Args:
            from_currency: ISO 4217 source currency code.
            to_currency: ISO 4217 target currency code.
            at: Point-in-time for historical rate (None = latest available).

        Returns:
            The exchange rate as Decimal (amount of to_currency per 1 from_currency).

        Raises:
            FxRateError: If the currency pair is unsupported or the provider fails.
        """
        ...

    @abstractmethod
    async def get_history(
        self,
        from_currency: str,
        to_currency: str,
        since: datetime,
        until: datetime,
    ) -> list[tuple[datetime, Decimal]]:
        """Retrieve historical exchange rates in a date range.

        Args:
            from_currency: ISO 4217 source currency code.
            to_currency: ISO 4217 target currency code.
            since: Start of the range (inclusive, UTC).
            until: End of the range (inclusive, UTC).

        Returns:
            Chronologically ordered list of (timestamp, rate) tuples.

        Raises:
            FxRateError: If the currency pair is unsupported or the provider fails.
        """
        ...


class NewsFeedPort(ABC):
    """Abstract interface for financial news aggregation.

    Implementations:
        - NewsApiAdapter
        - GNewsAdapter
    """

    @abstractmethod
    async def fetch_recent(
        self,
        sources: list[str] | None = None,
        since: datetime | None = None,
    ) -> list[NewsItem]:
        """Fetch recent financial news articles.

        Args:
            sources: Optional filter by publisher names (e.g. ['bloomberg', 'reuters']).
            since: Only return articles published after this UTC datetime.

        Returns:
            List of NewsItem, most recent first.
        """
        ...


class PortfolioRepositoryPort(ABC):
    """Abstract interface for portfolio data persistence.

    Implementations:
        - PortfolioSqlRepository (SQLAlchemy async)
    """

    # ── Holdings ──────────────────────────────────────────────────────────

    @abstractmethod
    async def get_holdings(self, user_id: UUID) -> list[Holding]:
        """Retrieve all holdings for a user.

        Args:
            user_id: Owner's user identifier.

        Returns:
            List of Holding objects (empty list if none).
        """
        ...

    @abstractmethod
    async def get_holding(self, holding_id: UUID) -> Holding | None:
        """Retrieve a single holding by ID.

        Args:
            holding_id: Unique holding identifier.

        Returns:
            The Holding, or None if not found.
        """
        ...

    @abstractmethod
    async def save_holding(self, holding: Holding) -> None:
        """Persist a new or updated holding (upsert).

        Args:
            holding: The Holding to save.
        """
        ...

    @abstractmethod
    async def delete_holding(self, holding_id: UUID) -> None:
        """Remove a holding by ID.

        Args:
            holding_id: Unique holding identifier.
        """
        ...

    # ── Trades ────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_trade(self, trade: Trade) -> None:
        """Persist a trade record.

        Args:
            trade: The Trade to save.
        """
        ...

    @abstractmethod
    async def get_trades(
        self,
        holding_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Trade]:
        """Retrieve trades for a holding, optionally filtered by date range.

        Args:
            holding_id: Parent holding identifier.
            since: Inclusive start of date range (UTC).
            until: Inclusive end of date range (UTC).

        Returns:
            Chronologically ordered list of Trades (oldest first).
        """
        ...

    # ── Quotes ────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_quote(self, quote: Quote) -> None:
        """Persist a market quote.

        Args:
            quote: The Quote to save.
        """
        ...

    @abstractmethod
    async def get_quotes(
        self, ticker: Ticker, since: datetime, until: datetime
    ) -> list[Quote]:
        """Retrieve persisted quotes for a ticker in a date range.

        Args:
            ticker: The instrument identifier.
            since: Inclusive start of range (UTC).
            until: Inclusive end of range (UTC).

        Returns:
            Chronologically ordered list of Quotes (oldest first).
        """
        ...

    @abstractmethod
    async def get_latest_quote(self, ticker: Ticker) -> Quote | None:
        """Retrieve the most recent persisted quote for a ticker.

        Args:
            ticker: The instrument identifier.

        Returns:
            The latest Quote, or None if no quote has been persisted.
        """
        ...

    # ── Price alerts ──────────────────────────────────────────────────────

    @abstractmethod
    async def save_alert(self, alert: PriceAlert) -> None:
        """Persist a price alert.

        Args:
            alert: The PriceAlert to save.
        """
        ...

    @abstractmethod
    async def get_alerts(
        self, user_id: UUID, triggered: bool | None = None
    ) -> list[PriceAlert]:
        """Retrieve price alerts for a user.

        Args:
            user_id: Owner's user identifier.
            triggered: If True, only triggered alerts; if False, only pending;
                if None, all alerts.

        Returns:
            List of PriceAlert objects.
        """
        ...

    @abstractmethod
    async def delete_alert(self, alert_id: UUID) -> None:
        """Remove a price alert by ID.

        Args:
            alert_id: Unique alert identifier.
        """
        ...

    @abstractmethod
    async def mark_alert_triggered(self, alert_id: UUID) -> None:
        """Mark a price alert as triggered.

        Args:
            alert_id: Unique alert identifier.
        """
        ...

    # ── News digest ───────────────────────────────────────────────────────

    @abstractmethod
    async def save_news_digest(self, digest: NewsDigest) -> None:
        """Persist a news digest.

        Args:
            digest: The NewsDigest to save.
        """
        ...

    @abstractmethod
    async def get_latest_digest(
        self, user_id: UUID | None = None
    ) -> NewsDigest | None:
        """Retrieve the most recent news digest.

        Args:
            user_id: Optional user identifier to scope digests.

        Returns:
            The latest NewsDigest, or None if none found.
        """
        ...

    # ── Workers helpers ───────────────────────────────────────────────────

    @abstractmethod
    async def get_active_tickers(self) -> list[Ticker]:
        """Return distinct tickers from all holdings across all users.

        Used by background workers (PricePoller) to know which instruments
        to poll for current prices.

        Returns:
            List of unique Ticker objects (empty list if no holdings).
        """
        ...

    @abstractmethod
    async def get_active_user_ids(self) -> list[UUID]:
        """Return distinct user IDs who have holdings or alerts.

        Used by background workers (PricePoller) to scope alert checking
        to users who actually use the platform.

        Returns:
            List of unique user UUIDs (empty list if no users with holdings/alerts).
        """
        ...


__all__ = [
    "FxRatePort",
    "NewsDigest",
    "NewsFeedPort",
    # Data contracts
    "NewsItem",
    "PortfolioRepositoryPort",
    "PriceAlert",
    # Abstract ports
    "PriceFeedPort",
]
