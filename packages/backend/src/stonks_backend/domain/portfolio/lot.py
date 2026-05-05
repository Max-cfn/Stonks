"""Lot value object — a tax-lot/sub-position within a Holding.

Each Lot represents a single buy or sell event with a specific quantity,
price, and date.  Lots are the basis for calculating realised P&L and
weighted-average cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from stonks_backend.domain.portfolio.currency import Money


class LotValidationError(ValueError):
    """Raised when a Lot invariant is violated."""


@dataclass(frozen=True)
class Lot:
    """A single tax-lot corresponding to a buy or sell.

    Attributes:
        id: Unique lot identifier.
        holding_id: Parent holding this lot belongs to.
        trade_type: 'buy' or 'sell'.
        quantity: Number of units transacted (always positive).
        price: Price per unit (non-negative).
        currency: ISO 4217 currency code.
        date: UTC datetime of the trade (must be timezone-aware).
        fees: Transaction fees paid (default 0).
    """

    id: UUID
    holding_id: UUID
    trade_type: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal
    currency: str
    date: datetime
    fees: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.date.tzinfo is None:
            raise LotValidationError("Lot date must be timezone-aware (UTC)")
        if self.quantity <= 0:
            raise LotValidationError(f"Quantity must be positive, got {self.quantity}")
        if self.price < 0:
            raise LotValidationError(f"Price must be non-negative, got {self.price}")
        if self.fees < 0:
            raise LotValidationError(f"Fees must be non-negative, got {self.fees}")
        if self.trade_type not in ("buy", "sell"):
            raise LotValidationError(
                f"trade_type must be 'buy' or 'sell', got {self.trade_type!r}"
            )

    def cost_basis(self) -> Money:
        """Compute the total cost basis including fees.

        cost_basis = (price x quantity) + fees

        Returns:
            Money representing the total cost of this lot.
        """
        total = self.price * self.quantity + self.fees
        return Money(total, self.currency)

    @property
    def proceeds(self) -> Money:
        """Gross proceeds (price x quantity) without fees."""
        return Money(self.price * self.quantity, self.currency)
