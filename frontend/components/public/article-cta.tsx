"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Calendar, Mail, MessageCircle } from "lucide-react";

import {
  cleanPhone,
  renderTemplate,
  type SiteSettings,
} from "@/lib/use-site-settings";

interface ArticleCTAProps {
  settings: SiteSettings;
}

/**
 * Renders the editorial CTA at the end of articles. Pulls the markdown
 * template from settings.cta_template_darija and substitutes
 * {{placeholders}} with values from the public site_settings.
 *
 * If neither WhatsApp nor email are set, the CTA card is hidden entirely.
 */
export function ArticleCTA({ settings }: ArticleCTAProps) {
  const template = settings.cta_template_darija;
  const whatsapp = settings.contact_whatsapp;
  const whatsappClean = cleanPhone(whatsapp);
  const email = settings.contact_email;
  const calendly = settings.calendly_url;

  if (!template || (!whatsapp && !email)) return null;

  const rendered = renderTemplate(template, settings);

  return (
    <aside
      className="my-16 rounded-xl border-2 border-[var(--color-accent)] bg-[var(--color-bg-elevated)] p-8 shadow-sm"
      dir="rtl"
    >
      <div className="prose-rtl max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{rendered}</ReactMarkdown>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        {whatsappClean && (
          <a
            href={`https://wa.me/${whatsappClean}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-700"
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
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-primary-dark)]"
          >
            <Calendar className="h-4 w-4" />
            Calendly
          </a>
        )}
        {email && (
          <a
            href={`mailto:${email}`}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-md border border-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/5"
          >
            <Mail className="h-4 w-4" />
            Email
          </a>
        )}
      </div>
    </aside>
  );
}
