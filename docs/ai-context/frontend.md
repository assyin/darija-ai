# Frontend Context — DarijaAI

> Load this file when: UI, components, pages, RTL, styling, SEO, Next.js routing.

---

## Stack

- Next.js 15 App Router (RSC by default) · TypeScript strict · `pnpm`
- Tailwind CSS v4 + `tailwindcss-rtl` · shadcn/ui (copy-paste in `components/ui/`) · `lucide-react`
- Forms: `react-hook-form` + `zod`
- Fonts: Tajawal (Arabic) via `next/font/google`
- i18n: `next-intl` · Locale: `ar-MA`

## Route structure

```
frontend/app/
├── [locale]/               # Public site (Arabic RTL)
│   ├── page.tsx            # Home — article grid
│   ├── articles/           # Articles list + [slug] detail
│   ├── about/contact/services/page.tsx
│   └── layout.tsx          # Locale provider
├── (admin)/admin/          # Admin panel
│   ├── articles/           # List + [id] editor (13KB — complex)
│   ├── settings/           # Site settings
│   ├── sources/            # RSS source management
│   └── login/              # Magic link login
└── api/                    # Route handlers only (contact, newsletter)
```

## Component structure

```
frontend/components/
├── admin/     # article-card, markdown-editor, sidebar, status-badge
├── public/    # article-card-public, header, footer, newsletter-signup, contact-form
├── shared/    # rtl-content
└── ui/        # shadcn/ui primitives (badge, button, card, dialog, etc.)
```

## Hard rules

**RSC default**: Server Components everywhere. `"use client"` only for state/effects/browser APIs/event handlers. Push client boundaries as low as possible.

**TypeScript**: `strict: true`, `noUncheckedIndexedAccess`. NO `any`, NO `as` casts without comment, NO `!` assertions in prod.

**State shape**: Discriminated unions, not `{ loading, error, data }` optionals.

**Styling**: Tailwind only. `cn()` for conditional classes. No inline styles for non-dynamic values. No custom CSS except `globals.css`.

## RTL rules (non-negotiable)

- `<html lang="ar-MA" dir="rtl">` — set in root layout, never changes.
- Logical CSS properties: `ms-4` not `ml-4`, `ps-2` not `pl-2`.
- `tailwindcss-rtl` plugin is mandatory for all RTL-aware utilities.
- Arabic punctuation in display text: `،` (comma) `؟` (question mark).
- Mixed Arabic/Latin content → wrap Latin in `<bdi>` tags.

## SEO requirements (every public page)

- `generateMetadata()` exported — no fallback to defaults.
- OG image required: 1200×630, served from R2 via Cloudflare CDN.
- Canonical URL set. `NewsArticle` JSON-LD on article pages.
- `lang="ar"` and `dir="rtl"` declared.

## Performance targets

- LCP < 2.0s (mobile 4G) · CLS < 0.05 · INP < 200ms
- JS bundle < 100kb gzipped/page
- All images via `next/image` with explicit `width`/`height`
- `priority` on first-fold images only

## Data fetching

- RSC fetches data, passes down as props. No client-side fetching for SEO content.
- Mutations via Server Actions passed as props to client components.
- No SWR / React Query for server-rendered data.

## Testing

No frontend tests exist yet. When adding: Vitest + Testing Library for interactive components. E2E (Playwright) for 3 critical paths (home, article detail, admin publish flow).
