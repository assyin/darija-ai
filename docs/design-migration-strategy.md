# 🧭 TitritAI — Visual Migration Strategy (Phase 1: Public Editorial)

> Generated **2026-05-26**. Pre-implementation plan. **No code yet.**
> Scope: **public editorial only** — Home, Articles list, Article detail, nav/footer/CTA, mobile polish. **Admin dashboard is out of scope for now.**
> Goal: premium modern AI-startup look, **without rebuilding the architecture**. Progressive token-first migration on the existing Next.js 15 + RTL foundation.

---

## 0. Key finding that shapes everything

The **current** design system is a **light** "Moroccan Modern Tech" theme (bg `#FAFAF7`, Bleu Majorelle `#1B4D8C`, terracotta `#E07856`) — **not** the dark AI-premium look of the mockups. So this is a **light → dark** restyle.

**Why it's still low-risk**: the whole UI is driven by:
- **CSS design tokens** in `globals.css` (`@theme inline { --color-*, --radius-* }`) — Tailwind v4, no JS config.
- **Utility classes** (`container-wide`, `font-arabic-display`, `prose-rtl`, `zellige-*`).
- **Component primitives** that consume those tokens (`components/ui/*`, `components/public/*`).
- A locale already exposed on the root element: `<html lang={locale} dir={...}>` (set from the `x-next-intl-locale` header), and CSS **already** branches on it (`html[lang="fr"] body { … }`).

➡️ Changing **tokens + utilities** re-themes most of the app at once; new **sections/components** are added incrementally. **Locale-aware look is pure CSS** via `html[lang]` / `html[dir]` selectors + token overrides — **one codebase, shared components**.

---

# PART A — Core migration strategy

## A1. Visual migration strategy (progressive, token-first)

Five ordered layers, each shippable & verifiable on its own:

1. **Token layer** — introduce the new dark palette + intensity/elevation/glow tokens in `@theme inline`. Keep the old token *names* (`--color-primary`, `--color-bg`…) so existing components re-skin automatically; only the **values** change. Add new semantic tokens (`--glow`, `--gradient-hero`, `--surface-1/2/3`).
2. **Primitive layer** — restyle `components/ui/*` (Button, Card, Badge, Input) and the core utilities (`container-*`, `prose-rtl`, dividers). This propagates to every page.
3. **Chrome layer** — Header + Footer + CTA banner + Newsletter (sitewide furniture).
4. **Page layer** — Home (hero, stats, latest, services, testimonials, CTA), then Articles list, then Article detail.
5. **Polish layer** — motion, mobile (375px), perf (LCP/CLS), a11y contrast, locale intensity tuning.

**Principles**
- **No architecture changes** — same routes, same data fetching, same components folder.
- **Token-first, not rewrite** — prefer changing a variable over editing many components.
- **Strangler/progressive** — migrate per layer; the site stays shippable at every step (we deploy via the existing push-to-deploy pipeline).
- **Admin untouched** — the "Legacy admin tokens" block in `globals.css` stays as-is so the admin keeps working while public migrates.

## A2. Component mapping (old → new)

| Existing | Action | New / added |
|---|---|---|
| `globals.css` `@theme` tokens (light) | **Replace values** (keep names) + add tokens | Dark palette, glow/elevation/gradient tokens, locale intensity vars |
| `components/ui/button.tsx` | Restyle variants | `primary` (violet+glow), `outline`, `ghost`, sizes; hover glow |
| `components/ui/card.tsx` | Restyle | Dark surface, hairline border, hover lift+glow; add `featured` variant |
| `components/ui/badge.tsx` | Restyle | Category/tag pill on dark |
| `components/ui/input/textarea/label` | Restyle | Dark form fields (used by contact/newsletter) |
| `components/public/header.tsx` | Restyle | Glass dark sticky nav, active-link glow, mobile drawer |
| `components/public/footer.tsx` | Restyle + enrich | Multi-column dark footer + newsletter + social |
| `components/public/article-card-public.tsx` | Restyle | Glow-on-hover, `featured`/`compact`/`list` formats |
| `components/public/article-cta.tsx` | Restyle | Gradient CTA banner + mascot slot |
| `components/public/newsletter-signup.tsx` | Restyle | Inline dark field + button |
| `components/public/social-icons.tsx` | Keep, recolor | — |
| `components/shared/rtl-content.tsx` + `.prose-rtl` | Restyle prose | Dark reading theme, accent rules, code blocks |
| `components/shared/not-found-content.tsx` | Restyle | Dark 404 + custom astronaut-style asset |
| `app/[locale]/page.tsx` (home) | Recompose | **New sections**: `<Hero>`, `<StatStrip>`, `<ServicesGrid>`, `<Testimonials>` |
| `app/[locale]/articles/page.tsx` | Restyle | Dark list + pagination |
| `app/[locale]/articles/[slug]/page.tsx` | Restyle | Dark article, author block, share row, related |
| — (none) | **Create** | `Hero`, `StatStrip`, `StatCounter`, `ServicesGrid`/`ServiceCard`, `Testimonials`/`TestimonialCard`, `SectionHeading`, `GlowWrap` |

