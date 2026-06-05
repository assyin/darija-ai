/**
 * robots.txt — the public crawl manifest for Google/Bing/etc.
 *
 *   - Allow everything by default (public content).
 *   - Disallow `/admin*`, `/login`, `/api/`, `/_next/` — pages behind auth or
 *     internal to Next.js. robots.txt is consultative; the real security is
 *     the admin JWT, but signalling these as crawl-skip preserves crawl
 *     budget.
 *   - Point Google at our dynamic sitemap.
 *
 * The `host` directive (non-standard but honoured by Yandex and a few others)
 * declares the canonical hostname so any www. variant gets normalised.
 */

import type { MetadataRoute } from "next";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin", "/login", "/api/", "/_next/"],
      },
    ],
    sitemap: `${SITE_BASE}/sitemap.xml`,
    host: SITE_BASE.replace(/^https?:\/\//, ""),
  };
}
