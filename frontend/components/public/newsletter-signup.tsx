"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

export function NewsletterSignup() {
  const t = useTranslations("home");
  const [email, setEmail] = React.useState("");
  const [state, setState] = React.useState<"idle" | "loading" | "ok" | "error">("idle");

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

  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-widest text-[var(--color-muted)]">
        {t("newsletter_title")}
      </h4>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
        {t("newsletter_subtitle")}
      </p>
      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("newsletter_placeholder")}
          dir="auto"
          className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30"
        />
        <button
          type="submit"
          disabled={state === "loading"}
          className="inline-flex items-center justify-center rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--color-primary-dark)] hover:shadow-[var(--glow-primary)] disabled:opacity-60"
        >
          {state === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : t("newsletter_cta")}
        </button>
      </form>
      {state === "ok" && (
        <p className="mt-2 text-xs text-[var(--color-success)]">
          {t("newsletter_success")}
        </p>
      )}
      {state === "error" && (
        <p className="mt-2 text-xs text-[var(--color-danger)]">
          {t("newsletter_error")}
        </p>
      )}
    </div>
  );
}
