"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Landmark, ArrowUpRight, ArrowDownRight, Filter, Loader2, Plus } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { useAccounts, useTransactions, useCashflowSummary, useConnectBank } from "@/lib/hooks/useCashflow";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Button } from "@/components/ui/button";
import type { TransactionResponse } from "@stonks/shared-types";

// ── Formatters ──
function formatAmount(amount: string | number, currency = "EUR"): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR");
}

// ── Transaction Table ──
function TransactionTable({
  transactions,
  noTxLabel,
}: {
  transactions: TransactionResponse[];
  noTxLabel: string;
}) {
  const t = useTranslations("cashflow");

  if (!transactions.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {noTxLabel}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              {t("date")}
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              {t("description")}
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">
              {t("amount")}
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden sm:table-cell">
              {t("category")}
            </th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr
              key={tx.id}
              className="border-b border-border/50 transition-colors hover:bg-muted/30"
            >
              <td className="px-4 py-2.5 whitespace-nowrap">
                {formatDate(tx.transaction_date)}
              </td>
              <td className="px-4 py-2.5 max-w-[200px] truncate">
                {tx.description}
              </td>
              <td
                className={`px-4 py-2.5 text-right whitespace-nowrap font-medium ${
                  tx.is_expense ? "text-red-500" : "text-emerald-500"
                }`}
              >
                <span className="inline-flex items-center gap-1">
                  {tx.is_expense ? (
                    <ArrowDownRight className="h-3.5 w-3.5" />
                  ) : (
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  )}
                  {formatAmount(tx.amount, tx.currency)}
                </span>
              </td>
              <td className="px-4 py-2.5 hidden sm:table-cell text-muted-foreground">
                {tx.category ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Summary Chart ──
function SummaryChart({
  income,
  expenses,
  incomeLabel,
  expensesLabel,
}: {
  income: number;
  expenses: number;
  incomeLabel: string;
  expensesLabel: string;
}) {
  const data = [
    { name: incomeLabel, value: income },
    { name: expensesLabel, value: Math.abs(expenses) },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">
          {incomeLabel} / {expensesLabel}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="name" className="text-xs" />
            <YAxis
              className="text-xs"
              tickFormatter={(v: number) =>
                new Intl.NumberFormat("fr-FR", {
                  notation: "compact",
                  style: "currency",
                  currency: "EUR",
                }).format(v)
              }
            />
            <RechartsTooltip
              formatter={(value: number) => [formatAmount(value), ""]}
              cursor={{ fill: "hsl(var(--muted))", opacity: 0.2 }}
            />
            <Bar
              dataKey="value"
              fill="hsl(var(--primary))"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ── ConnectBankButton ──
function ConnectBankButton() {
  const t = useTranslations("cashflow");
  const connectBank = useConnectBank();

  const handleConnect = () => {
    connectBank.mutate(undefined, {
      onSuccess: (data) => {
        window.location.href = data.authorization_url;
      },
    });
  };

  return (
    <Button
      onClick={handleConnect}
      disabled={connectBank.isPending}
    >
      {connectBank.isPending ? (
        <span className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("connectAccount")}
        </span>
      ) : (
        t("connectAccount")
      )}
    </Button>
  );
}

// ── CashflowContent ──
function CashflowContent() {
  const t = useTranslations("cashflow");

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateUntil, setDateUntil] = useState("");
  // Draft state for date inputs — only applied on button click
  const [draftDateFrom, setDraftDateFrom] = useState("");
  const [draftDateUntil, setDraftDateUntil] = useState("");

  const { data: accountsData, isLoading: loadingAccounts } = useAccounts();
  const summary = useCashflowSummary("month");

  const queryAccountId = selectedAccountId || undefined;

  const { data: transactionsData, isLoading: loadingTx } = useTransactions(
    queryAccountId,
    {
      since: dateFrom || undefined,
      until: dateUntil || undefined,
    },
  );

  const handleApplyFilters = () => {
    setDateFrom(draftDateFrom);
    setDateUntil(draftDateUntil);
  };

  const hasPendingFilters =
    draftDateFrom !== dateFrom || draftDateUntil !== dateUntil;

  // ── Loading ──
  if (loadingAccounts) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <LoadingSkeleton variant="card" />
        <LoadingSkeleton variant="chart" height={256} />
        <LoadingSkeleton variant="table" rows={5} cols={4} />
      </div>
    );
  }

  // ── Empty: no accounts ──
  if (!accountsData?.accounts?.length) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <EmptyState
          icon={<Landmark className="h-8 w-8" />}
          title={t("noAccounts")}
          description={t("noAccountsDesc")}
          cta={<ConnectBankButton />}
        />
      </div>
    );
  }

  const accounts = accountsData.accounts;
  const transactions = transactionsData?.transactions ?? [];
  const income = summary.data?.total_income
    ? parseFloat(summary.data.total_income)
    : 0;
  const expenses = summary.data?.total_expenses
    ? parseFloat(summary.data.total_expenses)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <ConnectBankButton />
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t("selectAccount")}
            </label>
            <select
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
            >
              <option value="">{t("allAccounts")}</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.account_name || a.iban || a.id}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t("dateFrom")}
            </label>
            <input
              type="date"
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={draftDateFrom}
              onChange={(e) => setDraftDateFrom(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t("dateTo")}
            </label>
            <input
              type="date"
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={draftDateUntil}
              onChange={(e) => setDraftDateUntil(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            onClick={handleApplyFilters}
            disabled={!hasPendingFilters}
            className="h-9"
          >
            {t("applyFilter")}
          </Button>
          {hasPendingFilters && (
            <Button
              variant="ghost"
              size="sm"
              className="h-9"
              onClick={() => {
                setDraftDateFrom(dateFrom);
                setDraftDateUntil(dateUntil);
              }}
            >
              {t("resetFilter")}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Summary Chart */}
      <SummaryChart
        income={income}
        expenses={expenses}
        incomeLabel={t("income")}
        expensesLabel={t("expenses")}
      />

      {/* Transactions */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Transactions</h2>
        {loadingTx ? (
          <LoadingSkeleton variant="table" rows={5} cols={4} />
        ) : (
          <TransactionTable
            transactions={transactions}
            noTxLabel={t("noTransactions")}
          />
        )}
      </div>
    </div>
  );
}

export function CashflowView() {
  return (
    <ErrorBoundary>
      <CashflowContent />
    </ErrorBoundary>
  );
}
