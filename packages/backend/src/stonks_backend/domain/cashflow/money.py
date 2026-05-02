"""Money value object — amount + ISO 4217 currency.

Invariant: toutes les opérations arithmétiques nécessitent la même devise.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any


class CurrencyMismatchError(TypeError):
    """Raised when attempting arithmetic on Money values with different currencies."""


class MoneyParseError(ValueError):
    """Raised when a string cannot be parsed as Money."""


SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {
        "EUR",
        "USD",
        "GBP",
        "CHF",
        "JPY",
        "CAD",
        "AUD",
        "NZD",
        "SEK",
        "NOK",
        "DKK",
        "PLN",
        "CZK",
        "HUF",
        "RON",
        "BGN",
    }
)

# Matches "EUR 42.50" or "+EUR 42.50" or "-12.34 EUR"
_MONEY_RE = re.compile(
    r"^\s*(?P<sign>[+-]?)\s*(?:(?P<currency1>[A-Z]{3})\s+)?"
    r"(?P<amount>[\d\s]+[.,]?\d*)"
    r"\s*(?:(?P<currency2>[A-Z]{3}))?\s*$"
)


class Money:
    """An amount of money in a specific currency.

    Immutable value object — all operations return new instances.
    """

    __slots__ = ("_amount", "_currency")

    def __init__(self, amount: Decimal | str | int, currency: str) -> None:
        currency = currency.upper().strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency '{currency}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}"
            )

        if isinstance(amount, Decimal):
            self._amount = amount
        elif isinstance(amount, int):
            self._amount = Decimal(str(amount))
        elif isinstance(amount, str):
            try:
                self._amount = Decimal(amount.replace(",", ".").replace(" ", ""))
            except InvalidOperation as exc:
                raise MoneyParseError(f"Cannot parse amount: {amount!r}") from exc
        elif isinstance(amount, float):
            self._amount = Decimal(str(amount))
        else:
            raise TypeError(f"Unsupported amount type: {type(amount)}")

        self._currency = currency

    # ── Properties ─────────────────────────────────────────────────

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def is_positive(self) -> bool:
        return self._amount > 0

    @property
    def is_negative(self) -> bool:
        return self._amount < 0

    @property
    def is_zero(self) -> bool:
        return self._amount == 0


    # ── String representation ──────────────────────────────────────

    def __repr__(self) -> str:
        return f"Money({self._amount}, '{self._currency}')"

    def __str__(self) -> str:
        return f"{self._amount:.2f} {self._currency}"

    # ── Arithmetic ─────────────────────────────────────────────────

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self._amount + other._amount, self._currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self._amount - other._amount, self._currency)

    def __neg__(self) -> Money:
        return Money(-self._amount, self._currency)

    def __abs__(self) -> Money:
        return Money(abs(self._amount), self._currency)

    def __mul__(self, factor: int | Decimal) -> Money:
        if isinstance(factor, int):
            factor = Decimal(factor)
        elif not isinstance(factor, Decimal):
            return NotImplemented
        return Money(self._amount * factor, self._currency)

    def __truediv__(self, divisor: int | Decimal) -> Money:
        if isinstance(divisor, int):
            divisor = Decimal(divisor)
        elif not isinstance(divisor, Decimal):
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        return Money(self._amount / divisor, self._currency)

    # ── Comparison ─────────────────────────────────────────────────

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._currency == other._currency and self._amount == other._amount

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self._amount < other._amount

    def __le__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self._amount <= other._amount

    def __gt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self._amount > other._amount

    def __ge__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return self._amount >= other._amount

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def zero(currency: str) -> Money:
        """Shortcut for zero amount in a given currency."""
        return Money(Decimal("0"), currency)

    def _require_same_currency(self, other: Money) -> None:
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self._currency} and {other._currency}"
            )

    @classmethod
    def parse(cls, raw: str, default_currency: str = "EUR") -> Money:
        """Parse a string like '+EUR 42.50' or '-12.34 EUR' or '42,50 EUR'.

        If no currency prefix/suffix, uses default_currency.
        """
        raw = raw.strip()
        m = _MONEY_RE.match(raw)
        if m:
            sign = -1 if m.group("sign") == "-" else 1
            cur = m.group("currency1") or m.group("currency2")
            amt_str = m.group("amount").replace(" ", "").replace(",", ".")
            if cur:
                return Money(Decimal(amt_str) * sign, cur)
            else:
                return Money(Decimal(amt_str) * sign, default_currency)

        # Last resort: just a number
        try:
            amt = Decimal(raw.replace(",", ".").replace(" ", ""))
            return Money(amt, default_currency)
        except InvalidOperation as exc:
            raise MoneyParseError(f"Cannot parse Money from: {raw!r}") from exc
