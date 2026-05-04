"use client";

interface GuestLayoutProps {
  children: React.ReactNode;
}

/**
 * Minimal layout for unauthenticated pages (login, register).
 * No sidebar, centered card.
 */
export function GuestLayout({ children }: GuestLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="mb-8 flex items-center gap-2">
        <span className="text-2xl font-bold tracking-tight">Stonks</span>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