> `components/admin/*`, `services/page.tsx`, `about/page.tsx`, `contact/*` are **not** Phase 1 (restyled later; they keep working on legacy tokens meanwhile).

## A3. Reusable design tokens (proposed)

Defined in `globals.css @theme inline` (illustrative values — not final code):

```
/* Surfaces (dark, near-black navy) */
--color-bg:            #060914;   /* page */
--surface-1:           #0d1324;   /* cards */
--surface-2:           #111a2e;   /* raised cards / inputs */
--color-border:        rgba(255,255,255,.08);

/* Brand */
--color-primary:       #7c3aed;   /* violet (CTA, active) */
--color-primary-dark:  #6d28d9;
--color-secondary:     #2563eb;   /* blue */
--color-accent:        #f59e0b;   /* amber (service icons) */
--color-cyan:          #22d3ee;   /* data / highlights */

/* Text */
--color-fg:            #f1f5f9;
--color-muted-foreground:#94a3b8;

/* Effects */
--gradient-hero:   linear-gradient(135deg,#7c3aed,#2563eb 50%,#db2777);
--gradient-cta:    linear-gradient(120deg,#6d28d9,#4f46e5);
--glow-primary:    0 0 40px -8px rgba(124,58,237,.55);
--shadow-card:     0 8px 30px -12px rgba(0,0,0,.6);

/* Radius */
--radius-sm:.5rem; --radius-md:.75rem; --radius-lg:1rem; --radius-xl:1.5rem;

/* Locale-intensity knobs (overridden per locale — see Part B) */
--glow-strength: 1;       /* 1 = full (AR), 0.4 = subtle (FR) */
--accent-sat:    1;       /* saturation multiplier */
--section-gap:   6rem;    /* vertical rhythm */
```

Token rules: components **never hardcode hex** — always `var(--…)`. Glow/gradient/elevation go through tokens so locale + dark/light tuning is centralized.

## A4. Typography system

| Role | Family | Notes |
|---|---|---|
| Arabic / Darija UI + body | **Tajawal** (already loaded) | RTL, the default `body` font |
| Latin (FR + inline tech terms) | **Inter** (already loaded) | via `<bdi>` and `html[lang="fr"]` |
| Display / hero accents | Tajawal 800 (AR) · Inter tight (FR) | locale-driven (Part B) |
| Code | mono stack | unchanged |

**Type scale** (fluid, `clamp()`): Display `2.5–4rem/800`, H1 `2–2.75rem/700`, H2 `1.5–1.875rem/700`, H3 `1.25rem/600`, Body `1–1.0625rem/400`, Small `.875rem`, Caption `.75rem`. Line-height: headings 1.2–1.35, body **1.85** for Arabic readability (already used in `prose-rtl`). Keep Frank_Ruhl_Libre only if a serif accent is wanted; otherwise drop to reduce font payload.

## A5. Spacing system

