import { getTranslations, setRequestLocale } from "next-intl/server";

import { getSiteSettings } from "@/lib/use-site-settings";

export default async function AboutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("about");
  const settings = await getSiteSettings();
  const ownerName = settings.business_owner_name;
  const ownerRole = settings.business_owner_role;

  return (
    <div className="container-narrow py-16">
      <header>
        <h1 dir="rtl" className="font-arabic-display text-4xl md:text-5xl">
          {t("page_title")}
        </h1>
        <p
          dir="rtl"
          className="font-arabic mt-4 text-lg text-[var(--color-muted-foreground)]"
        >
          {t("intro")}
        </p>
      </header>

      <section className="mt-12">
        <h2 dir="rtl" className="font-arabic-display text-2xl">
          {t("mission_title")}
        </h2>
        <p
          dir="rtl"
          className="font-arabic mt-4 text-base leading-relaxed text-[var(--color-fg)]/90"
        >
          {t("mission_text")}
        </p>
      </section>

      <section className="mt-12">
        <h2 dir="rtl" className="font-arabic-display text-2xl">
          {t("why_darija_title")}
        </h2>
        <p
          dir="rtl"
          className="font-arabic mt-4 text-base leading-relaxed text-[var(--color-fg)]/90"
        >
          {t("why_darija_text")}
        </p>
      </section>

      {ownerName && (
        <section className="mt-12 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6">
          <p
            dir="rtl"
            className="font-arabic text-sm uppercase tracking-wider text-[var(--color-muted)]"
          >
            {t("founder_intro")}
          </p>
          <p
            dir="rtl"
            className="font-arabic-display mt-2 text-2xl"
          >
            {ownerName}
          </p>
          {ownerRole && (
            <p
              dir="rtl"
              className="font-arabic mt-1 text-sm text-[var(--color-muted-foreground)]"
            >
              {ownerRole}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
