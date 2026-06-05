/**
 * Locale-aware canonical URL builder.
 *
 * Before this helper landed (SEO audit 2026-06-05), every `generateMetadata`
 * built canonicals as `${SITE_BASE}/path`, ignoring the locale. The result was
 * that `/fr/articles/<slug>` returned a canonical pointing to the Arabic
 * version, telling Google "this is just a duplicate of /articles/<slug>" —
 * which suppressed FR pages from the index entirely.
 *
 * The default locale (per `routing.ts`: ar-MA) carries no URL prefix; other
 * locales prefix with `/fr` or `/ar`. The helper handles the empty-path home
 * case so it never emits `https://x.com/fr/` (trailing slash) — just
 * `https://x.com/fr`.
 *
 * `og:url`, `mainEntityOfPage.@id` and any other "self URL" should reuse the
 * same value so all signals agree.
 */

import { routing } from "@/i18n/routing";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export function localizedCanonical(locale: string, path: string = ""): string {
  const prefix = locale === routing.defaultLocale ? "" : `/${locale}`;
  // Normalise: "" and "/" both mean home and must produce no trailing slash.
  // Any other path is rendered with exactly one leading "/".
  let normalisedPath: string;
  if (path === "" || path === "/") {
    normalisedPath = "";
  } else {
    normalisedPath = path.startsWith("/") ? path : `/${path}`;
  }
  return `${SITE_BASE}${prefix}${normalisedPath}`;
}