- **Base unit 4px**; scale 4/8/12/16/24/32/48/64/96.
- **Section rhythm** via `--section-gap` (default 6rem desktop, 3.5rem mobile).
- **Containers**: keep `container-wide` (72rem) and `container-narrow` (42rem, article reading width).
- **Card padding** 16–24px; **grid gaps** 20–24px.
- Use **logical properties** everywhere (`padding-inline`, `margin-block`) so RTL/LTR both work — already the convention.
- Density is locale-tuned via `--section-gap` and card padding (Part B).

## A6. Animation strategy

- **Philosophy**: subtle, fast, purposeful. CSS-first (transitions/keyframes); reach for **Framer Motion** only for scroll-reveal/staggered lists if needed (lazy-loaded, client components only).
- **Catalogue**:
  - Hover: card **lift + glow** (`translateY(-2px)` + `box-shadow: var(--glow-primary)`), button glow, link underline grow.
  - Entrance: fade/slide-up on scroll (IntersectionObserver), staggered for grids.
  - Ambient: slow **gradient/glow pulse** behind hero (very subtle).
  - Page/route: light fade.
- **Constraints**: respect `prefers-reduced-motion` (disable non-essential motion); keep within CLS budget (no layout-shifting animations); GPU-friendly (transform/opacity only).
- Intensity is locale-tuned (Part B): AR livelier, FR restrained.

## A7. Asset generation strategy (original custom assets)

We generate **original** assets (not copies of the mockup) using the project's **Flux pipeline** (`replicate_client` + R2 already wired) — plus SVG for UI.

| Asset | Type | Source |
|---|---|---|
| Hero illustration (AI + MENA atmosphere) | PNG/WebP | Flux, locale-tuned prompt |
| CTA mascot | PNG/WebP (transparent) | Flux |
| 404 illustration | PNG/WebP | Flux |
| Section/ambient backgrounds (glow, mesh gradient, zellige) | SVG/CSS | hand-authored (lightweight) |
| Service icons | SVG | `lucide-react` (already used), amber-tinted |
| OG images (1200×630) | PNG | template + per-article hero |
| Logo / brand mark (TitritAI) | SVG | designed (star "titrit" motif) |

**Consistency controls**: one **prompt style guide** (palette violet/blue/amber, dark, neon glow, clean, no text-in-image), fixed aspect ratios, a seed/style suffix reused across assets so they feel like one set. Store under `frontend/public/brand/*` (UI/static) and R2 (article heroes). Prefer **WebP**, explicit dimensions (CLS), `next/image`.

## A8. Implementation order (Phase 1)

1. **Tokens & utilities** (dark palette, glow/gradient/elevation, intensity knobs) — re-skins existing pages instantly.
2. **UI primitives** (Button, Card, Badge, Input) + `prose-rtl` dark.
3. **Header + Footer + CTA banner + Newsletter**.
4. **Home**: Hero → StatStrip → Latest articles → Services → Testimonials → CTA.
5. **Articles list** (cards + pagination).
6. **Article detail** (author, share, related, dark prose).
7. **Assets**: generate + integrate hero/mascot/404/OG + brand mark.
8. **Locale tuning** (Part B intensity overrides) + **mobile polish** + perf/a11y QA.

Each step: verify locally → deploy via push-to-deploy.

---

# PART B — Locale-aware visual expression (AR/Darija vs FR)

**One design system, one brand, two "moods."** Same components, same tokens, same architecture — only **intensity, density, type, and motion** shift per locale, driven entirely by `html[lang]` / `html[dir]` CSS. **No duplicated components, no duplicated codebase.**

### Mechanism (already supported)
Root layout renders `<html lang={locale} dir={rtl?"rtl":"ltr"}>`. We override the **intensity tokens** per locale in CSS:

```
/* Shared base = warm AR default */
:root { --glow-strength:1; --accent-sat:1; --section-gap:6rem; --radius-lg:1rem; }

/* French = minimal premium SaaS (Linear/Stripe/Vercel) */
html[lang="fr"] {
  --glow-strength:.4;     /* dimmer halos */
  --accent-sat:.85;       /* cooler, less saturated */
  --section-gap:7rem;     /* more whitespace */
  --radius-lg:.75rem;     /* tighter corners */
  --color-accent:#6366f1; /* shift amber→indigo for enterprise feel (optional) */
}
```
Every glow/gradient/spacing value multiplies by these knobs, so the **same component** renders warm+vibrant in AR and clean+restrained in FR.

