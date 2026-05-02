"""GetCashflowSummary — aggregated view of income, expenses, and category breakdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from stonks_backend.application.ports.cashflow import CashflowRepositoryPort
from stonks_backend.domain.cashflow.account import AccountStatus
from stonks_backend.domain.cashflow.money import Money


class GetCashflowSummaryError(Exception):
    """Raised when summary computation fails."""


@dataclass(kw_only=True, slots=True)
class CategorySummary:
    """Summary for a single category within a period."""

    category_id: UUID
    category_name: str
    category_icon: str
    category_group: str
    total_amount: Decimal
    currency: str
    transaction_count: int

    @property
    def total_money(self) -> Money:
        return Money(self.total_amount, self.currency)


@dataclass(kw_only=True, slots=True)
class MonthlyCashflowSummary:
    """Aggregated cashflow for a period (month or year)."""

    period_label: str  # e.g. "2026-05" or "2026"
    period_type: str  # "month" or "year"
    total_income: Money
    total_expenses: Money
    net_flow: Money  # income - expenses
    categories: list[CategorySummary] = field(default_factory=list)
    account_count: int = 0
    total_balance: Money | None = None


class GetCashflowSummary:
    """Compute aggregated cashflow summaries across all user accounts.

    Usage:
        use_case = GetCashflowSummary(cashflow_repo)
        summary = await use_case.compute(user_id, period="month")
    """

    def __init__(self, cashflow_repo: CashflowRepositoryPort) -> None:
        self._repo = cashflow_repo

    async def compute(
        self, user_id: UUID, period: str = "month",
    ) -> MonthlyCashflowSummary:
        """Compute the cashflow summary for the current period.

        Args:
            user_id: The authenticated user's UUID.
            period: "month" or "year".

        Returns:
            MonthlyCashflowSummary with income, expenses, and category breakdown.
        """
        accounts = await self._repo.get_accounts_by_user(user_id)
        active_accounts = [a for a in accounts if a.status == AccountStatus.ACTIVE]

        zero = Money(Decimal("0"), "EUR")

        if not active_accounts:
            return MonthlyCashflowSummary(
                period_label=datetime.now(UTC).strftime("%Y-%m"),
                period_type=period,
                total_income=zero,
                total_expenses=zero,
                net_flow=zero,
                account_count=0,
            )

        # Compute date range
        now = datetime.now(UTC)
        if period == "year":
            since = datetime(now.year, 1, 1, tzinfo=UTC)
            until = datetime(now.year, 12, 31, 23, 59, 59, tzinfo=UTC)
            period_label = f"{now.year}"
        else:
            since = datetime(now.year, now.month, 1, tzinfo=UTC)
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
            else:
                next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
            until = next_month
            period_label = now.strftime("%Y-%m")

        # Aggregate
        total_income = Decimal("0")
        total_expenses = Decimal("0")
        currency = active_accounts[0].currency or "EUR"
        category_totals: dict[UUID, tuple[Decimal, int]] = {}

        for account in active_accounts:
            transactions = await self._repo.get_transactions(
                account_id=account.id,
                since=since,
                until=until,
                limit=10000,
            )
            for tx in transactions:
                amt = tx.amount.amount
                if amt > 0:
                    total_income += amt
                else:
                    total_expenses += abs(amt)

                if tx.category_id is not None:
                    prev = category_totals.get(tx.category_id, (Decimal("0"), 0))
                    category_totals[tx.category_id] = (
                        prev[0] + amt,
                        prev[1] + 1,
                    )

        # Build category summaries
        cat_summaries: list[CategorySummary] = []
        for cat_id, (total_amt, count) in category_totals.items():
            cat = await self._repo.get_category(cat_id)
            if cat is not None:
                cat_summaries.append(CategorySummary(
                    category_id=cat.id,
                    category_name=cat.name,
                    category_icon=cat.icon,
                    category_group=cat.group.value,
                    total_amount=total_amt,
                    currency=currency,
                    transaction_count=count,
                ))

        # Sort: largest absolute amount first
        cat_summaries.sort(key=lambda c: abs(c.total_amount), reverse=True)

        # Total balance across all accounts
        total_balance = None
        for a in active_accounts:
            if a.current_balance is not None:
                if total_balance is None:
                    total_balance = a.current_balance
                elif total_balance.currency == a.current_balance.currency:
                    total_balance += a.current_balance

        income_money = Money(total_income, currency)
        expenses_money = Money(-total_expenses, currency)  # negative for display
        net_flow = Money(total_income - total_expenses, currency)

        return MonthlyCashflowSummary(
            period_label=period_label,
            period_type=period,
            total_income=income_money,
            total_expenses=expenses_money,
            net_flow=net_flow,
            categories=cat_summaries,
            account_count=len(active_accounts),
            total_balance=total_balance,
        )
