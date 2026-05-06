import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Bot, GraduationCap, LineChart, Workflow } from "lucide-react";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { publicApi } from "@/lib/api-client";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");
  const tServices = await getTranslations("services");

  const articles = await publicApi.getArticles(10).catch(() => []);
  const featured = articles.slice(0, 3);
  const recent = articles.slice(3);

  return (
    <>
      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 zellige-overlay opacity-50" aria-hidden="true" />
        <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-[var(--color-accent)]/5" aria-hidden="true" />
        <div className="container-wide relative py-20 md:py-32">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--color-accent)]">
              {t("tagline")}
            </p>
            <h1
              dir="rtl"
              className="font-arabic-display mt-6 text-4xl leading-tight md:text-6xl"
            >
              {t("hero_title")}
            </h1>
            <p
              dir="rtl"
              className="font-arabic mt-6 text-lg text-[var(--color-muted-foreground)] md:text-xl"
            >
              {t("hero_subtitle")}
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/articles"
                className="inline-flex items-center justify-center rounded-md bg-[var(--color-primary)] px-7 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-[var(--color-primary-dark)]"
              >
                {t("hero_cta_primary")}
              </Link>
              <Link
                href="/services"
                className="inline-flex items-center justify-center rounded-md border-2 border-[var(--color-primary)] px-7 py-3 text-base font-semibold text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/5"
              >
                {t("hero_cta_secondary")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURED */}
      {featured.length > 0 && (
        <section className="container-wide py-16">
          <h2
            dir="rtl"
            className="font-arabic-display mb-10 text-3xl md:text-4xl"
          >
            {t("featured_title")}
          </h2>
          <div className="grid gap-6 md:grid-cols-3">
            {featured.map((a) => (
              <ArticleCardPublic key={a.id} article={a} variant="featured" />
            ))}
          </div>
        </section>
      )}

      <div className="zellige-divider container-wide" aria-hidden="true" />

      {/* RECENT */}
      {recent.length > 0 && (
        <section className="container-wide py-16">
          <div className="mb-10 flex items-end justify-between gap-4">
            <h2 dir="rtl" className="font-arabic-display text-3xl md:text-4xl">
              {t("recent_title")}
            </h2>
            <Link
              href="/articles"
              className="text-sm font-medium text-[var(--color-primary)] hover:text-[var(--color-accent-dark)]"
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

      {articles.length === 0 && (
        <section className="container-wide py-24 text-center">
          <p
            dir="rtl"
            className="font-arabic text-[var(--color-muted-foreground)]"
          >
            ما كاينش حتى مقال دابا. عاود قريباً.
          </p>
        </section>
      )}

      {/* CTA — services oriented */}
      <section className="bg-[var(--color-accent)]/5 py-20">
        <div className="container-wide text-center">
          <h2
            dir="rtl"
            className="font-arabic-display text-3xl md:text-4xl"
          >
            {tServices("cta_title")}
          </h2>
          <p
            dir="rtl"
            className="font-arabic mx-auto mt-4 max-w-xl text-lg text-[var(--color-muted-foreground)]"
          >
            {tServices("cta_subtitle")}
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <ServicePill icon={Bot} label={tServices("service_1_title")} />
            <ServicePill icon={Workflow} label={tServices("service_2_title")} />
            <ServicePill icon={GraduationCap} label={tServices("service_3_title")} />
            <ServicePill icon={LineChart} label={tServices("service_4_title")} />
          </div>
          <Link
            href="/services"
            className="mt-10 inline-flex items-center justify-center rounded-md bg-[var(--color-primary)] px-7 py-3 text-base font-semibold text-white transition-colors hover:bg-[var(--color-primary-dark)]"
          >
            {tServices("page_title")}
          </Link>
        </div>
      </section>
    </>
  );
}

function ServicePill({ icon: Icon, label }: { icon: React.ComponentType<{ className?: string }>; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4 text-start">
      <Icon className="h-5 w-5 shrink-0 text-[var(--color-primary)]" />
      <span dir="rtl" className="font-arabic text-sm font-medium leading-tight">
        {label}
      </span>
    </div>
  );
}
