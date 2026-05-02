"""SyncTransactions — fetch and persist transactions for a bank account."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from stonks_backend.application.ports.cashflow import (
    BankConnectorPort,
    CashflowRepositoryPort,
)
from stonks_backend.domain.cashflow.account import AccountStatus

logger = logging.getLogger(__name__)


class SyncTransactionsError(Exception):
    """Raised when transaction synchronization fails."""


class SyncTransactions:
    """Fetch latest transactions from the bank and persist them.

    Usage:
        use_case = SyncTransactions(bank_connector, cashflow_repo)
        result = await use_case.sync(account_id)
        print(f"Synced {result.new_transactions} new transactions")
    """

    def __init__(
        self,
        bank_connector: BankConnectorPort,
        cashflow_repo: CashflowRepositoryPort,
    ) -> None:
        self._connector = bank_connector
        self._repo = cashflow_repo

    async def sync(self, account_id: UUID) -> SyncResult:
        """Synchronize transactions for a given account.

        Fetches transactions since last sync (or last 30 days if never synced),
        persists new ones (dedup by bank_tx_id).

        Returns:
            SyncResult with counts of new and total transactions.
        """
        account = await self._repo.get_account(account_id)
        if account is None:
            raise SyncTransactionsError(f"Account {account_id} not found")

        if account.status != AccountStatus.ACTIVE:
            raise SyncTransactionsError(
                f"Cannot sync account with status {account.status}"
            )

        # Determine sync window
        since = account.last_synced_at
        if since is None:
            since = datetime.now(UTC) - timedelta(days=30)
        until = datetime.now(UTC)

        # Fetch from bank
        transactions = await self._connector.fetch_transactions(
            user_id=account.user_id,
            account_id=account_id,
            since=since,
            until=until,
        )

        if not transactions:
            account.last_synced_at = until
            account.touch()
            await self._repo.save_account(account)
            return SyncResult(new=0, total=0)

        # Persist with dedup
        new_count = await self._repo.save_transactions(transactions)

        # Update last_synced_at
        account.last_synced_at = until
        account.touch()
        await self._repo.save_account(account)

        logger.info(
            "Synced transactions for account %s: %d new out of %d fetched",
            account_id, new_count, len(transactions),
        )

        return SyncResult(new=new_count, total=len(transactions))


class SyncResult:
    """Result of a transaction synchronization."""

    __slots__ = ("new", "total")

    def __init__(self, new: int, total: int) -> None:
        self.new = new
        self.total = total
