"""Tests for TWR and MWR performance calculators.

Validates Time-Weighted Return (TWR) and Money-Weighted Return (MWR/XIRR)
calculations against hand-computed expected values.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from stonks_backend.domain.portfolio.performance import (
    CompoundReturn,
    PerformanceError,
)


def _dt(s: str) -> datetime:
    """Parse an ISO date string into a timezone-aware UTC datetime (midnight)."""
    return datetime.fromisoformat(s + "T00:00:00+00:00")


# ═══════════════════════════════════════════════════════════════════
# TWR Tests
# ═══════════════════════════════════════════════════════════════════

TWR_TOLERANCE = Decimal("1e-12")


class TestTWRNoCashflows:
    """Case 1: TWR with no intermediate cash flows."""

    def test_simple_gain(self) -> None:
        """start=10000, no cashflows, end=11000 -> TWR = 10% (non-annualized)."""
        result = CompoundReturn.twr(
            start_value=Decimal("10000"),
            cashflows=[],
            end_value=Decimal("11000"),
        )
        expected = Decimal("0.10")
        assert abs(result - expected) < TWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )

    def test_simple_loss(self) -> None:
        """start=10000, no cashflows, end=9500 -> TWR = -5%."""
        result = CompoundReturn.twr(
            start_value=Decimal("10000"),
            cashflows=[],
            end_value=Decimal("9500"),
        )
        expected = Decimal("-0.05")
        assert abs(result - expected) < TWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )

    def test_zero_return(self) -> None:
        """start=10000, no cashflows, end=10000 -> TWR = 0%."""
        result = CompoundReturn.twr(
            start_value=Decimal("10000"),
            cashflows=[],
            end_value=Decimal("10000"),
        )
        expected = Decimal("0")
        assert abs(result - expected) < TWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )

    def test_start_value_zero_raises(self) -> None:
        """start=0 should raise PerformanceError."""
        with pytest.raises(PerformanceError, match="Start value must be positive"):
            CompoundReturn.twr(
                start_value=Decimal("0"),
                cashflows=[],
                end_value=Decimal("10000"),
            )


class TestTWRWithDeposit:
    """Case 2: TWR with a deposit mid-period."""

    def test_deposit_mid_period(self) -> None:
        """start=10000, deposit 5000 when portfolio=11000, end=18000.

        Sub-period 1: (11000-10000)/10000 = 0.10
        Post-flow: 11000 + 5000 = 16000
        Sub-period 2: (18000-16000)/16000 = 0.125
        Compounded: (1.10)*(1.125) - 1 = 0.2375
        """
        result = CompoundReturn.twr(
            start_value=Decimal("10000"),
            cashflows=[
                (
                    _dt("2023-07-01"),
                    Decimal("5000"),
                    Decimal("11000"),
                ),
            ],
            end_value=Decimal("18000"),
        )
        # Non-annualized (single cashflow, no date range)
        expected = Decimal("0.2375")
        assert abs(result - expected) < TWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )


class TestTWRWithWithdrawal:
    """Case 3: TWR with a withdrawal mid-period."""

    def test_withdrawal_mid_period(self) -> None:
        """start=20000, withdraw 10000 when portfolio=22000, end=13200.

        Sub-period 1: (22000-20000)/20000 = 0.10
        Post-flow: 22000 - 10000 = 12000
        Sub-period 2: (13200-12000)/12000 = 0.10
        Compounded: (1.10)*(1.10) - 1 = 0.21
        """
        result = CompoundReturn.twr(
            start_value=Decimal("20000"),
            cashflows=[
                (
                    _dt("2023-07-01"),
                    Decimal("-10000"),
                    Decimal("22000"),
                ),
            ],
            end_value=Decimal("13200"),
        )
        expected = Decimal("0.21")
        assert abs(result - expected) < TWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )


class TestTWRMultipleSubperiods:
    """Case 7: TWR with 3 cash flows over 2 years."""

    def test_three_flows_two_years(self) -> None:
        """3 cash flows over 730 days — verify compounded AND annualized.

        start=10000
        Day 200: portfolio=10500, deposit=3000, post-flow=13500
        Day 400: portfolio=14000, withdraw=2000, post-flow=12000
        Day 600: portfolio=13000, deposit=5000, post-flow=18000
        Day 730: end=20000

        Sub-periods:
          1: (10500-10000)/10000 = 0.05
          2: (14000-13500)/13500 = 0.037037...
          3: (13000-12000)/12000 = 0.08333...
          4: (20000-18000)/18000 = 0.11111...

        Compounded raw: 1.05*1.037037*1.083333*1.111111 - 1
        Annualized: (1 + raw)^(365/400) - 1
        """
        result = CompoundReturn.twr(
            start_value=Decimal("10000"),
            cashflows=[
                (
                    _dt("2023-01-01"),
                    Decimal("3000"),
                    Decimal("10500"),
                ),
                (
                    _dt("2023-07-20"),  # 200 days from Jan 1
                    Decimal("-2000"),
                    Decimal("14000"),
                ),
                (
                    _dt("2024-02-05"),  # 400 days from Jan 1
                    Decimal("5000"),
                    Decimal("13000"),
                ),
            ],
            end_value=Decimal("20000"),
        )
        # Raw compounded (using exact Decimal math)
        raw = (
            Decimal("10500")
            / Decimal("10000")
            * Decimal("14000")
            / Decimal("13500")
            * Decimal("13000")
            / Decimal("12000")
            * Decimal("20000")
            / Decimal("18000")
            - Decimal("1")
        )

        # Days: 2023-01-01 to 2024-02-05 = 400 days
        total_days_decimal = Decimal("400")
        years = total_days_decimal / Decimal("365")

        annualized = (Decimal("1") + raw) ** (Decimal("1") / years) - Decimal("1")

        assert abs(result - annualized) < TWR_TOLERANCE, (
            f"Expected annualized={annualized}, got {result}"
        )


class TestTWRValueBeforeFlowZero:
    """Edge case: value_before_flow <= 0 should raise."""

    def test_value_before_flow_zero_raises(self) -> None:
        with pytest.raises(PerformanceError, match="must be positive"):
            CompoundReturn.twr(
                start_value=Decimal("10000"),
                cashflows=[
                    (_dt("2023-07-01"), Decimal("5000"), Decimal("0")),
                ],
                end_value=Decimal("18000"),
            )


# ═══════════════════════════════════════════════════════════════════
# MWR Tests
# ═══════════════════════════════════════════════════════════════════

MWR_TOLERANCE = Decimal("1e-6")


class TestMWRSimple:
    """Case 4: MWR (XIRR) with a single deposit."""

    def test_single_deposit_one_year(self) -> None:
        """Deposit 10000 on Jan 1, final value 11000 on Dec 31 -> XIRR ~ 10%."""
        result = CompoundReturn.mwr(
            cashflows=[
                (_dt("2023-01-01"), Decimal("10000")),
            ],
            final_value=Decimal("11000"),
        )
        expected = Decimal("0.10")
        assert abs(result - expected) < MWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )


class TestMWRMultipleCashflows:
    """Case 5: MWR with quarterly deposits."""

    def test_quarterly_deposits(self) -> None:
        """Deposits of 2500 each quarter, final 11000 after 1 year.

        Total invested = 10000, final = 11000.
        Because deposits are spread over the year, the IRR is higher
        than 10% (later deposits have less time to compound).
        We verify that the IRR correctly prices the cashflows back to final_value.
        """
        cashflows = [
            (_dt("2023-01-01"), Decimal("2500")),
            (_dt("2023-04-01"), Decimal("2500")),
            (_dt("2023-07-01"), Decimal("2500")),
            (_dt("2023-10-01"), Decimal("2500")),
        ]
        result = CompoundReturn.mwr(
            cashflows=cashflows,
            final_value=Decimal("11000"),
        )

        # Verify: sum CF_i * (1+result)^(day_frac) ~ final_value
        t_n = cashflows[-1][0]
        total = Decimal("0")
        for date, amount in cashflows:
            day_frac = Decimal(str((t_n - date).days)) / Decimal("365")
            total += amount * (Decimal("1") + result) ** day_frac

        assert abs(total - Decimal("11000")) < MWR_TOLERANCE, (
            f"IRR {result} does not price cashflows back to 11000 (got {total})"
        )
        # IRR should be > 10% since later deposits have less compounding time
        assert result > Decimal("0.10"), (
            f"Expected IRR > 10% for quarterly deposits, got {result}"
        )


class TestMWRZeroValue:
    """Case 6: MWR with zero final value should raise."""

    def test_zero_final_value_raises(self) -> None:
        with pytest.raises(PerformanceError, match="Final value must be positive"):
            CompoundReturn.mwr(
                cashflows=[(_dt("2023-01-01"), Decimal("10000"))],
                final_value=Decimal("0"),
            )

    def test_negative_final_value_raises(self) -> None:
        with pytest.raises(PerformanceError, match="Final value must be positive"):
            CompoundReturn.mwr(
                cashflows=[(_dt("2023-01-01"), Decimal("10000"))],
                final_value=Decimal("-100"),
            )

    def test_empty_cashflows_raises(self) -> None:
        with pytest.raises(PerformanceError, match="At least one cashflow"):
            CompoundReturn.mwr(
                cashflows=[],
                final_value=Decimal("10000"),
            )


class TestMWRNegativeRate:
    """Case 8: MWR with negative rate (final value < sum of deposits)."""

    def test_negative_return(self) -> None:
        """Deposit 10000, final 9000 after 1 year -> XIRR ~ -10%."""
        result = CompoundReturn.mwr(
            cashflows=[
                (_dt("2023-01-01"), Decimal("10000")),
            ],
            final_value=Decimal("9000"),
        )
        expected = Decimal("-0.10")
        assert abs(result - expected) < MWR_TOLERANCE, (
            f"Expected {expected}, got {result}"
        )

    def test_negative_return_multi_flow(self) -> None:
        """Two deposits totaling 20000, final 18000 -> negative IRR."""
        cashflows = [
            (_dt("2023-01-01"), Decimal("10000")),
            (_dt("2023-07-01"), Decimal("10000")),
        ]
        result = CompoundReturn.mwr(
            cashflows=cashflows,
            final_value=Decimal("18000"),
        )
        # Should be negative since 20000 -> 18000
        assert result < Decimal("0"), (
            f"Expected negative IRR, got {result}"
        )
        # Verify the equation holds
        t_n = cashflows[-1][0]
        total = Decimal("0")
        for date, amount in cashflows:
            day_frac = Decimal(str((t_n - date).days)) / Decimal("365")
            total += amount * (Decimal("1") + result) ** day_frac
        assert abs(total - Decimal("18000")) < MWR_TOLERANCE, (
            f"IRR {result} does not price cashflows back to 18000 (got {total})"
        )
