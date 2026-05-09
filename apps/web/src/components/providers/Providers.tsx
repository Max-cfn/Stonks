"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { QueryProvider } from "./QueryProvider";
import { AuthProvider } from "@/lib/auth/AuthContext";
import { TooltipProvider } from "@/components/ui/tooltip";
import { type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      enableColorScheme={false}
    >
      <QueryProvider>
        <AuthProvider>
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        </AuthProvider>
      </QueryProvider>
    </NextThemesProvider>
  );
}
