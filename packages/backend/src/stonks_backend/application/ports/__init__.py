"""Application ports — abstract interfaces for infrastructure adapters.

Portfolio ports are available under stonks_backend.application.ports.portfolio,
re-exported here for convenience.
"""

from stonks_backend.application.ports.cashflow import (
    BankConnectorPort,
    CashflowRepositoryPort,
    CategorizationPort,
)
from stonks_backend.application.ports.portfolio import (
    FxRatePort,
    NewsDigest,
    NewsFeedPort,
    NewsItem,
    PortfolioRepositoryPort,
    PriceAlert,
    PriceFeedPort,
)
from stonks_backend.application.ports.repositories import (
    RefreshTokenRepositoryPort,
    UserRepositoryPort,
)

__all__ = [
    # ── Cashflow ─────────────────────────────
    "BankConnectorPort",
    "CashflowRepositoryPort",
    "CategorizationPort",
    "FxRatePort",
    "NewsDigest",
    "NewsFeedPort",
    # ── Portfolio (data contracts) ───────────
    "NewsItem",
    "PortfolioRepositoryPort",
    "PriceAlert",
    # ── Portfolio (ports) ────────────────────
    "PriceFeedPort",
    "RefreshTokenRepositoryPort",
    # ── User / Auth ──────────────────────────
    "UserRepositoryPort",
]
