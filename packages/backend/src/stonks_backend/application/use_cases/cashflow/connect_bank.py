"""ConnectBankAccount — OAuth flow to connect a user's bank account."""

from __future__ import annotations

import uuid
from uuid import UUID

from stonks_backend.application.ports.cashflow import BankConnectorPort, CashflowRepositoryPort
from stonks_backend.domain.cashflow.account import Account, AccountStatus


class ConnectBankAccountError(Exception):
    """Raised when bank account connection fails."""


class ConnectBankAccount:
    """Orchestrate the OAuth flow for connecting a bank account.

    Usage:
        use_case = ConnectBankAccount(bank_connector, cashflow_repo)
        auth_url = await use_case.get_authorization_url(user_id, redirect_uri)
        # User visits auth_url, bank redirects to callback with ?code=...
        accounts = await use_case.handle_callback(user_id, code, redirect_uri)
    """

    def __init__(
        self,
        bank_connector: BankConnectorPort,
        cashflow_repo: CashflowRepositoryPort,
    ) -> None:
        self._connector = bank_connector
        self._repo = cashflow_repo

    async def get_authorization_url(self, user_id: UUID, redirect_uri: str) -> str:
        """Generate the OAuth authorization URL for a user.

        Returns:
            URL the user must visit to authenticate with their bank.
        """
        return await self._connector.get_authorization_url(user_id, redirect_uri)

    async def handle_callback(
        self, user_id: UUID, code: str, redirect_uri: str
    ) -> list[Account]:
        """Exchange OAuth code for token, fetch accounts, and persist them.

        Args:
            user_id: The authenticated Stonks user.
            code: The OAuth2 authorization code from the bank callback.
            redirect_uri: The same redirect_uri used in the authorization request.

        Returns:
            List of Account domain objects fetched from the bank and persisted.
        """
        # Step 1: Exchange code for tokens (stored in Vault by the adapter)
        await self._connector.exchange_code_for_token(user_id, code, redirect_uri)

        # Step 2: Fetch accounts from the bank
        accounts = await self._connector.list_accounts(user_id)

        # Step 3: Persist each account
        for account in accounts:
            await self._repo.save_account(account)

        return accounts

    async def disconnect_bank(self, user_id: UUID, account_id: UUID) -> None:
        """Mark an account as disconnected."""
        account = await self._repo.get_account(account_id)
        if account is None:
            raise ConnectBankAccountError(f"Account {account_id} not found")
        if account.user_id != user_id:
            raise ConnectBankAccountError("Access denied: account belongs to another user")
        account.status = AccountStatus.DISCONNECTED
        account.touch()
        await self._repo.save_account(account)
