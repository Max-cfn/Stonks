"use client";

import { useTranslations } from "next-intl";
import { LogOut, User, Landmark, Bell, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth/useAuth";
import { useAccounts } from "@/lib/hooks/useCashflow";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Separator } from "@/components/ui/separator";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function SettingsContent() {
  const t = useTranslations("settings");
  const c = useTranslations("common");
  const { user, logout } = useAuth();
  const { data: accountsData, isLoading: loadingAccounts } = useAccounts();

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <User className="h-5 w-5" />
            {t("profile")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">{t("email")}</span>
            <span className="text-sm">{user?.email ?? "—"}</span>
          </div>
          {user?.created_at && (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">{t("memberSince")}</span>
              <span className="text-sm">{formatDate(user.created_at)}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Banks Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Landmark className="h-5 w-5" />
            {t("banks")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loadingAccounts ? (
            <LoadingSkeleton variant="card" className="h-24" />
          ) : !accountsData?.accounts?.length ? (
            <p className="text-sm text-muted-foreground">{t("noBanks")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {accountsData.accounts.map((account) => (
                <li
                  key={account.id}
                  className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {account.account_name || account.iban || account.id}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {account.bank_connector} · {account.currency}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {account.status === "active" ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : account.status === "syncing" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="text-xs text-muted-foreground">
                      {account.status === "active"
                        ? t("connected")
                        : account.status === "syncing"
                          ? t("syncing")
                          : t("disconnected")}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Alerts Section (placeholder) */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Bell className="h-5 w-5" />
            {t("alerts")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{t("comingSoon")}</p>
        </CardContent>
      </Card>

      <Separator />

      {/* Logout */}
      <Button variant="destructive" onClick={logout} className="gap-2">
        <LogOut className="h-4 w-4" />
        {c("logout")}
      </Button>
    </div>
  );
}

export function SettingsView() {
  return (
    <ErrorBoundary>
      <SettingsContent />
    </ErrorBoundary>
  );
}
