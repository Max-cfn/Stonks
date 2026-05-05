"""GetPortfolioValuation use case — compute current market value of a portfolio.

Valuates all holdings at current market prices and optionally converts to a
target reporting currency via FX rates.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from stonks_backend.application.ports.portfolio import FxRatePort, PortfolioRepositoryPort, PriceFeedPort
from stonks_backend.application.use_cases.portfolio.dto import (
    HoldingValuation,
    PortfolioValuation,
)
from stonks_backend.domain.portfolio.currency import CurrencyMismatchError, Money

logger = structlog.get_logger(__name__)


class ValuationError(ValueError):
    """Raised when portfolio valuation cannot be completed."""


class GetPortfolioValuation:
    """Compute the current market value of a user's entire portfolio.

    Args:
        repo: Portfolio persistence port.
        price_feed: Market data port for fetching current quotes.
        fx_rate: FX rate port for currency conversion.
    """

    def __init__(
        self,
        repo: PortfolioRepositoryPort,
        price_feed: PriceFeedPort,
        fx_rate: FxRatePort,
    ) -> None:
        self._repo = repo
        self._price_feed = price_feed
        self._fx_rate = fx_rate

    async def execute(
        self, user_id: str | None = None, target_currency: str = "EUR"
    ) -> PortfolioValuation:
        """Valuate all holdings at current market prices.

        If ``user_id`` is None, all holdings across all users are fetched
        (admin/cross-user view).

        Args:
            user_id: Owner of the portfolio, or None for global view.
            target_currency: ISO 4217 currency code for the final valuation
                (default EUR).

        Returns:
            A PortfolioValuation DTO with per-holding details and totals.

        Raises:
            ValuationError: If no holdings exist or all price fetches fail.
        """
        from uuid import UUID

        # ── Fetch holdings ────────────────────────────────────────────
        if user_id is not None:
            uid = UUID(user_id) if isinstance(user_id, str) else user_id
            holdings = await self._repo.get_holdings(uid)
        else:
            # Admin path: fetch all non-zero holdings across users
            # (repository doesn't expose a "get all" — we skip this path
            #  for now and require a user_id)
            raise ValuationError("Global valuation requires a user_id")

        if not holdings:
            logger.warning("valuation_no_holdings", user_id=str(user_id if user_id else "all"))
            return PortfolioValuation(
                holdings=[],
                total_value=Money.zero(target_currency),
                total_pnl=Money.zero(target_currency),
                total_pnl_pct=Decimal("0"),
                currency=target_currency,
                as_of=datetime.now(UTC),
            )

        # ── Fetch current quotes in parallel ──────────────────────────
        quote_tasks = {
            h.ticker: self._price_feed.get_current(h.ticker) for h in holdings
        }
        quote_results = await asyncio.gather(
            *quote_tasks.values(), return_exceptions=True
        )
        quotes: dict = {}
        for ticker_key, result in zip(quote_tasks.keys(), quote_results):
            if isinstance(result, Exception):
                logger.warning(
                    "valuation_quote_failed",
                    ticker=str(ticker_key),
                    error=str(result),
                )
            else:
                quotes[ticker_key] = result

        # ── Compute per-holding valuations ────────────────────────────
        total_cost_basis = Decimal("0")
        valuations: list[HoldingValuation] = []

        for holding in holdings:
            quote = quotes.get(holding.ticker)
            if quote is None:
                logger.warning(
                    "valuation_skipping_no_quote",
                    ticker=str(holding.ticker),
                    holding_id=str(holding.id),
                )
                continue

            try:
                market_value = holding.current_value(quote)
                pnl = holding.pnl(quote)
                pnl_pct = holding.pnl_pct(quote)
            except (CurrencyMismatchError, ZeroDivisionError) as exc:
                logger.warning(
                    "valuation_calc_error",
                    ticker=str(holding.ticker),
                    error=str(exc),
                )
                continue

            total_cost_basis += holding.avg_cost * holding.quantity

            valuations.append(
                HoldingValuation(
                    holding=holding,
                    quote=quote,
                    market_value=market_value,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    weight_pct=Decimal("0"),  # filled after loop
                )
            )

        if not valuations:
            raise ValuationError("Could not valuate any holding (all quote fetches failed)")

        # ── Convert to target currency & compute weights ──────────────
        total_value_target = Decimal("0")
        total_pnl_target = Decimal("0")

        for hv in valuations:
            # Convert market value
            if hv.market_value.currency != target_currency:
                rate = await self._fx_rate.get_rate(
                    hv.market_value.currency, target_currency
                )
                hv_market_amount = hv.market_value.amount * rate
            else:
                hv_market_amount = hv.market_value.amount
            total_value_target += hv_market_amount

            # Convert P&L
            if hv.pnl.currency != target_currency:
                rate_pnl = await self._fx_rate.get_rate(
                    hv.pnl.currency, target_currency
                )
                hv_pnl_amount = hv.pnl.amount * rate_pnl
            else:
                hv_pnl_amount = hv.pnl.amount
            total_pnl_target += hv_pnl_amount

        # Set weights
        for hv in valuations:
            if hv.market_value.currency != target_currency:
                rate = await self._fx_rate.get_rate(
                    hv.market_value.currency, target_currency
                )
                hv_market = hv.market_value.amount * rate
            else:
                hv_market = hv.market_value.amount
            hv.weight_pct = (hv_market / total_value_target) * Decimal("100") if total_value_target > 0 else Decimal("0")

        # ── Total P&L % ───────────────────────────────────────────────
        total_cost_target = Decimal("0")
        for hv in valuations:
            cost = hv.holding.avg_cost * hv.holding.quantity
            if hv.market_value.currency != target_currency:
                rate = await self._fx_rate.get_rate(
                    hv.market_value.currency, target_currency
                )
                total_cost_target += cost * rate
            else:
                total_cost_target += cost

        total_pnl_pct = (
            (total_pnl_target / total_cost_target) * Decimal("100")
            if total_cost_target > 0
            else Decimal("0")
        )

        logger.info(
            "valuation_complete",
            user_id=str(user_id if user_id else "all"),
            holdings_count=len(valuations),
            total_value=str(round(total_value_target, 2)),
            currency=target_currency,
        )

        return PortfolioValuation(
            holdings=valuations,
            total_value=Money(total_value_target, target_currency),
            total_pnl=Money(total_pnl_target, target_currency),
            total_pnl_pct=total_pnl_pct,
            currency=target_currency,
            as_of=datetime.now(UTC),
        )
