"""Portfolio performance calculators — TWR and MWR (XIRR).

Implements Time-Weighted Return (TWR) and Money-Weighted Return (MWR / XIRR)
for investment portfolio performance measurement.

TWR segments the period at each cash flow, computes sub-period returns,
and compounds them geometrically — independent of the size/timing of flows.

MWR finds the internal rate of return (IRR) that equalizes the present value
of all cash flows with the final portfolio value — sensitive to flow timing.

Uses ``scipy.optimize.newton`` if available; otherwise falls back to a
manual Newton-Raphson implementation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Ticker
from stonks_backend.domain.portfolio.trade import Trade

logger = logging.getLogger(__name__)

# ── Optional scipy import ──────────────────────────────────────────
try:
    from scipy.optimize import newton  # type: ignore[import-untyped]

    _HAS_SCIPY = True
except ImportError:  # pragma: no cover
    _HAS_SCIPY = False


# ═══════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════


class PerformanceError(ValueError):
    """Raised when a performance calculation cannot be completed."""


# ═══════════════════════════════════════════════════════════════════
# Newton-Raphson fallback (when scipy is absent)
# ═══════════════════════════════════════════════════════════════════

_MAX_NEWTON_ITERATIONS = 100
_NEWTON_TOLERANCE = Decimal("1e-8")
_DEFAULT_GUESS = Decimal("0.1")


def _xirr_f(
    rate: Decimal,
    cashflows: list[tuple[datetime, Decimal]],
    final_value: Decimal,
    days_to_end: list[Decimal],
) -> Decimal:
    r"""Evaluate the XIRR residual function f(r).

    f(r) = sum CF_i * (1+r)^{day\_frac_i} - final\_value

    Args:
        rate: Current guess for the IRR (as Decimal).
        cashflows: (date, amount) tuples (amount > 0 = deposit).
        final_value: Terminal portfolio value.
        days_to_end: Pre-computed (t_n - t_i) / 365 for each cashflow.

    Returns:
        Decimal residual — zero when rate equals the IRR.
    """
    total = Decimal("0")
    one_plus_r = Decimal("1") + rate
    for (_, amount), day_frac in zip(cashflows, days_to_end, strict=True):
        total += amount * (one_plus_r**day_frac)
    return total - final_value


def _xirr_fprime(
    rate: Decimal,
    cashflows: list[tuple[datetime, Decimal]],
    days_to_end: list[Decimal],
) -> Decimal:
    r"""Evaluate the first derivative of the XIRR residual.

    f'(r) = sum CF_i * day\_frac_i * (1+r)^{day\_frac_i - 1}

    Args:
        rate: Current guess for the IRR.
        cashflows: (date, amount) tuples.
        days_to_end: Pre-computed (t_n - t_i) / 365.

    Returns:
        Decimal derivative value.
    """
    total = Decimal("0")
    one_plus_r = Decimal("1") + rate
    for (_, amount), day_frac in zip(cashflows, days_to_end, strict=True):
        if day_frac == 0:
            continue  # derivative is 0 for flows at t_n
        total += amount * day_frac * (one_plus_r ** (day_frac - Decimal("1")))
    return total


def _newton_raphson(
    cashflows: list[tuple[datetime, Decimal]],
    final_value: Decimal,
    days_to_end: list[Decimal],
    guess: Decimal = _DEFAULT_GUESS,
    tolerance: Decimal = _NEWTON_TOLERANCE,
    max_iterations: int = _MAX_NEWTON_ITERATIONS,
) -> Decimal:
    """Manual Newton-Raphson root-finding for XIRR.

    Args:
        cashflows: (date, amount) tuples.
        final_value: Terminal portfolio value.
        days_to_end: Pre-computed (t_n - t_i) / 365.
        guess: Initial rate guess (default 0.1 = 10%).
        tolerance: Convergence tolerance on |f(r)|.
        max_iterations: Maximum iterations before failure.

    Returns:
        The IRR as a Decimal.

    Raises:
        PerformanceError: If the solver fails to converge.
    """
    rate = guess
    for i in range(max_iterations):
        f_val = _xirr_f(rate, cashflows, final_value, days_to_end)
        if abs(f_val) < tolerance:
            logger.debug("Newton-Raphson converged in %d iterations", i + 1)
            return rate
        fprime_val = _xirr_fprime(rate, cashflows, days_to_end)
        if fprime_val == 0:
            raise PerformanceError(
                f"Newton-Raphson stalled: zero derivative at rate={float(rate):f}"
            )
        rate = rate - f_val / fprime_val
        # Guard against pathological negative rates below -100%
        if rate <= Decimal("-0.999"):
            rate = Decimal("-0.5")

    raise PerformanceError(
        f"Newton-Raphson did not converge after {max_iterations} iterations"
    )


# ═══════════════════════════════════════════════════════════════════
# CompoundReturn
# ═══════════════════════════════════════════════════════════════════


class CompoundReturn:
    """Calculates compound portfolio returns (TWR and MWR/XIRR).

    Stores a list of trades and optionally a callable to fetch
    historical quotes for mark-to-market valuations.

    Attributes:
        trades: The list of Trade records.
        quote_getter: Optional ``Callable[[Ticker, datetime], Quote]``.
    """

    def __init__(
        self,
        trades: list[Trade] | None = None,
        quote_getter: Callable[[Ticker, datetime], Quote] | None = None,
    ) -> None:
        self.trades = trades or []
        self.quote_getter = quote_getter

    # ── TWR (Time-Weighted Return) ─────────────────────────────────

    @staticmethod
    def twr(
        start_value: Decimal,
        cashflows: list[tuple[datetime, Decimal, Decimal]],
        end_value: Decimal,
    ) -> Decimal:
        """Compute the annualized Time-Weighted Return.

        Segments the measurement period at each external cash flow,
        computes sub-period returns, and compounds them geometrically.

        The TWR is independent of the size and timing of deposits/withdrawals,
        isolating the manager's investment skill.

        Args:
            start_value: Portfolio value at the beginning of the period.
            cashflows: List of ``(date, flow_amount, value_before_flow)``
                tuples.  ``flow_amount > 0`` is a deposit, ``< 0`` a
                withdrawal.  ``value_before_flow`` is the portfolio value
                *immediately before* the cash flow occurred (used to compute
                the sub-period return that just ended).
            end_value: Portfolio value at the end of the period.

        Returns:
            The annualized TWR as a ``Decimal``
            (e.g. ``Decimal("0.1245")`` = 12.45 %).

            If there are no cashflows the raw (non-annualized) return is
            returned since no date range can be inferred.

        Raises:
            PerformanceError: If *start_value* <= 0, *end_value* <= 0, or any
                intermediate portfolio value is non-positive.
        """
        if start_value <= 0:
            raise PerformanceError(
                f"Start value must be positive, got {start_value}"
            )
        if end_value <= 0:
            raise PerformanceError(
                f"End value must be positive, got {end_value}"
            )

        sorted_cfs = sorted(cashflows, key=lambda x: x[0])

        if not sorted_cfs:
            # No cashflows -> simple return, no annualization possible
            return (end_value - start_value) / start_value

        # Determine period bounds from cashflow dates
        t_start = sorted_cfs[0][0]
        t_end = sorted_cfs[-1][0]
        days = (t_end - t_start).days
        if days <= 0:
            days = 365  # assume 1 year when all flows are same-day

        current_value = start_value
        cumulative_factor = Decimal("1")

        for _, flow_amount, value_before in sorted_cfs:
            if value_before <= 0:
                raise PerformanceError(
                    f"Portfolio value before flow must be positive, got {value_before}"
                )
            # Sub-period return
            sub_return = (value_before - current_value) / current_value
            cumulative_factor *= Decimal("1") + sub_return
            # Post-flow value
            current_value = value_before + flow_amount
            if current_value <= 0:
                raise PerformanceError(
                    f"Portfolio value after flow must be positive, got {current_value}"
                )

        # Final sub-period: from last post-flow value to end_value
        if current_value <= 0:
            raise PerformanceError("Portfolio value before final sub-period is non-positive")
        final_return = (end_value - current_value) / current_value
        cumulative_factor *= Decimal("1") + final_return

        cumulative_return = cumulative_factor - Decimal("1")

        # Annualize: (1 + R_cum)^(365 / days) - 1
        if days > 0 and cumulative_return > Decimal("-1"):
            annualized = (
                (Decimal("1") + cumulative_return)
                ** (Decimal("365") / Decimal(str(days)))
                - Decimal("1")
            )
            return annualized
        return cumulative_return

    # ── MWR (Money-Weighted Return / XIRR) ─────────────────────────

    @staticmethod
    def mwr(
        cashflows: list[tuple[datetime, Decimal]],
        final_value: Decimal,
    ) -> Decimal:
        """Compute the Money-Weighted Return (XIRR).

        Finds the annualised discount rate *r* that makes the present
        value of all cash flows equal to the terminal portfolio value::

            sum CF_i * (1 + r)^{(t_n - t_i) / 365} - final_value = 0

        Uses ``scipy.optimize.newton`` when available, otherwise a
        manual Newton-Raphson implementation.

        **Stonks convention**: a positive cash-flow amount is a deposit
        (money entering the portfolio); a negative amount is a withdrawal.

        Args:
            cashflows: ``(date, amount)`` tuples sorted or unsorted.
                Internally sorted by date ascending.
            final_value: Portfolio value at the end of the measurement
                period (must be positive).

        Returns:
            The annualised MWR as a ``Decimal``
            (e.g. ``Decimal("0.1245")`` = 12.45 %).

        Raises:
            PerformanceError: If *final_value* <= 0, *cashflows* is empty,
                or the solver does not converge.
        """
        if final_value <= 0:
            raise PerformanceError(
                f"Final value must be positive, got {final_value}"
            )
        if not cashflows:
            raise PerformanceError("At least one cashflow is required for MWR")

        sorted_cfs = sorted(cashflows, key=lambda x: x[0])
        t_n = sorted_cfs[-1][0]

        days_to_end: list[Decimal] = []
        for date, _ in sorted_cfs:
            days = (t_n - date).days
            days_to_end.append(Decimal(str(days)) / Decimal("365"))

        # Sanity check: if all cashflows are at t_n, IRR is degenerate
        if all(d == 0 for d in days_to_end):
            total_invested = sum(amount for _, amount in sorted_cfs)
            if total_invested == 0:
                raise PerformanceError(
                    "Sum of cashflows is zero; cannot compute MWR"
                )
            raw_return = (final_value - total_invested) / total_invested
            return raw_return

        if _HAS_SCIPY:
            # Use scipy's newton (float-based, convert at boundaries)
            def _f_scipy(r: float) -> float:
                d = Decimal(str(r))
                return float(_xirr_f(d, sorted_cfs, final_value, days_to_end))

            def _fprime_scipy(r: float) -> float:
                d = Decimal(str(r))
                return float(_xirr_fprime(d, sorted_cfs, days_to_end))

            try:
                result_float = newton(
                    _f_scipy,
                    x0=0.1,
                    fprime=_fprime_scipy,
                    tol=1e-8,
                    maxiter=100,
                )
                return Decimal(str(result_float))
            except RuntimeError as exc:
                raise PerformanceError(
                    f"scipy.newton failed to converge: {exc}"
                ) from exc
        else:
            return _newton_raphson(sorted_cfs, final_value, days_to_end)

    # ── Period TWR (mark-to-market) ────────────────────────────────

    def compute_period_twr(
        self,
        holdings: list[Holding],
        quotes_start: dict[Ticker, Quote],
        quotes_end: dict[Ticker, Quote],
        cashflows: list[tuple[datetime, Decimal, Decimal]] | None = None,
    ) -> Decimal:
        """Compute the annualized TWR over a period using mark-to-market valuations.

        The start value is the sum of each holding's ``current_value``
        against *quotes_start*.  The end value is likewise computed from
        *quotes_end*.  Cash flows segment the period into sub-periods.

        Args:
            holdings: The list of holdings to value.
            quotes_start: Quote for each holding's ticker at period start.
            quotes_end: Quote for each holding's ticker at period end.
            cashflows: Optional ``(date, amount, value_before_flow)``
                tuples for sub-period segmentation.

        Returns:
            Annualized TWR as a ``Decimal``.

        Raises:
            PerformanceError: If a holding lacks a quote, or start/end
                values are non-positive.
        """
        # Compute start value
        start_value = Decimal("0")
        for h in holdings:
            if h.ticker not in quotes_start:
                raise PerformanceError(
                    f"No start quote for ticker {h.ticker}"
                )
            start_value += h.current_value(quotes_start[h.ticker]).amount

        if start_value <= 0:
            raise PerformanceError(
                f"Start portfolio value must be positive, got {start_value}"
            )

        # Compute end value
        end_value = Decimal("0")
        for h in holdings:
            if h.ticker not in quotes_end:
                raise PerformanceError(
                    f"No end quote for ticker {h.ticker}"
                )
            end_value += h.current_value(quotes_end[h.ticker]).amount

        if end_value <= 0:
            raise PerformanceError(
                f"End portfolio value must be positive, got {end_value}"
            )

        cfs = cashflows or []
        return CompoundReturn.twr(start_value, cfs, end_value)
