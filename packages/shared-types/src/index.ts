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
  amount: string;
  currency: string;
  description: string;
  transaction_date: string;
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
export interface HoldingResponse {
  id: string;
  ticker: string;
  name: string;
  asset_type: string;
  shares: string;
  average_cost: string;
  current_price: string | null;
  market_value: string | null;
  unrealized_gain: string | null;
  unrealized_gain_pct: number | null;
  currency: string;
}

export interface HoldingListResponse {
  holdings: HoldingResponse[];
  total_value: string | null;
  total_gain: string | null;
  total_gain_pct: number | null;
  currency: string;
}

export interface AlertResponse {
  id: string;
  ticker: string;
  target_price: string;
  direction: "above" | "below";
  is_active: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface AlertListResponse {
  alerts: AlertResponse[];
}

export interface CreateAlertRequest {
  ticker: string;
  target_price: number;
  direction: "above" | "below";
}

export interface CompoundSimulateRequest {
  initial: number;
  monthly: number;
  rate_pct: number;
  years: number;
}

export interface CompoundSimulateResponse {
  future_value: number;
  total_contributions: number;
  total_interest: number;
}

// ── Error ──────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}
