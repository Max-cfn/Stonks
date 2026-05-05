"""Portfolio API routes — trades, valuation, performance, alerts, simulation, news.

All endpoints require authentication via get_current_user.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.portfolio import (
    FxRatePort,
    NewsFeedPort,
    PortfolioRepositoryPort,
    PriceFeedPort,
)
from stonks_backend.application.use_cases.portfolio import (
    AddTrade,
    AddTradeError,
    AnalyzeMarketSentiment,
    ComputePerformance,
    GetPortfolioValuation,
    ManageAlerts,
    ManageAlertsError,
    SentimentAnalyzerError,
    SimulateCompoundGrowth,
    ValuationError,
)
from stonks_backend.domain.portfolio.performance import CompoundReturn
from stonks_backend.domain.portfolio.ticker import Exchange, Ticker
from stonks_backend.domain.user import User
from stonks_backend.infrastructure.config import get_settings
from stonks_backend.infrastructure.database import get_session
from stonks_backend.infrastructure.market_data.coingecko_adapter import (
    CoinGeckoAdapter,
)
from stonks_backend.infrastructure.market_data.fx_ecb_adapter import FxRateECBAdapter
from stonks_backend.infrastructure.market_data.rss_news_adapter import RssNewsAdapter
from stonks_backend.infrastructure.persistence.portfolio_repo import (
    PortfolioSqlRepository,
)
from stonks_backend.interfaces.api.dependencies.auth import get_current_user
from stonks_backend.interfaces.api.schemas import (
    AlertListResponse,
    AlertRequest,
    AlertResponse,
    ErrorResponse,
    HoldingsValuationResponse,
    HoldingValuationItem,
    NewsDigestItem,
    NewsDigestResponse,
    PerformanceResponse,
    QuoteResponse,
    ScenarioResult,
    SimulationRequest,
    SimulationResponse,
    TradeRequest,
    TradeResponse,
    YearSnapshotItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ── Dependencies ──────────────────────────────────────────────────────────


async def get_portfolio_repo(
    session: AsyncSession = Depends(get_session),
) -> PortfolioRepositoryPort:
    """Return a PortfolioSqlRepository for the current session."""
    return PortfolioSqlRepository(session)


def get_price_feed() -> PriceFeedPort:
    """Return a CoinGecko price feed adapter."""
    settings = get_settings()
    return CoinGeckoAdapter(settings)


def get_fx_rate() -> FxRatePort:
    """Return an ECB FX rate adapter."""
    settings = get_settings()
    return FxRateECBAdapter(settings)


def get_news_feed() -> NewsFeedPort:
    """Return an RSS news feed adapter."""
    settings = get_settings()
    return RssNewsAdapter(settings)


# ── Helpers ───────────────────────────────────────────────────────────────


def _parse_exchange(raw: str | None) -> Exchange | None:
    """Parse an exchange string to an Exchange enum member."""
    if raw is None:
        return None
    raw_upper = raw.upper().strip()
    for ex in Exchange:
        if ex.value == raw_upper:
            return ex
    # Try by name (e.g. "CRYPTO" or just the key)
    try:
        return Exchange[raw_upper]
    except KeyError:
        return None


# ── Simple 30s cache for quotes ───────────────────────────────────────────

_quote_cache: dict[str, tuple[datetime, dict]] = {}


def _cached_quote(ticker_symbol: str, ticker_exchange: str | None) -> dict | None:
    """Return cached quote data if it's fresh enough (< 30s)."""
    key = f"{ticker_symbol}:{ticker_exchange or ''}"
    if key in _quote_cache:
        ts, data = _quote_cache[key]
        if (datetime.now(UTC) - ts).total_seconds() < 30:
            return data
    return None


def _cache_quote(ticker_symbol: str, ticker_exchange: str | None, data: dict) -> None:
    """Store a quote in the in-memory cache."""
    key = f"{ticker_symbol}:{ticker_exchange or ''}"
    _quote_cache[key] = (datetime.now(UTC), data)


