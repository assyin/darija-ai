import type { Metadata } from "next";
import { Quote, Sparkles } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { LogoMark } from "@/components/public/logo-mark";
import { getSiteSettings } from "@/lib/use-site-settings";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "about" });
  return {
    title: t("page_title"),
    description: t("intro"),
    alternates: { canonical: `${SITE_BASE}/about` },
  };
}

export default async function AboutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("about");
  const settings = await getSiteSettings();
  const ownerName = settings.business_owner_name;
  const ownerRole = settings.business_owner_role;

  return (
    <div className="relative isolate">
      {/* Ambient top glow — same brand cue as the hero, much subtler */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-fuchsia-500/10 via-violet-500/5 to-transparent"
      />

      <div className="container-narrow py-20 md:py-28">
        {/* Hero */}
        <header className="text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90">
            {t("tagline_kicker")}
          </p>
          <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-white md:text-5xl lg:text-6xl">
            {t("page_title")}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-white/75 md:text-xl">
            {t("intro")}
          </p>
        </header>

        {/* Manifesto pull-quote */}
        <figure className="relative mx-auto mt-20 max-w-3xl rounded-3xl border border-white/10 bg-white/[0.04] p-8 backdrop-blur-xl md:p-12">
          <Quote
            aria-hidden
            className="absolute -top-4 start-8 h-8 w-8 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 p-1.5 text-white shadow-[0_0_24px_-4px_rgba(168,85,247,0.7)] ring-1 ring-white/15"
          />
          <blockquote className="text-2xl font-medium leading-relaxed text-white md:text-3xl md:leading-snug">
            <p
              dir="auto"
              className="font-arabic-display"
            >
              «&nbsp;{t("manifesto_quote")}&nbsp;»
            </p>
          </blockquote>
        </figure>

        {/* Mission */}
        <section className="mt-24">
          <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
            {t("mission_title")}
          </h2>
          <p
            dir="auto"
            className="font-arabic mt-5 text-lg leading-[1.85] text-white/80"
          >
            {t("mission_text")}
          </p>
        </section>

        {/* Why Darija */}
        <section className="mt-16">
          <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
            {t("why_darija_title")}
          </h2>
          <p
            dir="auto"
            className="font-arabic mt-5 text-lg leading-[1.85] text-white/80"
          >
            {t("why_darija_text")}
          </p>
        </section>

        {/* Non-commercial pledge */}
        <section className="mt-20 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.04] p-7 backdrop-blur-xl md:p-9">
          <p className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.25em] text-emerald-300">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            {t("non_commercial_label")}
          </p>
          <p
            dir="auto"
            className="font-arabic mt-3 text-base leading-relaxed text-white/85 md:text-lg"
          >
            {t("non_commercial_text")}
          </p>
        </section>

        {/* The person behind */}
        {ownerName && (
          <section className="mt-20">
            <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
              {t("behind_title")}
            </h2>

            <div className="mt-7 rounded-2xl border border-white/10 bg-white/[0.04] p-7 backdrop-blur-xl md:p-9">
              <div className="flex flex-wrap items-center gap-4">
                <LogoMark size={56} />
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-fuchsia-300/85">
                    {t("behind_intro")}
                  </p>
                  <p
                    dir="auto"
                    className="mt-1 text-2xl font-bold tracking-tight text-white"
                  >
                    {ownerName}
                  </p>
                  {ownerRole && (
                    <p
                      dir="auto"
                      className="font-arabic mt-0.5 text-sm text-white/65"
                    >
                      {ownerRole}
                    </p>
                  )}
                </div>
              </div>
              <p
                dir="auto"
                className="font-arabic mt-6 text-base leading-[1.85] text-white/80 md:text-lg"
              >
                {t("behind_note")}
              </p>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
