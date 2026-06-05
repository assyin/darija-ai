import { setRequestLocale } from "next-intl/server";

import { NotFoundContent } from "@/components/shared/not-found-content";
import { routing } from "@/i18n/routing";

// Global 404 for unmatched top-level routes (renders in the root layout,
// which sets <html lang/dir> from the next-intl locale header).
//
// IMPORTANT: NotFoundContent uses `getTranslations` which requires the request
// locale to be set. Unlike [locale]/not-found.tsx — which is triggered by
// `notFound()` inside a page that already called `setRequestLocale(locale)` —
// this global boundary has no caller to register the locale, so we set the
// default locale explicitly. Without this, next-intl throws inside
// `NotFoundContent`, the React error boundary catches it, and the response
// status becomes 500 instead of the expected 404. Google then surfaces those
// unknown paths as "server errors" in Search Console.
export default function NotFound() {
  setRequestLocale(routing.defaultLocale);
  return <NotFoundContent />;
}
