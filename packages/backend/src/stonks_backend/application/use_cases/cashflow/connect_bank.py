"""ConnectBankAccount — Session flow to connect a user's bank account."""

from __future__ import annotations

from uuid import UUID

from stonks_backend.application.ports.cashflow import BankConnectorPort, CashflowRepositoryPort
from stonks_backend.domain.cashflow.account import Account, AccountStatus


class ConnectBankAccountError(Exception):
    """Raised when bank account connection fails."""


class ConnectBankAccount:
    """Orchestrate the bank connection flow (Enable Banking 2026 JWT + sessions).

    Usage:
        use_case = ConnectBankAccount(bank_connector, cashflow_repo)
        auth_url = await use_case.get_authorization_url(user_id, redirect_uri)
        # User visits auth_url, bank redirects to callback with ?session_id=...
        accounts = await use_case.handle_callback(user_id, session_id)
    """

    def __init__(
        self,
        bank_connector: BankConnectorPort,
        cashflow_repo: CashflowRepositoryPort | None = None,
    ) -> None:
        self._connector = bank_connector
        # Repo is optional: get_authorization_url() doesn't need persistence.
        # handle_callback() and disconnect_bank() will raise if repo is None.
        self._repo = cashflow_repo

    def _require_repo(self) -> CashflowRepositoryPort:
        if self._repo is None:
            raise ConnectBankAccountError(
                "CashflowRepositoryPort is required for this operation. "
                "Pass cashflow_repo to the ConnectBankAccount constructor."
            )
        return self._repo

    async def get_authorization_url(self, user_id: UUID, redirect_uri: str) -> str:
        """Generate the bank authorization URL for a user.

        Returns:
            URL the user must visit to authenticate with their bank.
        """
        return await self._connector.get_authorization_url(user_id, redirect_uri)

    async def handle_callback(self, user_id: UUID, session_id: str) -> list[Account]:
        """Handle the session callback: resolve session, fetch accounts, persist.

        Args:
            user_id: The authenticated Stonks user.
            session_id: The session_id query param from the bank redirect callback.

        Returns:
            List of Account domain objects fetched from the bank and persisted.
        """
        # Step 1: Resolve session → account IDs (stored in Vault by the adapter)
        await self._connector.handle_session_callback(user_id, session_id)

        # Step 2: Fetch accounts from the bank
        accounts = await self._connector.list_accounts(user_id)

        # Step 3: Persist each account
        repo = self._require_repo()
        for account in accounts:
            await repo.save_account(account)

        return accounts

    async def disconnect_bank(self, user_id: UUID, account_id: UUID) -> None:
        """Mark an account as disconnected."""
        repo = self._require_repo()
        account = await repo.get_account(account_id)
        if account is None:
            raise ConnectBankAccountError(f"Account {account_id} not found")
        if account.user_id != user_id:
            raise ConnectBankAccountError("Access denied: account belongs to another user")
        account.status = AccountStatus.DISCONNECTED
        account.touch()
        await repo.save_account(account)
