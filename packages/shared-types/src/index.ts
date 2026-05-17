// API client type-safe — mirrors backend schemas

// ── Auth ───────────────────────────────────────────────────────
export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface UserResponse {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

// ── Cashflow ───────────────────────────────────────────────────
export interface AccountResponse {
  id: string;
  bank_connector: string;
  bank_id: string;
  bank_name: string;
  iban: string;
  account_name: string;
  account_type: string;
  currency: string;
  current_balance: string | null;
  status: string;
  last_synced_at: string | null;
}

export interface AccountListResponse {
  accounts: AccountResponse[];
}

export interface BankResponse {
  id: string;
  name: string;
  country: string;
  connector_type: string;
  logo_path: string;
  supported: boolean;
  account_types: string[] | null;
  notes: string | null;
}

export interface BankListResponse {
  banks: BankResponse[];
}

export interface ConnectBankRequest {
  bank_id: string;
}

export interface ConnectResponse {
  authorization_url: string;
}

export interface SyncResponse {
  transactions_synced: number;
  message: string;
}

export interface TransactionResponse {
  id: string;
  account_id: string;
  account_name?: string | null;
  bank_tx_id?: string | null;
  amount: string;
  currency: string;
  description: string;
  transaction_date: string | null;
  booking_date: string | null;
  category: string | null;
  is_expense: boolean;
}

export interface TransactionListResponse {
  transactions: TransactionResponse[];
  total: number;
}

export interface CashflowSummaryResponse {
  total_income: string;
  total_expenses: string;
  net: string;
  transaction_count: number;
  currency: string;
  start_date: string;
  end_date: string;
}

// ── Portfolio ──────────────────────────────────────────────────

export interface TradeRequest {
  trade_type: string;
  ticker_symbol: string;
  ticker_exchange?: string;
  quantity: string;
  price: string;
  currency: string;
  fees?: string;
  notes?: string | null;
}

export interface TradeResponse {
  id: string;
  holding_id: string;
  trade_type: string;
  ticker_symbol: string;
  ticker_exchange?: string | null;
  quantity: string;
  price: string;
  currency: string;
  fees?: string | null;
  date: string;
  notes?: string | null;
  dividend_amount?: string | null;
}

export interface HoldingValuationItem {
  holding_id: string;
  ticker_symbol: string;
  ticker_exchange?: string | null;
  instrument_type: string;
  quantity: string;
  avg_cost: string;
  currency: string;
  market_price: string;
  market_price_currency: string;
  market_value: string;
  market_value_currency: string;
  pnl: string;
  pnl_currency: string;
  pnl_pct: string | null;
  weight_pct: string | null;
  quote_source: string;
  quote_timestamp: string | null;
}

export interface HoldingsValuationResponse {
  holdings: HoldingValuationItem[];
  total_value: string;
  total_pnl: string;
  total_pnl_pct: string | null;
  currency: string;
  as_of: string;
}

export interface PerformanceResponse {
  period: string;
  twr: string | null;
  mwr: string | null;
  start_value: string;
  start_value_currency: string;
  end_value: string;
  end_value_currency: string;
  cashflows_count: number;
}

export interface QuoteResponse {
  symbol: string;
  ticker_exchange?: string | null;
  price: string;
  currency: string;
  bid?: string | null;
  ask?: string | null;
  volume?: string | null;
  source: string;
  timestamp: string;
}

export interface AlertResponse {
  id: string;
  ticker_symbol: string;
  ticker_exchange?: string | null;
  threshold: string;
  direction: string;
  webhook_url: string;
  triggered: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface AlertListResponse {
  alerts: AlertResponse[];
}

export interface CreateAlertRequest {
  ticker_symbol: string;
  ticker_exchange?: string;
  threshold: string;
  direction: string;
  webhook_url?: string;
}

export interface SimulationRequest {
  capital: number;
  monthly_contrib: number;
  annual_rate: number;
  years: number;
  scenarios?: string[] | null;
}

export interface YearSnapshotItem {
  year: number;
  balance: number;
  contributions_ytd: number;
  interest_ytd: number;
}

export interface ScenarioResult {
  name: string;
  final_amount: number;
  total_contributions: number;
  total_interest: number;
  yearly_breakdown: YearSnapshotItem[];
}

export interface SimulationResponse {
  scenarios: ScenarioResult[];
}

export interface NewsDigestItem {
  title: string;
  url: string;
  source: string;
  published_at: string;
  sentiment_label: string;
  sentiment_score: string;
  summary: string;
  affected_tickers: string[] | null;
}

export interface NewsDigestResponse {
  id: string;
  title: string;
  source: string;
  published_at: string;
  sentiment_label: string;
  sentiment_score: string;
  summary: string;
  affected_tickers: string[] | null;
  processed_at: string;
  items: NewsDigestItem[] | null;
}

// ── Error ──────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}
