"""Ticker value object — financial instrument identifier.

A Ticker is a symbol (e.g. AAPL, TSLA) optionally qualified by an exchange.
For crypto assets like BTC or ETH, the exchange is None.
"""

from __future__ import annotations

import enum
from typing import Any


class Exchange(enum.Enum):
    """Supported stock exchanges."""

    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"
    EURONEXT = "EURONEXT"
    XETRA = "XETRA"
    SIX = "SIX"
    TSX = "TSX"
    TSE = "TSE"
    CRYPTO = "CRYPTO"


class InstrumentType(enum.Enum):
    """Broad classification of financial instruments."""

    STOCK = "STOCK"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    BOND = "BOND"
    COMMODITY = "COMMODITY"


class TickerValidationError(ValueError):
    """Raised when ticker symbol validation fails."""


_MAX_SYMBOL_LENGTH = 10


class Ticker:
    """Immutable value object representing a tradable ticker.

    Attributes:
        symbol: The uppercase ticker symbol (e.g. 'AAPL', 'BTC').
        exchange: The exchange the instrument trades on, or None for crypto.

    Example:
        >>> t = Ticker("AAPL", Exchange.NASDAQ)
        >>> str(t)
        'AAPL.NASDAQ'
        >>> hash(t) == hash(Ticker("AAPL", Exchange.NASDAQ))
        True
    """

    __slots__ = ("_exchange", "_symbol")

    def __init__(self, symbol: str, exchange: Exchange | None = None) -> None:
        s = symbol.strip().upper()
        if not s:
            raise TickerValidationError("Ticker symbol must not be empty")
        if len(s) > _MAX_SYMBOL_LENGTH:
            raise TickerValidationError(
                f"Ticker symbol exceeds {_MAX_SYMBOL_LENGTH} characters: {s!r}"
            )
        if not s.replace(".", "").replace("-", "").isalnum():
            raise TickerValidationError(f"Ticker symbol contains invalid characters: {s!r}")
        self._symbol = s
        self._exchange = exchange

    @property
    def symbol(self) -> str:
        """The uppercase ticker symbol."""
        return self._symbol

    @property
    def exchange(self) -> Exchange | None:
        """The exchange, or None for unqualified / crypto."""
        return self._exchange

    @property
    def is_crypto(self) -> bool:
        """True if the ticker trades on CRYPTO exchange."""
        return self._exchange is Exchange.CRYPTO

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Ticker):
            return NotImplemented
        return self._symbol == other._symbol and self._exchange is other._exchange

    def __hash__(self) -> int:
        return hash((self._symbol, self._exchange))

    def __repr__(self) -> str:
        return f"Ticker('{self._symbol}', {self._exchange})"

    def __str__(self) -> str:
        if self._exchange is None:
            return self._symbol
        return f"{self._symbol}.{self._exchange.value}"
