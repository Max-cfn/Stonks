import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApi } from "./client";
import type {
  UserResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  AccountListResponse,
} from "./types";

// ── Auth ────────────────────────────────────────────────────────
export function useUserQuery() {
  const { get } = useApi();
  return useQuery({
    queryKey: ["user", "me"],
    queryFn: () => get<UserResponse>("/auth/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLoginMutation() {
  const { post } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: LoginRequest) => post<TokenResponse>("/auth/login", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user"] }),
  });
}

export function useRegisterMutation() {
  const { post } = useApi();
  return useMutation({
    mutationFn: (data: RegisterRequest) => post<UserResponse>("/auth/register", data),
  });
}

// ── Cashflow ────────────────────────────────────────────────────
export function useAccountsQuery() {
  const { get } = useApi();
  return useQuery({
    queryKey: ["cashflow", "accounts"],
    queryFn: () => get<AccountListResponse>("/cashflow/accounts"),
    staleTime: 30_000,
  });
}

export function useConnectBankMutation() {
  const { post } = useApi();
  return useMutation({
    mutationFn: () =>
      post<{ authorization_url: string }>("/cashflow/banks/connect"),
  });
}

export function useSyncAccountMutation() {
  const { post } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) =>
      post<{ transactions_synced: number }>(`/cashflow/accounts/${accountId}/sync`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

export function useTransactionsQuery(params?: {
  startDate?: string;
  endDate?: string;
  category?: string;
  limit?: number;
}) {
  const { get } = useApi();
  const searchParams = new URLSearchParams();
  if (params?.startDate) searchParams.set("start_date", params.startDate);
  if (params?.endDate) searchParams.set("end_date", params.endDate);
  if (params?.category) searchParams.set("category", params.category);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["cashflow", "transactions", params],
    queryFn: () =>
      get<{ transactions: unknown[]; total: number }>(
        `/cashflow/transactions${qs ? `?${qs}` : ""}`
      ),
    staleTime: 30_000,
  });
}

export function useCashflowSummaryQuery(params?: {
  startDate?: string;
  endDate?: string;
}) {
  const { get } = useApi();
  const searchParams = new URLSearchParams();
  if (params?.startDate) searchParams.set("start_date", params.startDate);
  if (params?.endDate) searchParams.set("end_date", params.endDate);

  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["cashflow", "summary", params],
    queryFn: () =>
      get<{
        total_income: string;
        total_expenses: string;
        net: string;
        transaction_count: number;
        currency: string;
        start_date: string;
        end_date: string;
      }>(`/cashflow/summary${qs ? `?${qs}` : ""}`),
    staleTime: 60_000,
  });
}

// ── Portfolio ───────────────────────────────────────────────────
export function useHoldingsQuery() {
  const { get } = useApi();
  return useQuery({
    queryKey: ["portfolio", "holdings"],
    queryFn: () =>
      get<{
        holdings: unknown[];
        total_value: string | null;
        total_gain: string | null;
        total_gain_pct: number | null;
        currency: string;
      }>("/portfolio/holdings"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useAlertsQuery() {
  const { get } = useApi();
  return useQuery({
    queryKey: ["portfolio", "alerts"],
    queryFn: () => get<{ alerts: unknown[] }>("/portfolio/alerts"),
    staleTime: 30_000,
  });
}

export function useCreateAlertMutation() {
  const { post } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      ticker: string;
      target_price: number;
      direction: "above" | "below";
    }) => post("/portfolio/alerts", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio", "alerts"] }),
  });
}

export function useDeleteAlertMutation() {
  const { del } = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => del(`/portfolio/alerts/${alertId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio", "alerts"] }),
  });
}

export function useCompoundSimulatorMutation() {
  const { post } = useApi();
  return useMutation({
    mutationFn: (data: {
      initial: number;
      monthly: number;
      rate_pct: number;
      years: number;
    }) =>
      post<{
        future_value: number;
        total_contributions: number;
        total_interest: number;
      }>("/portfolio/simulate", data),
  });
}

// ── Push Token ──────────────────────────────────────────────────
export function useRegisterPushTokenMutation() {
  const { post } = useApi();
  return useMutation({
    mutationFn: (token: string) =>
      post("/users/push-token", { token, platform: "expo" }),
  });
}
