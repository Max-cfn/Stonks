"""ScrapingFallbackAdapter — web scraping pour banques sans PSD2/Open Banking.

*** DÉSACTIVÉ PAR DÉFAUT (FEATURE_BANK_SCRAPING_FALLBACK=false) ***

Risques documentés :
- Violation des CGU des banques (la plupart interdisent le scraping automatisé)
- Blocage IP par les banques après détection de patterns non-humains
- Fragilité : le moindre changement de DOM casse le connecteur
- Pas de consentement explicite de l'utilisateur (contrairement à PSD2/OAuth)
- Données potentiellement inexactes (parsing HTML vs API structurée)

Inspiré conceptuellement par les patterns de Zoeille/picsou-finance (Spring Boot),
ce module est une adaptation PUREMENT ORIGINALE pour le contexte Stonks (Python/async).
Aucun code de picsou-finance n'est importé ou traduit.

Ce module est un STUB — il ne sera implémenté qu'avec l'accord explicite
de l'utilisateur après validation des risques juridiques.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from stonks_backend.application.ports.cashflow import BankConnectorPort
from stonks_backend.domain.cashflow.account import Account
from stonks_backend.domain.cashflow.balance import BalanceSnapshot
from stonks_backend.domain.cashflow.transaction_entity import Transaction

logger = logging.getLogger(__name__)


class ScrapingFallbackError(Exception):
    """Raised when scraping operations fail or are disabled."""


class ScrapingFallbackAdapter(BankConnectorPort):
    """Bank connector using web scraping (HTML parsing).

    *** REQUIRES FEATURE_BANK_SCRAPING_FALLBACK=true ***

    Architecture conceptuelle (non implémenté — stub) :
    1. L'utilisateur fournit ses identifiants bancaires (login/password)
       → stockés chiffrés dans Vault
    2. Playwright/httpx navigue sur le site de la banque
    3. Parse le DOM pour extraire les comptes, soldes, transactions
    4. Retourne les mêmes entités domain que EnableBankingAdapter

    Patterns clés (inspirés de picsou-finance, adaptés à Python) :
    - Bank-specific drivers: une classe par banque (LCLDriver, BoursoramaDriver, ...)
    - Registry pattern: mapping BIC/bank_name → driver class
    - Two-phase parsing: login → dashboard → account list → transaction list
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        if not enabled:
            logger.warning(
                "ScrapingFallbackAdapter initialized but DISABLED. "
                "Set FEATURE_BANK_SCRAPING_FALLBACK=true to enable."
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise ScrapingFallbackError(
                "Bank scraping is disabled. Set FEATURE_BANK_SCRAPING_FALLBACK=true "
                "and acknowledge the risks before enabling. See /docs/briefs/ for details."
            )

    # ── BankConnectorPort Implementation (all stubs) ───────────────

    async def get_authorization_url(self, user_id: UUID, redirect_uri: str) -> str:
        """Scraping doesn't use OAuth — returns a dummy URL.

        Instead, the frontend should show a form for manual credential entry.
        """
        self._require_enabled()
        return f"{redirect_uri}?scraping=credentials_required"

    async def exchange_code_for_token(self, user_id: UUID, code: str, redirect_uri: str) -> None:
        """Scraping doesn't use OAuth — credential storage is manual."""
        self._require_enabled()
        logger.warning("exchange_code_for_token called on scraping adapter — no-op")

    async def list_accounts(self, user_id: UUID) -> list[Account]:
        """Scrape account list from bank website (not implemented — stub)."""
        self._require_enabled()
        raise NotImplementedError(
            "Scraping account listing is not yet implemented. "
            "Use EnableBankingAdapter (PSD2) for production."
        )

    async def fetch_transactions(
        self,
        user_id: UUID,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Transaction]:
        """Scrape transactions from bank website (not implemented — stub)."""
        self._require_enabled()
        raise NotImplementedError(
            "Scraping transaction fetch is not yet implemented. "
            "Use EnableBankingAdapter (PSD2) for production."
        )

    async def get_balances(self, user_id: UUID) -> list[BalanceSnapshot]:
        """Scrape balances from bank website (not implemented — stub)."""
        self._require_enabled()
        raise NotImplementedError(
            "Scraping balance fetch is not yet implemented. "
            "Use EnableBankingAdapter (PSD2) for production."
        )
