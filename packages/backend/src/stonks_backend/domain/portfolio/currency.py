"""Portfolio currency utilities — re-exports Money + crypto helpers.

Re-exports Money, CurrencyMismatchError, and SUPPORTED_CURRENCIES from
stonks_backend.domain.cashflow.money to avoid duplication.
"""

from __future__ import annotations

from stonks_backend.domain.cashflow.money import (
    SUPPORTED_CURRENCIES,
    CurrencyMismatchError,
    Money,
    MoneyParseError,
)

SUPPORTED_CRYPTO_TICKERS: frozenset[str] = frozenset(
    {
        "BTC",
        "ETH",
        "USDT",
        "USDC",
        "BNB",
        "XRP",
        "SOL",
        "ADA",
        "DOGE",
        "DOT",
        "MATIC",
        "SHIB",
        "LTC",
        "AVAX",
        "UNI",
        "LINK",
    }
)


def is_crypto(symbol: str) -> bool:
    """Check whether a ticker symbol is a known crypto asset.

    Args:
        symbol: The ticker symbol to check (case-insensitive).

    Returns:
        True if the uppercase symbol is in SUPPORTED_CRYPTO_TICKERS.
    """
    return symbol.strip().upper() in SUPPORTED_CRYPTO_TICKERS


def is_fiat(currency_code: str) -> bool:
    """Check whether a currency code is a supported fiat currency.

    Args:
        currency_code: The ISO 4217 currency code to check (case-insensitive).

    Returns:
        True if the uppercase code is in SUPPORTED_CURRENCIES.
    """
    return currency_code.strip().upper() in SUPPORTED_CURRENCIES


__all__ = [
    "SUPPORTED_CRYPTO_TICKERS",
    "SUPPORTED_CURRENCIES",
    "CurrencyMismatchError",
    "Money",
    "MoneyParseError",
    "is_crypto",
    "is_fiat",
]
