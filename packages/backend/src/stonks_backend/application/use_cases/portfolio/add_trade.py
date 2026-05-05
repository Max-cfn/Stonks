"""AddTrade use case — record a BUY, SELL, or DIVIDEND transaction.

Creates or updates a Holding, persists the Trade (Lot), and recalculates
the weighted-average cost basis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from stonks_backend.application.ports.portfolio import PortfolioRepositoryPort, PriceFeedPort
from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.ticker import InstrumentType, Ticker
from stonks_backend.domain.portfolio.trade import Trade, TradeType

logger = structlog.get_logger(__name__)


class AddTradeError(ValueError):
    """Raised when a trade cannot be recorded (e.g. insufficient quantity for a SELL)."""


class AddTrade:
    """Record a BUY, SELL, or DIVIDEND transaction on a portfolio holding.

    Args:
        repo: Portfolio persistence port.
        price_feed: Market data port (reserved for future enrichment, e.g.
            auto-detecting instrument type or validating ticker).
    """

    def __init__(self, repo: PortfolioRepositoryPort, price_feed: PriceFeedPort) -> None:
        self._repo = repo
        self._price_feed = price_feed

    async def execute(
        self,
        user_id: uuid.UUID,
        trade_type: str,
        ticker: Ticker,
        quantity: Decimal,
        price: Decimal,
        currency: str,
        fees: Decimal = Decimal("0"),
        notes: str | None = None,
    ) -> Trade:
        """Record a trade and update the corresponding holding.

        For **BUY**: increases holding quantity and updates the weighted-average
        cost::

            new_avg = (old_qty x old_avg + new_qty x new_price) / (old_qty + new_qty)

        For **SELL**: decreases holding quantity.  Average cost is left unchanged.
        The quantity sold must be ≤ the current holding quantity.

        For **DIVIDEND**: quantity must be zero; the ``dividend_amount`` is
        stored on the Trade.  Holding quantity is unchanged.

        Args:
            user_id: Owner of the portfolio.
            trade_type: One of ``"BUY"``, ``"SELL"``, ``"DIVIDEND"``.
            ticker: The instrument identifier.
            quantity: Number of units transacted (positive; zero for DIVIDEND).
            price: Price per unit (non-negative; zero for DIVIDEND).
            currency: ISO 4217 currency code.
            fees: Transaction fees (default 0).
            notes: Optional free-text notes.

        Returns:
            The persisted Trade record.

        Raises:
            AddTradeError: If the trade violates business rules (e.g. SELL
                quantity exceeds holdings).
            ValueError: If trade_type is unrecognised.
        """
        tt = TradeType(trade_type.upper())
        now = datetime.now(UTC)

        # ── Resolve or create the holding ──────────────────────────────
        existing_holdings = await self._repo.get_holdings(user_id)
        holding = self._find_holding(existing_holdings, ticker)

        if holding is None:
            # Infer instrument type from the ticker
            if ticker.is_crypto:
                instr_type = InstrumentType.CRYPTO
            else:
                instr_type = InstrumentType.STOCK

            holding = Holding(
                id=uuid.uuid4(),
                user_id=user_id,
                ticker=ticker,
                instrument_type=instr_type,
                quantity=Decimal("0"),
                avg_cost=Decimal("0"),
                currency=currency,
            )

        holding_id = holding.id

        # ── Apply trade logic ─────────────────────────────────────────
        if tt is TradeType.BUY:
            if quantity <= 0:
                raise AddTradeError(f"BUY quantity must be positive, got {quantity}")
            new_qty = holding.quantity + quantity
            if new_qty == 0:
                new_avg = Decimal("0")
            else:
                new_avg = (
                    holding.quantity * holding.avg_cost + quantity * price
                ) / new_qty
            holding = Holding(
                id=holding.id,
                user_id=holding.user_id,
                ticker=holding.ticker,
                instrument_type=holding.instrument_type,
                quantity=new_qty,
                avg_cost=new_avg,
                currency=holding.currency,
            )
            dividend_amount = None

        elif tt is TradeType.SELL:
            if quantity <= 0:
                raise AddTradeError(f"SELL quantity must be positive, got {quantity}")
            if holding.quantity < quantity:
                raise AddTradeError(
                    f"Insufficient quantity for SELL: "
                    f"holding has {holding.quantity}, tried to sell {quantity}"
                )
            new_qty = holding.quantity - quantity
            # avg_cost unchanged for SELL
            holding = Holding(
                id=holding.id,
                user_id=holding.user_id,
                ticker=holding.ticker,
                instrument_type=holding.instrument_type,
                quantity=new_qty,
                avg_cost=holding.avg_cost,
                currency=holding.currency,
            )
            dividend_amount = None

        elif tt is TradeType.DIVIDEND:
            if quantity != Decimal("0"):
                raise AddTradeError(
                    f"DIVIDEND quantity must be zero, got {quantity}"
                )
            if price < Decimal("0"):
                raise AddTradeError(
                    f"DIVIDEND price must be non-negative, got {price}"
                )
            # Holding unchanged; dividend_amount stored on Trade
            dividend_amount = price  # price field carries the dividend amount per share or total
            new_qty = holding.quantity
            holding = Holding(
                id=holding.id,
                user_id=holding.user_id,
                ticker=holding.ticker,
                instrument_type=holding.instrument_type,
                quantity=new_qty,
                avg_cost=holding.avg_cost,
                currency=holding.currency,
            )

        else:
            raise AddTradeError(f"Unknown trade type: {trade_type}")

        # ── Persist holding & trade ────────────────────────────────────
        await self._repo.save_holding(holding)

        trade = Trade(
            id=uuid.uuid4(),
            holding_id=holding_id,
            trade_type=tt,
            quantity=quantity if tt is not TradeType.DIVIDEND else Decimal("0"),
            price=price,
            currency=currency,
            date=now,
            fees=fees,
            notes=notes,
            dividend_amount=dividend_amount,
        )
        await self._repo.save_trade(trade)

        logger.info(
            "add_trade_executed",
            user_id=str(user_id),
            trade_type=tt.value,
            ticker=str(ticker),
            quantity=str(quantity),
            price=str(price),
            currency=currency,
            trade_id=str(trade.id),
        )
        return trade

    @staticmethod
    def _find_holding(holdings: list[Holding], ticker: Ticker) -> Holding | None:
        """Find a holding matching the given ticker in the user's holdings list.

        Args:
            holdings: The user's current holdings.
            ticker: The instrument ticker to search for.

        Returns:
            The matching Holding, or None if not found.
        """
        for h in holdings:
            if h.ticker == ticker:
                return h
        return None
