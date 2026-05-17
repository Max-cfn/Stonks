"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Landmark, ArrowUpRight, ArrowDownRight, Filter, Loader2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useAccounts, useTransactions } from "@/lib/hooks/useCashflow";
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

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR");
}

// ── Period helpers ──

function getPeriodDates(yyyyMm: string): { from: string; until: string } {
  if (yyyyMm === "__12m__") {
    const now = new Date();
    const lastDayOfCurrent = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const until = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(lastDayOfCurrent.getDate()).padStart(2, "0")}`;
    const fromDate = new Date(now.getFullYear(), now.getMonth() - 11, 1);
    const from = `${fromDate.getFullYear()}-${String(fromDate.getMonth() + 1).padStart(2, "0")}-01`;
    return { from, until };
  }
  const [year, month] = yyyyMm.split("-");
  const lastDay = new Date(parseInt(year), parseInt(month), 0);
  const from = `${year}-${month}-01`;
  const until = `${year}-${month}-${String(lastDay.getDate()).padStart(2, "0")}`;
  return { from, until };
}

function generateMonthOptions(last12Label: string): { value: string; label: string }[] {
  const months: { value: string; label: string }[] = [
    { value: "__12m__", label: last12Label },
  ];
  const now = new Date();
  const fmt = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.push({ value, label: fmt.format(d) });
  }
  return months;
}

// ── Transaction Table ──
function TransactionTable({
  transactions,
  noTxLabel,
  showAccount,
  accountLabel,
}: {
  transactions: TransactionResponse[];
  noTxLabel: string;
  showAccount?: boolean;
  accountLabel?: string;
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
            {showAccount && (
              <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden sm:table-cell">
                {accountLabel || t("account")}
              </th>
            )}
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
              {showAccount && (
                <td className="px-4 py-2.5 max-w-[120px] truncate hidden sm:table-cell text-muted-foreground text-xs">
                  {tx.account_name || tx.account_id}
                </td>
              )}
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

// ── Month label formatter ──
const monthFmt = new Intl.DateTimeFormat("fr-FR", { month: "short" });

function formatMonthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split("-");
  const d = new Date(parseInt(y), parseInt(m) - 1, 1);
  return `${monthFmt.format(d)} ${y}`;
}

// ── Chart colors ──
const TOTAL_INCOME = "#16a34a";
const TOTAL_EXPENSES = "#ea580c";
const ACCT_INCOME = "#0891b2";
const ACCT_EXPENSES = "#db2777";

// ── Summary Chart ──
function SummaryChart({
  income,
  expenses,
  incomeLabel,
  expensesLabel,
  perAccountData,
  showPerAccount,
  monthlyData,
  perAccountMonthly,
}: {
  income: number;
  expenses: number;
  incomeLabel: string;
  expensesLabel: string;
  perAccountData?: { name: string; income: number; expenses: number }[];
  showPerAccount?: boolean;
  monthlyData?: { month: string; income: number; expenses: number }[];
  perAccountMonthly?: {
    month: string;
    total_income: number;
    total_expenses: number;
    accounts: { key: string; name: string; income: number; expenses: number }[];
  }[];
}) {
  // Determine display mode and build data + bars
  const allAccountKeys = new Set<string>();
  if (perAccountMonthly) {
    for (const m of perAccountMonthly) {
      for (const acct of m.accounts) {
        allAccountKeys.add(acct.key);
      }
    }
  }
  const hasMultipleAccounts = allAccountKeys.size > 1;

  let chartData: Record<string, unknown>[];
  let bars: React.ReactNode[];
  const labelMap: Record<string, string> = {};

  if (hasMultipleAccounts && perAccountMonthly) {
    // Build a consistent sorted list of all unique accounts (with names)
    const accountNames: Record<string, string> = {};
    for (const m of perAccountMonthly) {
      for (const acct of m.accounts) {
        if (!accountNames[acct.key]) accountNames[acct.key] = acct.name;
      }
    }
    const sortedAccounts = Object.entries(accountNames).sort((a, b) => a[1].localeCompare(b[1]));
    const sanitize = (k: string) => k.replace(/[^a-zA-Z0-9_]/g, "_");

    // Per-account + monthly: each month has total + per-account bars
    chartData = perAccountMonthly.map((m) => {
      const row: Record<string, unknown> = { name: formatMonthLabel(m.month) };
      row.total_income = m.total_income;
      row.total_expenses = Math.abs(m.total_expenses);
      labelMap.total_income = `${incomeLabel} (total)`;
      labelMap.total_expenses = `${expensesLabel} (total)`;
      const monthAccounts = new Map(m.accounts.map((a) => [a.key, a]));
      for (const [key, name] of sortedAccounts) {
        const dk = sanitize(key);
        const acct = monthAccounts.get(key);
        row[`acct_${dk}_inc`] = acct ? acct.income : 0;
        row[`acct_${dk}_exp`] = acct ? Math.abs(acct.expenses) : 0;
        labelMap[`acct_${dk}_inc`] = `${name} — ${incomeLabel}`;
        labelMap[`acct_${dk}_exp`] = `${name} — ${expensesLabel}`;
      }
      return row;
    });

    bars = [
      <Bar key="total_income" dataKey="total_income" fill={TOTAL_INCOME} radius={[4, 4, 0, 0]} />,
      <Bar key="total_expenses" dataKey="total_expenses" fill={TOTAL_EXPENSES} radius={[4, 4, 0, 0]} />,
      ...sortedAccounts.flatMap(([key]) => {
        const dk = sanitize(key);
        return [
          <Bar key={`acct_${dk}_inc`} dataKey={`acct_${dk}_inc`} fill={ACCT_INCOME} radius={[4, 4, 0, 0]} />,
          <Bar key={`acct_${dk}_exp`} dataKey={`acct_${dk}_exp`} fill={ACCT_EXPENSES} radius={[4, 4, 0, 0]} />,
        ];
      }),
    ];
  } else if (showPerAccount && perAccountData && perAccountData.length > 0) {
    // Per-account only (single month)
    chartData = perAccountData.map((d) => ({
      name: d.name,
      income: d.income,
      expenses: Math.abs(d.expenses),
    }));
    labelMap.income = incomeLabel;
    labelMap.expenses = expensesLabel;
    bars = [
      <Bar key="income" dataKey="income" fill={TOTAL_INCOME} radius={[4, 4, 0, 0]} />,
      <Bar key="expenses" dataKey="expenses" fill={TOTAL_EXPENSES} radius={[4, 4, 0, 0]} />,
    ];
  } else if (monthlyData && monthlyData.length > 0) {
    // Monthly only
    chartData = monthlyData.map((d) => ({
      name: formatMonthLabel(d.month),
      income: d.income,
      expenses: Math.abs(d.expenses),
    }));
    labelMap.income = incomeLabel;
    labelMap.expenses = expensesLabel;
    bars = [
      <Bar key="income" dataKey="income" fill={TOTAL_INCOME} radius={[4, 4, 0, 0]} />,
      <Bar key="expenses" dataKey="expenses" fill={TOTAL_EXPENSES} radius={[4, 4, 0, 0]} />,
    ];
  } else {
    // Single aggregated bar
    chartData = [{ name: "", income, expenses: Math.abs(expenses) }];
    labelMap.income = incomeLabel;
    labelMap.expenses = expensesLabel;
    bars = [
      <Bar key="income" dataKey="income" fill={TOTAL_INCOME} radius={[4, 4, 0, 0]} />,
      <Bar key="expenses" dataKey="expenses" fill={TOTAL_EXPENSES} radius={[4, 4, 0, 0]} />,
    ];
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">
          {incomeLabel} / {expensesLabel}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
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
              formatter={(value: number, dataKey: string) => [
                formatAmount(value),
                labelMap[dataKey] || dataKey,
              ]}
              cursor={{ fill: "hsl(var(--muted))", opacity: 0.2 }}
            />
            {bars}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ── ConnectBankButton ──
function ConnectBankButton() {
  const t = useTranslations("cashflow");
  const locale = useLocale();
  const router = useRouter();

  return (
    <Button onClick={() => router.push(`/${locale}/cashflow/connect`)}>
      {t("connectAccount")}
    </Button>
  );
}

// ── CashflowContent ──
function CashflowContent() {
  const t = useTranslations("cashflow");

  const monthOptions = useMemo(() => generateMonthOptions(t("last12Months")), [t]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("__12m__");
  // Default to "all accounts" (empty string) — user can filter to a specific account
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [showPerAccount, setShowPerAccount] = useState(false);

  const { data: accountsData, isLoading: loadingAccounts } = useAccounts();

  const { from, until } = getPeriodDates(selectedPeriod);

  const { data: transactionsData, isLoading: loadingTx } = useTransactions(
    selectedAccountId || undefined,
    {
      since: from || undefined,
      until: until || undefined,
    },
  );

  const isAllAccounts = !selectedAccountId;

  // Compute income/expenses client-side from filtered transactions
  const { income, expenses, perAccountData, monthlyData, perAccountMonthly } = useMemo(() => {
    const txs = transactionsData?.transactions ?? [];
    let inc = 0;
    let exp = 0;
    const byAccount: Record<string, { name: string; income: number; expenses: number }> = {};
    const byMonth: Record<string, { month: string; income: number; expenses: number }> = {};
    // per-month → per-account totals
    const byMonthAccount: Record<string, Record<string, { income: number; expenses: number }>> = {};

    for (const tx of txs) {
      const amt = typeof tx.amount === "string" ? parseFloat(tx.amount) : 0;
      if (amt > 0) inc += amt;
      else exp += amt;

      const key = tx.account_id ?? "unknown";
      const acctName = tx.account_name || key;
      if (!byAccount[key]) {
        byAccount[key] = { name: acctName, income: 0, expenses: 0 };
      }
      if (amt > 0) byAccount[key].income += amt;
      else byAccount[key].expenses += amt;

      if (tx.transaction_date) {
        const m = tx.transaction_date.substring(0, 7);
        if (!byMonth[m]) {
          byMonth[m] = { month: m, income: 0, expenses: 0 };
        }
        if (amt > 0) byMonth[m].income += amt;
        else byMonth[m].expenses += amt;

        if (!byMonthAccount[m]) byMonthAccount[m] = {};
        if (!byMonthAccount[m][key]) {
          byMonthAccount[m][key] = { income: 0, expenses: 0 };
        }
        if (amt > 0) byMonthAccount[m][key].income += amt;
        else byMonthAccount[m][key].expenses += amt;
      }
    }

    // Build per-account monthly data (only months with transactions)
    const perAccountMonthly = Object.entries(byMonthAccount)
      .map(([month, accounts]) => {
        let total_income = 0;
        let total_expenses = 0;
        const acctEntries = Object.entries(accounts).map(([acctId, vals]) => {
          total_income += vals.income;
          total_expenses += vals.expenses;
          return {
            key: acctId,
            name: byAccount[acctId]?.name || acctId,
            income: vals.income,
            expenses: vals.expenses,
          };
        });
        // Sort accounts alphabetically
        acctEntries.sort((a, b) => a.name.localeCompare(b.name));
        return { month, total_income, total_expenses, accounts: acctEntries };
      })
      .sort((a, b) => a.month.localeCompare(b.month));

    return {
      income: inc,
      expenses: exp,
      perAccountData: Object.values(byAccount).sort((a, b) => a.name.localeCompare(b.name)),
      monthlyData: Object.values(byMonth).sort((a, b) => a.month.localeCompare(b.month)),
      perAccountMonthly,
    };
  }, [transactionsData]);

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
              {t("period")}
            </label>
            <select
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
            >
              {monthOptions.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          {isAllAccounts && (
            <label className="flex items-center gap-2 text-sm cursor-pointer self-end pb-px">
              <input
                type="checkbox"
                checked={showPerAccount}
                onChange={(e) => setShowPerAccount(e.target.checked)}
                className="h-4 w-4 rounded border-muted-foreground/30 text-primary focus:ring-ring"
              />
              <span>{t("perAccount")}</span>
            </label>
          )}
        </CardContent>
      </Card>

      {/* Summary Chart */}
      <SummaryChart
        income={income}
        expenses={expenses}
        incomeLabel={t("income")}
        expensesLabel={t("expenses")}
        perAccountData={perAccountData}
        showPerAccount={showPerAccount && isAllAccounts && selectedPeriod !== "__12m__"}
        monthlyData={selectedPeriod === "__12m__" && !showPerAccount ? monthlyData : undefined}
        perAccountMonthly={
          showPerAccount && isAllAccounts && selectedPeriod === "__12m__"
            ? perAccountMonthly
            : undefined
        }
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
            showAccount={isAllAccounts}
            accountLabel={t("account")}
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
