import { useTranslations } from "next-intl";

import { Brand } from "@/components/public/brand";
import { Link } from "@/i18n/navigation";
import { LogoMark } from "@/components/public/logo-mark";
import { NewsletterSignup } from "@/components/public/newsletter-signup";
import {
  InstagramIcon,
  LinkedinIcon,
  TiktokIcon,
  XIcon,
} from "@/components/public/social-icons";
import { NAV_LINKS } from "@/lib/nav";
import type { SiteSettings } from "@/lib/use-site-settings";

interface FooterProps {
  settings: SiteSettings;
}

/** Public site footer — dark glass aesthetic that closes the page on the same
 *  visual key as the hero / CTA / cards. Subtle inset top glow ties it back
 *  to the brand palette. */
export function Footer({ settings }: FooterProps) {
  const t = useTranslations("footer");
  const tHome = useTranslations("home");
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
    <footer className="relative isolate border-t border-white/10 bg-[#0a0418] text-white">
      {/* Subtle top gradient — echoes the CTA glow without bleeding into content */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-fuchsia-400/40 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-40 bg-gradient-to-b from-fuchsia-500/[0.06] to-transparent"
      />

      <div className="container-wide py-14">
        <div className="grid gap-12 md:grid-cols-4 md:gap-8">
          <section className="md:col-span-1">
            <div className="flex items-center gap-2.5">
              <LogoMark size={32} />
              <Brand name={businessName} className="text-lg" />
            </div>
            {tagline && (
              <p className="mt-3 text-sm leading-relaxed text-white/60">
                {tagline}
              </p>
            )}
          </section>

          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-fuchsia-300/80">
              {t("links_title")}
            </h4>
            <ul className="mt-4 space-y-2.5 text-sm">
              {NAV_LINKS.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className="text-white/65 transition-colors hover:text-white"
                  >
                    {tNav(l.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-fuchsia-300/80">
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
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/75 backdrop-blur transition-colors hover:border-fuchsia-400/50 hover:bg-white/10 hover:text-white"
                    >
                      <Icon className="h-4 w-4" />
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-white/40">—</p>
            )}
          </section>

          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-fuchsia-300/80">
              {tHome("newsletter_title")}
            </h4>
            <p className="mt-2 text-sm text-white/60">
              {tHome("newsletter_subtitle")}
            </p>
            <div className="mt-4">
              <NewsletterSignup variant="dark" />
            </div>
          </section>
        </div>

        <div
          aria-hidden
          className="mt-12 h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent"
        />

        <div className="mt-6 flex flex-col items-center justify-between gap-3 text-xs text-white/50 md:flex-row">
          <p>{t("rights", { year, name: businessName })}</p>
          <p className="font-arabic">{t("made_with")}</p>
        </div>
      </div>
    </footer>
  );
}
