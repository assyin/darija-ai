// Shared (server + client safe) helpers for the public site_settings.
// The React hook lives in `use-site-settings.client.ts`.

export type SiteSettings = Record<string, string>;

/**
 * Server-side fetch for use in Server Components / layouts.
 * 5-minute revalidation cache. Falls back to {} on failure so layouts still render.
 */
export async function getSiteSettings(): Promise<SiteSettings> {
  const base =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  try {
    const res = await fetch(`${base}/settings/public`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return {};
    return (await res.json()) as SiteSettings;
  } catch {
    return {};
  }
}

/** Strip non-digits from a phone number (used to build wa.me links). */
export function cleanPhone(raw: string | undefined): string {
  if (!raw) return "";
  return raw.replace(/\D/g, "");
}

/**
 * Replace {{placeholder}} tokens in a template using a settings map.
 * Supports a `_clean` suffix for phone-like values.
 */
export function renderTemplate(
  template: string,
  settings: SiteSettings,
): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => {
    if (key.endsWith("_clean")) {
      const base = key.slice(0, -"_clean".length);
      return cleanPhone(settings[base]);
    }
    return settings[key] ?? "";
  });
}
