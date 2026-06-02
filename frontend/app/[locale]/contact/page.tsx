import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ContactDirect } from "@/components/public/contact-direct";
import { ContactForm } from "@/components/public/contact-form";
import { getSiteSettings } from "@/lib/use-site-settings";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "contact" });
  return {
    title: t("page_title"),
    description: t("page_subtitle"),
    alternates: { canonical: `${SITE_BASE}/contact` },
  };
}

export default async function ContactPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("contact");
  const settings = await getSiteSettings();

  return (
    <div className="relative isolate">
      {/* Ambient top glow — matches About/Hero */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-fuchsia-500/10 via-violet-500/5 to-transparent"
      />

      <div className="container-wide py-20 md:py-24">
        {/* Hero */}
        <header className="mx-auto max-w-2xl text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90">
            ● {t("page_title")}
          </p>
          <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-white md:text-5xl">
            {t("page_subtitle")}
          </h1>
        </header>

        {/* Two-column: form + direct channels */}
        <div className="mt-14 grid gap-8 md:mt-16 lg:grid-cols-[1fr_360px] lg:gap-10">
          <ContactForm />
          <ContactDirect settings={settings} />
        </div>
      </div>
    </div>
  );
}
