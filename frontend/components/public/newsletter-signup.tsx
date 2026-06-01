"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type Variant = "default" | "dark";

/**
 * Newsletter signup form. Two visual variants:
 *   - "default" — small heading + light input, used in the footer.
 *   - "dark"    — no internal heading (caller renders its own big H2),
 *                  glassy input on dark backgrounds (e.g. CTA banner).
 *
 * Both POST to `/api/newsletter` and share the same client state machine.
 */
export function NewsletterSignup({
  variant = "default",
}: {
  variant?: Variant;
}) {
  const t = useTranslations("home");
  const [email, setEmail] = React.useState("");
  const [state, setState] = React.useState<"idle" | "loading" | "ok" | "error">(
    "idle",
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setState("loading");
    try {
      const res = await fetch("/api/newsletter", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error("failed");
      setState("ok");
      setEmail("");
    } catch {
      setState("error");
    }
  }

  const isDark = variant === "dark";

  return (
    <div>
      {!isDark && (
        <>
          <h4 className="text-xs font-semibold uppercase tracking-widest text-[var(--color-muted)]">
            {t("newsletter_title")}
          </h4>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
            {t("newsletter_subtitle")}
          </p>
        </>
      )}
      <form
        onSubmit={onSubmit}
        className={cn("flex gap-2", isDark ? "mt-0" : "mt-4")}
      >
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("newsletter_placeholder")}
          dir="auto"
          className={cn(
            "flex-1 rounded-md px-3 py-2 text-sm transition focus:outline-none focus:ring-2",
            isDark
              ? "border border-white/15 bg-white/10 text-white placeholder:text-white/50 backdrop-blur focus:border-fuchsia-400/60 focus:ring-fuchsia-400/30"
              : "border border-[var(--color-border)] bg-[var(--color-bg)] focus:border-[var(--color-primary)] focus:ring-[var(--color-primary)]/30",
          )}
        />
        <button
          type="submit"
          disabled={state === "loading"}
          className={cn(
            "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-all disabled:opacity-60",
            isDark
              ? "bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white shadow-[0_0_24px_-6px_rgba(168,85,247,0.7)] hover:brightness-110"
              : "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-dark)] hover:shadow-[var(--glow-primary)]",
          )}
        >
          {state === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            t("newsletter_cta")
          )}
        </button>
      </form>
      {state === "ok" && (
        <p
          className={cn(
            "mt-2 text-xs",
            isDark ? "text-emerald-300" : "text-[var(--color-success)]",
          )}
        >
          {t("newsletter_success")}
        </p>
      )}
      {state === "error" && (
        <p
          className={cn(
            "mt-2 text-xs",
            isDark ? "text-rose-300" : "text-[var(--color-danger)]",
          )}
        >
          {t("newsletter_error")}
        </p>
      )}
    </div>
  );
}