## B1. Locale-aware visual differences (summary)

| Dimension | AR / Darija (expressive, warm, community) | FR (minimal, premium SaaS, enterprise) |
|---|---|---|
| Glow / gradients | Strong, present, emotional | Subtle, mostly flat surfaces |
| Color intensity | Vibrant violet+amber, warm | Cooler, desaturated, more neutral/indigo |
| Density | Cozier, tighter rhythm | Airier, more whitespace |
| Corners | Softer (1rem) | Tighter (.75rem) |
| Imagery | Cultural MENA warmth, expressive | Abstract, clean, business |
| Motion | Livelier | Precise, restrained |
| Reference vibe | Warm AI community media | Linear / Stripe / Vercel |

## B2. Typography per locale
- **AR/Darija**: Tajawal; slightly larger display sizes, bolder weights (800 hero), generous line-height (1.85 body) — warmth & readability.
- **FR**: Inter; tighter tracking (`-0.02em` on display), slightly smaller/cooler scale, more restrained weights (600–700), Linear-like precision. Switch via `html[lang="fr"] body { font-family: var(--font-sans); letter-spacing:-.011em; }` (the body-font switch already exists).

## B3. Spacing / intensity adjustments
- AR: `--section-gap:6rem`, denser cards, more decorative dividers (zellige, glow seams).
- FR: `--section-gap:7rem`, more breathing room, **fewer** decorative elements, hairline separators instead of glowing ones.
- All via the intensity knobs — no per-locale component variants.

## B4. Illustration strategy per audience
- **Shared brand mark** (TitritAI star) identical in both — the anchor of consistency.
- **AR heroes/mascot**: warmer palette (violet+amber+magenta), Moroccan/MENA atmospheric cues, more expressive/emotional, stronger neon.
- **FR heroes**: cooler/cleaner (violet+indigo+blue), abstract AI/geometric, enterprise-grade, reduced neon.
- Implementation: locale-keyed asset variants where it matters (hero, CTA), shared assets elsewhere (icons, logo). Same Flux style guide, two palette presets → cohesive but distinct.

## B5. Motion / animation differences
- **AR**: more entrance motion, livelier hover glow, ambient hero pulse on.
- **FR**: minimal entrances (short fades), crisp hovers, ambient pulse off/reduced.
- Driven by `--glow-strength` + a `--motion-scale` token + `html[lang="fr"]` disabling ambient keyframes. `prefers-reduced-motion` always wins.

## B6. Preserving brand consistency (invariants)
These are **identical across locales** — the guardrails that keep it "one product":
1. **Logo & brand mark** (TitritAI star) — same everywhere.
2. **Core palette identity** — violet primary + dark navy base are constant; only intensity/secondary-accent shifts.
3. **Component library & layout grammar** — same components, same structures, same spacing scale (only multipliers differ).
4. **Typography families** — Tajawal/Inter pairing is the brand voice in both.
5. **Voice & iconography** — same icon set, same tone of motion language.
> Rule of thumb: **locale changes the *intensity dial*, never the *instrument*.** A FR user and an AR user must instantly recognize the same brand.

---

## Open decisions (to confirm before coding)
1. **Brand mark**: design a TitritAI "star" logo now (SVG), or temporary wordmark first?
2. **FR accent**: keep amber in FR too, or shift to indigo (`#6366f1`) for the enterprise feel? (table B1 assumes optional shift.)
3. **Motion lib**: CSS-only first (recommended), add Framer Motion only if scroll-reveal needs it?
4. **Drop Frank_Ruhl_Libre** (serif) to cut font payload, since the new look is sans-driven?
5. **Asset palette presets**: confirm AR=violet+amber+magenta, FR=violet+indigo+blue.

---

*Foundation: `frontend/` Next.js 15, Tailwind v4 (`@theme inline`), next-intl (locales ar-MA/ar/fr, `html[lang]` already styled), components in `components/{ui,public,shared}`. Migration is token-first + additive sections — no architecture rebuild.*
