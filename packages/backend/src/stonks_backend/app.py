"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from stonks_backend.application.ports.portfolio import PortfolioRepositoryPort
from stonks_backend.infrastructure.config import get_settings
from stonks_backend.infrastructure.database import get_session_factory
from stonks_backend.infrastructure.market_data.fx_ecb_adapter import FxRateECBAdapter
from stonks_backend.infrastructure.market_data.rss_news_adapter import RssNewsAdapter
from stonks_backend.infrastructure.market_data.yahoo_finance_adapter import (
    YahooFinanceAdapter,
)
from stonks_backend.infrastructure.persistence.portfolio_repo import (
    PortfolioSqlRepository,
)
from stonks_backend.interfaces.api.routes.auth import router as auth_router
from stonks_backend.interfaces.api.routes.cashflow import limiter as cashflow_limiter
from stonks_backend.interfaces.api.routes.cashflow import router as cashflow_router
from stonks_backend.interfaces.api.routes.health import router as health_router
from stonks_backend.interfaces.api.routes.portfolio import router as portfolio_router
from stonks_backend.interfaces.api.routes.push import router as push_router

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Crée et configure l'application FastAPI (ports & adapters)."""
    app = FastAPI(
        title="Stonks API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    # Rate limit handler
    app.state.limiter = cashflow_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    _register_routers(app)
    _register_middleware(app)
    return app


def _register_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(cashflow_router)
    app.include_router(portfolio_router)
    app.include_router(push_router)


def _register_middleware(app: FastAPI) -> None:
    """Register application middleware."""

    # Request-ID middleware — propagated via X-Request-ID header
    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ═══════════════════════════════════════════════════════════════════════════════
# Lifespan — background workers (optional)
# ═══════════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage background worker lifecycle.

    Workers are optional — if the database is unreachable or dependencies
    are missing, they log a warning and the application starts without them.
    """
    # ── Initialize adapters ───────────────────────────────────────────────
    settings = get_settings()
    price_feed = YahooFinanceAdapter(settings)
    fx_rate = FxRateECBAdapter(settings)
    news_feed = RssNewsAdapter(settings)

    # ── Repo factory — creates a fresh session per worker cycle ───────────
    async def _repo_factory() -> PortfolioRepositoryPort:
        factory = get_session_factory()
        session = factory()
        return PortfolioSqlRepository(session)

    # ── Import workers lazily to avoid import-time side effects ───────────
    from stonks_backend.infrastructure.workers.news_analyzer import NewsAnalyzer
    from stonks_backend.infrastructure.workers.price_poller import PricePoller

    poller: PricePoller | None = None
    analyzer: NewsAnalyzer | None = None

    # ── Start PricePoller ─────────────────────────────────────────────────
    try:
        # Verify DB connectivity with a quick session test
        test_repo = await _repo_factory()
        await test_repo.get_active_tickers()
        await test_repo.aclose()

        poller = PricePoller(
            repo_factory=_repo_factory,
            price_feed=price_feed,
            fx_rate=fx_rate,
            interval_seconds=60,
        )
        await poller.start()
        app.state.price_poller = poller
        logger.info("lifespan_price_poller_started")
    except Exception as exc:
        logger.warning(
            "lifespan_price_poller_skipped",
            error=str(exc),
            hint="DB may be unreachable; price polling is disabled",
        )
        app.state.price_poller = None

    # ── Start NewsAnalyzer ────────────────────────────────────────────────
    try:
        # Quick DB test
        test_repo2 = await _repo_factory()
        await test_repo2.aclose()

        analyzer = NewsAnalyzer(
            news_feed=news_feed,
            repo_factory=_repo_factory,
            interval_minutes=15,
        )
        await analyzer.start()
        app.state.news_analyzer = analyzer
        logger.info("lifespan_news_analyzer_started")
    except Exception as exc:
        logger.warning(
            "lifespan_news_analyzer_skipped",
            error=str(exc),
            hint="News sentiment analysis is disabled",
        )
        app.state.news_analyzer = None

    # ── Yield to application ──────────────────────────────────────────────
    yield

    # ── Shutdown workers ──────────────────────────────────────────────────
    if poller is not None:
        try:
            await poller.stop()
            logger.info("lifespan_price_poller_stopped")
        except Exception:
            logger.exception("lifespan_price_poller_stop_error")

    if analyzer is not None:
        try:
            await analyzer.stop()
            logger.info("lifespan_news_analyzer_stopped")
        except Exception:
            logger.exception("lifespan_news_analyzer_stop_error")

    # ── Close adapter clients ─────────────────────────────────────────────
    try:
        await price_feed.close()
    except Exception:
        logger.exception("lifespan_price_feed_close_error")

    try:
        await news_feed.close()
        logger.debug("lifespan_news_feed_closed")
    except Exception:
        logger.exception("lifespan_news_feed_close_error")

    try:
        await fx_rate.close()
        logger.debug("lifespan_fx_rate_closed")
    except Exception:
        logger.exception("lifespan_fx_rate_close_error")
