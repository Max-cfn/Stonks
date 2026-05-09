"""EnableBankingAdapter — PSD2 bank connector via Enable Banking API (2026 JWT).

Implements BankConnectorPort using Enable Banking's 2026 API:
- Auth: JWT RS256 signed with application private key (no OAuth2 PKCE)
- Flow: POST /auth → redirect → session callback → accounts
- Endpoint: api.enablebanking.com (single production endpoint)

Enable Banking 2026 API docs: https://enablebanking.com/docs/
"""

from __future__ import annotations

import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt

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

# Enable Banking 2026 API — single endpoint
ENABLE_BANKING_API = "https://api.enablebanking.com"

# JWT TTL: 24h (max allowed by Enable Banking)
JWT_TTL_SECONDS = 86400


class EnableBankingError(Exception):
    """Raised when Enable Banking API returns an error."""


class EnableBankingTokenError(EnableBankingError):
    """Raised when JWT generation or session retrieval fails."""


class EnableBankingAdapter(BankConnectorPort):
    """PSD2 bank connector using Enable Banking 2026 (JWT + sessions).

    Architecture:
        - Auth: JWT RS256 signed with application private key (PKCS#8 PEM)
        - Sessions: POST /auth → redirect user → callback with ?session_id=
        - Data: GET /sessions/{id} → account IDs → GET /accounts/{id}/*
        - Credentials stored in Vault under stonks/bank/<user_id>
        - No long-lived tokens stored at Enable Banking side
    """

    VAULT_PATH_PREFIX = "stonks/bank"

    def __init__(
        self,
        vault: VaultClient,
        key_path: str,
        application_id: str,
    ) -> None:
        """Initialize the Enable Banking 2026 adapter.

        Args:
            vault: VaultClient for secure credential storage.
            key_path: Path to the RSA private key (PKCS#8 PEM format).
            application_id: Enable Banking Application ID (UUID v4).
        """
        self._vault = vault
        self._key_path = key_path
        self._application_id = application_id
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

        # JWT cache — regenerate if expiring in < 5 minutes
        self._jwt_cache: str | None = None
        self._jwt_expires_at: float = 0.0

    # ── JWT Generation ─────────────────────────────────────────────

    def _load_private_key(self) -> str:
        """Load the RSA private key from disk."""
        import os

        path = self._key_path
        # Support relative paths relative to the package root
        if not os.path.isabs(path):
            # Try relative to /opt/stonks/packages/backend/
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", path.lstrip("./")),
                os.path.join("/opt/stonks", path.lstrip("./")),
                path,
            ]
            for candidate in candidates:
                if os.path.isfile(candidate):
                    path = candidate
                    break

        with open(path) as f:
            return f.read()

    def _generate_jwt(self) -> str:
        """Generate a JWT signed with the application private key (RS256).

        Format:
            Header: {"typ":"JWT","alg":"RS256","kid":"<application_id>"}
            Body:   {"iss":"enablebanking.com","aud":"api.enablebanking.com",
                     "iat":<ts>,"exp":<ts+86400>}

        Cached for the JWT lifetime (24h) — regenerated if expiring in < 5 min.
        """
        now = time.time()
        if self._jwt_cache and now < self._jwt_expires_at - 300:
            return self._jwt_cache

        private_key = self._load_private_key()
        iat = int(now)
        exp = iat + JWT_TTL_SECONDS

        payload = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": exp,
        }
        headers = {
            "typ": "JWT",
            "alg": "RS256",
            "kid": self._application_id,
        }

        token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
        self._jwt_cache = token
        self._jwt_expires_at = exp
        return token

    # ── OAuth 2026 Session Flow ────────────────────────────────────

    async def get_authorization_url(
        self,
        user_id: UUID,
        redirect_uri: str,
        aspsp_name: str | None = None,
        aspsp_country: str = "FR",
    ) -> str:
        """Initiate the Enable Banking 2026 session flow.

        POST /auth with JWT → returns {url, authorization_id}.
        Stores authorization_id in Vault for callback verification.

        Args:
            user_id: The authenticated Stonks user.
            redirect_uri: URL where Enable Banking redirects the user after auth.
            aspsp_name: Optional bank name filter (e.g. "Boursorama").
            aspsp_country: Two-letter country code (default "FR").

        Returns:
            URL the user must visit to authenticate with their bank.
        """
        jwt_token = self._generate_jwt()
        state = secrets.token_urlsafe(32)

        # Build /auth request body
        body: dict[str, Any] = {
            "access": {
                "valid_until": (datetime.now(UTC) + timedelta(days=90)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
            "aspsp": {"name": "Nordea", "country": "FI"},
            "state": state,
            "redirect_url": redirect_uri,
            "psu_type": "personal",
            "language": "fr",
        }

        try:
            resp = await self._http.post(
                f"{ENABLE_BANKING_API}/auth",
                json=body,
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except httpx.HTTPStatusError as exc:
            raise EnableBankingError(
                f"POST /auth failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        auth_url = str(data["url"])
        authorization_id = data.get("authorization_id")
        if not auth_url:
            raise EnableBankingError("POST /auth response missing 'url' field")

        # Store authorization_id + state in Vault
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        await self._vault.write_secret(
            vault_path,
            {
                "authorization_id": authorization_id or "",
                "state": state,
                "redirect_uri": redirect_uri,
            },
        )

        logger.info("Enable Banking 2026: auth URL generated for user %s", user_id)
        return auth_url
    async def handle_session_callback(self, user_id: UUID, code: str) -> None:
        """Handle the callback from Enable Banking after user auth.

        Enable Banking redirects to our callback URL with ?code=XXX.
        We exchange this code for a session via POST /sessions to get accounts.

        Args:
            user_id: The authenticated Stonks user.
            code: The code query param from the redirect callback.
        """
        jwt_token = self._generate_jwt()

        try:
            resp = await self._http.post(
                f"{ENABLE_BANKING_API}/sessions",
                json={"code": code},
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise EnableBankingError(
                f"POST /sessions failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        # Extract account IDs from session response
        account_ids: list[str] = []
        for item in data.get("accounts", []):
            if acc_id := item.get("uid") or item.get("id") or item.get("account_id"):
                account_ids.append(str(acc_id))

        if not account_ids:
            raise EnableBankingError(
                f"Session returned no account IDs. "
                "Ensure the user completed the authentication flow."
            )

        session_id = data.get("session_id", "")

        # Store session data + account IDs in Vault
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        await self._vault.write_secret(
            vault_path,
            {
                "session_id": session_id,
                "account_ids": ",".join(account_ids),
                "session_status": data.get("status", "authorized"),
            },
        )

        logger.info(
            "Enable Banking 2026: session %s resolved for user %s (%d accounts)",
            session_id,
            user_id,
            len(account_ids),
        )

    # ── API Helpers ────────────────────────────────────────────────

    async def _api_get(self, path: str) -> Any:
        """Authenticated GET to Enable Banking 2026 API with JWT."""
        jwt_token = self._generate_jwt()
        resp = await self._http.get(
            f"{ENABLE_BANKING_API}{path}",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def _api_post(self, path: str, body: dict[str, Any]) -> Any:
        """Authenticated POST to Enable Banking 2026 API with JWT."""
        jwt_token = self._generate_jwt()
        resp = await self._http.post(
            f"{ENABLE_BANKING_API}{path}",
            json=body,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── BankConnectorPort Implementation ──────────────────────────

    async def list_accounts(self, user_id: UUID) -> list[Account]:
        """Fetch all bank accounts for a connected user.

        Iterates over account_ids stored in Vault (from session callback),
        calls GET /accounts/{id}/details for each.
        """
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        account_ids_raw = await self._vault.read_secret(vault_path, "account_ids")
        if not account_ids_raw:
            raise EnableBankingError(
                f"No account IDs found for user {user_id}. "
                "Ensure the session callback completed successfully."
            )

        account_ids = [aid.strip() for aid in account_ids_raw.split(",") if aid.strip()]
        accounts: list[Account] = []
        now = datetime.now(UTC)

        for acc_id in account_ids:
            try:
                data = await self._api_get(f"/accounts/{acc_id}/details")
            except httpx.HTTPStatusError as exc:
                logger.warning("Failed to fetch account %s: %s", acc_id, exc)
                continue

            iban = None
            if iban_str := data.get("iban"):
                iban = IBAN.try_parse(iban_str)

            current_balance = None
            balance_data = data.get("balances", [{}])
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
                id=UUID(data.get("uid", acc_id)),
                user_id=user_id,
                bank_connector="enable_banking",
                bank_id=data.get("bankId", ""),
                iban=iban,
                holder_name=data.get("ownerName"),
                account_type=self._map_account_type(
                    data.get("accountType", {}).get("type")
                    if isinstance(data.get("accountType"), dict)
                    else data.get("accountType")
                ),
                account_name=data.get("name") or data.get("product", "Compte"),
                currency=data.get("currency", "EUR"),
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
        """Fetch transactions for a specific account.

        Uses GET /accounts/{id}/transactions. Pagination: the 2026 API may
        use continuation_token — we handle it if present, otherwise single page.
        """
        from urllib.parse import urlencode

        continuation_token: str | None = None
        transactions: list[Transaction] = []

        while True:
            params: dict[str, str] = {}
            if continuation_token:
                params["continuation_token"] = continuation_token
            if since:
                params["date_from"] = since.strftime("%Y-%m-%d")
            if until:
                params["date_to"] = until.strftime("%Y-%m-%d")

            url_path = f"/accounts/{account_id}/transactions"
            if params:
                url_path = f"{url_path}?{urlencode(params)}"

            data = await self._api_get(url_path)

            for item in data.get("transactions", []):
                transactions.append(self._parse_transaction(item, account_id))

            # Check for pagination (2026 API may or may not use continuation_token)
            continuation_token = data.get("continuation_token")
            if not continuation_token:
                break

        return transactions

    async def get_balances(self, user_id: UUID) -> list[BalanceSnapshot]:
        """Fetch current balances for all connected accounts.

        Iterates account_ids from Vault, calls GET /accounts/{id}/balances for each.
        """
        vault_path = f"{self.VAULT_PATH_PREFIX}/{user_id}"
        account_ids_raw = await self._vault.read_secret(vault_path, "account_ids")
        if not account_ids_raw:
            raise EnableBankingError(f"No account IDs found for user {user_id}.")

        account_ids = [aid.strip() for aid in account_ids_raw.split(",") if aid.strip()]
        snapshots: list[BalanceSnapshot] = []
        now = datetime.now(UTC)

        for acc_id in account_ids:
            try:
                data = await self._api_get(f"/accounts/{acc_id}/balances")
            except httpx.HTTPStatusError as exc:
                logger.warning("Failed to fetch balances for account %s: %s", acc_id, exc)
                continue

            for item in data.get("balances", []):
                bal = item.get("balanceAmount", {})
                if not bal:
                    continue
                try:
                    money = Money(str(bal["amount"]), bal["currency"])
                    snapshots.append(
                        BalanceSnapshot(
                            account_id=UUID(acc_id),
                            balance=money,
                            currency=bal["currency"],
                            timestamp=now,
                            source="psd2",
                        )
                    )
                except (KeyError, ValueError, TypeError):
                    continue

        return snapshots

    # ── Parsers (preserved from original) ──────────────────────────

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
