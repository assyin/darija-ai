import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowLeft, Clock, ImageIcon } from "lucide-react";

import { Link } from "@/i18n/navigation";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { RtlContent } from "@/components/shared/rtl-content";
import { publicApi } from "@/lib/api-client";
import { localizeArticle } from "@/lib/article-localize";
import { bdiHtml, stripBdi } from "@/lib/bidi";
import { localizedCanonical } from "@/lib/canonical";
import type { ArticlePublic } from "@/lib/types";
import { getSiteSettings } from "@/lib/use-site-settings";
import { cn } from "@/lib/utils";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; locale: string }>;
}): Promise<Metadata> {
  const { slug, locale } = await params;
  const article = await publicApi.getArticle(slug);
  if (!article) return { title: "Article" };

  // Each locale points to its own canonical (and to its own siblings via
  // hreflang in the sitemap). Before this fix all locales reported the
  // ar-MA URL as canonical, suppressing FR/AR pages from the Google index.
  const url = localizedCanonical(locale, `/articles/${article.slug}`);
  const localized = localizeArticle(article, locale);
  // Strip bdi tags — metadata is plain-text, not HTML.
  const title = stripBdi(localized.metaTitle || localized.title);
  const description = stripBdi(localized.metaDescription || localized.excerpt);
  // Hero image when available, else fall back to the bundled brand mark so
  // social previews always carry our identity.
  const heroImage = article.hero_image_url;
  const ogImage = heroImage ?? `${SITE_BASE}/logo-mark.png`;
  return {
    // `absolute` opts out of the root layout's "%s · DarijaAI" template.
    // The Localizer keeps meta_title under 60 chars so it already fits in
    // Google's SERP cut-off (~60 chars desktop, ~50 mobile); appending
    // " · DarijaAI" pushed every article 10-15 chars over the limit and
    // SEO audit tools surfaced "Title too long" on the whole catalogue.
    // The domain (titritai.com) carries the brand in the SERP anyway.
    title: { absolute: title },
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      locale: localized.contentLang === "fr" ? "fr_FR" : "ar_MA",
      title,
      description,
      url,
      images: [
        heroImage
          ? { url: heroImage, width: 1200, height: 630 }
          : { url: ogImage, width: 1024, height: 1024 },
      ],
      publishedTime: article.published_at ?? undefined,
    },
    twitter: {
      card: heroImage ? "summary_large_image" : "summary",
      title,
      description,
      images: [ogImage],
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
  // Semantic related rail — ranks the corpus by category + tag overlap with
  // a freshness bonus. Replaces a previous "3 most recent" slice that had
  // no topical relevance. Fail-soft: backend errors → empty array, the
  // section just doesn't render below.
  const related = await publicApi
    .getRelatedArticles(slug, locale === "fr" ? "fr" : undefined, 4)
    .catch(() => [] as ArticlePublic[]);
  // Same locale-aware URL as in generateMetadata so JSON-LD mainEntityOfPage
  // agrees with the canonical and og:url.
  const url = localizedCanonical(locale, `/articles/${article.slug}`);
  const businessName = settings.business_name || "DarijaAI";
  const localized = localizeArticle(article, locale);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: stripBdi(localized.title),
    description: stripBdi(localized.excerpt),
    image: article.hero_image_url ? [article.hero_image_url] : undefined,
    datePublished: article.published_at,
    dateModified: article.published_at,
    author: { "@type": "Organization", name: businessName },
    publisher: {
      "@type": "Organization",
      name: businessName,
      logo: {
        "@type": "ImageObject",
        url: settings.business_logo_url || `${SITE_BASE}/logo-mark.png`,
      },
    },
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    inLanguage: localized.contentLang,
  };

  // Light editorial theme — only this page swaps the public dark tokens for
  // light values; header + footer outside this wrapper stay on the brand dark.
  // Brand accents (--color-primary, --color-accent) are inherited unchanged
  // so violet links + h2 underlines keep the brand voice.
  const lightTheme: React.CSSProperties = {
    "--color-bg": "#fafaf7",
    "--color-bg-elevated": "#ffffff",
    "--color-fg": "#18181b",
    "--color-muted-foreground": "#52525b",
    "--color-muted": "#71717a",
    "--color-border": "#e4e4e7",
  } as React.CSSProperties;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <article
        className="bg-[#fafaf7] pb-20 text-zinc-900"
        style={lightTheme}
      >
        {/* Breadcrumb — chrome, inherits locale direction/font */}
        <div className="container-wide pt-8">
          <nav className="text-sm text-zinc-500">
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
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-zinc-600">
            {article.categories[0] && (
              <span className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-violet-700">
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
            dir={localized.dir}
            className={cn(
              "mt-6 text-3xl font-bold leading-tight text-zinc-900 md:text-5xl",
              localized.dir === "rtl" && "font-arabic-display",
            )}
            dangerouslySetInnerHTML={{ __html: bdiHtml(localized.title) }}
          />
          <p
            dir={localized.dir}
            className={cn(
              "mx-auto mt-5 max-w-2xl text-lg text-zinc-600 md:text-xl",
              localized.dir === "rtl" && "font-arabic",
            )}
            dangerouslySetInnerHTML={{ __html: bdiHtml(localized.excerpt) }}
          />
          {localized.isFallback && (
            <p className="mx-auto mt-3 max-w-2xl rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">
              Traduction française non disponible — version originale en darija
              affichée.
            </p>
          )}
        </header>

        {/* Hero image — light backdrop + soft shadow */}
        {article.hero_image_url && (
          <div className="container-wide">
            <figure className="relative mx-auto aspect-video w-full max-w-4xl overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-[0_18px_50px_-22px_rgba(15,23,42,0.18)]">
              <ImageIcon
                aria-hidden
                className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 text-zinc-300"
              />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={article.hero_image_url}
                alt={stripBdi(article.hero_image_alt ?? localized.title)}
                className="relative h-full w-full object-cover"
              />
            </figure>
          </div>
        )}

        {/* Body */}
        <div className="container-narrow py-10">
          <RtlContent
            markdown={localized.content ?? article.content_darija}
            dir={localized.dir}
          />
        </div>

        {/* Related — light cards inside the light page */}
        {related.length > 0 && (
          <section className="container-wide py-14">
            <h2 className="mb-8 text-2xl font-bold tracking-tight text-zinc-900 md:text-3xl">
              {t("related_articles")}
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {related.map((r) => (
                <ArticleCardPublic
                  key={r.id}
                  article={r}
                  variant="compact"
                  theme="light"
                />
              ))}
            </div>
          </section>
        )}

        {/* Back to articles */}
        <div className="container-wide">
          <Link
            href="/articles"
            className="inline-flex items-center gap-2 text-sm font-medium text-violet-700 transition-colors hover:text-violet-900"
          >
            <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
            {t("back_to_articles")}
          </Link>
        </div>
      </article>
    </>
  );
}
