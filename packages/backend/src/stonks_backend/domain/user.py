"""Domain entities & value objects — User, Email, HashedPassword."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import bcrypt

_BCRYPT_ROUNDS = 12


# ── Value Objects ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Email:
    """Validated email value object."""

    address: str

    def __post_init__(self) -> None:
        _validate_email(self.address)

    def __str__(self) -> str:
        return self.address


@dataclass(frozen=True)
class HashedPassword:
    """Bcrypt-hashed password value object (cost 12)."""

    hash: str

    @classmethod
    def from_plain(cls, password: str) -> HashedPassword:
        """Hash a plain-text password with bcrypt (cost 12)."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(password) > 128:
            raise ValueError("Password must not exceed 128 characters")
        # Truncate to 72 bytes for bcrypt compatibility
        password_bytes = password.encode("utf-8")[:72]
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
        return cls(hashed.decode("utf-8"))

    def verify(self, plain: str) -> bool:
        """Verify a plain-text password against this hash."""
        plain_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(plain_bytes, self.hash.encode("utf-8"))

    def __str__(self) -> str:
        return self.hash


# ── Entity ────────────────────────────────────────────────────────


@dataclass
class User:
    """Domain user entity."""

    id: uuid.UUID
    email: Email
    hashed_password: HashedPassword
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    @classmethod
    def register(cls, email: str, password: str) -> User:
        """Factory: create a new user ready for persistence."""
        return cls(
            id=uuid.uuid4(),
            email=Email(email),
            hashed_password=HashedPassword.from_plain(password),
        )

    def verify_password(self, plain: str) -> bool:
        """Verify the user's password."""
        return self.hashed_password.verify(plain)


# ── Helpers ───────────────────────────────────────────────────────

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
)


def _validate_email(email: str) -> None:
    if not 5 <= len(email) <= 254:
        raise ValueError(f"Email length must be between 5 and 254, got {len(email)}")
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email format: {email}")
