"""Tests for domain user entity & value objects."""

import pytest

from stonks_backend.domain.user import Email, HashedPassword, User

# Use passwords ≤ 72 bytes for bcrypt 5.0 compatibility
_VALID_PASSWORD = "secure12"
_SHORT_PASSWORD = "short"


class TestEmail:
    def test_valid_email(self) -> None:
        e = Email("test@example.com")
        assert e.address == "test@example.com"
        assert str(e) == "test@example.com"

    def test_email_equality(self) -> None:
        assert Email("a@b.com") == Email("a@b.com")
        assert Email("a@b.com") != Email("x@b.com")

    def test_email_too_short(self) -> None:
        with pytest.raises(ValueError):
            Email("a@b")

    def test_email_invalid_format(self) -> None:
        invalid = ["notanemail", "@no-local.com", "no-at-sign", "", "user@", "@domain"]
        for addr in invalid:
            with pytest.raises(ValueError):
                Email(addr)


class TestHashedPassword:
    def test_from_plain_and_verify(self) -> None:
        hp = HashedPassword.from_plain(_VALID_PASSWORD)
        assert hp.verify(_VALID_PASSWORD) is True
        assert hp.verify("wrongpass") is False

    def test_password_too_short(self) -> None:
        with pytest.raises(ValueError, match="at least 8"):
            HashedPassword.from_plain(_SHORT_PASSWORD)

    def test_password_too_long(self) -> None:
        with pytest.raises(ValueError, match="128"):
            HashedPassword.from_plain("x" * 129)

    def test_different_salts(self) -> None:
        hp1 = HashedPassword.from_plain(_VALID_PASSWORD)
        hp2 = HashedPassword.from_plain(_VALID_PASSWORD)
        assert str(hp1) != str(hp2), "Hashes should differ due to salt"


class TestUser:
    def test_register_creates_user(self) -> None:
        user = User.register("alice@stonks.com", _VALID_PASSWORD)
        assert user.email.address == "alice@stonks.com"
        assert user.is_active is True
        assert user.verify_password(_VALID_PASSWORD) is True

    def test_register_password_validation(self) -> None:
        with pytest.raises(ValueError):
            User.register("bob@stonks.com", _SHORT_PASSWORD)

    def test_user_ids_are_unique(self) -> None:
        u1 = User.register("a1@stonks.com", _VALID_PASSWORD)
        u2 = User.register("a2@stonks.com", _VALID_PASSWORD)
        assert u1.id != u2.id

    def test_verify_password(self) -> None:
        user = User.register("test@stonks.com", _VALID_PASSWORD)
        assert user.verify_password(_VALID_PASSWORD) is True
        assert user.verify_password("wrong") is False
