import Link from "next/link";
import { Bot } from "lucide-react";
import { useTranslations } from "next-intl";

import { NewsletterSignup } from "@/components/public/newsletter-signup";
import { Button } from "@/components/ui/button";

/**
 * Gradient CTA banner (services-oriented) + reused Newsletter block.
 * The mascot is a placeholder icon until a bespoke asset is generated.
 * Gradient reads --gradient-cta (cooler in FR, warmer in AR).
 */
export function CtaBanner() {
  const t = useTranslations("services");

  return (
    <section className="container-wide">
      <div
        className="relative overflow-hidden rounded-3xl p-8 md:p-12"
        style={{ background: "var(--gradient-cta)" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -end-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl"
        />
        <div className="relative grid items-center gap-8 md:grid-cols-[1fr_auto]">
          <div className="text-center text-white md:text-start">
            <h2 className="text-2xl font-bold tracking-tight md:text-3xl">{t("cta_title")}</h2>
            <p className="mt-3 max-w-xl text-white/85">{t("cta_subtitle")}</p>
            <div className="mt-6 flex justify-center md:justify-start">
              <Button
                asChild
                size="lg"
                className="bg-white text-[var(--color-primary)] hover:bg-white/90 hover:shadow-none"
              >
                <Link href="/contact">{t("cta_button")}</Link>
              </Button>
            </div>
          </div>

          <div
            aria-hidden
            className="hidden h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-white/10 backdrop-blur md:flex"
          >
            <Bot className="h-14 w-14 text-white" />
          </div>
        </div>
      </div>

      <div className="mx-auto mt-10 max-w-xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6">
        <NewsletterSignup />
      </div>
    </section>
  );
}
