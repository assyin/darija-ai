import type { ArticlePublic, ArticlePublicDetail } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const REVALIDATE_ARTICLES = {
  next: { revalidate: 60 },
} satisfies RequestInit;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE" | "PUT",
  path: string,
  body?: unknown,
  init?: RequestInit,
  base: string = API_BASE,
): Promise<T> {
  const url = path.startsWith("http") ? path : `${base}${path}`;
  const res = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  });

  let parsed: unknown = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    parsed = await res.json().catch(() => null);
  }

  if (!res.ok) {
    // Admin session expired (proxy stamped the 401 with this code) → boot the
    // user to the login screen with a callbackUrl so they land back on the
    // page they came from. Without this, react-query would just swallow the
    // 401 and the UI shows "0 items".
    const code = (parsed as { error?: { code?: string } } | null)?.error?.code;
    if (
      base === ADMIN_BASE &&
      res.status === 401 &&
      code === "SESSION_EXPIRED" &&
      typeof window !== "undefined"
    ) {
      const here = encodeURIComponent(window.location.pathname + window.location.search);
      // Hard navigate — react-query callers (mutations, etc.) shouldn't see the
      // promise resolve in this case.
      window.location.assign(`/login?callbackUrl=${here}`);
    }

    const message =
      (parsed as { error?: { message?: string } } | null)?.error?.message ||
      `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, message, parsed);
  }

  return parsed as T;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => request<T>("GET", path, undefined, init),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>("POST", path, body, init),
  patch: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>("PATCH", path, body, init),
  delete: <T>(path: string, init?: RequestInit) =>
    request<T>("DELETE", path, undefined, init),
};

// Admin client — calls the same-origin authed proxy at /api/admin/*, which
// injects the backend JWT from the httpOnly NextAuth session server-side.
// The browser never sees the token; the session cookie rides along automatically.
const ADMIN_BASE = "/api/admin";

export const adminApi = {
  get: <T>(path: string, init?: RequestInit) =>
    request<T>("GET", path, undefined, init, ADMIN_BASE),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>("POST", path, body, init, ADMIN_BASE),
  patch: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>("PATCH", path, body, init, ADMIN_BASE),
  delete: <T>(path: string, init?: RequestInit) =>
    request<T>("DELETE", path, undefined, init, ADMIN_BASE),
};

export const publicApi = {
  /**
   * @param lang Pass "fr" to restrict to articles that have a French
   *             translation (used on /fr listings so we never serve a
   *             Darija-only article on the French index).
   */
  getArticles: (limit: number, lang?: "fr"): Promise<ArticlePublic[]> => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (lang) params.set("lang", lang);
    return api.get<ArticlePublic[]>(`/articles?${params}`, REVALIDATE_ARTICLES);
  },

  getArticle: (slug: string): Promise<ArticlePublicDetail | null> =>
    api
      .get<ArticlePublicDetail>(`/articles/${encodeURIComponent(slug)}`, REVALIDATE_ARTICLES)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }),

  /**
   * Semantic related-articles rail. Backend ranks by weighted overlap of
   * categories (x4) + tags (x2) + recency (+1 if <30 days). Falls back
   * to the most recent publications when no topical neighbours exist.
   * @param slug   The source article's slug.
   * @param lang   Pass "fr" so we only get articles that have a FR translation.
   * @param limit  1-5, default 4 — matches the 2x2 grid in the page.
   */
  getRelatedArticles: (
    slug: string,
    lang?: "fr",
    limit: number = 4,
  ): Promise<ArticlePublic[]> => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (lang) params.set("lang", lang);
    return api.get<ArticlePublic[]>(
      `/articles/${encodeURIComponent(slug)}/related?${params}`,
      REVALIDATE_ARTICLES,
    );
  },
};
