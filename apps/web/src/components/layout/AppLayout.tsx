"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  // Extract locale from URL: /en/dashboard → "en"
  const pathname = usePathname();
  const locale = pathname.split("/")[1] || "fr";

  return (
    <div className="flex min-h-screen">
      <Sidebar locale={locale} />
      <div className="ml-[240px] flex flex-1 flex-col">
        <Topbar />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
