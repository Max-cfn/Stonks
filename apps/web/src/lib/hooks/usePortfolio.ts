"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "./api";
import type {
  HoldingsValuationResponse,
  PerformanceResponse,
  QuoteResponse,
  AlertListResponse,
  AlertResponse,
  NewsDigestResponse,
  TradeRequest,
  TradeResponse,
} from "@stonks/shared-types";

// ── Query keys ──
export const portfolioKeys = {
  all: ["portfolio"] as const,
  holdings: () => [...portfolioKeys.all, "holdings"] as const,
  performance: (period: string) => [...portfolioKeys.all, "performance", period] as const,
  quotes: (symbol: string, exchange?: string) =>
    [...portfolioKeys.all, "quotes", symbol, exchange ?? ""] as const,
  alerts: () => [...portfolioKeys.all, "alerts"] as const,
  newsDigest: () => [...portfolioKeys.all, "newsDigest"] as const,
};

// ── useHoldings ──
export function useHoldings(currency = "EUR") {
  return useQuery({
    queryKey: portfolioKeys.holdings(),
    queryFn: () =>
      apiGet<HoldingsValuationResponse>("/api/portfolio/holdings", {
        target_currency: currency,
      }),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

// ── usePortfolioPerformance ──
export function usePortfolioPerformance(period = "YTD") {
  return useQuery({
    queryKey: portfolioKeys.performance(period),
    queryFn: () =>
      apiGet<PerformanceResponse>("/api/portfolio/performance", { period }),
    staleTime: 60_000,
  });
}

// ── usePortfolioQuotes ──
export function usePortfolioQuotes(symbol: string, exchange?: string) {
  return useQuery({
    queryKey: portfolioKeys.quotes(symbol, exchange),
    queryFn: () =>
      apiGet<QuoteResponse>(
        `/api/portfolio/quote/${symbol}`,
        exchange ? { ticker_exchange: exchange } : undefined,
      ),
    staleTime: 25_000,
    enabled: !!symbol,
  });
}

// ── useAlerts ──
export function useAlerts() {
  return useQuery({
    queryKey: portfolioKeys.alerts(),
    queryFn: () => apiGet<AlertListResponse>("/api/portfolio/alerts"),
    staleTime: 30_000,
  });
}

// ── useNewsDigest ──
export function useNewsDigest() {
  return useQuery({
    queryKey: portfolioKeys.newsDigest(),
    queryFn: () => apiGet<NewsDigestResponse>("/api/portfolio/news/digest"),
    staleTime: 10 * 60_000,
  });
}

// ── useAddTrade ──
export function useAddTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TradeRequest) =>
      apiPost<TradeResponse>("/api/portfolio/trades", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: portfolioKeys.holdings() });
      queryClient.invalidateQueries({ queryKey: portfolioKeys.all });
    },
  });
}

// ── useCreateAlert ──
export function useCreateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      ticker_symbol: string;
      ticker_exchange?: string;
      threshold: string;
      direction: string;
      webhook_url?: string;
    }) => apiPost<AlertResponse>("/api/portfolio/alerts", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: portfolioKeys.alerts() });
    },
  });
}

// ── useDeleteAlert ──
export function useDeleteAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      apiDelete<{ status: string }>(`/api/portfolio/alerts/${alertId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: portfolioKeys.alerts() });
    },
  });
}
