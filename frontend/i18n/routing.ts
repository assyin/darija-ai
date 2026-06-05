import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // "ar" (MSA) was previously listed alongside ar-MA + fr but no MSA
  // translations are produced by the Localizer pipeline. The result was
  // duplicate content under /ar/* (the page served the Darija fallback
  // while declaring /ar/<slug> as its own canonical), which Google would
  // treat as a duplicate-content penalty against the canonical
  // /<slug> URL. Re-add "ar" when the MSA pipeline ships.
  locales: ["ar-MA", "fr"] as const,
  defaultLocale: "ar-MA",
  // Default locale (ar-MA) has no prefix in the URL ("/" → ar-MA);
  // /fr/articles is the only explicit prefix today.
  localePrefix: "as-needed",
  // Don't sniff Accept-Language. Darija is the default, full stop.
  // FR visitors must opt in via /fr URLs.
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];
