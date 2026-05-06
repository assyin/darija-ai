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
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
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

export const publicApi = {
  getArticles: (limit: number): Promise<ArticlePublic[]> => {
    const params = new URLSearchParams({ limit: String(limit) });
    return api.get<ArticlePublic[]>(`/articles?${params}`, REVALIDATE_ARTICLES);
  },

  getArticle: (slug: string): Promise<ArticlePublicDetail | null> =>
    api
      .get<ArticlePublicDetail>(`/articles/${encodeURIComponent(slug)}`, REVALIDATE_ARTICLES)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }),
};
