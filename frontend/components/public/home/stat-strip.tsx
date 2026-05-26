import { useTranslations } from "next-intl";

/**
 * Truthful product stats (NOT fabricated vanity metrics): real published
 * article count + honest product facts (language, cadence, free).
 */
export function StatStrip({ articlesCount }: { articlesCount: number }) {
  const t = useTranslations("home");

  const stats = [
    { value: `+${articlesCount}`, label: t("stats.articles_label") },
    { value: t("stats.lang_value"), label: t("stats.lang_label") },
    { value: t("stats.freq_value"), label: t("stats.freq_label") },
    { value: t("stats.free_value"), label: t("stats.free_label") },
  ];

  return (
    <section className="container-wide">
      <div className="grid grid-cols-2 gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 md:grid-cols-4 md:gap-6">
        {stats.map((s, i) => (
          <div key={i} className="text-center">
            <div className="text-2xl font-bold text-[var(--color-primary)] md:text-3xl">
              {s.value}
            </div>
            <div className="mt-1 text-sm text-[var(--color-muted-foreground)]">{s.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
