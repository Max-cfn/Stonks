"""Bank connector adapters — PSD2 + feature-flagged scraping fallback.

- EnableBankingAdapter: production-ready PSD2 via Enable Banking (OAuth2 PKCE)
- ScrapingFallbackAdapter: disabled by default, stub only (risks documented)
"""

from stonks_backend.infrastructure.bank_connectors.enable_banking import (
    EnableBankingAdapter,
    EnableBankingError,
    EnableBankingTokenError,
)
from stonks_backend.infrastructure.bank_connectors.scraping_fallback import (
    ScrapingFallbackAdapter,
    ScrapingFallbackError,
)

__all__ = [
    "EnableBankingAdapter",
    "EnableBankingError",
    "EnableBankingTokenError",
    "ScrapingFallbackAdapter",
    "ScrapingFallbackError",
]
