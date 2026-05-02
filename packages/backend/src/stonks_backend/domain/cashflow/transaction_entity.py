"""Transaction domain entity — a single financial movement on an account.

A Transaction is identified by a unique TransactionId, optionally linked to a bank's native ID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from stonks_backend.domain.cashflow.money import Money
from stonks_backend.domain.cashflow.transaction import TransactionId


class TransactionStatus(StrEnum):
    PENDING = "pending"
    BOOKED = "booked"
    REVERSED = "reversed"


class TransactionSource(StrEnum):
    """Origin of the transaction data."""

    PSD2 = "psd2"
    SCRAPING = "scraping"
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"


@dataclass(kw_only=True, slots=True)
class Transaction:
    """A financial transaction on a bank/cash account.

    Domain entity — identity defined by `id` (TransactionId).
    Deduplication key from the bank: `bank_tx_id` (bank's own transaction ID).
    """

    id: TransactionId = field(default_factory=TransactionId.generate)
    account_id: uuid.UUID
    bank_tx_id: str | None = None  # Bank-native ID for dedup
    amount: Money
    currency: str  # Redundant with amount.currency for query convenience
    description: str = ""  # Cleaned label (bank raw_label is encrypted in DB)
    booking_date: datetime | None = None
    value_date: datetime | None = None
    status: TransactionStatus = TransactionStatus.BOOKED
    source: TransactionSource = TransactionSource.PSD2
    creditor_name: str | None = None
    creditor_iban: str | None = None  # Not encrypted — used for auto-categorization
    debtor_name: str | None = None
    debtor_iban: str | None = None
    category_id: uuid.UUID | None = None  # Assigned by categorizer
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Money):
            raise TypeError(f"amount must be a Money instance, got {type(self.amount)}")
        if self.currency != self.amount.currency:
            raise ValueError(
                f"Transaction currency ({self.currency}) must match amount currency "
                f"({self.amount.currency})"
            )

    def assign_category(self, category_id: uuid.UUID) -> None:
        """Assign this transaction to a category."""
        self.category_id = category_id
