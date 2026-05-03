"""IBAN value object — validated via ISO 13616 MOD 97 check.

The IBAN (International Bank Account Number) format:
- Max 34 alphanumeric characters
- Country code (2 letters) + check digits (2 digits) + BBAN
- Validated using MOD 97 on rearranged string (move first 4 chars to end, replace letters by A=10...Z=35)
"""

from __future__ import annotations

import re
from typing import Any


class IBANValidationError(ValueError):
    """Raised when an IBAN string fails validation."""


# Clean pattern: removes whitespace
_IBAN_CLEAN_RE = re.compile(r"[^A-Za-z0-9]")
# Format pattern after cleaning: letters then digits
_IBAN_FORMAT_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Za-z0-9]{1,30}$")

# Character offset for ISO 13636: A=10, B=11, ..., Z=35
_LETTER_OFFSET = ord("A") - 10


def _char_to_int(c: str) -> int:
    """Convert a single IBAN character to its numeric value."""
    if "0" <= c <= "9":
        return int(c)
    return ord(c.upper()) - _LETTER_OFFSET


class IBAN:
    """Validated IBAN value object.

    Once constructed, an IBAN instance is guaranteed to pass MOD 97.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        """Create an IBAN from a raw string (spaces allowed, case-insensitive).

        Raises:
            IBANValidationError: if the IBAN format is invalid or MOD 97 fails.
        """
        cleaned = _IBAN_CLEAN_RE.sub("", value.upper())
        if not _IBAN_FORMAT_RE.match(cleaned):
            raise IBANValidationError(f"Invalid IBAN format: {value!r}")
        if not self._check_mod97(cleaned):
            raise IBANValidationError(f"IBAN check digits fail MOD 97: {value!r}")
        self._value = cleaned

    @property
    def value(self) -> str:
        """The canonical, uppercased, space-free IBAN."""
        return self._value

    @property
    def country_code(self) -> str:
        """Two-letter ISO country code."""
        return self._value[:2]

    @property
    def check_digits(self) -> str:
        """Two check digits."""
        return self._value[2:4]

    @property
    def bban(self) -> str:
        """Basic Bank Account Number (everything after check digits)."""
        return self._value[4:]

    @property
    def pretty(self) -> str:
        """Human-readable IBAN with groups of 4 characters."""
        return " ".join(self._value[i : i + 4] for i in range(0, len(self._value), 4))

    @staticmethod
    def _check_mod97(iban: str) -> bool:
        """Validate IBAN using ISO 13616 MOD 97 check.

        Algorithm: Move first 4 chars to end, convert letters to numbers (A=10...Z=35),
        compute big integer modulo 97. Result must be 1.
        """
        rearranged = iban[4:] + iban[:4]
        # Build integer digit-by-digit to handle huge numbers
        remainder = 0
        for ch in rearranged:
            val = _char_to_int(ch)
            if val > 9:  # letter
                remainder = (remainder * 100 + val) % 97
            else:  # digit
                remainder = (remainder * 10 + val) % 97
        return remainder == 1

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, IBAN):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"IBAN({self.pretty})"

    def __str__(self) -> str:
        return self._value

    @classmethod
    def try_parse(cls, value: str) -> IBAN | None:
        """Safe parse: returns None instead of raising."""
        try:
            return cls(value)
        except IBANValidationError:
            return None
