"""Tests for Transaction domain entities."""

import uuid

import pytest

from stonks_backend.domain.cashflow.money import Money
from stonks_backend.domain.cashflow.transaction import TransactionId
from stonks_backend.domain.cashflow.transaction_entity import (
    Transaction,
    TransactionSource,
    TransactionStatus,
)


class TestTransactionId:
    def test_create_from_string(self):
        tid = TransactionId("bank-tx-123")
        assert tid.value == "bank-tx-123"

    def test_create_from_uuid(self):
        uid = uuid.uuid4()
        tid = TransactionId(uid)
        assert tid.value == str(uid)

    def test_generate(self):
        tid = TransactionId.generate()
        assert len(tid.value) > 0
        uuid.UUID(tid.value)  # Should be parseable as UUID

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            TransactionId("")

    def test_equality(self):
        assert TransactionId("abc") == TransactionId("abc")
        assert TransactionId("abc") != TransactionId("def")

    def test_hash(self):
        assert hash(TransactionId("abc")) == hash(TransactionId("abc"))


class TestTransaction:
    def test_create_minimal(self):
        tx = Transaction(
            account_id=uuid.uuid4(),
            amount=Money(-50, "EUR"),
            currency="EUR",
            description="CARREFOUR PARIS 75012",
        )
        assert isinstance(tx.id, TransactionId)
        assert tx.amount == Money(-50, "EUR")
        assert tx.currency == "EUR"
        assert tx.status == TransactionStatus.BOOKED
        assert tx.source == TransactionSource.PSD2

    def test_create_with_all_fields(self):
        account_id = uuid.uuid4()
        tx = Transaction(
            account_id=account_id,
            bank_tx_id="BANK-REF-456",
            amount=Money(1500, "EUR"),
            currency="EUR",
            description="SALAIRE JANVIER",
            creditor_name="ACME Corp",
            creditor_iban="FR7630006000011234567890189",
        )
        assert tx.bank_tx_id == "BANK-REF-456"
        assert tx.creditor_name == "ACME Corp"
        assert tx.amount > Money(0, "EUR")  # amount is positive

    def test_currency_must_match_amount_currency(self):
        with pytest.raises(ValueError, match="must match amount currency"):
            Transaction(
                account_id=uuid.uuid4(),
                amount=Money(50, "EUR"),
                currency="USD",
                description="test",
            )

    def test_amount_must_be_money(self):
        with pytest.raises(TypeError):
            Transaction(
                account_id=uuid.uuid4(),
                amount=50,  # type: ignore[arg-type]
                currency="EUR",
                description="test",
            )

    def test_assign_category(self):
        cat_id = uuid.uuid4()
        tx = Transaction(
            account_id=uuid.uuid4(),
            amount=Money(-25, "EUR"),
            currency="EUR",
            description="test",
        )
        assert tx.category_id is None
        tx.assign_category(cat_id)
        assert tx.category_id == cat_id


class TestTransactionEnums:
    def test_status_values(self):
        assert TransactionStatus.PENDING == "pending"
        assert TransactionStatus.BOOKED == "booked"
        assert TransactionStatus.REVERSED == "reversed"

    def test_source_values(self):
        assert TransactionSource.PSD2 == "psd2"
        assert TransactionSource.SCRAPING == "scraping"
        assert TransactionSource.MANUAL == "manual"
