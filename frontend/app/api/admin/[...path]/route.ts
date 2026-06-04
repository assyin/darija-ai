import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/lib/auth";

// Same-origin authed proxy: forwards /api/admin/* to the backend's
// /admin/* endpoints with the backend JWT pulled from the NextAuth session
// (httpOnly cookie). Keeps the token server-side; the browser never sees it.
const BACKEND_BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000/api/v1";

type Ctx = { params: Promise<{ path: string[] }> };

function expiredResponse(): NextResponse {
  return NextResponse.json(
    {
      error: {
        code: "SESSION_EXPIRED",
        message:
          "Votre session d'administration a expiré. Reconnectez-vous pour continuer.",
      },
    },
    { status: 401 },
  );
}

function unauthorizedResponse(): NextResponse {
  return NextResponse.json(
    { error: { code: "UNAUTHORIZED", message: "No admin session" } },
    { status: 401 },
  );
}

async function proxy(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const session = await auth();
  const token = session?.accessToken;
  if (!token) return unauthorizedResponse();

  // Catch the JWT expiry locally so we never send a stale token to the backend
  // (which would respond 401 with a backend error shape and confuse the client
  // into rendering "0 articles" instead of triggering a re-login).
  const expiresAt = session?.accessTokenExpires;
  if (typeof expiresAt === "number" && Date.now() >= expiresAt) {
    return expiredResponse();
  }

  const { path } = await ctx.params;
  const target = `${BACKEND_BASE}/admin/${path.join("/")}${req.nextUrl.search}`;

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.text() : undefined;

  const res = await fetch(target, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body && body.length > 0 ? body : undefined,
    cache: "no-store",
  });

  // Backend may itself reject as 401 (token revoked, secret rotated, clock
  // skew); translate that into the same SESSION_EXPIRED shape so the client
  // has a single recovery path.
  if (res.status === 401) return expiredResponse();

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") || "application/json",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
