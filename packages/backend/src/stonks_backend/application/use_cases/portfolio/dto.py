"""DTOs for portfolio use cases — output types returned to callers.

These dataclasses live at the application layer (not domain) because they
are use-case-specific projections, not core business invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from stonks_backend.domain.portfolio.currency import Money
from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.quote import Quote


@dataclass
class HoldingValuation:
    """Market valuation of a single holding at a point in time.

    Attributes:
        holding: The underlying holding.
        quote: The market quote used for valuation.
        market_value: Current market value (quantity × mid_price).
        pnl: Unrealised profit/loss in the holding's currency.
        pnl_pct: Unrealised P&L as a percentage of average cost.
        weight_pct: Weight of this holding in the total portfolio (0-100).
    """

    holding: Holding
    quote: Quote
    market_value: Money
    pnl: Money
    pnl_pct: Decimal
    weight_pct: Decimal


@dataclass
class PortfolioValuation:
    """Aggregated portfolio valuation DTO.

    Attributes:
        holdings: Per-holding valuation details.
        total_value: Sum of all market values converted to target currency.
        total_pnl: Sum of all unrealised P&L in target currency.
        total_pnl_pct: Total P&L as percentage of total cost basis.
        currency: Reporting currency.
        as_of: UTC timestamp of valuation.
    """

    holdings: list[HoldingValuation]
    total_value: Money
    total_pnl: Money
    total_pnl_pct: Decimal
    currency: str
    as_of: datetime


@dataclass
class PerformanceResult:
    """DTO for portfolio performance calculation.

    Attributes:
        period: Period identifier (e.g. 'YTD', '1Y').
        twr: Annualized Time-Weighted Return as a decimal (0.1245 = 12.45%).
        mwr: Annualized Money-Weighted Return (XIRR), or None if not computable.
        start_value: Portfolio value at period start.
        end_value: Portfolio value at period end.
        cashflows_count: Number of cash flows used in the calculation.
    """

    period: str
    twr: Decimal
    mwr: Decimal | None
    start_value: Money
    end_value: Money
    cashflows_count: int


@dataclass
class YearSnapshot:
    """Year-by-year breakdown for compound growth simulation.

    Attributes:
        year: Calendar year number (1-based).
        balance: Portfolio balance at end of year.
        contributions_ytd: Total contributions made during this year.
        interest_ytd: Total interest earned during this year.
    """

    year: int
    balance: Decimal
    contributions_ytd: Decimal
    interest_ytd: Decimal


@dataclass
class GrowthScenario:
    """Single scenario result for compound growth simulation.

    Attributes:
        name: Human-readable scenario label.
        final_amount: Portfolio balance after the full term.
        total_contributions: Sum of all contributions made over the term.
        total_interest: Total compound interest earned.
        yearly_breakdown: Year-by-year snapshots.
    """

    name: str
    final_amount: Decimal
    total_contributions: Decimal
    total_interest: Decimal
    yearly_breakdown: list[YearSnapshot] = field(default_factory=list)


@dataclass
class CompoundGrowthResult:
    """Aggregated result for compound growth simulation.

    Attributes:
        scenarios: One GrowthScenario per simulation variant.
    """

    scenarios: list[GrowthScenario] = field(default_factory=list)
