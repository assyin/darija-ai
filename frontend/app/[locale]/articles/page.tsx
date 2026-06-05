import type { Metadata } from "next";
import { Newspaper } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { publicApi } from "@/lib/api-client";
import { localizedCanonical } from "@/lib/canonical";
import { getSiteSettings } from "@/lib/use-site-settings";

// `ar` (MSA) was dropped from routing.locales (see i18n/routing.ts).
function ogLocale(locale: string): string {
  if (locale === "fr") return "fr_FR";
  return "ar_MA";
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const [s, t] = await Promise.all([
    getSiteSettings(),
    getTranslations({ locale, namespace: "articles_list" }),
  ]);
  const siteName = s.business_name || "DarijaAI";
  const title = `${t("page_title")} | ${siteName}`;
  const description = s.seo_default_description || t("page_subtitle");
  const url = localizedCanonical(locale, "/articles");
  const ogImage = s.business_logo_url;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      locale: ogLocale(locale),
      title,
      description,
      url,
      images: ogImage ? [{ url: ogImage, width: 1200, height: 630 }] : [],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ogImage ? [ogImage] : [],
    },
  };
}

export default async function ArticlesListPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("articles_list");
  // On /fr, restrict to articles that have an actual French translation.
  // Default locale keeps the full Darija index.
  const articles = await publicApi
    .getArticles(100, locale === "fr" ? "fr" : undefined)
    .catch(() => []);
  const [lead, ...rest] = articles;

  return (
    <div className="container-wide py-12 md:py-16">
      <header className="relative mb-12 overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute -z-10 start-0 top-[-40%] h-56 w-56 rounded-full opacity-30 blur-3xl"
          style={{ background: "var(--gradient-hero)" }}
        />
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">{t("page_title")}</h1>
        <p className="mt-4 max-w-2xl text-lg text-[var(--color-muted-foreground)]">
          {t("page_subtitle")}
        </p>
        {articles.length > 0 && (
          <span className="mt-5 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1 text-sm text-[var(--color-muted-foreground)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-primary)]" />
            {t("count", { count: articles.length })}
          </span>
        )}
      </header>

      {articles.length === 0 ? (
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-8 py-16 text-center">
          <Newspaper className="mx-auto h-10 w-10 text-[var(--color-muted)]" aria-hidden />
          <p className="mt-4 text-[var(--color-muted-foreground)]">{t("no_results")}</p>
        </div>
      ) : (
        <div className="space-y-8">
          {lead && <ArticleCardPublic article={lead} variant="featured" />}
          {rest.length > 0 && (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {rest.map((a) => (
                <ArticleCardPublic key={a.id} article={a} variant="compact" />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
