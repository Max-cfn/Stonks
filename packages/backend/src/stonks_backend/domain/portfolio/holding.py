"""Holding value object — a position in a financial instrument.

A Holding tracks quantity and average cost for a given ticker, enabling
valuation and P&L calculations against market quotes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from stonks_backend.domain.portfolio.currency import Money
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import InstrumentType, Ticker


class HoldingValidationError(ValueError):
    """Raised when a Holding invariant is violated."""


@dataclass(frozen=True)
class Holding:
    """An investor's position in a single instrument.

    Attributes:
        id: Unique holding identifier.
        user_id: Owner's user identifier.
        ticker: The instrument identifier.
        instrument_type: STOCK, ETF, CRYPTO, BOND, or COMMODITY.
        quantity: Number of units held (can be fractional for some instruments).
        avg_cost: Average purchase price per unit.
        currency: ISO 4217 currency code for cost and valuation.
    """

    id: UUID
    user_id: UUID
    ticker: Ticker
    instrument_type: InstrumentType
    quantity: Decimal
    avg_cost: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise HoldingValidationError(f"Quantity must be non-negative, got {self.quantity}")
        if self.avg_cost < 0:
            raise HoldingValidationError(f"Average cost must be non-negative, got {self.avg_cost}")
        if self.instrument_type is InstrumentType.CRYPTO and not self.ticker.is_crypto:
            raise HoldingValidationError(
                f"Instrument type CRYPTO but ticker {self.ticker} is not a crypto"
            )

    def _validate_quote(self, quote: Quote) -> None:
        """Ensure the quote matches this holding's ticker and currency.

        Raises:
            HoldingValidationError: if ticker or currency mismatch.
        """
        if quote.ticker != self.ticker:
            raise HoldingValidationError(
                f"Quote ticker {quote.ticker} does not match holding ticker {self.ticker}"
            )
        if quote.currency != self.currency:
            raise HoldingValidationError(
                f"Quote currency {quote.currency} does not match holding currency {self.currency}"
            )

    def current_value(self, quote: Quote) -> Money:
        """Compute the current market value of the holding.

        Args:
            quote: A current market quote for this holding's ticker.

        Returns:
            Money representing quantity x quote mid_price.

        Raises:
            HoldingValidationError: if quote ticker or currency mismatch.
        """
        self._validate_quote(quote)
        return Money(self.quantity * quote.mid_price, self.currency)

    def pnl(self, quote: Quote) -> Money:
        """Compute unrealised profit/loss against average cost.

        P&L = (quote.mid_price - avg_cost) x quantity

        Args:
            quote: A current market quote for this holding's ticker.

        Returns:
            Money representing the unrealised gain or loss.

        Raises:
            HoldingValidationError: if quote ticker or currency mismatch.
        """
        self._validate_quote(quote)
        pnl_amount = (quote.mid_price - self.avg_cost) * self.quantity
        return Money(pnl_amount, self.currency)

    def pnl_pct(self, quote: Quote) -> Decimal:
        """Compute unrealised P&L as a percentage of average cost.

        Returns (quote.mid_price - avg_cost) / avg_cost x 100.

        Args:
            quote: A current market quote for this holding's ticker.

        Returns:
            Decimal percentage (e.g. Decimal("5.42") means +5.42%).

        Raises:
            HoldingValidationError: if quote ticker or currency mismatch.
            ZeroDivisionError: if avg_cost is zero.
        """
        self._validate_quote(quote)
        if self.avg_cost == 0:
            raise ZeroDivisionError("Cannot compute P&L% when average cost is zero")
        return (quote.mid_price - self.avg_cost) / self.avg_cost * Decimal("100")
