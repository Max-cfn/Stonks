"""PortfolioSqlRepository — persiste les entités portfolio avec SQLAlchemy async.

Implements PortfolioRepositoryPort.
Handles holdings, trades (lots), quotes, alerts, and news digests.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.portfolio import (
    NewsDigest,
    PortfolioRepositoryPort,
    PriceAlert,
)
from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Exchange, InstrumentType, Ticker
from stonks_backend.domain.portfolio.trade import Trade, TradeType
from stonks_backend.infrastructure.persistence.portfolio_models import (
    PortfolioAlertModel,
    PortfolioHoldingModel,
    PortfolioLotModel,
    PortfolioNewsDigestModel,
    PortfolioQuoteModel,
)

logger = logging.getLogger(__name__)


class PortfolioSqlRepository(PortfolioRepositoryPort):
    """SQLAlchemy async adapter for portfolio persistence.

    Args:
        session: Async SQLAlchemy session for database operations.

    Usage:
        repo = PortfolioSqlRepository(session)
        holdings = await repo.get_holdings(user_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Holdings ──────────────────────────────────────────────────────────

    async def get_holdings(self, user_id: UUID) -> list[Holding]:
        """Retrieve all holdings for a user.

        Args:
            user_id: Owner's user identifier.

        Returns:
            List of Holding domain objects (empty list if none).
        """
        stmt = select(PortfolioHoldingModel).where(PortfolioHoldingModel.user_id == user_id)
        result = await self._session.execute(stmt)
        return [self._model_to_holding(m) for m in result.scalars().all()]

    async def get_holding(self, holding_id: UUID) -> Holding | None:
        """Retrieve a single holding by ID.

        Args:
            holding_id: Unique holding identifier.

        Returns:
            The Holding domain object, or None if not found.
        """
        stmt = select(PortfolioHoldingModel).where(PortfolioHoldingModel.id == holding_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_holding(model) if model is not None else None

    async def save_holding(self, holding: Holding) -> None:
        """Insert or update (upsert) a holding.

        Uses PostgreSQL INSERT ... ON CONFLICT on the unique constraint
        (user_id, ticker_symbol, ticker_exchange).

        Args:
            holding: The Holding domain object to persist.
        """
        ticker_exchange = (
            holding.ticker.exchange.value if holding.ticker.exchange is not None else None
        )

        stmt = insert(PortfolioHoldingModel).values(
            id=holding.id,
            user_id=holding.user_id,
            ticker_symbol=holding.ticker.symbol,
            ticker_exchange=ticker_exchange,
            instrument_type=holding.instrument_type.value,
            quantity=holding.quantity,
            avg_cost=holding.avg_cost,
            currency=holding.currency,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_holding_user_ticker_exchange",
            set_={
                "instrument_type": stmt.excluded.instrument_type,
                "quantity": stmt.excluded.quantity,
                "avg_cost": stmt.excluded.avg_cost,
                "currency": stmt.excluded.currency,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_holding(self, holding_id: UUID) -> None:
        """Remove a holding by ID.

        Args:
            holding_id: Unique holding identifier.
        """
        stmt = select(PortfolioHoldingModel).where(PortfolioHoldingModel.id == holding_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    # ── Trades ────────────────────────────────────────────────────────────

    async def save_trade(self, trade: Trade) -> None:
        """Persist a trade record.

        Args:
            trade: The Trade domain object to persist.
        """
        model = self._trade_to_model(trade)
        self._session.add(model)
        await self._session.flush()

    async def get_trades(
        self,
        holding_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Trade]:
        """Retrieve trades for a holding, optionally filtered by date range.

        Args:
            holding_id: Parent holding identifier.
            since: Inclusive start of date range (UTC).
            until: Inclusive end of date range (UTC).

        Returns:
            Chronologically ordered list of Trade domain objects (oldest first).
        """
        stmt = select(PortfolioLotModel).where(PortfolioLotModel.holding_id == holding_id)
        if since is not None:
            stmt = stmt.where(PortfolioLotModel.date >= since)
        if until is not None:
            stmt = stmt.where(PortfolioLotModel.date <= until)
        stmt = stmt.order_by(PortfolioLotModel.date.asc())

        result = await self._session.execute(stmt)
        return [self._model_to_trade(m) for m in result.scalars().all()]

    # ── Quotes ────────────────────────────────────────────────────────────

    async def save_quote(self, quote: Quote) -> None:
        """Persist a market quote.

        Args:
            quote: The Quote domain object to persist.
        """
        model = self._quote_to_model(quote)
        self._session.add(model)
        await self._session.flush()

    async def get_quotes(self, ticker: Ticker, since: datetime, until: datetime) -> list[Quote]:
        """Retrieve persisted quotes for a ticker in a date range.

        Args:
            ticker: The instrument identifier.
            since: Inclusive start of range (UTC).
            until: Inclusive end of range (UTC).

        Returns:
            Chronologically ordered list of Quote domain objects (oldest first).
        """
        exchange_str = ticker.exchange.value if ticker.exchange is not None else None
        stmt = (
            select(PortfolioQuoteModel)
            .where(PortfolioQuoteModel.ticker_symbol == ticker.symbol)
            .where(PortfolioQuoteModel.time >= since)
            .where(PortfolioQuoteModel.time <= until)
            .order_by(PortfolioQuoteModel.time.asc())
        )
        if exchange_str is not None:
            stmt = stmt.where(PortfolioQuoteModel.ticker_exchange == exchange_str)
        else:
            stmt = stmt.where(PortfolioQuoteModel.ticker_exchange.is_(None))

        result = await self._session.execute(stmt)
        return [self._model_to_quote(m) for m in result.scalars().all()]

    async def get_latest_quote(self, ticker: Ticker) -> Quote | None:
        """Retrieve the most recent persisted quote for a ticker.

        Args:
            ticker: The instrument identifier.

        Returns:
            The latest Quote domain object, or None if no quote has been persisted.
        """
        exchange_str = ticker.exchange.value if ticker.exchange is not None else None
        stmt = (
            select(PortfolioQuoteModel)
            .where(PortfolioQuoteModel.ticker_symbol == ticker.symbol)
            .order_by(PortfolioQuoteModel.time.desc())
            .limit(1)
        )
        if exchange_str is not None:
            stmt = stmt.where(PortfolioQuoteModel.ticker_exchange == exchange_str)
        else:
            stmt = stmt.where(PortfolioQuoteModel.ticker_exchange.is_(None))

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_quote(model) if model is not None else None

    # ── Price alerts ──────────────────────────────────────────────────────

    async def save_alert(self, alert: PriceAlert) -> None:
        """Persist a price alert (insert only, no upsert).

        Args:
            alert: The PriceAlert to persist.
        """
        model = self._alert_to_model(alert)
        self._session.add(model)
        await self._session.flush()

    async def get_alerts(self, user_id: UUID, triggered: bool | None = None) -> list[PriceAlert]:
        """Retrieve price alerts for a user, optionally filtered by triggered status.

        Args:
            user_id: Owner's user identifier.
            triggered: If True, only triggered alerts; if False, only pending;
                if None, all alerts.

        Returns:
            List of PriceAlert objects.
        """
        stmt = select(PortfolioAlertModel).where(PortfolioAlertModel.user_id == user_id)
        if triggered is not None:
            stmt = stmt.where(PortfolioAlertModel.triggered == triggered)
        result = await self._session.execute(stmt)
        return [self._model_to_alert(m) for m in result.scalars().all()]

    async def delete_alert(self, alert_id: UUID) -> None:
        """Remove a price alert by ID.

        Args:
            alert_id: Unique alert identifier.
        """
        stmt = select(PortfolioAlertModel).where(PortfolioAlertModel.id == alert_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def mark_alert_triggered(self, alert_id: UUID) -> None:
        """Mark a price alert as triggered.

        Sets triggered=True and triggered_at=now() in UTC.

        Args:
            alert_id: Unique alert identifier.
        """
        now = datetime.now(UTC)
        stmt = (
            update(PortfolioAlertModel)
            .where(PortfolioAlertModel.id == alert_id)
            .values(triggered=True, triggered_at=now)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    # ── News digest ───────────────────────────────────────────────────────

    async def save_news_digest(self, digest: NewsDigest) -> None:
        """Persist a news digest.

        Args:
            digest: The NewsDigest to persist.
        """
        model = self._digest_to_model(digest)
        self._session.add(model)
        await self._session.flush()

    async def get_latest_digest(self, user_id: UUID | None = None) -> NewsDigest | None:
        """Retrieve the most recent news digest (global scope).

        Args:
            user_id: Optional user identifier (currently unused — global digests).

        Returns:
            The latest NewsDigest, or None if none found.
        """
        stmt = (
            select(PortfolioNewsDigestModel)
            .order_by(PortfolioNewsDigestModel.processed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_digest(model) if model is not None else None

    # ── Model ↔ Domain mappers ────────────────────────────────────────────

    @staticmethod
    def _holding_to_model(h: Holding) -> PortfolioHoldingModel:
        """Convert domain Holding → ORM PortfolioHoldingModel.

        Args:
            h: Domain Holding object.

        Returns:
            A new PortfolioHoldingModel instance (not attached to any session).
        """
        return PortfolioHoldingModel(
            id=h.id,
            user_id=h.user_id,
            ticker_symbol=h.ticker.symbol,
            ticker_exchange=h.ticker.exchange.value if h.ticker.exchange is not None else None,
            instrument_type=h.instrument_type.value,
            quantity=h.quantity,
            avg_cost=h.avg_cost,
            currency=h.currency,
        )

    @staticmethod
    def _model_to_holding(m: PortfolioHoldingModel) -> Holding:
        """Convert ORM PortfolioHoldingModel → domain Holding.

        Args:
            m: ORM model instance.

        Returns:
            A new Holding domain object.
        """
        exchange = Exchange(m.ticker_exchange) if m.ticker_exchange is not None else None
        return Holding(
            id=m.id,
            user_id=m.user_id,
            ticker=Ticker(m.ticker_symbol, exchange),
            instrument_type=InstrumentType(m.instrument_type),
            quantity=m.quantity,
            avg_cost=m.avg_cost,
            currency=m.currency,
        )

    @staticmethod
    def _trade_to_model(t: Trade) -> PortfolioLotModel:
        """Convert domain Trade → ORM PortfolioLotModel.

        Args:
            t: Domain Trade object.

        Returns:
            A new PortfolioLotModel instance.
        """
        return PortfolioLotModel(
            id=t.id,
            holding_id=t.holding_id,
            trade_type=t.trade_type.value,
            quantity=t.quantity,
            price=t.price,
            currency=t.currency,
            fees=t.fees,
            date=t.date,
            notes=t.notes,
            dividend_amount=t.dividend_amount,
        )

    @staticmethod
    def _model_to_trade(m: PortfolioLotModel) -> Trade:
        """Convert ORM PortfolioLotModel → domain Trade.

        Args:
            m: ORM model instance.

        Returns:
            A new Trade domain object.
        """
        return Trade(
            id=m.id,
            holding_id=m.holding_id,
            trade_type=TradeType(m.trade_type),
            quantity=m.quantity,
            price=m.price,
            currency=m.currency,
            date=m.date,
            fees=m.fees if m.fees is not None else Decimal("0"),
            notes=m.notes,
            dividend_amount=m.dividend_amount,
        )

    @staticmethod
    def _quote_to_model(q: Quote) -> PortfolioQuoteModel:
        """Convert domain Quote → ORM PortfolioQuoteModel.

        Args:
            q: Domain Quote object.

        Returns:
            A new PortfolioQuoteModel instance.
        """
        return PortfolioQuoteModel(
            time=q.timestamp,
            ticker_symbol=q.ticker.symbol,
            ticker_exchange=q.ticker.exchange.value if q.ticker.exchange is not None else None,
            price=q.price,
            currency=q.currency,
            source=q.source,
            bid=q.bid,
            ask=q.ask,
            volume=q.volume,
        )

    @staticmethod
    def _model_to_quote(m: PortfolioQuoteModel) -> Quote:
        """Convert ORM PortfolioQuoteModel → domain Quote.

        Args:
            m: ORM model instance.

        Returns:
            A new Quote domain object.
        """
        exchange = Exchange(m.ticker_exchange) if m.ticker_exchange is not None else None
        return Quote(
            ticker=Ticker(m.ticker_symbol, exchange),
            price=m.price,
            currency=m.currency,
            timestamp=m.time,
            source=m.source,
            bid=m.bid,
            ask=m.ask,
            volume=m.volume,
        )

    @staticmethod
    def _alert_to_model(a: PriceAlert) -> PortfolioAlertModel:
        """Convert domain PriceAlert → ORM PortfolioAlertModel.

        Args:
            a: Domain PriceAlert object.

        Returns:
            A new PortfolioAlertModel instance.
        """
        return PortfolioAlertModel(
            id=a.id,
            user_id=a.user_id,
            ticker_symbol=a.ticker.symbol,
            ticker_exchange=a.ticker.exchange.value if a.ticker.exchange is not None else None,
            threshold=a.threshold,
            direction=a.direction,
            webhook_url=a.webhook_url,
            triggered=a.triggered,
            triggered_at=a.triggered_at,
            created_at=a.created_at,
        )

    @staticmethod
    def _model_to_alert(m: PortfolioAlertModel) -> PriceAlert:
        """Convert ORM PortfolioAlertModel → domain PriceAlert.

        Args:
            m: ORM model instance.

        Returns:
            A new PriceAlert object.
        """
        exchange = Exchange(m.ticker_exchange) if m.ticker_exchange is not None else None
        return PriceAlert(
            id=m.id,
            user_id=m.user_id,
            ticker=Ticker(m.ticker_symbol, exchange),
            threshold=m.threshold,
            direction=m.direction,
            webhook_url=m.webhook_url,
            triggered=m.triggered if m.triggered else False,
            triggered_at=m.triggered_at,
            created_at=m.created_at,
        )

    @staticmethod
    def _digest_to_model(d: NewsDigest) -> PortfolioNewsDigestModel:
        """Convert domain NewsDigest → ORM PortfolioNewsDigestModel.

        Uses the digest's UUID id as the guid for deduplication if no explicit
        guid is available.

        Args:
            d: Domain NewsDigest object.

        Returns:
            A new PortfolioNewsDigestModel instance.
        """
        return PortfolioNewsDigestModel(
            id=d.id,
            source=d.source,
            title=d.title,
            url=d.url,
            published_at=d.published_at,
            sentiment_label=d.sentiment_label,
            sentiment_score=d.sentiment_score,
            summary=d.summary,
            affected_tickers=d.affected_tickers,
            guid=str(d.id),
            processed_at=d.processed_at,
        )

    @staticmethod
    def _model_to_digest(m: PortfolioNewsDigestModel) -> NewsDigest:
        """Convert ORM PortfolioNewsDigestModel → domain NewsDigest.

        Args:
            m: ORM model instance.

        Returns:
            A new NewsDigest object.
        """
        return NewsDigest(
            id=m.id,
            source=m.source,
            title=m.title,
            url=m.url,
            published_at=m.published_at,
            sentiment_label=m.sentiment_label,
            sentiment_score=m.sentiment_score,
            summary=m.summary,
            affected_tickers=m.affected_tickers,
            processed_at=m.processed_at,
        )

    # ── Workers helpers ─────────────────────────────────────────────────

    async def get_active_tickers(self) -> list[Ticker]:
        """Return distinct tickers from all holdings across all users.

        Returns:
            List of unique Ticker objects (empty list if no holdings).
        """
        from sqlalchemy import distinct

        stmt = select(
            distinct(PortfolioHoldingModel.ticker_symbol),
            PortfolioHoldingModel.ticker_exchange,
        )
        result = await self._session.execute(stmt)
        tickers: list[Ticker] = []
        for row in result.all():
            symbol = row[0]
            exchange_val = row[1]
            exchange = Exchange(exchange_val) if exchange_val is not None else None
            tickers.append(Ticker(symbol, exchange))
        return tickers

    async def get_active_user_ids(self) -> list[UUID]:
        """Return distinct user IDs who have holdings or alerts.

        Combines user IDs from portfolio_holdings and portfolio_alerts tables.

        Returns:
            List of unique user UUIDs (empty list if none).
        """
        stmt_holdings = select(PortfolioHoldingModel.user_id)
        stmt_alerts = select(PortfolioAlertModel.user_id)
        union_stmt = stmt_holdings.union(stmt_alerts)
        result = await self._session.execute(union_stmt)
        return [row[0] for row in result.all()]

    async def aclose(self) -> None:
        """Close the underlying database session.

        Call this when the repository is no longer needed (e.g., at the end
        of a worker poll cycle) to return the connection to the pool.
        """
        await self._session.close()

    async def commit_and_close(self) -> None:
        """Commit pending changes and close the session.

        Safer alternative to aclose() when writes have been performed
        (e.g. worker cycles that persist quotes/alerts/digests).
        """
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        finally:
            await self._session.close()

    async def rollback_and_close(self) -> None:
        """Rollback any pending changes and close the session.

        Safe cleanup after an exception during a worker cycle.
        """
        await self._session.rollback()
        await self._session.close()
