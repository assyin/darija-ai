import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { CtaBanner } from "@/components/public/home/cta-banner";
import { Hero } from "@/components/public/home/hero";
import { ServicesPreview } from "@/components/public/home/services-preview";
import { StatStrip } from "@/components/public/home/stat-strip";
import { Testimonials } from "@/components/public/home/testimonials";
import { publicApi } from "@/lib/api-client";
import { getSiteSettings } from "@/lib/use-site-settings";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata(): Promise<Metadata> {
  const s = await getSiteSettings();
  const title = s.seo_default_title || s.business_name || "DarijaAI";
  const description = s.seo_default_description || "";
  const ogImage = s.business_logo_url;
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

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");

  const articles = await publicApi.getArticles(50).catch(() => []);
  const featured = articles.slice(0, 3);
  const recent = articles.slice(3, 9);

  return (
    <div className="space-y-16 py-10 md:space-y-24 md:py-14">
      <Hero />

      <StatStrip articlesCount={articles.length} />

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

      <Testimonials />

      <CtaBanner />
    </div>
  );
}
