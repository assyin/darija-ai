"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Menu, X } from "lucide-react";

import { Brand } from "@/components/public/brand";
import { NAV_LINKS, stripLocale } from "@/lib/nav";
import { cn } from "@/lib/utils";
import type { SiteSettings } from "@/lib/use-site-settings";

interface HeaderProps {
  settings: SiteSettings;
}

export function Header({ settings }: HeaderProps) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const current = stripLocale(pathname ?? "/");
  const [open, setOpen] = React.useState(false);
  const businessName = settings.business_name || "DarijaAI";

  const isActive = (href: string) =>
    href === "/" ? current === "/" : current === href || current.startsWith(`${href}/`);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-bg)]/85 backdrop-blur-md">
      <div className="container-wide flex h-16 items-center justify-between">
        <Link href="/" className="group flex items-baseline gap-0">
          <Brand name={businessName} />
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={isActive(l.href) ? "page" : undefined}
              className={cn(
                "text-sm font-medium transition-colors hover:text-[var(--color-primary)]",
                isActive(l.href) ? "text-[var(--color-primary)]" : "text-[var(--color-fg)]",
              )}
            >
              {t(l.key)}
            </Link>
          ))}
        </nav>

        <button
          type="button"
          onClick={() => setOpen(true)}
          className="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-md text-[var(--color-fg)] hover:bg-[var(--color-bg-elevated)]"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 bg-[var(--color-bg)] md:hidden">
          <div className="flex h-16 items-center justify-between px-6 border-b border-[var(--color-border)]">
            <Brand name={businessName} />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md hover:bg-[var(--color-bg-elevated)]"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex flex-col gap-1 p-6">
            {NAV_LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                aria-current={isActive(l.href) ? "page" : undefined}
                className={cn(
                  "rounded-md px-4 py-3 text-lg font-medium hover:bg-[var(--color-bg-elevated)]",
                  isActive(l.href) && "text-[var(--color-primary)]",
                )}
              >
                {t(l.key)}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
