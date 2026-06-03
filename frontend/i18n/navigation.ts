/**
 * Locale-aware navigation primitives.
 *
 * Use these instead of `next/link` / `next/navigation` everywhere we link to
 * a locale-scoped path (articles, /about, etc.). When the user is on `/fr`,
 * a wrapped `<Link href="/articles/foo">` resolves to `/fr/articles/foo`
 * automatically — with raw `next/link` it would jump back to the Darija
 * locale.
 *
 * The wrapped router (`useRouter`) also auto-prefixes. Pass `{locale: "fr"}`
 * to `router.push(...)` explicitly when switching locales.
 */

import { createNavigation } from "next-intl/navigation";

import { routing } from "@/i18n/routing";

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
