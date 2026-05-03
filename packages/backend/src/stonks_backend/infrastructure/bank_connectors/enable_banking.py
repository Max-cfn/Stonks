"""EnableBankingAdapter — PSD2 bank connector via Enable Banking API.

Implements BankConnectorPort using Enable Banking's OAuth2 PKCE flow.
Uses Vault for token storage (never in DB). Auto-refreshes expired tokens.

Enable Banking API docs: https://enablebanking.com/docs/
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from stonks_backend.application.ports.cashflow import BankConnectorPort
from stonks_backend.domain.cashflow.account import Account, AccountStatus, AccountType
from stonks_backend.domain.cashflow.balance import BalanceSnapshot
from stonks_backend.domain.cashflow.iban import IBAN
from stonks_backend.domain.cashflow.money import Money
from stonks_backend.domain.cashflow.transaction import TransactionId
from stonks_backend.domain.cashflow.transaction_entity import (
    Transaction,
    TransactionSource,
    TransactionStatus,
)
from stonks_backend.infrastructure.security.vault_client import VaultClient

logger = logging.getLogger(__name__)

# Enable Banking API base URL
ENABLE_BANKING_API = "https://api.enablebanking.com"
ENABLE_BANKING_AUTH = "https://enablebanking.com/auth"

# Required PSD2 scopes
ENABLE_SCOPES = ["accounts", "balances", "transactions"]


class EnableBankingError(Exception):
    """Raised when Enable Banking API returns an error."""


class EnableBankingTokenError(EnableBankingError):
    """Raised when OAuth token exchange/refresh fails."""


class EnableBankingAdapter(BankConnectorPort):
    """PSD2 bank connector using Enable Banking (OAuth2 PKCE).

    Architecture:
        - OAuth2 PKCE flow: code_verifier → code_challenge (SHA256)
        - Tokens stored in Vault under stonks/bank/<user_id>
        - Auto-refresh on 401
    """

    VAULT_PATH_PREFIX = "stonks/bank"

    def __init__(
        self,
        vault: VaultClient,
        client_id: str,
        client_secret: str | None = None,
        sandbox: bool = True,
    ) -> None:
        self._vault = vault
        self._client_id = client_id
        self._client_secret = client_secret
        self._sandbox = sandbox
        self._api_base = "https://api.sandbox.enablebanking.com" if sandbox else ENABLE_BANKING_API
        self._auth_base = (
            "https://auth.sandbox.enablebanking.com" if sandbox else ENABLE_BANKING_AUTH
        )
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    # ── OAuth2 PKCE Flow ───────────────────────────────────────────

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a PKCE code_verifier (128 chars, unreserved)."""
        token = secrets.token_bytes(96)
        return base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")

    @staticmethod
    def _compute_code_challenge(verifier: str) -> str:
        """Compute PKCE code_challenge = base64url(sha256(verifier))."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    async def get_authorization_url(self, user_id: UUID, redirect_uri: str) -> str:
        """Generate PKCE challenge and return the authorization URL."""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._compute_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)

        # Store code_verifier and state in Vault
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        await self._vault.write_secret(
            vault_path,
            {
                "code_verifier": code_verifier,
                "state": state,
                "redirect_uri": redirect_uri,
            },
        )

        from urllib.parse import urlencode

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(ENABLE_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._auth_base}/oauth/authorize?{urlencode(params)}"

    async def exchange_code_for_token(self, user_id: UUID, code: str, redirect_uri: str) -> None:
        """Exchange authorization code for access/refresh tokens, store in Vault."""
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        code_verifier = await self._vault.read_secret(vault_path, "code_verifier")
        if not code_verifier:
            code_verifier = self._generate_code_verifier()

        return await self._token_request(
            user_id,
            grant_type="authorization_code",
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

    # ── Token Management ───────────────────────────────────────────

    async def _token_request(self, user_id: UUID, **kwargs: str) -> None:
        """Execute a token exchange/refresh request and store tokens in Vault."""
        body: dict[str, str] = {"client_id": self._client_id, **kwargs}
        if self._client_secret:
            body["client_secret"] = self._client_secret

        try:
            response = await self._http.post(f"{self._auth_base}/oauth/token", data=body)
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as exc:
            raise EnableBankingTokenError(
                f"Token request failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        now = datetime.now(UTC)
        expires_at = int(now.timestamp()) + token_data.get("expires_in", 3600)

        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        await self._vault.write_secret(
            vault_path,
            {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token", ""),
                "expires_at": str(expires_at),
                "token_type": token_data.get("token_type", "Bearer"),
            },
        )

    async def _get_valid_access_token(self, user_id: UUID) -> str:
        """Return a valid access token, refreshing if expired."""
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        access_token = await self._vault.read_secret(vault_path, "access_token")
        expires_at_str = await self._vault.read_secret(vault_path, "expires_at")
        refresh_token = await self._vault.read_secret(vault_path, "refresh_token")

        if not access_token:
            raise EnableBankingTokenError("No access token found for user")

        if expires_at_str:
            expires_at = int(expires_at_str)
            if datetime.now(UTC).timestamp() > expires_at - 300:
                if not refresh_token:
                    raise EnableBankingTokenError("Token expired and no refresh token")
                await self._token_request(
                    user_id,
                    grant_type="refresh_token",
                    refresh_token=refresh_token,
                )
                access_token = await self._vault.read_secret(vault_path, "access_token")
                if not access_token:
                    raise EnableBankingTokenError("Failed to get refreshed access token")

        return access_token

    # ── API Calls ──────────────────────────────────────────────────

    async def _api_get(self, user_id: UUID, path: str) -> Any:
        """Authenticated GET to Enable Banking API with auto-retry on 401."""
        return await self._api_request_with_retry(user_id, "GET", path)

    async def _api_request_with_retry(
        self, user_id: UUID, method: str, path: str, retry: bool = True
    ) -> Any:
        """Execute API request; if 401, refresh token and retry once."""
        token = await self._get_valid_access_token(user_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        resp = await self._http.request(method, f"{self._api_base}{path}", headers=headers)

        if resp.status_code == 401 and retry:
            logger.info("Enable Banking: 401, refreshing token and retrying")
            vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
            refresh_token = await self._vault.read_secret(vault_path, "refresh_token")
            if refresh_token:
                await self._token_request(
                    user_id,
                    grant_type="refresh_token",
                    refresh_token=refresh_token,
                )
                return await self._api_request_with_retry(user_id, method, path, retry=False)

        resp.raise_for_status()
        return resp.json()

    # ── BankConnectorPort Implementation ──────────────────────────

    async def list_accounts(self, user_id: UUID) -> list[Account]:
        """Fetch all bank accounts for a connected user."""
        try:
            data = await self._api_get(user_id, "/v2/accounts")
        except httpx.HTTPStatusError as exc:
            raise EnableBankingError(
                f"Failed to fetch accounts: {exc.response.status_code}"
            ) from exc

        accounts: list[Account] = []
        now = datetime.now(UTC)

        for item in data.get("accounts", []):
            iban = None
            if iban_str := item.get("iban"):
                iban = IBAN.try_parse(iban_str)

            current_balance = None
            balance_data = item.get("balances", [{}])
            if balance_data and balance_data[0].get("balanceAmount"):
                ba = balance_data[0]
                try:
                    current_balance = Money(
                        str(ba["balanceAmount"]["amount"]),
                        ba["balanceAmount"]["currency"],
                    )
                except (KeyError, ValueError):
                    pass

            account = Account(
                id=UUID(item.get("uid", "")),  # Use bank's UID
                user_id=user_id,
                bank_connector="enable_banking",
                bank_id=item.get("bankId", ""),
                iban=iban,
                holder_name=item.get("ownerName"),
                account_type=self._map_account_type(item.get("accountType", {}).get("type")),
                account_name=item.get("name") or item.get("product", "Compte"),
                currency=item.get("currency", "EUR"),
                current_balance=current_balance,
                last_synced_at=now,
                status=AccountStatus.ACTIVE,
            )
            accounts.append(account)

        return accounts

    async def fetch_transactions(
        self,
        user_id: UUID,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Transaction]:
        """Fetch transactions for a specific account, paginated."""
        from urllib.parse import urlencode

        continuation_token: str | None = None
        transactions: list[Transaction] = []

        while True:
            url_path = f"/v2/accounts/{account_id}/transactions"
            params: dict[str, str] = {}
            if continuation_token:
                params["continuation_token"] = continuation_token
            if since:
                params["date_from"] = since.strftime("%Y-%m-%d")
            if until:
                params["date_to"] = until.strftime("%Y-%m-%d")
            if params:
                url_path = f"{url_path}?{urlencode(params)}"

            data = await self._api_get(user_id, url_path)

            for item in data.get("transactions", []):
                transactions.append(self._parse_transaction(item, account_id))

            continuation_token = data.get("continuation_token")
            if not continuation_token:
                break

        return transactions

    async def get_balances(self, user_id: UUID) -> list[BalanceSnapshot]:
        """Fetch current balances for all connected accounts."""
        data = await self._api_get(user_id, "/v2/balances")
        snapshots: list[BalanceSnapshot] = []
        now = datetime.now(UTC)

        for item in data.get("balances", []):
            bal = item.get("balanceAmount", {})
            if not bal:
                continue
            try:
                money = Money(str(bal["amount"]), bal["currency"])
                snapshots.append(
                    BalanceSnapshot(
                        account_id=UUID(item["accountId"]),
                        balance=money,
                        currency=bal["currency"],
                        timestamp=now,
                        source="psd2",
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue

        return snapshots

    # ── Parsers ───────────────────────────────────────────────────

    def _parse_transaction(self, item: dict[str, Any], account_id: UUID) -> Transaction:
        amount_data = item.get("transactionAmount", {})
        amount = Money(
            str(amount_data.get("amount", "0")),
            amount_data.get("currency", "EUR"),
        )
        desc_lines = item.get("remittanceInformationUnstructuredArray", [])
        description = (
            " ".join(desc_lines)
            if desc_lines
            else (item.get("remittanceInformationUnstructured", ""))
        )
        creditor = item.get("creditor", {}) or {}
        debtor = item.get("debtor", {}) or {}

        return Transaction(
            id=TransactionId(item.get("transactionId", "") or TransactionId.generate().value),
            account_id=account_id,
            bank_tx_id=item.get("entryReference") or item.get("transactionId"),
            amount=amount,
            currency=amount.currency,
            description=description,
            booking_date=self._parse_date(item.get("bookingDate")),
            value_date=self._parse_date(item.get("valueDate")),
            status=TransactionStatus.BOOKED,
            source=TransactionSource.PSD2,
            creditor_name=creditor.get("name"),
            creditor_iban=creditor.get("iban"),
            debtor_name=debtor.get("name"),
            debtor_iban=debtor.get("iban"),
        )

    @staticmethod
    def _map_account_type(account_type: str | None) -> AccountType:
        if not account_type:
            return AccountType.CHECKING
        mapping = {
            "current": AccountType.CHECKING,
            "savings": AccountType.SAVINGS,
            "creditCard": AccountType.CREDIT_CARD,
            "loan": AccountType.LOAN,
        }
        return mapping.get(account_type.lower(), AccountType.OTHER)

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    async def close(self) -> None:
        await self._http.aclose()
