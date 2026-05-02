"""Account domain entity — a bank/cash account belonging to a user.

An Account holds the bank identifier, IBAN, holder name, type, and current balance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from stonks_backend.domain.cashflow.iban import IBAN
from stonks_backend.domain.cashflow.money import Money


class AccountType(StrEnum):
    """Type of financial account."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    LOAN = "loan"
    OTHER = "other"


class AccountStatus(StrEnum):
    """Status of a bank account synced in Stonks."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass(kw_only=True, slots=True)
class Account:
    """A bank/cash account aggregated from PSD2 or manual entry.

    This is a domain entity with identity (id).
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    bank_connector: str  # e.g. "enable_banking", "scraping_fallback"
    bank_id: str  # Bank's internal identifier (e.g. Enable Banking bank UUID)
    iban: IBAN | None = None
    holder_name: str | None = None
    account_type: AccountType = AccountType.CHECKING
    account_name: str = ""  # User-friendly name (e.g. "Compte courant LCL")
    currency: str = "EUR"
    current_balance: Money | None = None
    last_synced_at: datetime | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.iban is not None and not isinstance(self.iban, IBAN):
            raise TypeError(f"iban must be an IBAN instance, got {type(self.iban)}")
        if self.current_balance is not None and not isinstance(self.current_balance, Money):
            raise TypeError(
                f"current_balance must be a Money instance, got {type(self.current_balance)}"
            )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)
