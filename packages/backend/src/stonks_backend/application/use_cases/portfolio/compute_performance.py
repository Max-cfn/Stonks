"""ComputePerformance use case — TWR and MWR portfolio return metrics.

Delegates calculation to the domain-layer CompoundReturn calculator.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog

from stonks_backend.application.ports.portfolio import PortfolioRepositoryPort
from stonks_backend.application.use_cases.portfolio.dto import PerformanceResult
from stonks_backend.domain.portfolio.currency import Money
from stonks_backend.domain.portfolio.performance import CompoundReturn, PerformanceError
from stonks_backend.domain.portfolio.trade import Trade, TradeType

logger = structlog.get_logger(__name__)

_VALID_PERIODS = frozenset({"1M", "3M", "6M", "YTD", "1Y", "ALL"})


class ComputePerformance:
    """Compute time-weighted and money-weighted returns for a portfolio.

    Args:
        repo: Portfolio persistence port.
        compound_return: Domain calculator (may be pre-loaded with a
            ``quote_getter`` for mark-to-market-based TWR).
    """

    def __init__(
        self,
        repo: PortfolioRepositoryPort,
        compound_return: CompoundReturn,
    ) -> None:
        self._repo = repo
        self._calc = compound_return

    async def execute(
        self, user_id: UUID, period: str = "YTD"
    ) -> PerformanceResult:
        """Compute TWR and MWR for the given period.

        Args:
            user_id: Owner of the portfolio.
            period: Measurement period identifier — one of
                ``1M``, ``3M``, ``6M``, ``YTD``, ``1Y``, ``ALL``.

        Returns:
            A PerformanceResult DTO with TWR, MWR, and value details.

        Raises:
            ValueError: If ``period`` is not recognised.
            PerformanceError: If calculation fails (see ``CompoundReturn``).
        """
        if period.upper() not in _VALID_PERIODS:
            raise ValueError(
                f"Invalid period '{period}'. Must be one of: "
                f"{', '.join(sorted(_VALID_PERIODS))}"
            )
        period = period.upper()

        now = datetime.now(UTC)
        since = self._period_start(now, period)

        # ── Fetch all holdings for the user ──────────────────────────
        holdings = await self._repo.get_holdings(user_id)
        if not holdings:
            logger.info("performance_no_holdings", user_id=str(user_id), period=period)
            return PerformanceResult(
                period=period,
                twr=Decimal("0"),
                mwr=Decimal("0"),
                start_value=Money.zero("EUR"),
                end_value=Money.zero("EUR"),
                cashflows_count=0,
            )

        # ── Fetch trades for each holding in the period ──────────────
        all_trades: list[Trade] = []
        for h in holdings:
            trades = await self._repo.get_trades(h.id, since=since, until=now)
            all_trades.extend(trades)

        # Build cashflow list for TWR/MWR:
        # For MWR: (date, amount) — amount > 0 = deposit, < 0 = withdrawal
        # For TWR: (date, amount, value_before_flow)

        # We reconstruct cashflows from trades:
        #   BUY  → positive cashflow (money enters) → but cost = price*qty + fees
        #   SELL → negative cashflow (money leaves) → but proceeds = price*qty - fees
        #   DIVIDEND → negative cashflow (money leaves portfolio? No, enters as income!)

        # Stonks convention for CompoundReturn:
        #   - positive cashflow = deposit (money entering the portfolio)
        #   - negative cashflow = withdrawal

        cashflows_mwr: list[tuple[datetime, Decimal]] = []
        cashflows_twr: list[tuple[datetime, Decimal, Decimal]] = []

        # Sort trades chronologically to reconstruct intermediate values
        all_trades.sort(key=lambda t: t.date)

        # Start with initial values
        # Simplification: we use the trade history to derive cashflows.
        # For each trade, the net cashflow effect on the portfolio is:
        #   BUY: -(price * quantity + fees)  [money leaves to buy asset]
        #   SELL: +(price * quantity - fees) [money enters from sale]
        #   DIVIDEND: +(dividend_amount)     [money enters as income]

        total_invested = Decimal("0")
        for t in all_trades:
            if t.trade_type is TradeType.BUY:
                net = -(t.price * t.quantity + t.fees)
                cashflows_mwr.append((t.date, net))
                total_invested += abs(net)
            elif t.trade_type is TradeType.SELL:
                net = t.price * t.quantity - t.fees
                cashflows_mwr.append((t.date, net))
            elif t.trade_type is TradeType.DIVIDEND:
                net = t.dividend_amount or Decimal("0")
                if net > 0:
                    cashflows_mwr.append((t.date, net))

        # For TWR we need value_before_flow. Without real-time snapshots,
        # we approximate by assuming value = total_invested up to that point.
        # This is a simplification; a real implementation would use
        # mark-to-market with historical quotes.

        running_value = Decimal("0")
        for date, flow in cashflows_mwr:
            cashflows_twr.append((date, flow, max(running_value, Decimal("1"))))
            running_value += flow

        start_value = Decimal("0")
        end_value = running_value if running_value > 0 else Decimal("0")

        # Try to get TWR
        try:
            twr = self._calc.twr(
                start_value=start_value or Decimal("1"),
                cashflows=cashflows_twr,
                end_value=end_value or Decimal("1"),
            )
        except PerformanceError as exc:
            logger.warning("performance_twr_failed", error=str(exc))
            twr = Decimal("0")

        # Try to get MWR
        mwr_val: Decimal | None = None
        if cashflows_mwr:
            try:
                mwr_val = self._calc.mwr(cashflows_mwr, end_value)
            except PerformanceError as exc:
                logger.warning("performance_mwr_failed", error=str(exc))

        currency = holdings[0].currency if holdings else "EUR"

        logger.info(
            "performance_computed",
            user_id=str(user_id),
            period=period,
            twr=str(twr),
            mwr=str(mwr_val) if mwr_val is not None else "N/A",
            cashflows_count=len(cashflows_mwr),
            holdings_count=len(holdings),
        )

        return PerformanceResult(
            period=period,
            twr=twr,
            mwr=mwr_val,
            start_value=Money(start_value, currency),
            end_value=Money(end_value, currency),
            cashflows_count=len(cashflows_mwr),
        )

    @staticmethod
    def _period_start(now: datetime, period: str) -> datetime:
        """Compute the start of a measurement period.

        Args:
            now: Current UTC datetime.
            period: Period identifier (1M, 3M, 6M, YTD, 1Y, ALL).

        Returns:
            Start of the period as timezone-aware UTC datetime.
        """
        if period == "1M":
            return now - timedelta(days=30)
        if period == "3M":
            return now - timedelta(days=90)
        if period == "6M":
            return now - timedelta(days=180)
        if period == "1Y":
            return now - timedelta(days=365)
        if period == "YTD":
            return datetime(now.year, 1, 1, tzinfo=UTC)
        if period == "ALL":
            return datetime(1970, 1, 1, tzinfo=UTC)
        return now - timedelta(days=365)
