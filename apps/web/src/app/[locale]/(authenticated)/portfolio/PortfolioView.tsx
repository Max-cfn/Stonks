"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useLocale } from "next-intl";
import {
  Briefcase,
  TrendingUp,
  PieChart,
  Plus,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { useHoldings, usePortfolioPerformance } from "@/lib/hooks/usePortfolio";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { AddTradeDialog } from "./AddTradeDialog";
import type { HoldingValuationItem } from "@stonks/shared-types";

// ── Formatters ──
function formatAmount(value: string | number, currency = "EUR"): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function formatPct(value: string | number | null): string {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

// ── Holdings Table ──
function HoldingsTable({ holdings }: { holdings: HoldingValuationItem[] }) {
  const t = useTranslations("portfolio");

  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              {t("ticker")}
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden sm:table-cell">
              {t("instrumentType")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">
              {t("quantity")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden md:table-cell">
              {t("avgCost")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden sm:table-cell">
              {t("marketPrice")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">
              {t("marketValue")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden md:table-cell">
              {t("pnl")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden lg:table-cell">
              {t("pnlPercent")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground hidden lg:table-cell">
              {t("weight")}
            </th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const pnlNum = parseFloat(h.pnl);
            const isPositive = pnlNum >= 0;
            return (
              <tr
                key={h.holding_id}
                className="border-b border-border/50 transition-colors hover:bg-muted/30"
              >
                <td className="px-4 py-2.5 font-medium whitespace-nowrap">
                  {h.ticker_symbol}
                  {h.ticker_exchange && (
                    <span className="text-xs text-muted-foreground ml-1">
                      {h.ticker_exchange}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 hidden sm:table-cell text-muted-foreground">
                  {h.instrument_type}
                </td>
                <td className="px-4 py-2.5 text-right whitespace-nowrap">
                  {parseFloat(h.quantity).toLocaleString("fr-FR")}
                </td>
                <td className="px-4 py-2.5 text-right hidden md:table-cell text-muted-foreground">
                  {formatAmount(h.avg_cost, h.currency)}
                </td>
                <td className="px-4 py-2.5 text-right font-medium hidden sm:table-cell">
                  {formatAmount(h.market_price, h.market_price_currency)}
                </td>
                <td className="px-4 py-2.5 text-right font-medium">
                  {formatAmount(h.market_value, h.market_value_currency)}
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-medium hidden md:table-cell ${
                    isPositive ? "text-emerald-500" : "text-red-500"
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {isPositive ? (
                      <ArrowUpRight className="h-3 w-3" />
                    ) : (
                      <ArrowDownRight className="h-3 w-3" />
                    )}
                    {formatAmount(h.pnl, h.pnl_currency)}
                  </span>
                </td>
                <td
                  className={`px-4 py-2.5 text-right hidden lg:table-cell ${
                    isPositive ? "text-emerald-500" : "text-red-500"
                  }`}
                >
                  {formatPct(h.pnl_pct)}
                </td>
                <td className="px-4 py-2.5 text-right hidden lg:table-cell text-muted-foreground">
                  {h.weight_pct ? `${parseFloat(h.weight_pct).toFixed(1)}%` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Performance Period Selector ──
const PERIODS = [
  { value: "1M", labelKey: "period_1M" },
  { value: "3M", labelKey: "period_3M" },
  { value: "6M", labelKey: "period_6M" },
  { value: "YTD", labelKey: "period_YTD" },
  { value: "1Y", labelKey: "period_1Y" },
  { value: "ALL", labelKey: "period_ALL" },
];

// ── PortfolioContent ──
function PortfolioContent() {
  const t = useTranslations("portfolio");
  const locale = useLocale();
  const [showAddTrade, setShowAddTrade] = useState(false);
  const [performancePeriod, setPerformancePeriod] = useState("YTD");

  const { data: holdingsData, isLoading: loadingHoldings } = useHoldings();
  const { data: perfData, isLoading: loadingPerf } =
    usePortfolioPerformance(performancePeriod);

  // ── Loading ──
  if (loadingHoldings) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
        </div>
        <LoadingSkeleton variant="table" rows={3} cols={6} />
      </div>
    );
  }

  const holdings = holdingsData?.holdings ?? [];
  const hasHoldings = holdings.length > 0;

  // ── Empty state ──
  if (!hasHoldings) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        </div>
        <EmptyState
          icon={<Briefcase className="h-8 w-8" />}
          title={t("noHoldings")}
          description={t("noHoldingsDesc")}
          cta={
            <Button onClick={() => setShowAddTrade(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              {t("addTrade")}
            </Button>
          }
        />
        {showAddTrade && (
          <AddTradeDialog onClose={() => setShowAddTrade(false)} />
        )}
      </div>
    );
  }

  // ── Data ──
  const totalValue = holdingsData?.total_value ?? "0";
  const totalPnl = holdingsData?.total_pnl ?? "0";
  const totalPnlPct = holdingsData?.total_pnl_pct;
  const pnlNum = parseFloat(totalPnl);
  const isPnlPositive = pnlNum >= 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <Button onClick={() => setShowAddTrade(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          {t("addTrade")}
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Total Value */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("totalValue")}
            </CardTitle>
            <Briefcase className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatAmount(totalValue, holdingsData?.currency)}
            </div>
          </CardContent>
        </Card>

        {/* Total P&L */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("totalPnl")}
            </CardTitle>
            <TrendingUp
              className={`h-4 w-4 ${
                isPnlPositive ? "text-emerald-500" : "text-red-500"
              }`}
            />
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                isPnlPositive ? "text-emerald-500" : "text-red-500"
              }`}
            >
              {isPnlPositive ? "+" : ""}
              {formatAmount(totalPnl, holdingsData?.currency)}
            </div>
            {totalPnlPct !== null && totalPnlPct !== undefined && (
              <p
                className={`text-xs mt-1 ${
                  isPnlPositive ? "text-emerald-500" : "text-red-500"
                }`}
              >
                {formatPct(totalPnlPct)}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Holdings Count */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("holdingsCount")}
            </CardTitle>
            <PieChart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{holdings.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Holdings Table */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">{t("holdings")}</h2>
        <HoldingsTable holdings={holdings} />
      </div>

      {/* Performance */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base font-medium">
            {t("performance")}
          </CardTitle>
          <select
            value={performancePeriod}
            onChange={(e) => setPerformancePeriod(e.target.value)}
            className="h-8 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>
                {t(p.labelKey)}
              </option>
            ))}
          </select>
        </CardHeader>
        <CardContent>
          {loadingPerf ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("loading")}
            </div>
          ) : perfData ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">{t("twr")}</p>
                <p className="text-lg font-semibold">
                  {perfData.twr ? formatPct(perfData.twr) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{t("mwr")}</p>
                <p className="text-lg font-semibold">
                  {perfData.mwr ? formatPct(perfData.mwr) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{t("startValue")}</p>
                <p className="text-lg font-semibold">
                  {formatAmount(perfData.start_value, perfData.start_value_currency)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{t("endValue")}</p>
                <p className="text-lg font-semibold">
                  {formatAmount(perfData.end_value, perfData.end_value_currency)}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("noPerformance")}</p>
          )}
        </CardContent>
      </Card>

      {/* Simulator link */}
      <div className="flex justify-end">
        <Link href={`/${locale}/portfolio/simulator`}>
          <Button variant="outline" size="sm" className="gap-1.5">
            <TrendingUp className="h-3.5 w-3.5" />
            {t("simulator")}
          </Button>
        </Link>
      </div>

      {/* Add Trade Dialog */}
      {showAddTrade && (
        <AddTradeDialog onClose={() => setShowAddTrade(false)} />
      )}
    </div>
  );
}

export function PortfolioView() {
  return (
    <ErrorBoundary>
      <PortfolioContent />
    </ErrorBoundary>
  );
}
