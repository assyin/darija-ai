import Image from "next/image";
import { ArrowLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  DEFAULT_HERO_VARIANT_AR,
  DEFAULT_HERO_VARIANT_FR,
  resolveHeroVariant,
} from "@/lib/hero-variants";
import { getSiteSettings } from "@/lib/use-site-settings";

/**
 * Home hero — V4. The illustration is a hand-curated asset shipped under
 * `/public/hero/`; no CSS scenography is layered on top — the image *is* the
 * hero. Only minimal additions:
 *   - A very subtle bottom darkening so the CTA gradient stays readable.
 *   - A small soft radial behind the text (8% extra dim) for WCAG contrast
 *     on the headline; this is light enough that the image still reads as
 *     one continuous scene.
 *
 * Layout is `dir="ltr"` so the text block sits visually-LEFT in both AR and
 * FR — Arabic characters inside still render right-to-left via Unicode bidi.
 *
 * Variant resolution: `hero_variant_ar` / `hero_variant_fr` site settings.
 */
export async function Hero({ locale }: { locale: string }) {
  const t = await getTranslations("home");
  const settings = await getSiteSettings();

  const isFr = locale === "fr";
  const variant = resolveHeroVariant(
    isFr ? settings.hero_variant_fr : settings.hero_variant_ar,
    isFr ? DEFAULT_HERO_VARIANT_FR : DEFAULT_HERO_VARIANT_AR,
  );

  const textDir: "ltr" | "rtl" = isFr ? "ltr" : "rtl";
  const textStyle = { textAlign: "left" as const, direction: textDir };

  return (
    <section
      dir="ltr"
      className="relative isolate flex min-h-[88vh] items-center overflow-hidden bg-[#0a0418] lg:min-h-[90vh]"
    >
      {/* The scene — full-bleed, untouched */}
      <div aria-hidden className="absolute inset-0 -z-20">
        <Image
          src={variant.src}
          alt=""
          fill
          sizes="100vw"
          priority
          className="object-cover object-center"
        />
      </div>

      {/* Minimal legibility aid — very soft bottom + left fade only.
          Stays under 20% opacity so the asset still reads as one image. */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10"
        style={{
          background:
            "linear-gradient(to top, rgba(10,4,24,0.35) 0%, rgba(10,4,24,0.05) 40%, transparent 70%)," +
            "radial-gradient(ellipse 55% 60% at 22% 50%, rgba(10,4,24,0.4) 0%, transparent 70%)",
        }}
      />

      {/* Content — layout & typography preserved */}
      <div className="container-wide relative w-full py-20 lg:py-24">
        <div className="max-w-md lg:max-w-xl" style={{ textAlign: "left" }}>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90"
            style={textStyle}
          >
            {t("tagline")}
          </p>
          <h1
            className="mt-6 text-4xl font-extrabold leading-[1.05] tracking-tight text-white md:text-5xl lg:text-[3.5rem] xl:text-6xl"
            style={textStyle}
          >
            {t("hero_title")}
          </h1>
          <p
            className="mt-6 max-w-md text-base leading-relaxed text-white/80 md:text-lg"
            style={textStyle}
          >
            {t("hero_subtitle")}
          </p>
          <div className="mt-10 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-start">
            <Button
              asChild
              size="lg"
              className="border-0 bg-gradient-to-r from-violet-600 to-fuchsia-500 px-7 text-white shadow-[0_0_32px_-4px_rgba(168,85,247,0.75)] hover:brightness-110 hover:shadow-[0_0_44px_-2px_rgba(168,85,247,0.9)]"
            >
              <Link href="/articles">{t("hero_cta_primary")}</Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-white/25 bg-white/5 px-6 text-white backdrop-blur-sm hover:border-white/40 hover:bg-white/10"
            >
              <Link href="/services" className="inline-flex items-center gap-2">
                <span>{t("hero_cta_secondary")}</span>
                <ArrowLeft className="h-4 w-4" aria-hidden />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
