// Single source of truth for the public navigation.
// Keep it lightweight and evolvable — edit here, Header + Footer follow.
// `key` is a translation key under the "nav" i18n namespace.
export interface NavLink {
  href: string;
  key: string;
}

export const NAV_LINKS: NavLink[] = [
  { href: "/", key: "home" },
  { href: "/articles", key: "articles" },
  { href: "/services", key: "services" },
  { href: "/about", key: "about" },
  { href: "/contact", key: "contact" },
];

/**
 * Strip the locale prefix (/fr, /ar) so active-state matching works across
 * locales. The default locale (ar-MA) has no prefix.
 */
export function stripLocale(pathname: string): string {
  return pathname.replace(/^\/(fr|ar)(?=\/|$)/, "") || "/";
}
