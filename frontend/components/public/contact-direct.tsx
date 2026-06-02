import { Calendar, Mail, MessageCircle } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { cleanPhone, type SiteSettings } from "@/lib/use-site-settings";
import { cn } from "@/lib/utils";

interface ContactDirectProps {
  settings: SiteSettings;
}

/**
 * Direct contact channels (WhatsApp / Email / Calendly). Each card has its
 * own accent color and gradient icon — provides a clear alternative to the
 * form for users who already know what they want.
 *
 * Server component — `getTranslations` is used directly; no client state
 * needed here.
 */
export async function ContactDirect({ settings }: ContactDirectProps) {
  const t = await getTranslations("contact");
  const whatsapp = settings.contact_whatsapp;
  const whatsappClean = cleanPhone(whatsapp);
  const email = settings.contact_email;
  const calendly = settings.calendly_url;

  const channels: {
    href: string;
    label: string;
    sub: string;
    Icon: typeof Mail;
    accent: string;
    glow: string;
    ringHover: string;
    external?: boolean;
  }[] = [];

  if (whatsappClean) {
    channels.push({
      href: `https://wa.me/${whatsappClean}`,
      label: t("via_whatsapp"),
      sub: whatsapp,
      Icon: MessageCircle,
      accent: "from-emerald-500 to-teal-500",
      glow: "shadow-[0_0_24px_-6px_rgba(16,185,129,0.6)]",
      ringHover: "hover:border-emerald-400/40",
      external: true,
    });
  }
  if (email) {
    channels.push({
      href: `mailto:${email}`,
      label: t("via_email"),
      sub: email,
      Icon: Mail,
      accent: "from-violet-500 to-indigo-500",
      glow: "shadow-[0_0_24px_-6px_rgba(139,92,246,0.6)]",
      ringHover: "hover:border-violet-400/40",
    });
  }
  if (calendly) {
    channels.push({
      href: calendly,
      label: t("via_calendly"),
      sub: calendly.replace(/^https?:\/\//, ""),
      Icon: Calendar,
      accent: "from-fuchsia-500 to-pink-500",
      glow: "shadow-[0_0_24px_-6px_rgba(217,70,239,0.6)]",
      ringHover: "hover:border-fuchsia-400/40",
      external: true,
    });
  }

  if (channels.length === 0) return null;

  return (
    <aside className="space-y-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-fuchsia-300/85">
        {t("or_directly")}
      </p>
      {channels.map(({ href, label, sub, Icon, accent, glow, ringHover, external }) => (
        <a
          key={label}
          href={href}
          {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
          className={cn(
            "group flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl transition-all duration-300 hover:-translate-y-0.5 hover:bg-white/[0.07]",
            ringHover,
          )}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white">{label}</p>
            <p
              dir="ltr"
              className="mt-0.5 truncate text-xs text-white/55"
            >
              {sub}
            </p>
          </div>
          <span
            className={cn(
              "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white ring-1 ring-white/15 transition-transform group-hover:scale-105",
              accent,
              glow,
            )}
          >
            <Icon className="h-5 w-5" aria-hidden />
          </span>
        </a>
      ))}
    </aside>
  );
}
