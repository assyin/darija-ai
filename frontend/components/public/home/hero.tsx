import Link from "next/link";
import { BrainCircuit } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

/**
 * Home hero. The visual is a CSS glow "orb" placeholder (no bespoke asset yet);
 * it reads --gradient-hero / --glow tokens, so AR renders warmer/stronger and
 * FR cooler/subtler automatically. Headings inherit the locale body font
 * (Tajawal for AR, Inter for FR).
 */
export function Hero() {
  const t = useTranslations("home");

  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute start-1/2 top-[-12%] h-[440px] w-[440px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{ background: "var(--gradient-hero)" }}
        />
      </div>

      <div className="container-wide grid items-center gap-12 py-16 md:py-24 lg:grid-cols-2">
        <div className="text-center lg:text-start">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--color-accent)]">
            {t("tagline")}
          </p>
          <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight md:text-5xl lg:text-6xl">
            {t("hero_title")}
          </h1>
          <p className="mt-5 text-lg text-[var(--color-muted-foreground)] md:text-xl">
            {t("hero_subtitle")}
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
            <Button asChild size="lg">
              <Link href="/articles">{t("hero_cta_primary")}</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/services">{t("hero_cta_secondary")}</Link>
            </Button>
          </div>
        </div>

        <div aria-hidden className="relative mx-auto hidden aspect-square w-full max-w-md lg:block">
          <div
            className="absolute inset-6 rounded-full opacity-70 blur-2xl"
            style={{ background: "var(--gradient-hero)" }}
          />
          <div className="absolute inset-10 rounded-full border border-white/10 bg-[var(--color-bg-elevated)]/40 backdrop-blur-sm" />
          <div className="absolute inset-0 flex items-center justify-center">
            <BrainCircuit className="h-28 w-28 text-white/90" />
          </div>
        </div>
      </div>
    </section>
  );
}
