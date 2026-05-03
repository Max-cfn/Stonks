// Types used by the mobile app (mirrors backend schemas)
// In production, these should come from @stonks/shared-types via workspace resolution

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

export interface AlertResponse {
  id: string;
  ticker: string;
  target_price: string;
  direction: "above" | "below";
  is_active: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface ApiError {
  detail: string;
}
