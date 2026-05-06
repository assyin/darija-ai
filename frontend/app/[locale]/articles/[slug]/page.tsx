import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Clock } from "lucide-react";

import { ArticleCTA } from "@/components/public/article-cta";
import { RtlContent } from "@/components/shared/rtl-content";
import { bdiHtml, stripBdi } from "@/lib/bidi";
import type { ArticlePublic, ArticlePublicDetail } from "@/lib/types";
import { getSiteSettings } from "@/lib/use-site-settings";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

async function fetchArticle(slug: string): Promise<ArticlePublicDetail | null> {
  try {
    const res = await fetch(`${API_BASE}/articles/${encodeURIComponent(slug)}`, {
      next: { revalidate: 60 },
    });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return (await res.json()) as ArticlePublicDetail;
  } catch {
    return null;
  }
}

async function fetchRelated(currentSlug: string): Promise<ArticlePublic[]> {
  try {
    const res = await fetch(`${API_BASE}/articles?limit=6`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const list = (await res.json()) as ArticlePublic[];
    return list.filter((a) => a.slug !== currentSlug).slice(0, 3);
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; locale: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const article = await fetchArticle(slug);
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
        ? [{ url: article.hero_image_url, width: 1024, height: 576 }]
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
    fetchArticle(slug),
    getSiteSettings(),
  ]);
  if (!article) notFound();

  const t = await getTranslations("article");
  const tNav = await getTranslations("nav");
  const related = await fetchRelated(slug);
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

      <article>
        {/* Breadcrumb */}
        <div className="container-wide pt-8">
          <nav
            dir="rtl"
            className="font-arabic text-sm text-[var(--color-muted-foreground)]"
          >
            <Link href="/" className="hover:text-[var(--color-primary)]">{tNav("home")}</Link>
            {" › "}
            <Link href="/articles" className="hover:text-[var(--color-primary)]">{tNav("articles")}</Link>
          </nav>
        </div>

        {/* Header */}
        <header className="container-narrow py-10 text-center">
          {article.categories[0] && (
            <span className="inline-block rounded-full bg-[var(--color-accent)]/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--color-accent-dark)]">
              {article.categories[0]}
            </span>
          )}
          <h1
            dir="rtl"
            className="font-arabic-display mt-6 text-3xl leading-tight md:text-5xl"
            dangerouslySetInnerHTML={{ __html: bdiHtml(article.title_darija) }}
          />
          <p
            dir="rtl"
            className="font-arabic mt-6 text-lg text-[var(--color-muted-foreground)] md:text-xl"
            dangerouslySetInnerHTML={{ __html: bdiHtml(article.excerpt_darija) }}
          />
          <div
            dir="rtl"
            className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm text-[var(--color-muted)]"
          >
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
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {t("reading_time", { minutes: article.reading_time_minutes })}
              </span>
            )}
          </div>
        </header>

        {/* Hero image */}
        {article.hero_image_url && (
          <div className="container-wide">
            <div className="mx-auto aspect-video w-full max-w-4xl overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={article.hero_image_url}
                alt={stripBdi(article.hero_image_alt ?? article.title_darija)}
                className="h-full w-full object-cover"
              />
            </div>
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
          <section className="container-wide py-16">
            <h2
              dir="rtl"
              className="font-arabic-display mb-8 text-2xl md:text-3xl"
            >
              {t("related_articles")}
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((r) => (
                <RelatedCard key={r.id} article={r} />
              ))}
            </div>
          </section>
        )}

        <div className="container-wide pb-16">
          <Link
            href="/articles"
            dir="rtl"
            className="font-arabic text-sm font-medium text-[var(--color-primary)] hover:text-[var(--color-accent-dark)]"
          >
            {t("back_to_articles")}
          </Link>
        </div>
      </article>
    </>
  );
}

function RelatedCard({ article }: { article: ArticlePublic }) {
  return (
    <Link
      href={`/articles/${article.slug}`}
      className="group block rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 transition-all hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md"
    >
      <h3
        dir="rtl"
        className="font-arabic-display line-clamp-2 text-lg leading-snug"
        dangerouslySetInnerHTML={{ __html: bdiHtml(article.title_darija) }}
      />
      <p
        dir="rtl"
        className="font-arabic mt-3 line-clamp-2 text-sm text-[var(--color-muted-foreground)]"
        dangerouslySetInnerHTML={{ __html: bdiHtml(article.excerpt_darija) }}
      />
    </Link>
  );
}
