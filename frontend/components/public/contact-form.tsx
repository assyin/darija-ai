"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

export function ContactForm() {
  const t = useTranslations("contact");
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [state, setState] = React.useState<"idle" | "loading" | "ok" | "error">("idle");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setState("loading");
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, email, message }),
      });
      if (!res.ok) throw new Error("failed");
      setState("ok");
      setName(""); setEmail(""); setMessage("");
    } catch {
      setState("error");
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6"
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium">{t("form_name")}</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-fg)] focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30"
          />
        </div>
        <div>
          <label className="block text-sm font-medium">{t("form_email")}</label>
          <input
            type="email"
            required
            dir="auto"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-fg)] focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30"
          />
        </div>
        <div>
          <label className="block text-sm font-medium">{t("form_message")}</label>
          <textarea
            required
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-fg)] focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30"
          />
        </div>
        <button
          type="submit"
          disabled={state === "loading"}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white transition-all hover:bg-[var(--color-primary-dark)] hover:shadow-[var(--glow-primary)] disabled:opacity-60"
        >
          {state === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {t("form_submit")}
        </button>
        {state === "ok" && (
          <p className="text-sm text-[var(--color-success)]">{t("form_success")}</p>
        )}
        {state === "error" && (
          <p className="text-sm text-[var(--color-danger)]">{t("form_error")}</p>
        )}
      </div>
    </form>
  );
}
