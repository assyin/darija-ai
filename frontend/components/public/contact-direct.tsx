"use client";

import { useTranslations } from "next-intl";
import { Calendar, Mail, MessageCircle } from "lucide-react";

import { cleanPhone, type SiteSettings } from "@/lib/use-site-settings";

interface ContactDirectProps {
  settings: SiteSettings;
}

export function ContactDirect({ settings }: ContactDirectProps) {
  const t = useTranslations("contact");
  const whatsapp = settings.contact_whatsapp;
  const whatsappClean = cleanPhone(whatsapp);
  const email = settings.contact_email;
  const calendly = settings.calendly_url;

  return (
    <aside dir="rtl" className="space-y-3">
      <p className="font-arabic text-sm font-medium uppercase tracking-wider text-[var(--color-muted)]">
        {t("or_directly")}
      </p>
      {whatsappClean && (
        <a
          href={`https://wa.me/${whatsappClean}`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4 transition-all hover:border-emerald-600 hover:shadow-sm"
        >
          <div>
            <p className="font-arabic font-semibold">{t("via_whatsapp")}</p>
            <p
              dir="ltr"
              className="text-sm text-[var(--color-muted-foreground)]"
            >
              {whatsapp}
            </p>
          </div>
          <MessageCircle className="h-5 w-5 text-emerald-600" />
        </a>
      )}
      {email && (
        <a
          href={`mailto:${email}`}
          className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4 transition-all hover:border-[var(--color-primary)] hover:shadow-sm"
        >
          <div>
            <p className="font-arabic font-semibold">{t("via_email")}</p>
            <p dir="ltr" className="text-sm text-[var(--color-muted-foreground)]">
              {email}
            </p>
          </div>
          <Mail className="h-5 w-5 text-[var(--color-primary)]" />
        </a>
      )}
      {calendly && (
        <a
          href={calendly}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4 transition-all hover:border-[var(--color-accent)] hover:shadow-sm"
        >
          <div>
            <p className="font-arabic font-semibold">{t("via_calendly")}</p>
            <p
              dir="ltr"
              className="truncate text-sm text-[var(--color-muted-foreground)]"
            >
              {calendly.replace(/^https?:\/\//, "")}
            </p>
          </div>
          <Calendar className="h-5 w-5 text-[var(--color-accent)]" />
        </a>
      )}
    </aside>
  );
}