# ── Trades ────────────────────────────────────────────────────────────────


@router.post(
    "/trades",
    response_model=TradeResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def add_trade(
    body: TradeRequest,
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
    price_feed: PriceFeedPort = Depends(get_price_feed),
) -> TradeResponse:
    """Record a BUY, SELL, or DIVIDEND transaction.

    Creates or updates the corresponding holding and recalculates
    the weighted-average cost basis.

    - **BUY**: increases holding quantity, updates avg_cost
    - **SELL**: decreases holding quantity (must have sufficient)
    - **DIVIDEND**: records income, quantity must be 0
    """
    ticker = Ticker(
        symbol=body.ticker_symbol,
        exchange=_parse_exchange(body.ticker_exchange),
    )

    use_case = AddTrade(repo, price_feed)
    try:
        trade = await use_case.execute(
            user_id=current_user.id,
            trade_type=body.trade_type.upper(),
            ticker=ticker,
            quantity=Decimal(body.quantity),
            price=Decimal(body.price),
            currency=body.currency.upper(),
            fees=Decimal(body.fees) if body.fees else Decimal("0"),
            notes=body.notes,
        )
    except AddTradeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {exc}",
        ) from exc

    return TradeResponse(
        id=str(trade.id),
        holding_id=str(trade.holding_id),
        trade_type=trade.trade_type.value,
        ticker_symbol=trade.ticker.symbol if hasattr(trade, 'ticker') else body.ticker_symbol,
        ticker_exchange=body.ticker_exchange,
        quantity=str(trade.quantity),
        price=str(trade.price),
        currency=trade.currency,
        fees=str(trade.fees),
        date=trade.date.isoformat(),
        notes=trade.notes,
        dividend_amount=str(trade.dividend_amount) if trade.dividend_amount else None,
    )


# ── Holdings / Valuation ──────────────────────────────────────────────────


@router.get(
    "/holdings",
    response_model=HoldingsValuationResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_holdings(
    target_currency: str = Query("EUR", description="Reporting currency (ISO 4217)"),
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
    price_feed: PriceFeedPort = Depends(get_price_feed),
    fx_rate: FxRatePort = Depends(get_fx_rate),
) -> HoldingsValuationResponse:
    """List all holdings with live mark-to-market valuation.

    Each holding is valued at the current market price and converted
    to the target reporting currency (default: EUR).
    """
    use_case = GetPortfolioValuation(repo, price_feed, fx_rate)
    try:
        valuation = await use_case.execute(
            user_id=str(current_user.id),
            target_currency=target_currency.upper(),
        )
    except ValuationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Valuation failed: {exc}",
        ) from exc

    holdings_items: list[HoldingValuationItem] = []
    for hv in valuation.holdings:
        holdings_items.append(
            HoldingValuationItem(
                holding_id=str(hv.holding.id),
                ticker_symbol=hv.holding.ticker.symbol,
                ticker_exchange=hv.holding.ticker.exchange.value
                if hv.holding.ticker.exchange
                else None,
                instrument_type=hv.holding.instrument_type.value,
                quantity=str(hv.holding.quantity),
                avg_cost=str(hv.holding.avg_cost),
                currency=hv.holding.currency,
                market_price=str(hv.quote.mid_price),
                market_price_currency=hv.quote.currency,
                market_value=str(hv.market_value.amount),
                market_value_currency=hv.market_value.currency,
                pnl=str(hv.pnl.amount),
                pnl_currency=hv.pnl.currency,
                pnl_pct=str(
                    hv.pnl_pct.quantize(Decimal("0.01"))
                ),
                weight_pct=str(
                    hv.weight_pct.quantize(Decimal("0.01"))
                ),
                quote_source=hv.quote.source,
                quote_timestamp=hv.quote.timestamp.isoformat(),
            )
        )

    return HoldingsValuationResponse(
        holdings=holdings_items,
        total_value=str(
            valuation.total_value.amount.quantize(Decimal("0.01"))
        ),
        total_pnl=str(
            valuation.total_pnl.amount.quantize(Decimal("0.01"))
        ),
        total_pnl_pct=str(
            valuation.total_pnl_pct.quantize(Decimal("0.01"))
        ),
        currency=valuation.currency,
        as_of=valuation.as_of.isoformat(),
    )


