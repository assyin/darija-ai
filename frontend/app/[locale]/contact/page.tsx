import { getTranslations, setRequestLocale } from "next-intl/server";

import { ContactForm } from "@/components/public/contact-form";
import { ContactDirect } from "@/components/public/contact-direct";
import { getSiteSettings } from "@/lib/use-site-settings";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("contact");
  const settings = await getSiteSettings();

  return (
    <div className="container-wide py-16">
      <header className="mx-auto max-w-2xl text-center">
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">{t("page_title")}</h1>
        <p className="mt-4 text-lg text-[var(--color-muted-foreground)]">
          {t("page_subtitle")}
        </p>
      </header>

      <div className="mt-12 grid gap-10 md:grid-cols-2">
        <ContactForm />
        <ContactDirect settings={settings} />
      </div>
    </div>
  );
}
