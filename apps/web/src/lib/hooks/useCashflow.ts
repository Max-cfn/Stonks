"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "./api";
import type {
  AccountListResponse,
  BankListResponse,
  TransactionListResponse,
  CashflowSummaryResponse,
  ConnectResponse,
  SyncResponse,
} from "@stonks/shared-types";

// ── Query keys ──
export const cashflowKeys = {
  all: ["cashflow"] as const,
  accounts: () => [...cashflowKeys.all, "accounts"] as const,
  transactions: (accountId?: string, filters?: TransactionFilters) =>
    [...cashflowKeys.all, "transactions", accountId ?? "all", JSON.stringify(filters)] as const,
  summary: (period?: string) =>
    [...cashflowKeys.all, "summary", period ?? "all"] as const,
};

// ── useAccounts ──
export function useAccounts() {
  return useQuery({
    queryKey: cashflowKeys.accounts(),
    queryFn: () => apiGet<AccountListResponse>("/api/cashflow/accounts"),
    staleTime: 30_000,
  });
}

// ── useTransactions ──
export interface TransactionFilters {
  account_id?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export function useTransactions(accountId?: string, filters?: TransactionFilters) {
  const params: Record<string, string | number | undefined> = {
    ...filters,
  };
  // Only send account_id when a specific account is selected
  if (accountId) {
    params.account_id = accountId;
  }

  return useQuery({
    queryKey: cashflowKeys.transactions(accountId, filters),
    queryFn: () =>
      apiGet<TransactionListResponse>("/api/cashflow/transactions", params),
    staleTime: 0,
    enabled: true,
  });
}

// ── useCashflowSummary ──
export function useCashflowSummary(period: "month" | "year" = "month") {
  return useQuery({
    queryKey: cashflowKeys.summary(period),
    queryFn: () =>
      apiGet<CashflowSummaryResponse>("/api/cashflow/summary", { period }),
    staleTime: 30_000,
  });
}

// ── useAvailableBanks ──
export function useAvailableBanks() {
  return useQuery({
    queryKey: [...cashflowKeys.all, "banks"],
    queryFn: () => apiGet<BankListResponse>("/api/cashflow/banks/available"),
    staleTime: 5 * 60_000,
  });
}

// ── useConnectBank ──
export function useConnectBank() {
  return useMutation({
    mutationFn: (bankId: string) =>
      apiPost<ConnectResponse>("/api/cashflow/banks/connect", { bank_id: bankId }),
  });
}

// ── useSyncAccount ──
export function useSyncAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: string) =>
      apiPost<SyncResponse>(`/api/cashflow/accounts/${accountId}/sync`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cashflowKeys.accounts() });
      queryClient.invalidateQueries({ queryKey: cashflowKeys.all });
    },
  });
}

// ── useDisconnectBank ──
export function useDisconnectBank() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: string) =>
      apiDelete<{ status: string }>(`/api/cashflow/banks/${accountId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cashflowKeys.all });
    },
  });
}

// ── useDashboardData (combined) ──
export function useDashboardData() {
  const accounts = useAccounts();
  const summary = useCashflowSummary("month");

  return {
    accounts,
    summary,
    isLoading: accounts.isLoading || summary.isLoading,
    isError: accounts.isError || summary.isError,
  };
}
