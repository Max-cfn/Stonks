"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Search, Landmark, Loader2, Globe } from "lucide-react";
import { useAvailableBanks, useConnectBank } from "@/lib/hooks/useCashflow";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import type { BankResponse } from "@stonks/shared-types";

// ── Country flag emoji helper ──
function countryFlag(country: string): string {
  const flags: Record<string, string> = {
    FR: "🇫🇷",
    DE: "🇩🇪",
    GB: "🇬🇧",
    ES: "🇪🇸",
    IT: "🇮🇹",
    NL: "🇳🇱",
    BE: "🇧🇪",
    PT: "🇵🇹",
    CH: "🇨🇭",
    LU: "🇱🇺",
    AT: "🇦🇹",
  };
  return flags[country] || "🏦";
}

// ── BankCard ──
function BankCard({
  bank,
  onSelect,
  isPending,
}: {
  bank: BankResponse;
  onSelect: () => void;
  isPending: boolean;
}) {
  const t = useTranslations("cashflow");

  return (
    <Card
      className={`cursor-pointer transition-all hover:shadow-md hover:border-primary/50 ${
        isPending ? "opacity-50 pointer-events-none" : ""
      }`}
      onClick={onSelect}
    >
      <CardContent className="p-4 flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-lg">
          {countryFlag(bank.country)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{bank.name}</p>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Globe className="h-3 w-3" />
            {bank.country}
          </p>
        </div>
        {isPending && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </CardContent>
    </Card>
  );
}

// ── Country filter chips ──
const COUNTRIES = [
  { code: "", labelKey: "allCountries" },
  { code: "FR", labelKey: "country_FR" },
  { code: "DE", labelKey: "country_DE" },
  { code: "GB", labelKey: "country_GB" },
];

// ── ConnectBankContent ──
function ConnectBankContent() {
  const t = useTranslations("cashflow");
  const locale = useLocale();
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [selectedBankId, setSelectedBankId] = useState<string | null>(null);

  const { data, isLoading } = useAvailableBanks();
  const connectBank = useConnectBank();

  const filteredBanks = useMemo(() => {
    const banks = data?.banks ?? [];
    return banks.filter((b) => {
      const matchSearch =
        !search ||
        b.name.toLowerCase().includes(search.toLowerCase());
      const matchCountry = !countryFilter || b.country === countryFilter;
      return matchSearch && matchCountry;
    });
  }, [data, search, countryFilter]);

  const handleSelect = (bankId: string) => {
    setSelectedBankId(bankId);
    connectBank.mutate(bankId, {
      onSuccess: (result) => {
        window.location.href = result.authorization_url;
      },
      onError: () => {
        setSelectedBankId(null);
      },
    });
  };

  // ── Loading ──
  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("selectBank")}</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </div>
    );
  }

  // ── Empty ──
  if (!data?.banks?.length) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">{t("selectBank")}</h1>
        <EmptyState
          icon={<Landmark className="h-8 w-8" />}
          title={t("noBanksAvailable")}
          description={t("noBanksAvailableDesc")}
        />
      </div>
    );
  }

  // ── No results after filter ──
  const noResults = filteredBanks.length === 0;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">{t("selectBank")}</h1>

      {/* Search + Country filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder={t("searchBanks")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 pl-9 pr-3 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {COUNTRIES.map((c) => (
            <Button
              key={c.code}
              variant={countryFilter === c.code ? "default" : "outline"}
              size="sm"
              onClick={() => setCountryFilter(c.code)}
            >
              {c.code ? countryFlag(c.code) : null} {c.code || t(c.labelKey)}
            </Button>
          ))}
        </div>
      </div>

      {/* Bank grid */}
      {noResults ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {t("noBanksFound")}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredBanks.map((bank) => (
            <BankCard
              key={bank.id}
              bank={bank}
              onSelect={() => handleSelect(bank.id)}
              isPending={selectedBankId === bank.id && connectBank.isPending}
            />
          ))}
        </div>
      )}

      {/* Error from mutation */}
      {connectBank.isError && (
        <p className="text-sm text-red-500 text-center">
          {t("connectError")}
        </p>
      )}
    </div>
  );
}

export function ConnectBankView() {
  return (
    <ErrorBoundary>
      <ConnectBankContent />
    </ErrorBoundary>
  );
}
