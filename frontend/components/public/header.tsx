"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SiteSettings } from "@/lib/use-site-settings";

interface HeaderProps {
  settings: SiteSettings;
}

export function Header({ settings }: HeaderProps) {
  const t = useTranslations("nav");
  const [open, setOpen] = React.useState(false);
  const businessName = settings.business_name || "DarijaAI";

  const links = [
    { href: "/", label: t("home") },
    { href: "/articles", label: t("articles") },
    { href: "/services", label: t("services") },
    { href: "/about", label: t("about") },
    { href: "/contact", label: t("contact") },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-bg)]/85 backdrop-blur-md">
      <div className="container-wide flex h-16 items-center justify-between">
        <Link href="/" className="group flex items-baseline gap-0">
          <Logo name={businessName} />
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm font-medium text-[var(--color-fg)] transition-colors hover:text-[var(--color-primary)]"
            >
              {l.label}
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
            <Logo name={businessName} />
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
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-4 py-3 text-lg font-medium hover:bg-[var(--color-bg-elevated)]"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}

/**
 * Typographic logo. Renders the business name with a subtle accent
 * on the first character, and primary color on the "AI" suffix when present.
 */
function Logo({ name, className }: { name: string; className?: string }) {
  const aiMatch = /AI$/i.test(name);
  const head = aiMatch ? name.slice(0, -2) : name;
  const tail = aiMatch ? name.slice(-2) : "";
  const firstChar = head.charAt(0);
  const restHead = head.slice(1);

  return (
    <span className={cn("font-display text-xl tracking-tight", className)}>
      <span className="text-[var(--color-accent)]">{firstChar}</span>
      <span className="text-[var(--color-fg)]">{restHead}</span>
      {tail && <span className="text-[var(--color-primary)]">{tail}</span>}
    </span>
  );
}
