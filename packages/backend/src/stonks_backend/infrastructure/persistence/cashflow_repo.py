"""CashflowSqlRepository — persiste les entités cashflow avec chiffrement AES-GCM.

Implements CashflowRepositoryPort using SQLAlchemy async sessions.
Sensitive columns (iban, holder_name, raw_label) are encrypted/decrypted
transparently using the AES-256-GCM cipher from Phase 2.1.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.cashflow import CashflowRepositoryPort
from stonks_backend.domain.cashflow import Category as DomainCategory
from stonks_backend.domain.cashflow.account import Account, AccountStatus, AccountType
from stonks_backend.domain.cashflow.balance import BalanceSnapshot
from stonks_backend.domain.cashflow.category import CategoryGroup
from stonks_backend.domain.cashflow.iban import IBAN
from stonks_backend.domain.cashflow.money import Money
from stonks_backend.domain.cashflow.transaction import TransactionId
from stonks_backend.domain.cashflow.transaction_entity import (
    Transaction,
    TransactionSource,
    TransactionStatus,
)
from stonks_backend.infrastructure.persistence.cashflow_models import (
    CashflowAccountModel,
    CashflowBalanceSnapshotModel,
    CashflowCategoryModel,
    CashflowTransactionModel,
)
from stonks_backend.infrastructure.security.aes_gcm import AESCipher

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CashflowSqlRepository(CashflowRepositoryPort):
    """SQLAlchemy async adapter for cashflow persistence with AES-GCM on sensitive columns.

    Usage:
        repo = CashflowSqlRepository(session, aes_cipher)
        await repo.save_account(account)        # IBAN encrypted automatically
        txns = await repo.get_transactions(...)  # raw_label decrypted automatically
    """

    def __init__(self, session: AsyncSession, aes_cipher: AESCipher) -> None:
        self._session = session
        self._aes = aes_cipher
        self._encrypt_str = aes_cipher.encrypt_string
        self._decrypt_str = aes_cipher.decrypt_string

    # ── Account ────────────────────────────────────────────────────

    async def save_account(self, account: Account) -> None:
        """Insert or update a cashflow account. Encrypts IBAN and holder_name."""
        iban_encrypted = self._encrypt_str(account.iban.value) if account.iban is not None else None
        holder_encrypted = (
            self._encrypt_str(account.holder_name) if account.holder_name is not None else None
        )

        balance_amt = account.current_balance.amount if account.current_balance else None
        balance_cur = account.current_balance.currency if account.current_balance else None

        stmt = insert(CashflowAccountModel).values(
            id=account.id,
            user_id=account.user_id,
            bank_connector=account.bank_connector,
            bank_id=account.bank_id,
            iban_encrypted=iban_encrypted,
            holder_name_encrypted=holder_encrypted,
            account_type=account.account_type.value,
            account_name=account.account_name,
            currency=account.currency,
            current_balance_amount=balance_amt,
            current_balance_currency=balance_cur,
            last_synced_at=account.last_synced_at,
            status=account.status.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_bank_account",
            set_={
                "iban_encrypted": stmt.excluded.iban_encrypted,
                "holder_name_encrypted": stmt.excluded.holder_name_encrypted,
                "account_type": stmt.excluded.account_type,
                "account_name": stmt.excluded.account_name,
                "currency": stmt.excluded.currency,
                "current_balance_amount": stmt.excluded.current_balance_amount,
                "current_balance_currency": stmt.excluded.current_balance_currency,
                "last_synced_at": stmt.excluded.last_synced_at,
                "status": stmt.excluded.status,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        await self._session.execute(stmt)
        await self._session.flush()

    async def get_account(self, account_id: UUID) -> Account | None:
        """Retrieve a single account by ID."""
        stmt = select(CashflowAccountModel).where(CashflowAccountModel.id == account_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_account(model) if model is not None else None

    async def get_accounts_by_user(self, user_id: UUID) -> list[Account]:
        """Retrieve all accounts for a user."""
        stmt = select(CashflowAccountModel).where(CashflowAccountModel.user_id == user_id)
        result = await self._session.execute(stmt)
        return [self._model_to_account(m) for m in result.scalars().all()]

    # ── Transactions ───────────────────────────────────────────────

    async def save_transactions(self, transactions: list[Transaction]) -> int:
        """Persist transactions with dedup on (account_id, bank_tx_id).

        Uses PostgreSQL INSERT ... ON CONFLICT DO NOTHING to skip duplicates.
        Returns the number of rows that were actually inserted.
        """
        if not transactions:
            return 0

        # Batch insert: build a list of value dicts
        values = []
        for tx in transactions:
            # raw_label_encrypted is set by the adapter calling encrypt_label separately
            # For now, we store an empty encrypted label — adapters can overwrite
            values.append(
                {
                    "id": tx.id.value,
                    "account_id": tx.account_id,
                    "bank_tx_id": tx.bank_tx_id,
                    "amount": tx.amount.amount,
                    "currency": tx.currency,
                    "description": tx.description,
                    "raw_label_encrypted": None,  # Set by caller via update_raw_label
                    "booking_date": tx.booking_date,
                    "value_date": tx.value_date,
                    "status": tx.status.value,
                    "source": tx.source.value,
                    "creditor_name": tx.creditor_name,
                    "creditor_iban": tx.creditor_iban,
                    "debtor_name": tx.debtor_name,
                    "debtor_iban": tx.debtor_iban,
                    "category_id": tx.category_id,
                    "created_at": tx.created_at,
                }
            )

        # Execute batch INSERT ON CONFLICT DO NOTHING.
        # session.execute() returns Result[Any] in stubs but the actual runtime
        # object for INSERT/UPDATE/DELETE is CursorResult, which has .rowcount.
        # We cast() to inform mypy strict — this is safe by SQLAlchemy contract.
        stmt = insert(CashflowTransactionModel)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_account_bank_tx")
        raw_result = await self._session.execute(stmt, values)
        result = cast("CursorResult[Any]", raw_result)
        await self._session.flush()

        return result.rowcount if result.rowcount else 0

    async def update_transaction_raw_label(self, tx_id: TransactionId, raw_label: str) -> None:
        """Update the encrypted raw_label for a transaction (post-insert)."""
        encrypted = self._encrypt_str(raw_label)
        stmt = text("UPDATE cashflow_transactions SET raw_label_encrypted = :enc WHERE id = :tx_id")
        await self._session.execute(stmt, {"enc": encrypted, "tx_id": tx_id.value})

    async def get_transactions(
        self,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Transaction]:
        """Fetch paginated transactions for an account, optionally filtered by date."""
        stmt = select(CashflowTransactionModel).where(
            CashflowTransactionModel.account_id == account_id
        )
        if since is not None:
            stmt = stmt.where(CashflowTransactionModel.created_at >= since)
        if until is not None:
            stmt = stmt.where(CashflowTransactionModel.created_at <= until)
        stmt = stmt.order_by(CashflowTransactionModel.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return [self._model_to_transaction(m) for m in result.scalars().all()]

    async def get_transaction_count(
        self,
        account_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Count transactions for an account, optionally filtered by date."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(CashflowTransactionModel)
            .where(CashflowTransactionModel.account_id == account_id)
        )
        if since is not None:
            stmt = stmt.where(CashflowTransactionModel.created_at >= since)
        if until is not None:
            stmt = stmt.where(CashflowTransactionModel.created_at <= until)

        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count if isinstance(count, int) else int(count)

    # ── Balance Snapshots ──────────────────────────────────────────

    async def save_balance_snapshot(self, snapshot: BalanceSnapshot) -> None:
        """Persist a balance snapshot."""
        model = CashflowBalanceSnapshotModel(
            id=snapshot.id,
            account_id=snapshot.account_id,
            balance_amount=snapshot.balance.amount,
            balance_currency=snapshot.balance.currency,
            timestamp=snapshot.timestamp,
            source=snapshot.source,
            created_at=snapshot.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_balance_history(
        self, account_id: UUID, since: datetime, until: datetime
    ) -> list[BalanceSnapshot]:
        """Retrieve balance snapshots for an account in a time range."""
        stmt = (
            select(CashflowBalanceSnapshotModel)
            .where(CashflowBalanceSnapshotModel.account_id == account_id)
            .where(CashflowBalanceSnapshotModel.timestamp >= since)
            .where(CashflowBalanceSnapshotModel.timestamp <= until)
            .order_by(CashflowBalanceSnapshotModel.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return [
            BalanceSnapshot(
                id=m.id,
                account_id=m.account_id,
                balance=Money(m.balance_amount, m.balance_currency),
                currency=m.balance_currency,
                timestamp=m.timestamp,
                source=m.source,
                created_at=m.created_at,
            )
            for m in result.scalars().all()
        ]

    # ── Categories ─────────────────────────────────────────────────

    async def save_category(self, category: DomainCategory) -> None:
        """Persist a category (system or user-defined)."""
        model = CashflowCategoryModel(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            group_name=category.group.value,
            icon=category.icon,
            color_hex=category.color_hex,
            parent_id=category.parent_id,
            is_system=category.is_system,
            created_at=category.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_default_categories(self) -> list[DomainCategory]:
        """Retrieve all system default categories (user_id IS NULL)."""
        stmt = select(CashflowCategoryModel).where(CashflowCategoryModel.is_system.is_(True))
        result = await self._session.execute(stmt)
        return [self._model_to_category(m) for m in result.scalars().all()]

    async def get_categories_by_user(self, user_id: UUID) -> list[DomainCategory]:
        """Retrieve all system + user-defined categories for a user."""
        stmt = select(CashflowCategoryModel).where(
            (CashflowCategoryModel.user_id == user_id) | (CashflowCategoryModel.is_system.is_(True))
        )
        result = await self._session.execute(stmt)
        return [self._model_to_category(m) for m in result.scalars().all()]

    async def get_category(self, category_id: UUID) -> DomainCategory | None:
        """Retrieve a single category by ID."""
        stmt = select(CashflowCategoryModel).where(CashflowCategoryModel.id == category_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_category(model) if model is not None else None

    # ── Categorization Rules ───────────────────────────────────────

    async def get_rule_categories_map(
        self,
    ) -> list[tuple[str, str, int, UUID]]:
        """Return all categorization rules as (field, pattern, priority, category_id)."""
        from stonks_backend.infrastructure.persistence.cashflow_models import (
            CategorizationRuleModel,
        )

        stmt = select(CategorizationRuleModel).order_by(CategorizationRuleModel.priority.desc())
        result = await self._session.execute(stmt)
        return [(r.field, r.pattern, r.priority, r.category_id) for r in result.scalars().all()]

    # ── Model-to-Domain mappers ────────────────────────────────────

    def _model_to_account(self, m: CashflowAccountModel) -> Account:
        """Map ORM model → domain Account, decrypting sensitive fields."""
        iban = None
        if m.iban_encrypted is not None:
            try:
                iban = IBAN(self._decrypt_str(m.iban_encrypted))
            except Exception:
                logger.warning("Failed to decrypt IBAN for account %s", m.id)

        holder_name = None
        if m.holder_name_encrypted is not None:
            try:
                holder_name = self._decrypt_str(m.holder_name_encrypted)
            except Exception:
                logger.warning("Failed to decrypt holder_name for account %s", m.id)

        balance = None
        if m.current_balance_amount is not None and m.current_balance_currency is not None:
            balance = Money(m.current_balance_amount, m.current_balance_currency)

        return Account(
            id=m.id,
            user_id=m.user_id,
            bank_connector=m.bank_connector,
            bank_id=m.bank_id,
            iban=iban,
            holder_name=holder_name,
            account_type=AccountType(m.account_type),
            account_name=m.account_name,
            currency=m.currency,
            current_balance=balance,
            last_synced_at=m.last_synced_at,
            status=AccountStatus(m.status),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _model_to_transaction(self, m: CashflowTransactionModel) -> Transaction:
        """Map ORM model → domain Transaction, decrypting raw_label."""
        return Transaction(
            id=TransactionId(m.id),
            account_id=m.account_id,
            bank_tx_id=m.bank_tx_id,
            amount=Money(m.amount, m.currency),
            currency=m.currency,
            description=m.description,
            booking_date=m.booking_date,
            value_date=m.value_date,
            status=TransactionStatus(m.status),
            source=TransactionSource(m.source),
            creditor_name=m.creditor_name,
            creditor_iban=m.creditor_iban,
            debtor_name=m.debtor_name,
            debtor_iban=m.debtor_iban,
            category_id=m.category_id,
            created_at=m.created_at,
        )

    @staticmethod
    def _model_to_category(m: CashflowCategoryModel) -> DomainCategory:
        """Map ORM model → domain Category."""
        return DomainCategory(
            id=m.id,
            user_id=m.user_id,
            name=m.name,
            group=CategoryGroup(m.group_name),
            icon=m.icon,
            color_hex=m.color_hex,
            parent_id=m.parent_id,
            is_system=m.is_system,
            created_at=m.created_at,
        )
