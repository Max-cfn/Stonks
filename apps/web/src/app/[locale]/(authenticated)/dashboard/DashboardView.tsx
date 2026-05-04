"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { Building2, TrendingUp, Wallet, Landmark } from "lucide-react";
import { useDashboardData } from "@/lib/hooks/useCashflow";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { ErrorBoundary } from "@/components/ui/error-boundary";

function formatCurrency(amount: string | number | null | undefined, currency = "EUR"): string {
  if (amount == null) return "—";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function DashboardContent() {
  const t = useTranslations("dashboard");
  const c = useTranslations("common");
  const { accounts, summary, isLoading } = useDashboardData();

  // ── Loading ──
  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
        </div>
      </div>
    );
  }

  // ── Empty ──
  if (!accounts.data?.accounts?.length) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <EmptyState
          icon={<Landmark className="h-8 w-8" />}
          title={t("noAccounts")}
          description={t("noAccountsDesc")}
          cta={
            <Button asChild>
              <Link href="/cashflow">{t("connectBank")}</Link>
            </Button>
          }
        />
      </div>
    );
  }

  // ── KPIs ──
  const totalCash = accounts.data.accounts
    .reduce((sum, a) => sum + (parseFloat(a.current_balance ?? "0") || 0), 0);

  const netFlow = summary.data?.net ? parseFloat(summary.data.net) : 0;
  const accountCount = accounts.data.accounts.length;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Total Cash */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("totalCash")}
            </CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(totalCash)}
            </div>
          </CardContent>
        </Card>

        {/* Net Flow */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("netFlow")}
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                netFlow >= 0 ? "text-emerald-500" : "text-red-500"
              }`}
            >
              {formatCurrency(netFlow)}
            </div>
          </CardContent>
        </Card>

        {/* Account Count */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t("accounts")}
            </CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{accountCount}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function DashboardView() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}
