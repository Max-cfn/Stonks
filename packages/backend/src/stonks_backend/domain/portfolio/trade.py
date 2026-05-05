"""Trade value object — a recorded transaction on a Holding.

A Trade is the persistent record of a BUY, SELL, or DIVIDEND event.
It carries the same data as a Lot but uses a different enum for trade_type
and adds optional notes and dividend_amount fields.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class TradeType(enum.Enum):
    """Classification of a trade."""

    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"


class TradeValidationError(ValueError):
    """Raised when a Trade invariant is violated."""


@dataclass(frozen=True)
class Trade:
    """A recorded trade on a holding.

    Attributes:
        id: Unique trade identifier.
        holding_id: Parent holding this trade belongs to.
        trade_type: BUY, SELL, or DIVIDEND.
        quantity: Number of units transacted (positive).
        price: Price per unit (non-negative; zero for dividend).
        currency: ISO 4217 currency code.
        date: UTC datetime of the trade (must be timezone-aware).
        fees: Transaction fees paid (default 0).
        notes: Optional free-text notes.
        dividend_amount: Per-unit or total dividend amount (DIVIDEND only).
    """

    id: UUID
    holding_id: UUID
    trade_type: TradeType
    quantity: Decimal
    price: Decimal
    currency: str
    date: datetime
    fees: Decimal = Decimal("0")
    notes: str | None = None
    dividend_amount: Decimal | None = None

    def __post_init__(self) -> None:
        if self.date.tzinfo is None:
            raise TradeValidationError("Trade date must be timezone-aware (UTC)")
        if self.quantity <= 0:
            raise TradeValidationError(f"Quantity must be positive, got {self.quantity}")
        if self.trade_type is TradeType.DIVIDEND:
            if self.price != Decimal("0"):
                raise TradeValidationError(
                    f"Price must be 0 for DIVIDEND trades, got {self.price}"
                )
            if self.dividend_amount is not None and self.dividend_amount < 0:
                raise TradeValidationError(
                    f"Dividend amount must be non-negative, got {self.dividend_amount}"
                )
        else:
            if self.price < 0:
                raise TradeValidationError(f"Price must be non-negative, got {self.price}")
        if self.fees < 0:
            raise TradeValidationError(f"Fees must be non-negative, got {self.fees}")
