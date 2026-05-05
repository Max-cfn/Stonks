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
    """A user-defined price alert on a financial instrument."""

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
    """A news article enriched with sentiment analysis."""

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
    """Abstract interface for real-time & historical market data."""

    @abstractmethod
    async def get_current(self, ticker: Ticker) -> Quote:
        """Retrieve the latest available quote for a single ticker."""
        ...

    @abstractmethod
    async def get_historical(self, ticker: Ticker, since: datetime, until: datetime) -> list[Quote]:
        """Retrieve historical quotes for a ticker in a date range."""
        ...

    @abstractmethod
    async def subscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Subscribe to real-time streaming updates."""
        ...

    @abstractmethod
    async def unsubscribe_realtime(self, tickers: list[Ticker]) -> None:
        """Cancel real-time streaming subscriptions."""
        ...

    async def close(self) -> None:  # noqa: B027
        """Release resources (no-op by default)."""
        pass


class FxRatePort(ABC):
    """Abstract interface for foreign exchange rate data."""

    @abstractmethod
    async def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        at: datetime | None = None,
    ) -> Decimal:
        """Retrieve the exchange rate between two currencies."""
        ...

    @abstractmethod
    async def get_history(
        self,
        from_currency: str,
        to_currency: str,
        since: datetime,
        until: datetime,
    ) -> list[tuple[datetime, Decimal]]:
        """Retrieve historical exchange rates in a date range."""
        ...

    async def close(self) -> None:  # noqa: B027
        """Release resources (no-op by default)."""
        pass


class NewsFeedPort(ABC):
    """Abstract interface for financial news aggregation."""

    @abstractmethod
    async def fetch_recent(
        self,
        sources: list[str] | None = None,
        since: datetime | None = None,
    ) -> list[NewsItem]:
        """Fetch recent financial news articles."""
        ...

    async def close(self) -> None:  # noqa: B027
        """Release resources (no-op by default)."""
        pass


class PortfolioRepositoryPort(ABC):
    """Abstract interface for portfolio data persistence."""

    # ── Holdings ──────────────────────────────────────────────────────────

    @abstractmethod
    async def get_holdings(self, user_id: UUID) -> list[Holding]:
        """Retrieve all holdings for a user."""
        ...

    @abstractmethod
    async def get_holding(self, holding_id: UUID) -> Holding | None:
        """Retrieve a single holding by ID."""
        ...

    @abstractmethod
    async def save_holding(self, holding: Holding) -> None:
        """Persist a new or updated holding (upsert)."""
        ...

    @abstractmethod
    async def delete_holding(self, holding_id: UUID) -> None:
        """Remove a holding by ID."""
        ...

    # ── Trades ────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_trade(self, trade: Trade) -> None:
        """Persist a trade record."""
        ...

    @abstractmethod
    async def get_trades(
        self,
        holding_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Trade]:
        """Retrieve trades for a holding, optionally filtered by date range."""
        ...

    # ── Quotes ────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_quote(self, quote: Quote) -> None:
        """Persist a market quote."""
        ...

    @abstractmethod
    async def get_quotes(self, ticker: Ticker, since: datetime, until: datetime) -> list[Quote]:
        """Retrieve persisted quotes for a ticker in a date range."""
        ...

    @abstractmethod
    async def get_latest_quote(self, ticker: Ticker) -> Quote | None:
        """Retrieve the most recent persisted quote for a ticker."""
        ...

    # ── Price alerts ──────────────────────────────────────────────────────

    @abstractmethod
    async def save_alert(self, alert: PriceAlert) -> None:
        """Persist a price alert."""
        ...

    @abstractmethod
    async def get_alerts(self, user_id: UUID, triggered: bool | None = None) -> list[PriceAlert]:
        """Retrieve price alerts for a user."""
        ...

    @abstractmethod
    async def delete_alert(self, alert_id: UUID) -> None:
        """Remove a price alert by ID."""
        ...

    @abstractmethod
    async def mark_alert_triggered(self, alert_id: UUID) -> None:
        """Mark a price alert as triggered."""
        ...

    # ── News digest ───────────────────────────────────────────────────────

    @abstractmethod
    async def save_news_digest(self, digest: NewsDigest) -> None:
        """Persist a news digest."""
        ...

    @abstractmethod
    async def get_latest_digest(self, user_id: UUID | None = None) -> NewsDigest | None:
        """Retrieve the most recent news digest."""
        ...

    # ── Workers helpers ───────────────────────────────────────────────────

    @abstractmethod
    async def get_active_tickers(self) -> list[Ticker]:
        """Return distinct tickers from all holdings across all users."""
        ...

    @abstractmethod
    async def get_active_user_ids(self) -> list[UUID]:
        """Return distinct user IDs who have holdings or alerts."""
        ...

    async def aclose(self) -> None:  # noqa: B027
        """Close the underlying database session (no-op by default)."""
        pass

    async def commit_and_close(self) -> None:  # noqa: B027
        """Commit pending changes and close the session (no-op by default)."""
        pass


__all__ = [
    "FxRatePort",
    "NewsDigest",
    "NewsFeedPort",
    "NewsItem",
    "PortfolioRepositoryPort",
    "PriceAlert",
    "PriceFeedPort",
]
