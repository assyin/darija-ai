import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArticleCTA } from "@/components/public/article-cta";
import { getSiteSettings } from "@/lib/use-site-settings";

export default async function ServicesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("services");
  const settings = await getSiteSettings();

  const services = [1, 2, 3, 4].map((n) => ({
    title: t(`service_${n}_title`),
    desc: t(`service_${n}_desc`),
  }));

  return (
    <div className="container-wide py-16">
      <header className="mx-auto max-w-2xl text-center">
        <h1 dir="rtl" className="font-arabic-display text-4xl md:text-5xl">
          {t("page_title")}
        </h1>
        <p
          dir="rtl"
          className="font-arabic mt-4 text-lg text-[var(--color-muted-foreground)]"
        >
          {t("page_subtitle")}
        </p>
      </header>

      <div className="mt-16 grid gap-6 md:grid-cols-2">
        {services.map((s, i) => (
          <article
            key={i}
            dir="rtl"
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-8 transition-all hover:border-[var(--color-accent)] hover:shadow-md"
          >
            <h3 className="font-arabic-display text-xl">{s.title}</h3>
            <p className="font-arabic mt-3 text-[var(--color-muted-foreground)]">
              {s.desc}
            </p>
          </article>
        ))}
      </div>

      <div className="mx-auto mt-16 max-w-2xl">
        <ArticleCTA settings={settings} />
      </div>
    </div>
  );
}
