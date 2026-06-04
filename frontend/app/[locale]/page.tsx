import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { ArticleCardPublic } from "@/components/public/article-card-public";
import { CtaBanner } from "@/components/public/home/cta-banner";
import { Hero } from "@/components/public/home/hero";
import { ServicesPreview } from "@/components/public/home/services-preview";
import { StatStrip } from "@/components/public/home/stat-strip";
import { publicApi } from "@/lib/api-client";
import { getSiteSettings } from "@/lib/use-site-settings";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata(): Promise<Metadata> {
  const s = await getSiteSettings();
  const title = s.seo_default_title || s.business_name || "DarijaAI";
  const description = s.seo_default_description || "";
  // Prefer the configured business logo; fall back to the bundled brand mark
  // so social previews are never imageless.
  const ogImage = s.business_logo_url || `${SITE_BASE}/logo-mark.png`;
  const ogImageIsBrandMark = !s.business_logo_url;
  return {
    title,
    description,
    alternates: { canonical: SITE_BASE },
    openGraph: {
      type: "website",
      locale: "ar_MA",
      title,
      description,
      url: SITE_BASE,
      images: [
        ogImageIsBrandMark
          ? { url: ogImage, width: 1024, height: 1024 }
          : { url: ogImage, width: 1200, height: 630 },
      ],
    },
    twitter: {
      card: ogImageIsBrandMark ? "summary" : "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");

  // /fr home only surfaces articles that actually have a French translation.
  const articles = await publicApi
    .getArticles(50, locale === "fr" ? "fr" : undefined)
    .catch(() => []);
  const featured = articles.slice(0, 3);
  const recent = articles.slice(3, 9);

  return (
    <div>
      {/* Hero + glass stat strip read as one cinematic block; the strip floats
          over the lower hero via its own negative margin. */}
      <Hero locale={locale} />
      <StatStrip articlesCount={articles.length} />

      <div className="space-y-16 pt-20 md:space-y-24 md:pt-28">
      {featured.length > 0 && (
        <section className="container-wide">
          <h2 className="mb-8 text-3xl font-bold tracking-tight md:text-4xl">
            {t("featured_title")}
          </h2>
          <div className="grid gap-6 md:grid-cols-3">
            {featured.map((a) => (
              <ArticleCardPublic key={a.id} article={a} variant="featured" />
            ))}
          </div>
        </section>
      )}

      {recent.length > 0 && (
        <section className="container-wide">
          <div className="mb-8 flex items-end justify-between gap-4">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              {t("recent_title")}
            </h2>
            <Link
              href="/articles"
              className="shrink-0 text-sm font-medium text-[var(--color-primary)] hover:underline"
            >
              {t("see_all")} →
            </Link>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((a) => (
              <ArticleCardPublic key={a.id} article={a} variant="compact" />
            ))}
          </div>
        </section>
      )}

      <ServicesPreview />

      <CtaBanner />
      </div>
    </div>
  );
}
