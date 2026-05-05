"""Market data adapters — CoinGecko, Yahoo Finance, ECB FX, RSS news.

Architecture: each adapter implements a port from application.ports.portfolio.
"""

from __future__ import annotations

from stonks_backend.infrastructure.market_data.binance_ws_adapter import (
    BinanceWebSocketAdapter,
)
from stonks_backend.infrastructure.market_data.coingecko_adapter import (
    CoinGeckoAdapter,
    CoinGeckoError,
)
from stonks_backend.infrastructure.market_data.fx_ecb_adapter import (
    FxRateECBAdapter,
    FxRateECBError,
)
from stonks_backend.infrastructure.market_data.rss_news_adapter import RssNewsAdapter
from stonks_backend.infrastructure.market_data.yahoo_finance_adapter import (
    YahooFinanceAdapter,
    YahooFinanceError,
)

__all__ = [
    "BinanceWebSocketAdapter",
    "CoinGeckoAdapter",
    "CoinGeckoError",
    "FxRateECBAdapter",
    "FxRateECBError",
    "RssNewsAdapter",
    "YahooFinanceAdapter",
    "YahooFinanceError",
]
