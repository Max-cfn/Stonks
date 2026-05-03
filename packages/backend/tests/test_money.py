"""Tests for Money value object."""

from decimal import Decimal

import pytest

from stonks_backend.domain.cashflow.money import (
    SUPPORTED_CURRENCIES,
    CurrencyMismatchError,
    Money,
    MoneyParseError,
)


class TestMoneyCreation:
    def test_create_eur_integer(self):
        m = Money(42, "EUR")
        assert m.amount == Decimal("42")
        assert m.currency == "EUR"

    def test_create_usd_decimal(self):
        m = Money(Decimal("99.99"), "USD")
        assert m.amount == Decimal("99.99")
        assert m.currency == "USD"

    def test_create_from_string(self):
        m = Money("1234.56", "EUR")
        assert m.amount == Decimal("1234.56")

    def test_create_with_comma_decimal(self):
        m = Money("1234,56", "EUR")
        assert m.amount == Decimal("1234.56")

    def test_create_negative(self):
        m = Money(-50, "EUR")
        assert m.amount == Decimal("-50")

    def test_create_from_float(self):
        m = Money(10.5, "EUR")
        assert m.amount == Decimal("10.5")

    def test_create_lowercase_currency(self):
        m = Money(10, "eur")
        assert m.currency == "EUR"

    def test_unsupported_currency_raises(self):
        with pytest.raises(ValueError, match="Unsupported currency"):
            Money(10, "XYZ")

    def test_invalid_amount_type_raises(self):
        with pytest.raises(TypeError):
            Money([], "EUR")  # type: ignore[arg-type]

    def test_unparseable_string_raises(self):
        with pytest.raises(MoneyParseError):
            Money("not-a-number", "EUR")


class TestMoneyArithmetic:
    def test_add_same_currency(self):
        a = Money(10, "EUR")
        b = Money(20, "EUR")
        assert a + b == Money(30, "EUR")

    def test_add_different_currency_raises(self):
        a = Money(10, "EUR")
        b = Money(20, "USD")
        with pytest.raises(CurrencyMismatchError):
            a + b

    def test_subtract_same_currency(self):
        a = Money(50, "EUR")
        b = Money(30, "EUR")
        assert a - b == Money(20, "EUR")

    def test_subtract_different_currency_raises(self):
        a = Money(10, "EUR")
        b = Money(5, "USD")
        with pytest.raises(CurrencyMismatchError):
            a - b

    def test_negate(self):
        m = Money(42, "EUR")
        assert -m == Money(-42, "EUR")

    def test_abs_positive(self):
        m = Money(42, "EUR")
        assert abs(m) == Money(42, "EUR")

    def test_abs_negative(self):
        m = Money(-42, "EUR")
        assert abs(m) == Money(42, "EUR")

    def test_multiply_by_int(self):
        m = Money(10, "EUR")
        assert m * 3 == Money(30, "EUR")

    def test_multiply_by_decimal(self):
        m = Money(10, "EUR")
        assert m * Decimal("1.5") == Money(15, "EUR")

    def test_divide_by_int(self):
        m = Money(100, "EUR")
        assert m / 4 == Money(25, "EUR")

    def test_divide_by_zero_raises(self):
        m = Money(100, "EUR")
        with pytest.raises(ZeroDivisionError):
            m / 0


class TestMoneyComparison:
    def test_equal(self):
        assert Money(10, "EUR") == Money(10, "EUR")

    def test_not_equal_amount(self):
        assert Money(10, "EUR") != Money(20, "EUR")

    def test_not_equal_currency(self):
        assert Money(10, "EUR") != Money(10, "USD")

    def test_less_than(self):
        assert Money(10, "EUR") < Money(20, "EUR")

    def test_greater_than(self):
        assert Money(20, "EUR") > Money(10, "EUR")

    def test_less_equal(self):
        assert Money(10, "EUR") <= Money(10, "EUR")
        assert Money(10, "EUR") <= Money(20, "EUR")

    def test_greater_equal(self):
        assert Money(10, "EUR") >= Money(10, "EUR")
        assert Money(20, "EUR") >= Money(10, "EUR")

    def test_comparison_different_currency_raises(self):
        with pytest.raises(CurrencyMismatchError):
            _ = Money(10, "EUR") < Money(5, "USD")


class TestMoneyProperties:
    def test_is_positive(self):
        assert Money(10, "EUR").is_positive
        assert not Money(-10, "EUR").is_positive

    def test_is_negative(self):
        assert Money(-10, "EUR").is_negative
        assert not Money(10, "EUR").is_negative

    def test_is_zero(self):
        assert Money(0, "EUR").is_zero
        assert not Money(1, "EUR").is_zero

    def test_str_representation(self):
        assert str(Money(Decimal("12.50"), "EUR")) == "12.50 EUR"

    def test_zero_shortcut(self):
        assert Money.zero("EUR") == Money(0, "EUR")


class TestMoneyParse:
    def test_parse_currency_amount(self):
        m = Money.parse("EUR 42.50")
        assert m == Money(Decimal("42.50"), "EUR")

    def test_parse_amount_currency(self):
        m = Money.parse("42.50 EUR")
        assert m == Money(Decimal("42.50"), "EUR")

    def test_parse_negative(self):
        m = Money.parse("-12.34 EUR")
        assert m == Money(Decimal("-12.34"), "EUR")

    def test_parse_number_only_default_currency(self):
        m = Money.parse("42.50")
        assert m == Money(Decimal("42.50"), "EUR")

    def test_parse_comma_decimal(self):
        m = Money.parse("42,50 EUR")
        assert m == Money(Decimal("42.50"), "EUR")


class TestSupportedCurrencies:
    def test_all_major_currencies(self):
        expected = {
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
        assert SUPPORTED_CURRENCIES == expected

    def test_each_currency_creatable(self):
        for cur in SUPPORTED_CURRENCIES:
            m = Money(1, cur)
            assert m.currency == cur
