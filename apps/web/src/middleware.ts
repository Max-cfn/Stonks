import { NextRequest, NextResponse } from "next/server";
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

const intlMiddleware = createMiddleware(routing);

// Auth desactivee temporairement — l'app est accessible sans login.
// Pour reactiver, retablir les checks d'authentification ci-dessous.

export default async function middleware(req: NextRequest) {
  // Laisser passer toutes les requetes, juste gerer i18n
  return intlMiddleware(req);
}

export const config = {
  matcher: ["/", "/(fr|en)/:path*"],
};
