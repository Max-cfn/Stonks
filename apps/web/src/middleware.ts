import { NextRequest, NextResponse } from "next/server";
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

const intlMiddleware = createMiddleware(routing);

// Pages that don't require authentication
const PUBLIC_PATHS = ["/login", "/register"];

// The auth cookie name (set by the backend)
const AUTH_COOKIE = "access_token";

export default async function middleware(req: NextRequest) {
  const pathname = req.nextUrl.pathname;

  // Extract the path without the locale prefix
  // e.g. /en/login → /login, /fr/dashboard → /dashboard
  const localePattern = new RegExp(`^/(${routing.locales.join("|")})(/.*)?$`);
  const match = pathname.match(localePattern);
  const pathWithoutLocale = match ? (match[2] ?? "/") : pathname;

  // Check if this is a public path
  const isPublicPath = PUBLIC_PATHS.some(
    (p) => pathWithoutLocale === p || pathWithoutLocale.startsWith(p + "/"),
  );

  // Check if access_token cookie is present
  const hasAuthCookie = req.cookies.get(AUTH_COOKIE)?.value;

  // If not authenticated and not on a public path → redirect to login
  if (!hasAuthCookie && !isPublicPath) {
    const locale = match?.[1] ?? routing.defaultLocale;
    const loginUrl = new URL(`/${locale}/login`, req.url);
    // Encode the original URL so we can redirect back after login
    loginUrl.searchParams.set("redirect", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // If authenticated and on a public path → redirect to dashboard
  if (hasAuthCookie && isPublicPath) {
    const locale = match?.[1] ?? routing.defaultLocale;
    const dashboardUrl = new URL(`/${locale}/dashboard`, req.url);
    return NextResponse.redirect(dashboardUrl);
  }

  // Otherwise, let next-intl middleware handle the request
  return intlMiddleware(req);
}

export const config = {
  matcher: ["/", "/(fr|en)/:path*"],
};
