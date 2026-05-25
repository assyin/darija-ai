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

async function proxy(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const session = await auth();
  const token = session?.accessToken;
  if (!token) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "No admin session" } },
      { status: 401 },
    );
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
