"""Quote value object — a price snapshot for a ticker at a point in time.

Represents a market data quote with optional bid/ask/volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from stonks_backend.domain.portfolio.ticker import Ticker


@dataclass(frozen=True)
class Quote:
    """Immutable price quote for a financial instrument.

    Attributes:
        ticker: The instrument identifier.
        price: Mid or last traded price.
        currency: ISO 4217 currency code.
        timestamp: UTC datetime of the quote (must be timezone-aware).
        source: Provider or source identifier (e.g. 'yahoo', 'alpha_vantage').
        bid: Optional bid price.
        ask: Optional ask price.
        volume: Optional 24h or session volume.
    """

    ticker: Ticker
    price: Decimal
    currency: str
    timestamp: datetime
    source: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: Decimal | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Quote timestamp must be timezone-aware (UTC required)")
        if self.price <= 0:
            raise ValueError(f"Quote price must be positive, got {self.price}")
        if self.bid is not None and self.bid <= 0:
            raise ValueError(f"Bid price must be positive, got {self.bid}")
        if self.ask is not None and self.ask <= 0:
            raise ValueError(f"Ask price must be positive, got {self.ask}")
        if self.volume is not None and self.volume < 0:
            raise ValueError(f"Volume must be non-negative, got {self.volume}")
        if not self.source.strip():
            raise ValueError("Quote source must not be empty")

    @property
    def spread(self) -> Decimal | None:
        """Bid-ask spread (ask - bid), or None if either side is missing."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def mid_price(self) -> Decimal:
        """Midpoint between bid and ask if both present, otherwise last price."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / Decimal("2")
        return self.price

    @property
    def age_seconds(self) -> float:
        """Age of the quote relative to now (UTC), in seconds."""
        now = datetime.now(UTC)
        return (now - self.timestamp).total_seconds()
