"""Portfolio use cases — application layer orchestrators.

Each use case is a class with constructor-injected dependencies.
"""

from __future__ import annotations

from stonks_backend.application.use_cases.portfolio.add_trade import AddTrade, AddTradeError
from stonks_backend.application.use_cases.portfolio.analyze_sentiment import (
    AnalyzeMarketSentiment,
    SentimentAnalyzerError,
)
from stonks_backend.application.use_cases.portfolio.compute_performance import ComputePerformance
from stonks_backend.application.use_cases.portfolio.dto import (
    CompoundGrowthResult,
    GrowthScenario,
    HoldingValuation,
    PerformanceResult,
    PortfolioValuation,
    YearSnapshot,
)
from stonks_backend.application.use_cases.portfolio.get_valuation import (
    GetPortfolioValuation,
    ValuationError,
)
from stonks_backend.application.use_cases.portfolio.manage_alerts import (
    ManageAlerts,
    ManageAlertsError,
)
from stonks_backend.application.use_cases.portfolio.simulate_growth import SimulateCompoundGrowth

__all__ = [
    # ── Use cases ───────────────────────────
    "AddTrade",
    "AddTradeError",
    "GetPortfolioValuation",
    "ValuationError",
    "ComputePerformance",
    "ManageAlerts",
    "ManageAlertsError",
    "SimulateCompoundGrowth",
    "AnalyzeMarketSentiment",
    "SentimentAnalyzerError",
    # ── DTOs ────────────────────────────────
    "PortfolioValuation",
    "HoldingValuation",
    "PerformanceResult",
    "CompoundGrowthResult",
    "GrowthScenario",
    "YearSnapshot",
]
