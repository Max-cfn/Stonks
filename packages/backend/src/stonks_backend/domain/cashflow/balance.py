"""BalanceSnapshot — a point-in-time balance record for an account."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from stonks_backend.domain.cashflow.money import Money


@dataclass(kw_only=True, slots=True)
class BalanceSnapshot:
    """A snapshot of an account's balance at a specific timestamp.

    Used for historical balance tracking and TWR/MWR calculations.
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    account_id: uuid.UUID
    balance: Money
    currency: str  # Redundant with balance.currency for query convenience
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "psd2"  # "psd2", "scraping", "manual"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.balance, Money):
            raise TypeError(f"balance must be a Money instance, got {type(self.balance)}")
        if self.currency != self.balance.currency:
            raise ValueError(
                f"BalanceSnapshot currency ({self.currency}) must match balance currency "
                f"({self.balance.currency})"
            )
