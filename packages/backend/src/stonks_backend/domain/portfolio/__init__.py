"""Portfolio domain — core business objects for investment portfolio tracking.

Architecture: ports & adapters — no infrastructure dependency here.
"""

from stonks_backend.domain.portfolio.currency import (
    SUPPORTED_CRYPTO_TICKERS,
    SUPPORTED_CURRENCIES,
    CurrencyMismatchError,
    Money,
    MoneyParseError,
    is_crypto,
    is_fiat,
)
from stonks_backend.domain.portfolio.holding import Holding, HoldingValidationError
from stonks_backend.domain.portfolio.lot import Lot, LotValidationError
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import (
    Exchange,
    InstrumentType,
    Ticker,
    TickerValidationError,
)
from stonks_backend.domain.portfolio.trade import Trade, TradeType, TradeValidationError

__all__ = [
    # ── Ticker ────────────────────────────
    "Exchange",
    "InstrumentType",
    "Ticker",
    "TickerValidationError",
    # ── Currency / Money ──────────────────
    "Money",
    "CurrencyMismatchError",
    "MoneyParseError",
    "SUPPORTED_CURRENCIES",
    "SUPPORTED_CRYPTO_TICKERS",
    "is_crypto",
    "is_fiat",
    # ── Quote ─────────────────────────────
    "Quote",
    # ── Holding ───────────────────────────
    "Holding",
    "HoldingValidationError",
    # ── Lot ───────────────────────────────
    "Lot",
    "LotValidationError",
    # ── Trade ─────────────────────────────
    "Trade",
    "TradeType",
    "TradeValidationError",
]
