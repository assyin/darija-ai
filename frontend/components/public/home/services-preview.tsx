import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  GraduationCap,
  Lightbulb,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

/**
 * Strip leading emoji + space from a translated title.
 * Translations carry emojis (🌐, 🤖, etc.) for the admin/markdown surfaces;
 * on this premium glass UI we prefer the gradient Lucide icon instead.
 */
function stripLeadingEmoji(s: string): string {
  return s.replace(/^[\p{Extended_Pictographic}‍]+\s*/u, "");
}

/** Home services preview — 4 glass cards with gradient icons. */
export function ServicesPreview() {
  const t = useTranslations("services");
  const tHome = useTranslations("home");

  const items = [
    { Icon: Bot, title: t("service_1_title"), desc: t("service_1_desc") },
    { Icon: Workflow, title: t("service_2_title"), desc: t("service_2_desc") },
    {
      Icon: GraduationCap,
      title: t("service_3_title"),
      desc: t("service_3_desc"),
    },
    {
      Icon: Lightbulb,
      title: t("service_4_title"),
      desc: t("service_4_desc"),
    },
  ];

  return (
    <section className="container-wide">
      <div className="mb-12 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-300/90">
          {t("page_title")}
        </p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">
          {tHome("services_title")}
        </h2>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {items.map(({ Icon, title, desc }, i) => (
          <article
            key={i}
            className={cn(
              "group relative rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur-xl transition-all duration-300",
              "hover:-translate-y-1 hover:border-fuchsia-400/40 hover:bg-white/[0.07]",
              "hover:shadow-[0_24px_60px_-20px_rgba(168,85,247,0.4)]",
            )}
          >
            <span className="relative inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-[0_0_22px_-4px_rgba(168,85,247,0.6)] ring-1 ring-white/15">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-5 text-base font-semibold leading-snug text-white">
              {stripLeadingEmoji(title)}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-white/65">{desc}</p>
          </article>
        ))}
      </div>
      <div className="mt-10 text-center">
        <Link
          href="/services"
          className="inline-flex items-center gap-1.5 text-sm font-semibold"
        >
          <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            {t("page_title")}
          </span>
          <ArrowLeft
            className="h-3.5 w-3.5 text-fuchsia-300"
            aria-hidden
          />
        </Link>
      </div>
    </section>
  );
}
