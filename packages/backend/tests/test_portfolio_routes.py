"""HTTP integration tests for portfolio API routes.

Uses httpx.AsyncClient with ASGITransport and FastAPI dependency_overrides
to mock all database/price-feed dependencies.  No real DB or external
services required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from stonks_backend.app import create_app
from stonks_backend.application.ports.portfolio import (
    FxRatePort,
    NewsFeedPort,
    PortfolioRepositoryPort,
    PriceAlert,
    PriceFeedPort,
)
from stonks_backend.domain.portfolio.holding import Holding
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import Exchange, InstrumentType, Ticker
from stonks_backend.domain.user import Email, HashedPassword, User
from stonks_backend.interfaces.api.dependencies.auth import get_current_user
from stonks_backend.interfaces.api.routes.portfolio import (
    get_fx_rate,
    get_news_feed,
    get_portfolio_repo,
    get_price_feed,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_test_user() -> User:
    """Create a minimal test User domain object."""
    return User(
        id=uuid.uuid4(),
        email=Email("test@stonks.com"),
        hashed_password=HashedPassword.from_plain("password123"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        is_active=True,
    )


def _make_holding(
    ticker_symbol: str = "AAPL",
    exchange: Exchange | None = Exchange.NASDAQ,
    quantity: Decimal = Decimal("10"),
    avg_cost: Decimal = Decimal("100"),
    currency: str = "USD",
) -> Holding:
    return Holding(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        ticker=Ticker(ticker_symbol, exchange),
        instrument_type=InstrumentType.STOCK,
        quantity=quantity,
        avg_cost=avg_cost,
        currency=currency,
    )


def _make_quote(
    ticker_symbol: str = "AAPL",
    exchange: Exchange | None = Exchange.NASDAQ,
    price: Decimal = Decimal("150"),
    currency: str = "USD",
    source: str = "yahoo",
) -> Quote:
    return Quote(
        ticker=Ticker(ticker_symbol, exchange),
        price=price,
        currency=currency,
        timestamp=datetime.now(UTC),
        source=source,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def test_user() -> User:
    return _make_test_user()


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mocked PortfolioRepositoryPort."""
    return AsyncMock(spec=PortfolioRepositoryPort)


@pytest.fixture
def mock_price_feed() -> AsyncMock:
    """Mocked PriceFeedPort."""
    return AsyncMock(spec=PriceFeedPort)


@pytest.fixture
def mock_fx_rate() -> AsyncMock:
    """Mocked FxRatePort."""
    return AsyncMock(spec=FxRatePort)


@pytest.fixture
def mock_news_feed() -> AsyncMock:
    """Mocked NewsFeedPort."""
    return AsyncMock(spec=NewsFeedPort)


