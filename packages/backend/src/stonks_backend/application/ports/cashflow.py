"""Cashflow-specific abstract ports — interfaces for bank connectors, categorization, and repository.

All adapters must implement these interfaces. This is the "port" side of ports & adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from stonks_backend.domain.cashflow.account import Account
from stonks_backend.domain.cashflow.balance import BalanceSnapshot
from stonks_backend.domain.cashflow.category import Category
from stonks_backend.domain.cashflow.transaction_entity import Transaction


class BankConnectorPort(ABC):
    """Abstract interface for connecting to a bank and fetching data.

    Implementations:
        - EnableBankingAdapter (PSD2 via Enable Banking 2026 JWT + sessions)
        - ScrapingFallbackAdapter (feature-flagged, OFF by default)
    """

    @abstractmethod
    async def get_authorization_url(self, user_id: UUID, redirect_uri: str) -> str:
        """Return the authorization URL the user must visit to authenticate with their bank."""
        ...

    @abstractmethod
    async def handle_session_callback(self, user_id: UUID, code: str) -> None:
        """Exchange callback code for a session, store account IDs in Vault.

        Replaces the old OAuth2 exchange_code_for_token flow (Enable Banking 2026).
        """
        ...

    @abstractmethod
    async def list_accounts(self, user_id: UUID) -> list[Account]:
        """Fetch all bank accounts for a connected user."""
        ...

    @abstractmethod
    async def fetch_transactions(
        self,
        user_id: UUID,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Transaction]:
        """Fetch transactions for a specific account, optionally in a date range."""
        ...

    @abstractmethod
    async def get_balances(self, user_id: UUID) -> list[BalanceSnapshot]:
        """Fetch current balances for all connected accounts."""
        ...


class CategorizationPort(ABC):
    """Abstract interface for transaction categorization.

    Implementations:
        - RuleBasedCategorizer (regex patterns on label/amount/creditor)
        - LLMCategorizer (DeepSeek V4 Flash via OpenRouter, fallback)
    """

    @abstractmethod
    async def categorize(self, transaction: Transaction) -> Category | None:
        """Categorize a single transaction. Returns None if unable to categorize."""
        ...

    @abstractmethod
    async def categorize_batch(self, transactions: list[Transaction]) -> dict[int, Category]:
        """Categorize a batch of transactions. Returns dict[index] -> Category."""
        ...


class CashflowRepositoryPort(ABC):
    """Abstract interface for cashflow data persistence.

    Implementations:
        - CashflowSqlRepository (SQLAlchemy async + AES-256-GCM on sensitive columns)
    """

    @abstractmethod
    async def save_account(self, account: Account) -> None:
        """Persist a new or updated account."""
        ...

    @abstractmethod
    async def get_account(self, account_id: UUID) -> Account | None:
        """Retrieve a single account by ID."""
        ...

    @abstractmethod
    async def get_accounts_by_user(self, user_id: UUID) -> list[Account]:
        """Retrieve all accounts for a user."""
        ...

    @abstractmethod
    async def save_transactions(self, transactions: list[Transaction]) -> int:
        """Persist transactions (insert or ignore by bank_tx_id). Returns count inserted."""
        ...

    @abstractmethod
    async def get_transactions(
        self,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Transaction]:
        """Fetch paginated transactions for an account, optionally filtered by date range."""
        ...

    @abstractmethod
    async def save_balance_snapshot(self, snapshot: BalanceSnapshot) -> None:
        """Persist a balance snapshot."""
        ...

    @abstractmethod
    async def get_balance_history(
        self,
        account_id: UUID,
        since: datetime,
        until: datetime,
    ) -> list[BalanceSnapshot]:
        """Retrieve balance snapshots for an account in a time range."""
        ...

    @abstractmethod
    async def save_category(self, category: Category) -> None:
        """Persist a category (system or user-defined)."""
        ...

    @abstractmethod
    async def get_default_categories(self) -> list[Category]:
        """Retrieve all system default categories."""
        ...

    @abstractmethod
    async def get_categories_by_user(self, user_id: UUID) -> list[Category]:
        """Retrieve all system + user-defined categories for a user."""
        ...

    @abstractmethod
    async def get_category(self, category_id: UUID) -> Category | None:
        """Retrieve a single category by ID."""
        ...
