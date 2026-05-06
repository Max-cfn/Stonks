"use client";

import { usePortfolioStream } from "@/lib/hooks/usePortfolioStream";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const STATUS_CONFIG = {
  connected: {
    dotClass: "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]",
    label: "Connecté",
    pulse: false,
  },
  connecting: {
    dotClass: "bg-amber-500 animate-pulse",
    label: "Connexion...",
    pulse: true,
  },
  disconnected: {
    dotClass: "bg-red-500",
    label: "Déconnecté",
    pulse: false,
  },
} as const;

export function ConnectionIndicator() {
  const { status } = usePortfolioStream();
  const config = STATUS_CONFIG[status];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-1.5 px-2 py-1 cursor-default">
          <span
            className={cn(
              "inline-block h-2.5 w-2.5 rounded-full",
              config.dotClass,
            )}
          />
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {status === "connected" ? "Live" : "Off"}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        <p>{config.label}</p>
      </TooltipContent>
    </Tooltip>
  );
}
