import { Quote } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Social proof section.
 * NOTE: the 3 entries are PLACEHOLDERS (in messages/*.json under
 * home.testimonials) — replace with real testimonials before public launch.
 * Avatars are initials only (no fabricated photos).
 */
export function Testimonials() {
  const t = useTranslations("home");

  const items = [1, 2, 3].map((n) => ({
    quote: t(`testimonials.t${n}_quote`),
    name: t(`testimonials.t${n}_name`),
    role: t(`testimonials.t${n}_role`),
  }));

  return (
    <section className="container-wide">
      <h2 className="mb-10 text-center text-3xl font-bold tracking-tight md:text-4xl">
        {t("testimonials_title")}
      </h2>
      <div className="grid gap-5 md:grid-cols-3">
        {items.map((it, i) => (
          <figure
            key={i}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 shadow-[var(--shadow-card)]"
          >
            <Quote className="h-6 w-6 text-[var(--color-primary)]/60" />
            <blockquote className="mt-3 text-sm leading-relaxed text-[var(--color-fg)]">
              {it.quote}
            </blockquote>
            <figcaption className="mt-4 flex items-center gap-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-primary)]/15 text-sm font-bold text-[var(--color-primary)]">
                {it.name.charAt(0)}
              </span>
              <span>
                <span className="block text-sm font-semibold">{it.name}</span>
                <span className="block text-xs text-[var(--color-muted-foreground)]">
                  {it.role}
                </span>
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
