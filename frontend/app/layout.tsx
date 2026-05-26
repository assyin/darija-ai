import type { Metadata } from "next";
import { Inter, Tajawal } from "next/font/google";
import { headers } from "next/headers";

import { Providers } from "@/components/providers";

import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const tajawal = Tajawal({
  variable: "--font-tajawal",
  subsets: ["arabic"],
  weight: ["400", "500", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "DarijaAI", template: "%s · DarijaAI" },
  description: "أول منصة لأخبار الذكاء الاصطناعي بالدارجة المغربية",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // next-intl middleware sets x-next-intl-locale on public routes.
  // Admin/login bypass i18n → header missing → fall back to fr/ltr.
  const h = await headers();
  const locale = h.get("x-next-intl-locale") ?? "fr";
  const isRTL = locale.startsWith("ar");

  return (
    <html
      lang={locale}
      dir={isRTL ? "rtl" : "ltr"}
      className={`${inter.variable} ${tajawal.variable}`}
    >
      <body className="min-h-screen bg-[var(--color-bg)] text-[var(--color-fg)] antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
