"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Brand } from "@/components/public/brand";
import { LogoMark } from "@/components/public/logo-mark";
import { Button } from "@/components/ui/button";
import { NAV_LINKS, stripLocale } from "@/lib/nav";
import { cn } from "@/lib/utils";
import type { SiteSettings } from "@/lib/use-site-settings";

interface HeaderProps {
  settings: SiteSettings;
}

// Default locale carries no URL prefix (per `i18n/routing.ts`).
function localePrefix(locale: string): string {
  return locale === "ar-MA" ? "" : `/${locale}`;
}

const LOCALE_SWITCHER: { id: "ar-MA" | "fr"; label: string }[] = [
  { id: "ar-MA", label: "عر" },
  { id: "fr", label: "FR" },
];

export function Header({ settings }: HeaderProps) {
  const t = useTranslations("nav");
  const tHome = useTranslations("home");
  const pathname = usePathname();
  const current = stripLocale(pathname ?? "/");
  const locale = useLocale();
  const [open, setOpen] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);
  const businessName = settings.business_name || "DarijaAI";

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const isActive = (href: string) =>
    href === "/"
      ? current === "/"
      : current === href || current.startsWith(`${href}/`);

  // Build a path in another locale preserving the current page.
  const pathFor = (target: string) =>
    `${localePrefix(target)}${current === "/" ? "" : current}` || "/";

  // The primary CTA scrolls to the home page's newsletter banner,
  // staying in the active locale.
  const ctaHref = `${localePrefix(locale)}/#cta-banner`;

  return (
    <header
      className={cn(
        "sticky top-0 z-40 transition-all duration-300",
        scrolled
          ? "border-b border-white/10 bg-[#0a0418]/85 backdrop-blur-xl"
          : "border-b border-transparent bg-[#0a0418]/25 backdrop-blur-md",
      )}
    >
      <div className="container-wide flex h-16 items-center justify-between gap-4 lg:h-[72px]">
        {/* Logo — mark + wordmark */}
        <Link
          href={`${localePrefix(locale)}/` || "/"}
          className="group inline-flex items-center gap-2.5 shrink-0"
        >
          <LogoMark size={36} priority />
          <Brand name={businessName} className="text-base lg:text-lg" />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={isActive(l.href) ? "page" : undefined}
              className={cn(
                "relative text-sm font-medium transition-colors",
                isActive(l.href)
                  ? "text-white"
                  : "text-white/65 hover:text-white",
              )}
            >
              {t(l.key)}
              {isActive(l.href) && (
                <span
                  aria-hidden
                  className="absolute inset-x-0 -bottom-2 h-0.5 rounded-full bg-gradient-to-r from-violet-400 to-fuchsia-400"
                />
              )}
            </Link>
          ))}
        </nav>

        {/* Right side — language switcher + CTA */}
        <div className="hidden items-center gap-3 md:flex">
          <div
            role="group"
            aria-label="Language"
            className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 p-0.5 backdrop-blur"
          >
            {LOCALE_SWITCHER.map((opt) => {
              const isCur =
                opt.id === locale || (opt.id === "ar-MA" && locale === "ar");
              return (
                <Link
                  key={opt.id}
                  href={pathFor(opt.id)}
                  className={cn(
                    "rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition",
                    isCur
                      ? "bg-white/15 text-white"
                      : "text-white/60 hover:text-white",
                  )}
                >
                  {opt.label}
                </Link>
              );
            })}
          </div>

          <Button
            asChild
            size="sm"
            className="border-0 bg-gradient-to-r from-violet-600 to-fuchsia-500 px-4 text-white shadow-[0_0_20px_-4px_rgba(168,85,247,0.65)] hover:brightness-110"
          >
            <Link href={ctaHref}>{tHome("newsletter_cta")}</Link>
          </Button>
        </div>

        {/* Mobile hamburger */}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md text-white hover:bg-white/10 md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {/* Mobile menu — fullscreen glass */}
      {open && (
        <div className="fixed inset-0 z-50 bg-[#0a0418]/95 backdrop-blur-xl md:hidden">

          <div className="container-wide flex h-16 items-center justify-between">
            <Link
              href={`${localePrefix(locale)}/` || "/"}
              className="inline-flex items-center gap-2.5"
              onClick={() => setOpen(false)}
            >
              <LogoMark size={32} />
              <Brand name={businessName} className="text-base" />
            </Link>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md text-white hover:bg-white/10"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex flex-col gap-1.5 px-6 pt-6">
            {NAV_LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                aria-current={isActive(l.href) ? "page" : undefined}
                className={cn(
                  "rounded-xl px-5 py-4 text-lg font-semibold transition",
                  isActive(l.href)
                    ? "bg-white/10 text-white"
                    : "text-white/75 hover:bg-white/5 hover:text-white",
                )}
              >
                {t(l.key)}
              </Link>
            ))}
          </nav>
          <div className="mt-8 flex flex-col gap-4 px-6">
            <div
              role="group"
              aria-label="Language"
              className="flex items-center justify-center gap-1 self-center rounded-full border border-white/10 bg-white/5 p-0.5 backdrop-blur"
            >
              {LOCALE_SWITCHER.map((opt) => {
                const isCur =
                  opt.id === locale || (opt.id === "ar-MA" && locale === "ar");
                return (
                  <Link
                    key={opt.id}
                    href={pathFor(opt.id)}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition",
                      isCur
                        ? "bg-white/15 text-white"
                        : "text-white/60",
                    )}
                  >
                    {opt.label}
                  </Link>
                );
              })}
            </div>
            <Button
              asChild
              size="lg"
              className="w-full border-0 bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white shadow-[0_0_24px_-4px_rgba(168,85,247,0.65)]"
            >
              <Link href={ctaHref} onClick={() => setOpen(false)}>
                {tHome("newsletter_cta")}
              </Link>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}

