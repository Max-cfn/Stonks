"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  ArrowLeftRight,
  Briefcase,
  Play,
  Settings,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

interface SidebarProps {
  locale: string;
}

const NAV_ITEMS = [
  { key: "dashboard", href: "/dashboard", icon: LayoutDashboard },
  { key: "cashflow", href: "/cashflow", icon: ArrowLeftRight },
  { key: "portfolio", href: "/portfolio", icon: Briefcase },
  { key: "simulator", href: "/portfolio/simulator", icon: Play },
  { key: "settings", href: "/settings", icon: Settings },
] as const;

export function Sidebar({ locale }: SidebarProps) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  const isActive = (href: string) => {
    // Remove locale prefix for comparison
    const pathWithoutLocale = pathname.replace(`/${locale}`, "") || "/";
    return pathWithoutLocale.startsWith(href);
  };

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-[240px] flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 px-6">
        <TrendingUp className="h-6 w-6 text-primary" />
        <span className="text-xl font-bold tracking-tight">Stonks</span>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.key}
              href={`/${locale}${item.href}`}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {t(item.key)}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4">
        <p className="text-xs text-muted-foreground">
          Stonks v0.1.0
        </p>
      </div>
    </aside>
  );
}
