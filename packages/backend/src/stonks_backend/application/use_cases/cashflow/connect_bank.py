"""ConnectBankAccount — Session flow to connect a user's bank account."""

from __future__ import annotations

import logging
from uuid import UUID

from stonks_backend.application.ports.cashflow import BankConnectorPort, CashflowRepositoryPort
from stonks_backend.domain.cashflow.account import Account, AccountStatus
from stonks_backend.infrastructure.bank_connectors.bank_registry import BankRegistry

logger = logging.getLogger(__name__)


class ConnectBankAccountError(Exception):
    """Raised when bank account connection fails."""


class ConnectBankAccount:
    """Orchestrate the bank connection flow (Enable Banking 2026 JWT + sessions).

    Usage:
        use_case = ConnectBankAccount(bank_connector, cashflow_repo, bank_registry)
        auth_url = await use_case.get_authorization_url(user_id, redirect_uri, bank_id="lcl")
        # User visits auth_url, bank redirects to callback with ?code=...
        accounts = await use_case.handle_callback(user_id, code)
    """

    def __init__(
        self,
        bank_connector: BankConnectorPort,
        cashflow_repo: CashflowRepositoryPort | None = None,
        bank_registry: BankRegistry | None = None,
    ) -> None:
        self._connector = bank_connector
        # Repo is optional: get_authorization_url() doesn't need persistence.
        # handle_callback() and disconnect_bank() will raise if repo is None.
        self._repo = cashflow_repo
        self._registry = bank_registry

    def _require_repo(self) -> CashflowRepositoryPort:
        if self._repo is None:
            raise ConnectBankAccountError(
                "CashflowRepositoryPort is required for this operation. "
                "Pass cashflow_repo to the ConnectBankAccount constructor."
            )
        return self._repo

    async def get_authorization_url(
        self,
        user_id: UUID,
        redirect_uri: str,
        bank_id: str | None = None,
    ) -> str:
        """Generate the bank authorization URL for a user.

        Args:
            user_id: The authenticated Stonks user.
            redirect_uri: URL where the bank redirects the user after auth.
            bank_id: Bank identifier from the registry (e.g. "lcl"). If None, uses defaults.

        Returns:
            URL the user must visit to authenticate with their bank.
        """
        aspsp_name = None
        aspsp_country = "FR"

        if bank_id and self._registry:
            bank = self._registry.get(bank_id)
            if bank is None:
                raise ConnectBankAccountError(f"Unknown bank: {bank_id}")
            if not bank.supported:
                raise ConnectBankAccountError(f"Bank {bank.name} is not yet supported")
            aspsp_name = bank.connector_config.get("aspsp_name")
            aspsp_country = bank.connector_config.get("aspsp_country", "FR")
            # Store for handle_callback to use when persisting accounts
            self._pending_bank_name = bank.name
        else:
            self._pending_bank_name = ""

        return await self._connector.get_authorization_url(
            user_id=user_id,
            redirect_uri=redirect_uri,
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country,
        )

    async def handle_callback(self, user_id: UUID, code: str) -> list[Account]:
        """Exchange code for session, fetch accounts, and persist them.

        Args:
            user_id: The authenticated Stonks user.
            code: The authorization code from Enable Banking callback.

        Returns:
            List of Account domain objects fetched from the bank and persisted.
        """
        # Step 1: Exchange code for session (accounts stored in Vault by adapter)
        await self._connector.handle_session_callback(user_id, code)

        # Step 2: Fetch accounts from the bank
        accounts = await self._connector.list_accounts(user_id)

        # Step 3: Apply bank_name and persist each account
        repo = self._require_repo()
        bank_name = getattr(self, "_pending_bank_name", "")
        for account in accounts:
            if bank_name:
                account.bank_name = bank_name
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
