"use client";

import { useTranslations } from "next-intl";
import { Briefcase, TrendingUp } from "lucide-react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ConnectionIndicator } from "@/components/layout/ConnectionIndicator";

// Mock columns for placeholder table
const PLACEHOLDER_COLUMNS = ["ticker", "name", "shares", "price", "value", "gain"] as const;

// Mock candle data for placeholder chart
const MOCK_CANDLES = Array.from({ length: 20 }).map((_, i) => {
  const base = 150 + Math.sin(i * 0.5) * 20 + i * 2;
  return {
    open: base - Math.random() * 5,
    high: base + Math.random() * 10,
    low: base - Math.random() * 10,
    close: base + (Math.random() - 0.5) * 5,
  };
});

function CandlePlaceholder() {
  return (
    <div className="flex items-end gap-[2px] h-48 px-4">
      {MOCK_CANDLES.map((c, i) => {
        const isUp = c.close >= c.open;
        const bodyTop = Math.min(c.open, c.close);
        const bodyH = Math.abs(c.close - c.open) || 0.5;
        const maxVal = 250;
        const chartH = 160;
        const yScale = chartH / maxVal;

        const topPx = (maxVal - c.high) * yScale;
        const bodyTopPx = (maxVal - bodyTop - bodyH) * yScale;
        const bodyHeightPx = Math.max(bodyH * yScale, 1);
        const wickTopPx = topPx;
        const wickHeightPx = (c.high - c.low) * yScale;

        return (
          <div key={i} className="flex flex-col items-center flex-1">
            <div className="relative flex flex-col items-center" style={{ height: chartH }}>
              {/* Wick */}
              <div
                className="w-[2px] bg-muted-foreground/60"
                style={{
                  position: "absolute",
                  top: wickTopPx,
                  height: wickHeightPx,
                }}
              />
              {/* Body */}
              <div
                className={`w-[8px] ${
                  isUp
                    ? "bg-emerald-400/70"
                    : "bg-red-400/70"
                }`}
                style={{
                  position: "absolute",
                  top: bodyTopPx,
                  height: bodyHeightPx,
                  borderRadius: 1,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PortfolioView() {
  const t = useTranslations("portfolio");
  const n = useTranslations("nav");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <ConnectionIndicator />
      </div>

      <EmptyState
        icon={<Briefcase className="h-8 w-8" />}
        title={t("comingSoon")}
        description={t("comingSoonDesc")}
        className="min-h-[300px]"
      />

      {/* Placeholder Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">
            Aperçu du portefeuille
          </CardTitle>
          <p className="text-xs text-muted-foreground">Données simulées</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  {PLACEHOLDER_COLUMNS.map((col) => (
                    <th
                      key={col}
                      className="px-4 py-3 text-left font-medium text-muted-foreground"
                    >
                      {t(col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/30 opacity-50">
                  <td className="px-4 py-3 font-mono">AAPL</td>
                  <td className="px-4 py-3">Apple Inc.</td>
                  <td className="px-4 py-3">10</td>
                  <td className="px-4 py-3">$178.50</td>
                  <td className="px-4 py-3">$1,785.00</td>
                  <td className="px-4 py-3 text-emerald-500">+12.4%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Placeholder Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Graphique</CardTitle>
          <p className="text-xs text-muted-foreground">Données simulées</p>
        </CardHeader>
        <CardContent>
          <CandlePlaceholder />
        </CardContent>
      </Card>
    </div>
  );
}