# ── Performance ───────────────────────────────────────────────────────────


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def get_performance(
    period: str = Query("YTD", description="Period: 1M, 3M, 6M, YTD, 1Y, ALL"),
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
) -> PerformanceResponse:
    """Compute portfolio performance (TWR and MWR) for a given period.

    **TWR** (Time-Weighted Return) isolates the manager's investment
    skill from the impact of deposits and withdrawals.

    **MWR** (Money-Weighted Return / XIRR) reflects the investor's
    actual experience, including the timing of cash flows.
    """
    calc = CompoundReturn()
    use_case = ComputePerformance(repo, calc)

    try:
        result = await use_case.execute(
            user_id=current_user.id,
            period=period.upper(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PerformanceResponse(
        period=result.period,
        twr=str(result.twr.quantize(Decimal("0.0001"))),
        mwr=str(result.mwr.quantize(Decimal("0.0001")))
        if result.mwr is not None
        else None,
        start_value=str(result.start_value.amount),
        start_value_currency=result.start_value.currency,
        end_value=str(result.end_value.amount),
        end_value_currency=result.end_value.currency,
        cashflows_count=result.cashflows_count,
    )


# ── Quote ─────────────────────────────────────────────────────────────────


@router.get(
    "/quote/{ticker_symbol}",
    response_model=QuoteResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_quote(
    ticker_symbol: str,
    ticker_exchange: str | None = Query(None, description="Exchange (e.g. NASDAQ, NYSE)"),
    current_user: User = Depends(get_current_user),
    price_feed: PriceFeedPort = Depends(get_price_feed),
) -> QuoteResponse:
    """Get current market quote for a ticker. Cached for 30 seconds."""
    # Check cache
    cached = _cached_quote(ticker_symbol, ticker_exchange)
    if cached:
        return QuoteResponse(**cached)

    ticker = Ticker(
        symbol=ticker_symbol,
        exchange=_parse_exchange(ticker_exchange),
    )

    try:
        quote = await price_feed.get_current(ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Price feed error: {exc}",
        ) from exc

    data = {
        "symbol": ticker.symbol,
        "ticker_exchange": ticker.exchange.value if ticker.exchange else None,
        "price": str(quote.mid_price),
        "currency": quote.currency,
        "bid": str(quote.bid) if quote.bid else None,
        "ask": str(quote.ask) if quote.ask else None,
        "volume": str(quote.volume) if quote.volume else None,
        "source": quote.source,
        "timestamp": quote.timestamp.isoformat(),
    }
    _cache_quote(ticker_symbol, ticker_exchange, data)
    return QuoteResponse(**data)


# ── Alerts ────────────────────────────────────────────────────────────────


@router.post(
    "/alerts",
    response_model=AlertResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def create_alert(
    body: AlertRequest,
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
) -> AlertResponse:
    """Create a price alert.

    When the ticker's price crosses the threshold in the specified
    direction, a POST is sent to the webhook_url.
    """
    ticker = Ticker(
        symbol=body.ticker_symbol,
        exchange=_parse_exchange(body.ticker_exchange),
    )

    use_case = ManageAlerts(repo)
    try:
        alert = await use_case.create(
            user_id=current_user.id,
            ticker=ticker,
            threshold=Decimal(body.threshold),
            direction=body.direction,
            webhook_url=body.webhook_url,
        )
    except ManageAlertsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AlertResponse(
        id=str(alert.id),
        ticker_symbol=alert.ticker.symbol,
        ticker_exchange=alert.ticker.exchange.value
        if alert.ticker.exchange
        else None,
        threshold=str(alert.threshold),
        direction=alert.direction,
        webhook_url=alert.webhook_url,
        triggered=alert.triggered,
        triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else None,
        created_at=alert.created_at.isoformat(),
    )


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_alerts(
    triggered: bool | None = Query(None, description="Filter by triggered status"),
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
) -> AlertListResponse:
    """List all price alerts for the authenticated user."""
    use_case = ManageAlerts(repo)
    alerts = await use_case.get_for_user(
        user_id=current_user.id,
        triggered=triggered,
    )

    return AlertListResponse(
        alerts=[
            AlertResponse(
                id=str(a.id),
                ticker_symbol=a.ticker.symbol,
                ticker_exchange=a.ticker.exchange.value
                if a.ticker.exchange
                else None,
                threshold=str(a.threshold),
                direction=a.direction,
                webhook_url=a.webhook_url,
                triggered=a.triggered,
                triggered_at=a.triggered_at.isoformat() if a.triggered_at else None,
                created_at=a.created_at.isoformat(),
            )
            for a in alerts
        ]
    )


@router.delete(
    "/alerts/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
) -> None:
    """Delete a price alert by ID."""
    use_case = ManageAlerts(repo)
    await use_case.delete(alert_id)


# ── Simulation ────────────────────────────────────────────────────────────


@router.post(
    "/simulate",
    response_model=SimulationResponse,
    responses={400: {"model": ErrorResponse}},
)
async def simulate_growth(
    body: SimulationRequest,
) -> SimulationResponse:
    """Simulate compound interest growth over a multi-year horizon.

    Runs month-by-month projections for one or more named scenarios
    (each with its own annual rate). Returns year-by-year breakdowns.
    """
    try:
        result = SimulateCompoundGrowth.compute(
            capital=Decimal(body.capital),
            monthly_contrib=Decimal(body.monthly_contrib),
            annual_rate=Decimal(body.annual_rate),
            years=body.years,
            scenarios=body.scenarios,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SimulationResponse(
        scenarios=[
            ScenarioResult(
                name=sc.name,
                final_amount=str(sc.final_amount),
                total_contributions=str(sc.total_contributions),
                total_interest=str(sc.total_interest),
                yearly_breakdown=[
                    YearSnapshotItem(
                        year=ys.year,
                        balance=str(ys.balance),
                        contributions_ytd=str(ys.contributions_ytd),
                        interest_ytd=str(ys.interest_ytd),
                    )
                    for ys in sc.yearly_breakdown
                ],
            )
            for sc in result.scenarios
        ]
    )


# ── News Digest ───────────────────────────────────────────────────────────


@router.get(
    "/news/digest",
    response_model=NewsDigestResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_news_digest(
    current_user: User = Depends(get_current_user),
    repo: PortfolioRepositoryPort = Depends(get_portfolio_repo),
    news_feed: NewsFeedPort = Depends(get_news_feed),
) -> NewsDigestResponse:
    """Get the latest market sentiment digest.

    Returns the most recent digest if it was processed within the last hour.
    Otherwise, fetches fresh RSS news, analyzes sentiment, and returns a
    new digest.
    """
    # Try cached digest first
    cached_digest = await repo.get_latest_digest()
    if cached_digest is not None:
        age = (datetime.now(UTC) - cached_digest.processed_at).total_seconds()
        if age < 3600:  # less than 1 hour old
            return NewsDigestResponse(
                id=str(cached_digest.id),
                title=cached_digest.title,
                source=cached_digest.source,
                published_at=cached_digest.published_at.isoformat(),
                sentiment_label=cached_digest.sentiment_label,
                sentiment_score=str(cached_digest.sentiment_score),
                summary=cached_digest.summary,
                affected_tickers=cached_digest.affected_tickers or [],
                processed_at=cached_digest.processed_at.isoformat(),
                items=[],  # stale digest, minimal info
            )

    # Generate fresh digest
    use_case = AnalyzeMarketSentiment(news_feed, repo)
    try:
        digest = await use_case.execute()
    except SentimentAnalyzerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sentiment analysis failed: {exc}",
        ) from exc

    return NewsDigestResponse(
        id=str(digest.id),
        title=digest.title,
        source=digest.source,
        published_at=digest.published_at.isoformat(),
        sentiment_label=digest.sentiment_label,
        sentiment_score=str(digest.sentiment_score),
        summary=digest.summary,
        affected_tickers=digest.affected_tickers or [],
        processed_at=digest.processed_at.isoformat(),
        items=[
            NewsDigestItem(
                title=digest.title,
                url=digest.url,
                source=digest.source,
                published_at=digest.published_at.isoformat(),
                sentiment_label=digest.sentiment_label,
                sentiment_score=str(digest.sentiment_score),
                summary=digest.summary,
                affected_tickers=digest.affected_tickers or [],
            )
        ],
    )


# ── WebSocket /portfolio/stream ───────────────────────────────────────────


@router.websocket("/stream")
async def portfolio_stream(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token for authentication"),
):
    """Real-time price streaming via WebSocket.

    Authenticate with a JWT token in the query string.
    Send JSON messages to subscribe/unsubscribe:

    ```json
    {"action": "subscribe", "tickers": ["AAPL.NASDAQ", "BTC"]}
    {"action": "unsubscribe", "tickers": ["AAPL.NASDAQ"]}
    {"action": "ping"}
    ```

    The server responds with price updates every 30 seconds:

    ```json
    {"type": "quote", "ticker": "AAPL", "price": "150.25", "currency": "USD",
     "timestamp": "2026-05-05T22:00:00Z", "source": "coingecko"}
    ```
    """
    # Auth via query token — reuse JWT verification
    from stonks_backend.infrastructure.config import get_settings
    from stonks_backend.infrastructure.security.jwt_service import JWTService

    settings = get_settings()
    jwt_service = JWTService(
        secret=settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        issuer=settings.jwt_issuer,
    )

    # We need to verify the token. If it's an access token:
    try:
        jwt_service.verify_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()

    subscribed_tickers: set[str] = set()
    price_feed: PriceFeedPort = get_price_feed()

    try:
        while True:
            # Non-blocking receive with timeout
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
            except TimeoutError:
                # No message from client — send price updates
                data = None

            # Process client message if any
            if data is not None:
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"type": "error", "detail": "Invalid JSON"}
                    )
                    continue

                action = msg.get("action", "")

                if action == "subscribe":
                    for t in msg.get("tickers", []):
                        subscribed_tickers.add(t.upper())
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "tickers": list(subscribed_tickers),
                        }
                    )

                elif action == "unsubscribe":
                    for t in msg.get("tickers", []):
                        subscribed_tickers.discard(t.upper())
                    await websocket.send_json(
                        {
                            "type": "unsubscribed",
                            "tickers": list(subscribed_tickers),
                        }
                    )

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            # Send price updates for subscribed tickers
            for ticker_str in list(subscribed_tickers):
                parts = ticker_str.rsplit(".", 1)
                symbol = parts[0]
                exchange_str = parts[1] if len(parts) > 1 else None
                exchange = _parse_exchange(exchange_str)

                ticker = Ticker(symbol=symbol, exchange=exchange)
                try:
                    quote = await price_feed.get_current(ticker)
                    await websocket.send_json(
                        {
                            "type": "quote",
                            "ticker": ticker_str,
                            "price": str(quote.mid_price),
                            "currency": quote.currency,
                            "timestamp": quote.timestamp.isoformat(),
                            "source": quote.source,
                            "bid": str(quote.bid) if quote.bid else None,
                            "ask": str(quote.ask) if quote.ask else None,
                        }
                    )
                except Exception:
                    # Skip failed tickers silently
                    pass

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc, exc_info=True)
        try:
            await websocket.close(code=4000, reason="Internal error")
        except Exception:
            pass
