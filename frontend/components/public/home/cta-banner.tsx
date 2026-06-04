import Image from "next/image";
import { ArrowLeft } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { NewsletterSignup } from "@/components/public/newsletter-signup";
import { Button } from "@/components/ui/button";

/**
 * Closing CTA banner — full-bleed Marrakech-dawn asset (user-curated).
 * Composition mirrors the hero treatment: image as the entire scene,
 * minimal scrim on the start side for legibility, content overlaid.
 *
 * The newsletter signup is the primary CTA (audience building); a small
 * outline button links to /services for the commercial path.
 */
export function CtaBanner() {
  const tHome = useTranslations("home");
  const tServices = useTranslations("services");

  return (
    <section id="cta-banner" className="container-wide scroll-mt-24">
      <div
        dir="ltr"
        className="relative isolate flex min-h-[420px] items-center overflow-hidden rounded-3xl bg-[#0a0418] md:min-h-[480px] lg:min-h-[520px]"
      >
        {/* Scene */}
        <div aria-hidden className="absolute inset-0 -z-20">
          <Image
            src="/cta/dawn-medina.png"
            alt=""
            fill
            sizes="(min-width: 1280px) 1100px, 100vw"
            className="object-cover object-center"
          />
        </div>

        {/* Soft scrim only where the text lives — left side */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 60% 70% at 22% 50%, rgba(10,4,24,0.55) 0%, rgba(10,4,24,0.25) 45%, transparent 75%)," +
              "linear-gradient(to top, rgba(10,4,24,0.35) 0%, transparent 50%)",
          }}
        />

        {/* Content */}
        <div className="relative w-full px-8 py-12 md:px-12 md:py-14 lg:px-16 lg:py-16">
          <div className="max-w-md lg:max-w-lg" style={{ textAlign: "left" }}>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90"
              style={{ direction: "rtl", textAlign: "left" }}
            >
              {tHome("newsletter_title")}
            </p>
            <h2
              className="mt-4 text-3xl font-extrabold leading-[1.1] tracking-tight text-white md:text-4xl lg:text-5xl"
              style={{ direction: "rtl", textAlign: "left" }}
            >
              {tHome("newsletter_subtitle")}
            </h2>

            <div className="mt-7">
              <NewsletterSignup variant="dark" />
            </div>

            <div className="mt-6 flex items-center gap-3 text-sm text-white/70">
              <span className="hidden sm:inline">{tServices("cta_subtitle")}</span>
              <Button
                asChild
                size="sm"
                variant="outline"
                className="border-white/25 bg-white/5 text-white backdrop-blur-sm hover:border-white/40 hover:bg-white/10"
              >
                <Link
                  href="/services"
                  className="inline-flex items-center gap-2"
                >
                  <span>{tServices("cta_button")}</span>
                  <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
