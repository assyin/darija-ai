/**
 * Dynamic sitemap.xml — the public discovery surface for Google/Bing.
 *
 * Emits two kinds of entries:
 *
 *  1. CHROME pages (home, articles list, services, about, contact) for every
 *     routing locale that has translations.
 *  2. Each published article × the locales where it has content:
 *       - ar-MA (default) — always present
 *       - fr            — only when `title_fr` is populated (the page would
 *                         otherwise serve the Darija fallback, creating a
 *                         duplicate-content signal we want to avoid)
 *       - ar (MSA)      — skipped today; the Localizer doesn't produce MSA
 *                         translations. Reactivate when an MSA Localizer ships.
 *
 *  Each entry carries `alternates.languages` so Google can see all sibling
 *  locale URLs for the same logical resource (hreflang annotation).
 *
 *  Caching: Next caches this route by default. We import the dynamic
 *  `publicApi.getArticles` so the cache invalidates with the same revalidate
 *  window as the article list (60 s). Within 60 seconds of a publish, the
 *  sitemap reflects the new article.
 *
 *  Fail-soft: if the backend is down, we still emit the chrome pages so the
 *  sitemap is never empty for Google.
 */

import type { MetadataRoute } from "next";

import { publicApi } from "@/lib/api-client";
import { localizedCanonical } from "@/lib/canonical";

// Locales that have static UI translations (everywhere in the chrome).
// Article translation availability is checked per-article below.
const CHROME_LOCALES = ["ar-MA", "fr"] as const;
type ChromeLocale = (typeof CHROME_LOCALES)[number];

// Locales for which we emit per-article entries. Subset of CHROME_LOCALES
// — only those for which the article body is actually translated. Today we
// skip "ar" (MSA) because no MSA pipeline exists yet.
const ARTICLE_LOCALES = ["ar-MA", "fr"] as const satisfies readonly ChromeLocale[];
type ArticleLocale = (typeof ARTICLE_LOCALES)[number];

interface ChromePage {
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
}

const CHROME_PAGES: readonly ChromePage[] = [
  { path: "/", changeFrequency: "daily", priority: 1.0 },
  { path: "/articles", changeFrequency: "daily", priority: 0.9 },
  { path: "/services", changeFrequency: "monthly", priority: 0.6 },
  { path: "/about", changeFrequency: "monthly", priority: 0.4 },
  { path: "/contact", changeFrequency: "monthly", priority: 0.4 },
];

function alternatesForChrome(path: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const locale of CHROME_LOCALES) {
    out[locale] = localizedCanonical(locale, path);
  }
  return out;
}

function alternatesForArticle(
  slug: string,
  hasFr: boolean,
): Record<string, string> {
  const out: Record<string, string> = {};
  out["ar-MA"] = localizedCanonical("ar-MA", `/articles/${slug}`);
  if (hasFr) {
    out["fr"] = localizedCanonical("fr", `/articles/${slug}`);
  }
  return out;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const chromeEntries: MetadataRoute.Sitemap = CHROME_PAGES.flatMap((page) =>
    CHROME_LOCALES.map((locale) => ({
      url: localizedCanonical(locale, page.path),
      lastModified: now,
      changeFrequency: page.changeFrequency,
      priority: page.priority,
      alternates: { languages: alternatesForChrome(page.path) },
    })),
  );

  // Pull the full published catalogue. 500 cap matches the backend Query
  // validator (raised for this same purpose). At >500 we split into multiple
  // sitemaps via `generateSitemaps`.
  const articles = await publicApi.getArticles(500).catch(() => []);

  const articleEntries: MetadataRoute.Sitemap = articles.flatMap((a) => {
    const hasFr =
      typeof a.title_fr === "string" && a.title_fr.trim().length > 0;
    const lastModified = a.updated_at
      ? new Date(a.updated_at)
      : a.published_at
        ? new Date(a.published_at)
        : now;
    const langs = alternatesForArticle(a.slug, hasFr);
    const presentLocales: readonly ArticleLocale[] = hasFr
      ? ARTICLE_LOCALES
      : (["ar-MA"] as const);
    return presentLocales.map((locale) => ({
      url: localizedCanonical(locale, `/articles/${a.slug}`),
      lastModified,
      changeFrequency: "weekly" as const,
      priority: 0.8,
      alternates: { languages: langs },
    }));
  });

  return [...chromeEntries, ...articleEntries];
}
