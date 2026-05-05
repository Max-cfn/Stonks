"""SimulateCompoundGrowth use case — compound interest projection with scenarios.

Pure calculation — no dependencies on ports or external services.
Supports multiple scenarios (conservative, moderate, aggressive) run in one call.
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from stonks_backend.application.use_cases.portfolio.dto import (
    CompoundGrowthResult,
    GrowthScenario,
    YearSnapshot,
)

logger = structlog.get_logger(__name__)

_MONTHS_PER_YEAR = Decimal("12")


class SimulateCompoundGrowth:
    """Static calculator for compound growth projections.

    No dependencies — pure domain calculation.
    """

    @staticmethod
    def compute(
        capital: Decimal,
        monthly_contrib: Decimal,
        annual_rate: Decimal,
        years: int,
        scenarios: list[dict] | None = None,
    ) -> CompoundGrowthResult:
        """Compute compound growth for one or more rate scenarios.

        Each scenario runs an independent month-by-month projection, using
        monthly compounding::

            balance_{t+1} = balance_t × (1 + r/12) + monthly_contrib

        where *r* is the scenario's annual rate (expressed as a decimal;
        0.07 = 7%).

        Args:
            capital: Initial lump-sum investment.
            monthly_contrib: Amount added at the end of each month.
            annual_rate: Default annual interest rate (decimal, e.g. 0.07).
                Used when ``scenarios`` is None.
            years: Projection horizon in years (must be ≥ 1).
            scenarios: Optional list of scenario overrides. Each dict may
                contain:

                - ``name`` (str): scenario label.
                - ``rate`` (float | Decimal | str): annual rate override.

                If None, a single ``"Default"`` scenario is run with
                ``annual_rate``.

        Returns:
            A ``CompoundGrowthResult`` containing one ``GrowthScenario`` per
            variant.

        Raises:
            ValueError: If *years* < 1, *capital* < 0, or any rate < -1.
        """
        if years < 1:
            raise ValueError(f"Years must be ≥ 1, got {years}")
        if capital < 0:
            raise ValueError(f"Capital must be non-negative, got {capital}")
        if monthly_contrib < 0:
            raise ValueError(
                f"Monthly contribution must be non-negative, got {monthly_contrib}"
            )
        if annual_rate <= Decimal("-1"):
            raise ValueError(
                f"Annual rate must be > -1 (cannot lose >100%), got {annual_rate}"
            )

        # Build scenario list
        scenario_defs: list[dict] = (
            scenarios
            if scenarios
            else [{"name": "Default", "rate": str(annual_rate)}]
        )

        result_scenarios: list[GrowthScenario] = []

        for scen_def in scenario_defs:
            name = scen_def.get("name", "Unnamed")
            raw_rate = scen_def.get("rate", str(annual_rate))

            if isinstance(raw_rate, (int, float)):
                rate = Decimal(str(raw_rate))
            elif isinstance(raw_rate, str):
                rate = Decimal(raw_rate)
            else:
                rate = Decimal(raw_rate)  # type: ignore[arg-type]

            if rate <= Decimal("-1"):
                raise ValueError(
                    f"Scenario '{name}': rate must be > -1, got {rate}"
                )

            monthly_rate = rate / _MONTHS_PER_YEAR

            balance = capital
            total_contributions = capital
            yearly_snapshots: list[YearSnapshot] = []

            for year_num in range(1, years + 1):
                contributions_ytd = Decimal("0")
                interest_ytd = Decimal("0")

                for _month in range(12):
                    # Interest earned this month
                    interest = balance * monthly_rate
                    interest_ytd += interest
                    balance += interest

                    # End-of-month contribution
                    balance += monthly_contrib
                    contributions_ytd += monthly_contrib

                total_contributions += contributions_ytd

                yearly_snapshots.append(
                    YearSnapshot(
                        year=year_num,
                        balance=balance.quantize(Decimal("0.01")),
                        contributions_ytd=contributions_ytd.quantize(Decimal("0.01")),
                        interest_ytd=interest_ytd.quantize(Decimal("0.01")),
                    )
                )

            total_interest = balance - total_contributions

            result_scenarios.append(
                GrowthScenario(
                    name=name,
                    final_amount=balance.quantize(Decimal("0.01")),
                    total_contributions=total_contributions.quantize(Decimal("0.01")),
                    total_interest=total_interest.quantize(Decimal("0.01")),
                    yearly_breakdown=yearly_snapshots,
                )
            )

        logger.info(
            "compound_growth_computed",
            capital=str(capital),
            monthly_contrib=str(monthly_contrib),
            years=years,
            scenario_count=len(result_scenarios),
        )

        return CompoundGrowthResult(scenarios=result_scenarios)
