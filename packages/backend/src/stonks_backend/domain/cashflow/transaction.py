"""Transaction value objects — TransactionId uniquely identifies a transaction."""

from __future__ import annotations

import uuid
from typing import Any


class TransactionId:
    """A strongly-typed identifier for a financial transaction.

    Can be constructed from a bank-provided ID (string) or generated (UUIDv4).
    """

    __slots__ = ("_value",)

    def __init__(self, value: str | uuid.UUID) -> None:
        if isinstance(value, uuid.UUID):
            self._value = str(value)
        elif isinstance(value, str) and value.strip():
            self._value = value.strip()
        else:
            raise ValueError("TransactionId must be a non-empty string or UUID")

    @property
    def value(self) -> str:
        return self._value

    @classmethod
    def generate(cls) -> TransactionId:
        """Create a new random TransactionId (UUIDv4)."""
        return cls(str(uuid.uuid4()))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TransactionId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"TransactionId({self._value!r})"

    def __str__(self) -> str:
        return self._value
