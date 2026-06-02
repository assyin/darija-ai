import { FileText, Globe2, RefreshCw, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Glassmorphism stat strip — sits below the hero and overlaps it slightly so
 * the card appears to float over the cinematic scene. Values are real product
 * facts (not vanity metrics): live article count + language + cadence + free.
 */
export function StatStrip({ articlesCount }: { articlesCount: number }) {
  const t = useTranslations("home");

  const stats = [
    {
      value: `+${articlesCount}`,
      label: t("stats.articles_label"),
      Icon: FileText,
    },
    { value: t("stats.lang_value"), label: t("stats.lang_label"), Icon: Globe2 },
    {
      value: t("stats.freq_value"),
      label: t("stats.freq_label"),
      Icon: RefreshCw,
    },
    { value: t("stats.free_value"), label: t("stats.free_label"), Icon: Sparkles },
  ];

  return (
    <section className="container-wide -mt-12 md:-mt-16 lg:-mt-20">
      <div
        className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl md:grid-cols-4"
        style={{
          boxShadow:
            "0 24px 80px -20px rgba(13,5,31,0.6), inset 0 1px 0 rgba(255,255,255,0.06)",
        }}
      >
        {stats.map((s, i) => (
          <div
            key={i}
            className="flex items-center justify-center gap-3 bg-[#0d051f]/40 px-6 py-5 md:py-6"
          >
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/25 to-fuchsia-500/15 text-fuchsia-300 ring-1 ring-white/10">
              <s.Icon className="h-4 w-4" aria-hidden />
            </span>
            <div className="text-start leading-tight">
              <div className="text-xl font-bold text-white md:text-2xl">
                {s.value}
              </div>
              <div className="text-[11px] uppercase tracking-wider text-white/55 md:text-xs">
                {s.label}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
