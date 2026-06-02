"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Loader2, Send } from "lucide-react";

import { cn } from "@/lib/utils";

const FIELD_BASE =
  "w-full rounded-lg border border-white/15 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder:text-white/35 backdrop-blur transition focus:border-fuchsia-400/60 focus:bg-white/[0.07] focus:outline-none focus:ring-2 focus:ring-fuchsia-400/25";

const LABEL_BASE =
  "block text-[11px] font-semibold uppercase tracking-[0.18em] text-fuchsia-300/85";

export function ContactForm() {
  const t = useTranslations("contact");
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [state, setState] = React.useState<"idle" | "loading" | "ok" | "error">(
    "idle",
  );

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
      setName("");
      setEmail("");
      setMessage("");
    } catch {
      setState("error");
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur-xl md:p-8"
    >
      <div className="space-y-5">
        <div>
          <label className={LABEL_BASE} htmlFor="contact-name">
            {t("form_name")}
          </label>
          <input
            id="contact-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={cn(FIELD_BASE, "mt-2")}
          />
        </div>
        <div>
          <label className={LABEL_BASE} htmlFor="contact-email">
            {t("form_email")}
          </label>
          <input
            id="contact-email"
            type="email"
            required
            dir="auto"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={cn(FIELD_BASE, "mt-2")}
          />
        </div>
        <div>
          <label className={LABEL_BASE} htmlFor="contact-message">
            {t("form_message")}
          </label>
          <textarea
            id="contact-message"
            required
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className={cn(FIELD_BASE, "mt-2 resize-y")}
          />
        </div>
        <button
          type="submit"
          disabled={state === "loading"}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_0_28px_-6px_rgba(168,85,247,0.7)] transition hover:brightness-110 hover:shadow-[0_0_40px_-4px_rgba(168,85,247,0.85)] disabled:opacity-60"
        >
          {state === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4 rtl:rotate-180" />
          )}
          {t("form_submit")}
        </button>
        {state === "ok" && (
          <p className="rounded-md border border-emerald-400/30 bg-emerald-400/[0.08] px-3 py-2 text-sm text-emerald-300">
            {t("form_success")}
          </p>
        )}
        {state === "error" && (
          <p className="rounded-md border border-rose-400/30 bg-rose-400/[0.08] px-3 py-2 text-sm text-rose-300">
            {t("form_error")}
          </p>
        )}
      </div>
    </form>
  );
}
