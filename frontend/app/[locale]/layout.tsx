import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";

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

  // EXPLICITLY pass locale + messages to the client provider. Under
  // next-intl v4 + Next 16, omitting them was supposed to let the provider
  // inherit from the server request context, but in practice the client
  // bundle falls back to `routing.defaultLocale` ("ar-MA"). Visible
  // symptoms on /fr: nav rendered with Arabic strings, locale switcher
  // hrefs built with the wrong prefix (`/ar-MA/fr/...`), `useLocale()`
  // returning ar-MA instead of fr — all inside the Header + Footer
  // client components.
  const [settings, messages] = await Promise.all([
    getSiteSettings(),
    getMessages(),
  ]);

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
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
