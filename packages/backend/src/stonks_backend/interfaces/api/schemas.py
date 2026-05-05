"""Pydantic schemas for API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

# ── Auth ──────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    created_at: str


class ErrorResponse(BaseModel):
    detail: str


# ── Cashflow ──────────────────────────────────────────────────────


class ConnectResponse(BaseModel):
    authorization_url: str


class AccountResponse(BaseModel):
    id: str
    bank_connector: str
    bank_id: str
    iban: str
    account_name: str
    account_type: str
    currency: str
    current_balance: str | None = None
    status: str
    last_synced_at: str | None = None


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]


class SyncResponse(BaseModel):
    new_transactions: int
    total_fetched: int


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    bank_tx_id: str | None = None
    amount: str
    currency: str
    description: str
    booking_date: str | None = None
    value_date: str | None = None
    status: str
    source: str
    creditor_name: str | None = None
    debtor_name: str | None = None
    category_id: str | None = None


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class CategoryResponse(BaseModel):
    category_id: str
    name: str
    icon: str
    group: str
    total_amount: str
    currency: str
    transaction_count: int


class CashflowSummaryResponse(BaseModel):
    period_label: str
    period_type: str
    total_income: str
    total_expenses: str
    net_flow: str
    account_count: int
    total_balance: str | None = None
    categories: list[CategoryResponse]

# ── Portfolio ──────────────────────────────────────────────────────


class TradeRequest(BaseModel):
    """Request body for recording a trade."""

    trade_type: str = Field(..., description="BUY, SELL, or DIVIDEND")
    ticker_symbol: str = Field(..., description="Ticker symbol (e.g. AAPL, BTC)")
    ticker_exchange: str | None = Field(None, description="Exchange (e.g. NASDAQ, NYSE)")
    quantity: str = Field(..., description="Number of units (as decimal string)")
    price: str = Field(..., description="Price per unit (as decimal string)")
    currency: str = Field(..., description="ISO 4217 currency code")
    fees: str = Field("0", description="Transaction fees (as decimal string)")
    notes: str | None = Field(None, description="Optional free-text notes")


class TradeResponse(BaseModel):
    """Response for a recorded trade."""

    id: str
    holding_id: str
    trade_type: str
    ticker_symbol: str
    ticker_exchange: str | None = None
    quantity: str
    price: str
    currency: str
    fees: str
    date: str
    notes: str | None = None
    dividend_amount: str | None = None


class HoldingValuationItem(BaseModel):
    """Per-holding valuation detail."""

    holding_id: str
    ticker_symbol: str
    ticker_exchange: str | None = None
    instrument_type: str
    quantity: str
    avg_cost: str
    currency: str
    market_price: str
    market_price_currency: str
    market_value: str
    market_value_currency: str
    pnl: str
    pnl_currency: str
    pnl_pct: str
    weight_pct: str
    quote_source: str
    quote_timestamp: str


class HoldingsValuationResponse(BaseModel):
    """Aggregated portfolio valuation."""

    holdings: list[HoldingValuationItem]
    total_value: str
    total_pnl: str
    total_pnl_pct: str
    currency: str
    as_of: str


class PerformanceResponse(BaseModel):
    """Portfolio performance metrics."""

    period: str
    twr: str
    mwr: str | None = None
    start_value: str
    start_value_currency: str
    end_value: str
    end_value_currency: str
    cashflows_count: int


class QuoteResponse(BaseModel):
    """Market quote for a ticker."""

    symbol: str
    ticker_exchange: str | None = None
    price: str
    currency: str
    bid: str | None = None
    ask: str | None = None
    volume: str | None = None
    source: str
    timestamp: str


class AlertRequest(BaseModel):
    """Request body for creating a price alert."""

    ticker_symbol: str = Field(..., description="Ticker symbol (e.g. AAPL, BTC)")
    ticker_exchange: str | None = Field(None, description="Exchange (e.g. NASDAQ)")
    threshold: str = Field(..., description="Price threshold (as decimal string)")
    direction: str = Field(..., description="above or below")
    webhook_url: str = Field(..., description="URL to POST when alert fires")


class AlertResponse(BaseModel):
    """Price alert details."""

    id: str
    ticker_symbol: str
    ticker_exchange: str | None = None
    threshold: str
    direction: str
    webhook_url: str
    triggered: bool
    triggered_at: str | None = None
    created_at: str


class AlertListResponse(BaseModel):
    """List of price alerts."""

    alerts: list[AlertResponse]


class SimulationRequest(BaseModel):
    """Request body for compound growth simulation."""

    capital: str = Field(..., description="Initial lump-sum investment")
    monthly_contrib: str = Field(..., description="Monthly contribution amount")
    annual_rate: str = Field(..., description="Annual interest rate (decimal, e.g. 0.07 = 7%)")
    years: int = Field(..., ge=1, description="Projection horizon in years")
    scenarios: list[dict] | None = Field(None, description="Optional scenario overrides")


class YearSnapshotItem(BaseModel):
    """Year-by-year breakdown in compound growth simulation."""

    year: int
    balance: str
    contributions_ytd: str
    interest_ytd: str


class ScenarioResult(BaseModel):
    """Single scenario result in compound growth simulation."""

    name: str
    final_amount: str
    total_contributions: str
    total_interest: str
    yearly_breakdown: list[YearSnapshotItem]


class SimulationResponse(BaseModel):
    """Aggregated result for compound growth simulation."""

    scenarios: list[ScenarioResult]


class NewsDigestItem(BaseModel):
    """Individual news digest entry."""

    title: str
    url: str
    source: str
    published_at: str
    sentiment_label: str
    sentiment_score: str
    summary: str
    affected_tickers: list[str] | None = None


class NewsDigestResponse(BaseModel):
    """News sentiment digest."""

    id: str
    title: str
    source: str
    published_at: str
    sentiment_label: str
    sentiment_score: str
    summary: str
    affected_tickers: list[str] | None = None
    processed_at: str
    items: list[NewsDigestItem]
