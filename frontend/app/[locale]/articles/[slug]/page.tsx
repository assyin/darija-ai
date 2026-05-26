import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowLeft, Clock, ImageIcon } from "lucide-react";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { ArticleCTA } from "@/components/public/article-cta";
import { RtlContent } from "@/components/shared/rtl-content";
import { bdiHtml, stripBdi } from "@/lib/bidi";
import { publicApi } from "@/lib/api-client";
import type { ArticlePublic } from "@/lib/types";
import { getSiteSettings } from "@/lib/use-site-settings";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; locale: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const article = await publicApi.getArticle(slug);
  if (!article) return { title: "Article" };

  const url = `${SITE_BASE}/articles/${article.slug}`;
  // Strip bdi tags — metadata is plain-text, not HTML.
  const title = stripBdi(article.meta_title || article.title_darija);
  const description = stripBdi(
    article.meta_description || article.excerpt_darija,
  );
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      locale: "ar_MA",
      title,
      description,
      url,
      images: article.hero_image_url
        ? [{ url: article.hero_image_url, width: 1200, height: 630 }]
        : [],
      publishedTime: article.published_at ?? undefined,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: article.hero_image_url ? [article.hero_image_url] : [],
    },
  };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string; locale: string }>;
}) {
  const { slug, locale } = await params;
  setRequestLocale(locale);

  const [article, settings] = await Promise.all([
    publicApi.getArticle(slug),
    getSiteSettings(),
  ]);
  if (!article) notFound();

  const t = await getTranslations("article");
  const tNav = await getTranslations("nav");
  const related = await publicApi
    .getArticles(6)
    .then((list) => list.filter((a) => a.slug !== slug).slice(0, 3))
    .catch(() => [] as ArticlePublic[]);
  const url = `${SITE_BASE}/articles/${article.slug}`;
  const businessName = settings.business_name || "DarijaAI";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: stripBdi(article.title_darija),
    description: stripBdi(article.excerpt_darija),
    image: article.hero_image_url ? [article.hero_image_url] : undefined,
    datePublished: article.published_at,
    dateModified: article.published_at,
    author: { "@type": "Organization", name: businessName },
    publisher: {
      "@type": "Organization",
      name: businessName,
      logo: settings.business_logo_url
        ? { "@type": "ImageObject", url: settings.business_logo_url }
        : undefined,
    },
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    inLanguage: "ar-MA",
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <article className="pb-16">
        {/* Breadcrumb — chrome, inherits locale direction/font */}
        <div className="container-wide pt-8">
          <nav className="text-sm text-[var(--color-muted-foreground)]">
            <Link href="/" className="hover:text-[var(--color-primary)]">
              {tNav("home")}
            </Link>
            <span className="mx-2 opacity-50">/</span>
            <Link href="/articles" className="hover:text-[var(--color-primary)]">
              {tNav("articles")}
            </Link>
          </nav>
        </div>

        {/* Header — centered to avoid RTL/LTR alignment clash */}
        <header className="container-narrow py-8 text-center md:py-10">
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-[var(--color-muted-foreground)]">
            {article.categories[0] && (
              <span className="rounded-full border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-primary)]">
                {article.categories[0]}
              </span>
            )}
            {article.published_at && (
              <span>
                {t("published_on")}{" "}
                {new Date(article.published_at).toLocaleDateString("fr-MA", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </span>
            )}
            {article.reading_time_minutes != null && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {t("reading_time", { minutes: article.reading_time_minutes })}
              </span>
            )}
          </div>

          <h1
            dir="rtl"
            className="font-arabic-display mt-6 text-3xl leading-tight md:text-5xl"
            dangerouslySetInnerHTML={{ __html: bdiHtml(article.title_darija) }}
          />
          <p
            dir="rtl"
            className="font-arabic mx-auto mt-5 max-w-2xl text-lg text-[var(--color-muted-foreground)] md:text-xl"
            dangerouslySetInnerHTML={{ __html: bdiHtml(article.excerpt_darija) }}
          />
        </header>

        {/* Hero image — polished, with a graceful placeholder behind it */}
        {article.hero_image_url && (
          <div className="container-wide">
            <figure className="relative mx-auto aspect-video w-full max-w-4xl overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
              <div
                aria-hidden
                className="absolute inset-0 opacity-15"
                style={{ background: "var(--gradient-hero)" }}
              />
              <ImageIcon
                aria-hidden
                className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 text-[var(--color-muted)]"
              />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={article.hero_image_url}
                alt={stripBdi(article.hero_image_alt ?? article.title_darija)}
                className="relative h-full w-full object-cover"
              />
            </figure>
          </div>
        )}

        {/* Body */}
        <div className="container-narrow py-10">
          <RtlContent markdown={article.content_darija} />
        </div>

        {/* Editorial CTA — driven by site_settings.cta_template_darija */}
        <div className="container-narrow">
          <ArticleCTA settings={settings} />
        </div>

        {/* Related */}
        {related.length > 0 && (
          <section className="container-wide py-12">
            <h2 className="mb-8 text-2xl font-bold tracking-tight md:text-3xl">
              {t("related_articles")}
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((r) => (
                <ArticleCardPublic key={r.id} article={r} variant="compact" />
              ))}
            </div>
          </section>
        )}

        {/* Back to articles */}
        <div className="container-wide">
          <Link
            href="/articles"
            className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-primary)] transition-colors hover:text-[var(--color-primary-dark)]"
          >
            <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
            {t("back_to_articles")}
          </Link>
        </div>
      </article>
    </>
  );
}
