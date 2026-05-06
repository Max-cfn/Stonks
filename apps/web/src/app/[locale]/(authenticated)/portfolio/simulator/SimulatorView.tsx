"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { Calculator, TrendingUp } from "lucide-react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorBoundary } from "@/components/ui/error-boundary";

// ── Form Schema ──
const simulatorSchema = z.object({
  initial: z.coerce.number().min(0, "Doit être ≥ 0"),
  monthly: z.coerce.number().min(0, "Doit être ≥ 0"),
  rate: z.coerce.number().min(0, "Doit être ≥ 0").max(100, "Doit être ≤ 100"),
  years: z.coerce.number().int().min(1, "Minimum 1 an").max(60, "Maximum 60 ans"),
});

type SimulatorInput = z.infer<typeof simulatorSchema>;

// ── Compound interest calculation ──
interface SimulationPoint {
  year: number;
  value: number;
  contributions: number;
}

function computeSimulation(input: SimulatorInput): {
  points: SimulationPoint[];
  futureValue: number;
  totalContributions: number;
  totalInterest: number;
} {
  const { initial, monthly, rate, years } = input;
  const monthlyRate = rate / 100 / 12;
  const months = years * 12;
  const points: SimulationPoint[] = [];

  let currentValue = initial;
  let totalContributionsAcc = initial;

  for (let m = 1; m <= months; m++) {
    currentValue = currentValue * (1 + monthlyRate) + monthly;
    totalContributionsAcc += monthly;

    if (m % 12 === 0) {
      points.push({
        year: m / 12,
        value: Math.round(currentValue * 100) / 100,
        contributions: Math.round(totalContributionsAcc * 100) / 100,
      });
    }
  }

  const futureValue = Math.round(currentValue * 100) / 100;
  const totalInterest = Math.round((futureValue - totalContributionsAcc) * 100) / 100;

  return { points, futureValue, totalContributions: totalContributionsAcc, totalInterest };
}

// ── Format currency ──
function formatEur(value: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// ── SimulatorContent ──
function SimulatorContent() {
  const t = useTranslations("simulator");
  const [result, setResult] = useState<ReturnType<typeof computeSimulation> | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SimulatorInput>({
    resolver: zodResolver(simulatorSchema),
    defaultValues: {
      initial: 10000,
      monthly: 500,
      rate: 7,
      years: 20,
    },
  });

  const onSubmit = (data: SimulatorInput) => {
    setResult(computeSimulation(data));
  };

  // Auto-compute on first render
  useEffect(() => {
    if (!result) {
      setResult(
        computeSimulation({ initial: 10000, monthly: 500, rate: 7, years: 20 }),
      );
    }
  }, [result]);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Calculator className="h-5 w-5" />
              Paramètres
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="initial">{t("initial")}</Label>
                <Input
                  id="initial"
                  type="number"
                  step="100"
                  {...register("initial")}
                  aria-invalid={!!errors.initial}
                />
                {errors.initial && (
                  <p className="text-xs text-destructive">
                    {errors.initial.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="monthly">{t("monthly")}</Label>
                <Input
                  id="monthly"
                  type="number"
                  step="50"
                  {...register("monthly")}
                  aria-invalid={!!errors.monthly}
                />
                {errors.monthly && (
                  <p className="text-xs text-destructive">
                    {errors.monthly.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="rate">{t("rate")}</Label>
                <Input
                  id="rate"
                  type="number"
                  step="0.1"
                  {...register("rate")}
                  aria-invalid={!!errors.rate}
                />
                {errors.rate && (
                  <p className="text-xs text-destructive">
                    {errors.rate.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="years">{t("years")}</Label>
                <Input
                  id="years"
                  type="number"
                  step="1"
                  {...register("years")}
                  aria-invalid={!!errors.years}
                />
                {errors.years && (
                  <p className="text-xs text-destructive">
                    {errors.years.message}
                  </p>
                )}
              </div>

              <Button type="submit" className="w-full gap-2">
                <TrendingUp className="h-4 w-4" />
                {t("calculate")}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Results */}
        <div className="space-y-4">
          {/* Result cards */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  {t("futureValue")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-bold text-primary">
                  {result ? formatEur(result.futureValue) : "—"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  {t("totalContributions")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-bold">
                  {result ? formatEur(result.totalContributions) : "—"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">
                  {t("totalInterest")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-bold text-emerald-500">
                  {result ? formatEur(result.totalInterest) : "—"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Chart */}
          <Card>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart
                  data={result?.points ?? []}
                  margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
                >
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="year"
                    className="text-xs"
                    tickFormatter={(y: number) => `${y} ans`}
                  />
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
                    formatter={(value: number, name: string) => {
                      if (name === "value") return [formatEur(value), "Valeur totale"];
                      if (name === "contributions")
                        return [formatEur(value), "Versements"];
                      return [value, name];
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="contributions"
                    stackId="1"
                    stroke="hsl(var(--muted-foreground))"
                    fill="hsl(var(--muted))"
                    fillOpacity={0.2}
                    strokeWidth={1}
                    name="contributions"
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stackId="2"
                    stroke="hsl(var(--primary))"
                    fill="url(#colorValue)"
                    strokeWidth={2}
                    name="value"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export function SimulatorView() {
  return (
    <ErrorBoundary>
      <SimulatorContent />
    </ErrorBoundary>
  );
}
