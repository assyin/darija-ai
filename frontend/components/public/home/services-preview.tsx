import Link from "next/link";
import { Bot, GraduationCap, Lightbulb, Workflow } from "lucide-react";
import { useTranslations } from "next-intl";

/** Home services preview — 4 amber-iconed cards from the `services` namespace. */
export function ServicesPreview() {
  const t = useTranslations("services");
  const tHome = useTranslations("home");

  const items = [
    { icon: Bot, title: t("service_1_title"), desc: t("service_1_desc") },
    { icon: Workflow, title: t("service_2_title"), desc: t("service_2_desc") },
    { icon: GraduationCap, title: t("service_3_title"), desc: t("service_3_desc") },
    { icon: Lightbulb, title: t("service_4_title"), desc: t("service_4_desc") },
  ];

  return (
    <section className="container-wide">
      <h2 className="mb-10 text-center text-3xl font-bold tracking-tight md:text-4xl">
        {tHome("services_title")}
      </h2>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {items.map(({ icon: Icon, title, desc }, i) => (
          <div
            key={i}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 transition-all hover:-translate-y-1 hover:border-[var(--color-primary)]/40 hover:shadow-[var(--shadow-card)]"
          >
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--color-accent)]/15 text-[var(--color-accent)]">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 text-base font-semibold">{title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
              {desc}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-8 text-center">
        <Link
          href="/services"
          className="text-sm font-medium text-[var(--color-primary)] hover:underline"
        >
          {t("page_title")} →
        </Link>
      </div>
    </section>
  );
}
