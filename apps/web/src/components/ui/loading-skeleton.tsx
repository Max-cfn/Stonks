"use client";

import { cn } from "@/lib/utils";

// ── Card Skeleton ──
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-xl border bg-card p-6",
        className,
      )}
    >
      <div className="h-4 w-24 rounded bg-muted" />
      <div className="mt-4 h-8 w-32 rounded bg-muted" />
      <div className="mt-2 h-3 w-48 rounded bg-muted" />
    </div>
  );
}

// ── Table Skeleton ──
export function TableSkeleton({
  rows = 5,
  cols = 4,
  className,
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("rounded-xl border bg-card", className)}
      role="status"
      aria-label="Loading"
    >
      {/* Header */}
      <div className="flex gap-4 border-b px-6 py-3">
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={`h-${i}`}
            className="h-4 flex-1 rounded bg-muted animate-pulse"
          />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={`r-${r}`}
          className="flex gap-4 border-b border-border/50 px-6 py-4 last:border-0"
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={`c-${r}-${c}`}
              className="h-3 flex-1 rounded bg-muted animate-pulse"
              style={{ animationDelay: `${r * 100}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Chart Skeleton ──
export function ChartSkeleton({
  height = 256,
  className,
}: {
  height?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-xl border bg-card p-4",
        className,
      )}
      style={{ height }}
    >
      <div className="flex h-full items-end gap-2 px-2">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 rounded-t bg-muted"
            style={{ height: `${20 + Math.random() * 60}%` }}
          />
        ))}
      </div>
    </div>
  );
}

// ── LoadingSkeleton (composite) ──
export function LoadingSkeleton({
  variant = "card",
  ...rest
}: {
  variant: "card" | "table" | "chart";
  className?: string;
  rows?: number;
  cols?: number;
  height?: number;
}) {
  switch (variant) {
    case "table":
      return <TableSkeleton rows={rest.rows} cols={rest.cols} className={rest.className} />;
    case "chart":
      return <ChartSkeleton height={rest.height} className={rest.className} />;
    case "card":
    default:
      return <CardSkeleton className={rest.className} />;
  }
}
