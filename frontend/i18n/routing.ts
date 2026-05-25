import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["ar-MA", "fr", "ar"] as const,
  defaultLocale: "ar-MA",
  // Default locale (ar-MA) has no prefix in the URL ("/" → ar-MA);
  // /fr/articles, /ar/articles are explicit.
  localePrefix: "as-needed",
  // Don't sniff Accept-Language. Darija is the default, full stop.
  // FR / AR visitors must opt in via /fr or /ar URLs.
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];
