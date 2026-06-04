import type { Metadata } from "next";
import {
  ArrowLeft,
  Bot,
  Calendar,
  GraduationCap,
  Lightbulb,
  Mail,
  MessageCircle,
  Workflow,
} from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { cleanPhone, getSiteSettings } from "@/lib/use-site-settings";
import { cn } from "@/lib/utils";

const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

function stripLeadingEmoji(s: string): string {
  return s.replace(/^[\p{Extended_Pictographic}‍]+\s*/u, "");
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "services" });
  return {
    title: t("page_title"),
    description: t("page_subtitle"),
    alternates: { canonical: `${SITE_BASE}/services` },
  };
}

const SERVICE_ICONS = [Bot, Workflow, GraduationCap, Lightbulb] as const;

export default async function ServicesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("services");
  const settings = await getSiteSettings();

  const services = SERVICE_ICONS.map((Icon, i) => ({
    Icon,
    title: stripLeadingEmoji(t(`service_${i + 1}_title`)),
    desc: t(`service_${i + 1}_desc`),
  }));

  const whatsapp = settings.contact_whatsapp;
  const whatsappClean = cleanPhone(whatsapp);
  const email = settings.contact_email;
  const calendly = settings.calendly_url;

  return (
    <div className="container-wide py-16 md:py-24">
      {/* Compact hero — no full-bleed asset; gradient text + accent dot */}
      <header className="mx-auto max-w-3xl text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/90">
          ● {t("page_title")}
        </p>
        <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-white md:text-5xl lg:text-[3.25rem]">
          {t("page_subtitle")}
        </h1>
      </header>

      {/* Services grid — glass cards */}
      <div className="mt-16 grid gap-6 md:grid-cols-2">
        {services.map(({ Icon, title, desc }, i) => (
          <article
            key={i}
            className={cn(
              "group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] p-8 backdrop-blur-xl transition-all duration-300",
              "hover:-translate-y-1 hover:border-fuchsia-400/40 hover:bg-white/[0.07]",
              "hover:shadow-[0_28px_70px_-22px_rgba(168,85,247,0.45)]",
            )}
          >
            {/* Decorative top-right glow */}
            <span
              aria-hidden
              className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-fuchsia-500/15 blur-3xl"
            />
            <span className="relative inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-[0_0_28px_-4px_rgba(168,85,247,0.7)] ring-1 ring-white/15">
              <Icon className="h-6 w-6" />
            </span>
            <h3 className="mt-6 text-xl font-bold tracking-tight text-white">
              {title}
            </h3>
            <p className="mt-3 leading-relaxed text-white/70">{desc}</p>
          </article>
        ))}
      </div>

      {/* CTA — services-specific (Contact, not newsletter) */}
      <section className="mt-20">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-violet-900/40 via-[#1a0f3b]/60 to-fuchsia-900/40 p-8 backdrop-blur-xl md:p-12">
          <span
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-fuchsia-500/20 blur-3xl"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute -left-20 -bottom-20 h-64 w-64 rounded-full bg-violet-500/20 blur-3xl"
          />
          <div className="relative mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
              {t("cta_title")}
            </h2>
            <p className="mt-3 text-white/75 md:text-lg">{t("cta_subtitle")}</p>
            <div className="mt-7 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
              {whatsappClean && (
                <a
                  href={`https://wa.me/${whatsappClean}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_0_24px_-6px_rgba(16,185,129,0.6)] transition hover:brightness-110"
                >
                  <MessageCircle className="h-4 w-4" />
                  WhatsApp
                </a>
              )}
              {calendly && (
                <a
                  href={calendly}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_0_24px_-6px_rgba(168,85,247,0.7)] transition hover:brightness-110"
                >
                  <Calendar className="h-4 w-4" />
                  {t("cta_button")}
                </a>
              )}
              {email && (
                <a
                  href={`mailto:${email}`}
                  className="inline-flex items-center justify-center gap-2 rounded-md border border-white/25 bg-white/5 px-5 py-3 text-sm font-semibold text-white backdrop-blur-sm transition hover:border-white/40 hover:bg-white/10"
                >
                  <Mail className="h-4 w-4" />
                  Email
                </a>
              )}
              {!whatsappClean && !calendly && !email && (
                <Link
                  href="/contact"
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_0_24px_-6px_rgba(168,85,247,0.7)] transition hover:brightness-110"
                >
                  {t("cta_button")}
                  <ArrowLeft className="h-4 w-4" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
