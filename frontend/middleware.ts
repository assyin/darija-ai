import createIntlMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";

import { auth } from "@/lib/auth";
import { routing } from "@/i18n/routing";

const intlMiddleware = createIntlMiddleware(routing);

export default async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Admin: NextAuth checks the `authorized` callback in authConfig.
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    // The auth() export is itself a middleware; cast to call directly.
    return (auth as unknown as (r: NextRequest) => Promise<NextResponse | undefined>)(req);
  }

  // /login is public (the dev-bypass page); no i18n routing needed.
  if (pathname === "/login" || pathname.startsWith("/login/")) {
    return NextResponse.next();
  }

  // API routes (incl. /api/auth/*) bypass everything.
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // Everything else is the public marketing/article surface — i18n handles it.
  return intlMiddleware(req);
}

export const config = {
  // Skip Next internals and any path with a file extension (favicon, images, etc.).
  matcher: ["/((?!_next/static|_next/image|.*\\.[a-zA-Z0-9]+$).*)"],
};
