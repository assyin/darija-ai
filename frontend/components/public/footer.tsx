import Link from "next/link";
import { useTranslations } from "next-intl";

import { NewsletterSignup } from "@/components/public/newsletter-signup";
import {
  InstagramIcon,
  LinkedinIcon,
  TiktokIcon,
  XIcon,
} from "@/components/public/social-icons";
import type { SiteSettings } from "@/lib/use-site-settings";

interface FooterProps {
  settings: SiteSettings;
}

export function Footer({ settings }: FooterProps) {
  const t = useTranslations("footer");
  const tNav = useTranslations("nav");
  const businessName = settings.business_name || "DarijaAI";
  const tagline = settings.business_tagline_darija || "";
  const year = new Date().getFullYear();

  const socials = [
    { url: settings.linkedin_url, icon: LinkedinIcon, label: "LinkedIn" },
    { url: settings.twitter_url, icon: XIcon, label: "X" },
    { url: settings.instagram_url, icon: InstagramIcon, label: "Instagram" },
    { url: settings.tiktok_url, icon: TiktokIcon, label: "TikTok" },
  ].filter((s) => s.url && s.url.trim().length > 0);

  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
      <div className="container-wide py-12">
        <div className="grid gap-10 md:grid-cols-4">
          <section className="md:col-span-1">
            <p className="font-display text-lg">{businessName}</p>
            {tagline && (
              <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
                {tagline}
              </p>
            )}
          </section>

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-[var(--color-muted)]">
              {t("links_title")}
            </h4>
            <ul className="mt-4 space-y-2 text-sm">
              <li><Link href="/" className="hover:text-[var(--color-primary)]">{tNav("home")}</Link></li>
              <li><Link href="/articles" className="hover:text-[var(--color-primary)]">{tNav("articles")}</Link></li>
              <li><Link href="/services" className="hover:text-[var(--color-primary)]">{tNav("services")}</Link></li>
              <li><Link href="/about" className="hover:text-[var(--color-primary)]">{tNav("about")}</Link></li>
              <li><Link href="/contact" className="hover:text-[var(--color-primary)]">{tNav("contact")}</Link></li>
            </ul>
          </section>

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-[var(--color-muted)]">
              {t("follow_title")}
            </h4>
            {socials.length > 0 ? (
              <ul className="mt-4 flex gap-3">
                {socials.map(({ url, icon: Icon, label }) => (
                  <li key={label}>
                    <a
                      href={url ?? "#"}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={label}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-fg)] transition-colors hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]"
                    >
                      <Icon className="h-4 w-4" />
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-[var(--color-muted-foreground)]">—</p>
            )}
          </section>

          <section>
            <NewsletterSignup />
          </section>
        </div>

        <div className="zellige-divider" aria-hidden="true" />

        <div className="flex flex-col items-center justify-between gap-3 text-sm text-[var(--color-muted-foreground)] md:flex-row">
          <p>{t("rights", { year, name: businessName })}</p>
          <p className="font-arabic">{t("made_with")}</p>
        </div>
      </div>
    </footer>
  );
}