@pytest.fixture
async def client(
    test_user: User,
    mock_repo: AsyncMock,
    mock_price_feed: AsyncMock,
    mock_fx_rate: AsyncMock,
    mock_news_feed: AsyncMock,
) -> AsyncClient:
    """Create a test client with all portfolio dependencies overridden.

    The lifespan (which starts workers) may fail silently due to missing
    DB — this is expected and harmless for route testing.
    """
    app = create_app()

    # Override auth dependency to return our test user
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Override portfolio dependencies with mocks
    app.dependency_overrides[get_portfolio_repo] = lambda: mock_repo
    app.dependency_overrides[get_price_feed] = lambda: mock_price_feed
    app.dependency_overrides[get_fx_rate] = lambda: mock_fx_rate
    app.dependency_overrides[get_news_feed] = lambda: mock_news_feed

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# Add Trade endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_add_trade_endpoint(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """POST /portfolio/trades → 200 with valid BUY trade."""
    mock_repo.get_holdings.return_value = []

    resp = await client.post(
        "/portfolio/trades",
        json={
            "trade_type": "BUY",
            "ticker_symbol": "AAPL",
            "ticker_exchange": "NASDAQ",
            "quantity": "10",
            "price": "150.00",
            "currency": "USD",
            "fees": "2.50",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade_type"] == "BUY"
    assert data["ticker_symbol"] == "AAPL"
    assert data["quantity"] == "10"


@pytest.mark.asyncio
async def test_add_trade_sell_insufficient_endpoint(
    client: AsyncClient, mock_repo: AsyncMock
) -> None:
    """POST /portfolio/trades SELL with insufficient holding → 400."""
    mock_repo.get_holdings.return_value = [
        _make_holding(quantity=Decimal("5")),
    ]

    resp = await client.post(
        "/portfolio/trades",
        json={
            "trade_type": "SELL",
            "ticker_symbol": "AAPL",
            "ticker_exchange": "NASDAQ",
            "quantity": "10",
            "price": "150.00",
            "currency": "USD",
        },
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Holdings endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_holdings_endpoint(
    client: AsyncClient,
    mock_repo: AsyncMock,
    mock_price_feed: AsyncMock,
    mock_fx_rate: AsyncMock,
) -> None:
    """GET /portfolio/holdings → 200 with valuation data."""
    holding = _make_holding("AAPL", Exchange.NASDAQ, Decimal("10"), Decimal("100"))
    mock_repo.get_holdings.return_value = [holding]
    mock_price_feed.get_current.return_value = _make_quote(
        "AAPL", Exchange.NASDAQ, Decimal("150")
    )
    mock_fx_rate.get_rate.return_value = Decimal("1")

    resp = await client.get("/portfolio/holdings")
    assert resp.status_code == 200
    data = resp.json()
    assert "holdings" in data
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["ticker_symbol"] == "AAPL"


# ═══════════════════════════════════════════════════════════════════════════════
# Performance endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_performance_endpoint(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """GET /portfolio/performance?period=YTD → 200."""
    mock_repo.get_holdings.return_value = []
    mock_repo.get_trades.return_value = []

    resp = await client.get("/portfolio/performance?period=YTD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "YTD"
    assert "twr" in data
    assert "mwr" in data


@pytest.mark.asyncio
async def test_get_performance_invalid_period(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """GET /portfolio/performance?period=INVALID → 400."""
    mock_repo.get_holdings.return_value = []

    resp = await client.get("/portfolio/performance?period=WEEKLY")
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Quote endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_quote_endpoint(
    client: AsyncClient,
    mock_price_feed: AsyncMock,
) -> None:
    """GET /portfolio/quote/AAPL → 200 with quote data."""
    mock_price_feed.get_current.return_value = _make_quote("AAPL", Exchange.NASDAQ)

    resp = await client.get("/portfolio/quote/AAPL?ticker_exchange=NASDAQ")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["price"] == "150"
    assert data["currency"] == "USD"


# ═══════════════════════════════════════════════════════════════════════════════
# Alerts endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_alert_endpoint(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """POST /portfolio/alerts → 200."""
    resp = await client.post(
        "/portfolio/alerts",
        json={
            "ticker_symbol": "AAPL",
            "ticker_exchange": "NASDAQ",
            "threshold": "200",
            "direction": "above",
            "webhook_url": "https://example.com/hook",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker_symbol"] == "AAPL"
    assert data["threshold"] == "200"
    assert data["direction"] == "above"
    assert data["triggered"] is False


@pytest.mark.asyncio
async def test_create_alert_invalid_direction_endpoint(
    client: AsyncClient, mock_repo: AsyncMock
) -> None:
    """POST /portfolio/alerts with invalid direction → 400."""
    resp = await client.post(
        "/portfolio/alerts",
        json={
            "ticker_symbol": "AAPL",
            "ticker_exchange": "NASDAQ",
            "threshold": "200",
            "direction": "sideways",
            "webhook_url": "https://example.com/hook",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_alerts_endpoint(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """GET /portfolio/alerts → 200."""
    mock_repo.get_alerts.return_value = [
        PriceAlert(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            ticker=Ticker("AAPL", Exchange.NASDAQ),
            threshold=Decimal("200"),
            direction="above",
            webhook_url="https://example.com/hook",
            triggered=False,
            triggered_at=None,
            created_at=datetime.now(UTC),
        )
    ]

    resp = await client.get("/portfolio/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert len(data["alerts"]) == 1


@pytest.mark.asyncio
async def test_delete_alert_endpoint(client: AsyncClient, mock_repo: AsyncMock) -> None:
    """DELETE /portfolio/alerts/{id} → 204."""
    alert_id = str(uuid.uuid4())
    resp = await client.delete(f"/portfolio/alerts/{alert_id}")
    assert resp.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════════
# Simulate endpoint (public — no auth required)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_simulate_endpoint(client: AsyncClient) -> None:
    """POST /portfolio/simulate → 200 (public endpoint)."""
    resp = await client.post(
        "/portfolio/simulate",
        json={
            "capital": "10000",
            "monthly_contrib": "500",
            "annual_rate": "0.07",
            "years": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) == 1


@pytest.mark.asyncio
async def test_simulate_endpoint_scenarios(client: AsyncClient) -> None:
    """POST /portfolio/simulate with multiple scenarios → 200."""
    resp = await client.post(
        "/portfolio/simulate",
        json={
            "capital": "10000",
            "monthly_contrib": "500",
            "annual_rate": "0.07",
            "years": 10,
            "scenarios": [
                {"name": "Low", "rate": "0.05"},
                {"name": "High", "rate": "0.10"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 2
    assert data["scenarios"][0]["name"] == "Low"
    assert data["scenarios"][1]["name"] == "High"


@pytest.mark.asyncio
async def test_simulate_endpoint_invalid(client: AsyncClient) -> None:
    """POST /portfolio/simulate with years=0 → 422 (Pydantic ge=1)."""
    resp = await client.post(
        "/portfolio/simulate",
        json={
            "capital": "10000",
            "monthly_contrib": "500",
            "annual_rate": "0.07",
            "years": 0,
        },
    )
    # Pydantic catches years=0 before the route handler → 422 Unprocessable Entity
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# News digest endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_news_digest_endpoint(
    client: AsyncClient,
    mock_repo: AsyncMock,
) -> None:
    """GET /portfolio/news/digest with fresh cache or no cache → 200."""
    from stonks_backend.application.ports.portfolio import NewsDigest

    fresh_digest = NewsDigest(
        id=uuid.uuid4(),
        source="reuters",
        title="Market Update",
        url="https://example.com/news",
        published_at=datetime.now(UTC),
        sentiment_label="neutral",
        sentiment_score=Decimal("0"),
        summary="Markets steady.",
        affected_tickers=[],
        processed_at=datetime.now(UTC),
    )
    mock_repo.get_latest_digest.return_value = fresh_digest

    resp = await client.get("/portfolio/news/digest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "reuters"


# ═══════════════════════════════════════════════════════════════════════════════
# Unauthenticated tests — remove auth override
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
async def unauthenticated_client() -> AsyncClient:
    """Client WITHOUT auth overrides — all endpoints should return 401."""
    app = create_app()

    # Only override DB deps (not auth) so auth check fails
    app.dependency_overrides[get_portfolio_repo] = lambda: AsyncMock(
        spec=PortfolioRepositoryPort
    )
    app.dependency_overrides[get_price_feed] = lambda: AsyncMock(spec=PriceFeedPort)
    app.dependency_overrides[get_fx_rate] = lambda: AsyncMock(spec=FxRatePort)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_unauthenticated_add_trade(unauthenticated_client: AsyncClient) -> None:
    """POST /portfolio/trades without token → 401."""
    resp = await unauthenticated_client.post(
        "/portfolio/trades",
        json={
            "trade_type": "BUY",
            "ticker_symbol": "AAPL",
            "ticker_exchange": "NASDAQ",
            "quantity": "10",
            "price": "150.00",
            "currency": "USD",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_get_holdings(unauthenticated_client: AsyncClient) -> None:
    """GET /portfolio/holdings without token → 401."""
    resp = await unauthenticated_client.get("/portfolio/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_get_performance(unauthenticated_client: AsyncClient) -> None:
    """GET /portfolio/performance without token → 401."""
    resp = await unauthenticated_client.get("/portfolio/performance?period=YTD")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_get_quote(unauthenticated_client: AsyncClient) -> None:
    """GET /portfolio/quote/AAPL without token → 401."""
    resp = await unauthenticated_client.get("/portfolio/quote/AAPL")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_create_alert(unauthenticated_client: AsyncClient) -> None:
    """POST /portfolio/alerts without token → 401."""
    resp = await unauthenticated_client.post(
        "/portfolio/alerts",
        json={
            "ticker_symbol": "AAPL",
            "threshold": "200",
            "direction": "above",
            "webhook_url": "https://example.com/hook",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_list_alerts(unauthenticated_client: AsyncClient) -> None:
    """GET /portfolio/alerts without token → 401."""
    resp = await unauthenticated_client.get("/portfolio/alerts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_delete_alert(unauthenticated_client: AsyncClient) -> None:
    """DELETE /portfolio/alerts/{id} without token → 401."""
    alert_id = str(uuid.uuid4())
    resp = await unauthenticated_client.delete(f"/portfolio/alerts/{alert_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_news_digest(unauthenticated_client: AsyncClient) -> None:
    """GET /portfolio/news/digest without token → 401."""
    resp = await unauthenticated_client.get("/portfolio/news/digest")
    assert resp.status_code == 401
