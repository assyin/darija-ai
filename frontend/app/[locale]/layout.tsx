import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";

import { Footer } from "@/components/public/footer";
import { Header } from "@/components/public/header";
import { routing } from "@/i18n/routing";
import { getSiteSettings } from "@/lib/use-site-settings";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function PublicLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const settings = await getSiteSettings();

  return (
    <NextIntlClientProvider>
      <div className="theme-public" data-locale={locale}>
        <a href="#main" className="skip-link">
          Aller au contenu
        </a>
        <Header settings={settings} />
        <main id="main">{children}</main>
        <Footer settings={settings} />
      </div>
    </NextIntlClientProvider>
  );
}
