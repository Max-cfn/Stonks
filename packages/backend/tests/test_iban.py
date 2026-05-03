"""Tests for IBAN value object (ISO 13616 MOD 97)."""

import pytest

from stonks_backend.domain.cashflow.iban import IBAN, IBANValidationError


class TestIBANCreation:
    def test_valid_french_iban(self):
        iban = IBAN("FR7630006000011234567890189")
        assert iban.value == "FR7630006000011234567890189"
        assert iban.country_code == "FR"
        assert iban.check_digits == "76"

    def test_valid_german_iban(self):
        iban = IBAN("DE89370400440532013000")
        assert iban.value == "DE89370400440532013000"
        assert iban.country_code == "DE"

    def test_valid_uk_iban(self):
        iban = IBAN("GB29NWBK60161331926819")
        assert iban.value == "GB29NWBK60161331926819"

    def test_valid_spanish_iban(self):
        iban = IBAN("ES9121000418450200051332")
        assert iban.value == "ES9121000418450200051332"

    def test_iban_with_spaces(self):
        iban = IBAN("FR76 3000 6000 0112 3456 7890 189")
        assert iban.value == "FR7630006000011234567890189"

    def test_iban_lowercase(self):
        iban = IBAN("fr7630006000011234567890189")
        assert iban.value == "FR7630006000011234567890189"

    def test_invalid_check_digits_raises(self):
        with pytest.raises(IBANValidationError, match="MOD 97"):
            IBAN("FR0030006000011234567890189")  # check digits changed

    def test_empty_string_raises(self):
        with pytest.raises(IBANValidationError):
            IBAN("")

    def test_too_short_raises(self):
        with pytest.raises(IBANValidationError):
            IBAN("FR76")

    def test_random_garbage_raises(self):
        with pytest.raises(IBANValidationError):
            IBAN("NOT AN IBAN AT ALL!!!")


class TestIBANProperties:
    @pytest.fixture
    def iban(self) -> IBAN:
        return IBAN("FR7630006000011234567890189")

    def test_country_code(self, iban):
        assert iban.country_code == "FR"

    def test_check_digits(self, iban):
        assert iban.check_digits == "76"

    def test_bban(self, iban):
        assert iban.bban == "30006000011234567890189"

    def test_pretty(self, iban):
        assert iban.pretty == "FR76 3000 6000 0112 3456 7890 189"


class TestIBANComparison:
    def test_equal_same(self):
        assert IBAN("FR7630006000011234567890189") == IBAN("FR7630006000011234567890189")

    def test_equal_different_formatting(self):
        assert IBAN("FR76 3000 6000 0112 3456 7890 189") == IBAN("FR7630006000011234567890189")

    def test_not_equal_different(self):
        assert IBAN("FR7630006000011234567890189") != IBAN("DE89370400440532013000")

    def test_hash(self):
        iban1 = IBAN("FR7630006000011234567890189")
        iban2 = IBAN("FR76 3000 6000 0112 3456 7890 189")
        assert hash(iban1) == hash(iban2)


class TestIBANTryParse:
    def test_valid_returns_iban(self):
        assert IBAN.try_parse("FR7630006000011234567890189") is not None

    def test_invalid_returns_none(self):
        assert IBAN.try_parse("INVALID") is None

    def test_empty_returns_none(self):
        assert IBAN.try_parse("") is None


class TestMOD97EdgeCases:
    """Additional MOD 97 test vectors from ISO 13616 registry."""

    def test_mod97_remainder_1_is_valid(self):
        # A manually verified valid IBAN using MOD 97
        iban = "FR7630006000011234567890189"
        assert IBAN._check_mod97(iban)

    def test_mod97_arbitrary(self):
        # 321428291 mod 97 = 1
        assert IBAN._check_mod97("GB82WEST12345698765432")

    def test_belgian_iban(self):
        iban = IBAN("BE68539007547034")
        assert iban.value == "BE68539007547034"
