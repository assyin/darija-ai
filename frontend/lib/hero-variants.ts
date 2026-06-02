// Single source of truth for the home Hero illustrations.
// The admin Settings page renders a thumbnail picker from this list,
// and the Hero component resolves the chosen ID to a file via `resolveHeroVariant`.
// To add a new variant: drop the PNG in `public/hero/`, add a row here,
// and (optionally) extend the values mentioned in the seed_site_settings description.

export type HeroVariantId =
  | "marrakech-hero"
  | "marrakech-sunset"
  | "cool-city"
  | "medina-atlas"
  | "marrakech-square";

export interface HeroVariant {
  id: HeroVariantId;
  label: string;
  description: string;
  src: string;
  width: number;
  height: number;
}

export const HERO_VARIANTS: readonly HeroVariant[] = [
  {
    id: "marrakech-hero",
    label: "Marrakech — hero clean (16:9)",
    description:
      "Asset fourni par l'utilisateur : cerveau néon à droite, médina + Koutoubia + reflets sur l'eau à droite, gauche atmosphérique vide pour overlay texte. Aucun retoucher CSS — l'image est le hero.",
    src: "/hero/marrakech-hero-v3.png",
    width: 1672,
    height: 941,
  },
  {
    id: "marrakech-sunset",
    label: "Marrakech — coucher de soleil (16:9)",
    description:
      "Cerveau néon + Koutoubia, palmiers, horizon orange. Chaud, format paysage.",
    src: "/hero/marrakech-sunset.png",
    width: 1344,
    height: 768,
  },
  {
    id: "cool-city",
    label: "Ville moderne — nuit froide (1:1)",
    description:
      "Skyline urbaine moderne, palette violet/indigo/bleu. Idéal locale FR.",
    src: "/hero/cool-city.png",
    width: 1024,
    height: 1024,
  },
  {
    id: "medina-atlas",
    label: "Médina + Atlas (1:1)",
    description: "Médina marocaine, montagnes de l'Atlas, motif zellige subtil.",
    src: "/hero/medina-atlas.png",
    width: 1024,
    height: 1024,
  },
  {
    id: "marrakech-square",
    label: "Marrakech — carré (1:1)",
    description:
      "Variante carrée façon maquette originale, Koutoubia + palmiers.",
    src: "/hero/marrakech-square.png",
    width: 1024,
    height: 1024,
  },
];

export const DEFAULT_HERO_VARIANT_AR: HeroVariantId = "marrakech-hero";
export const DEFAULT_HERO_VARIANT_FR: HeroVariantId = "cool-city";

/** Setting key per locale — kept in sync with backend seed. */
export const HERO_VARIANT_SETTING_KEYS = [
  "hero_variant_ar",
  "hero_variant_fr",
] as const;

export type HeroVariantSettingKey = (typeof HERO_VARIANT_SETTING_KEYS)[number];

export function isHeroVariantKey(key: string): key is HeroVariantSettingKey {
  return (HERO_VARIANT_SETTING_KEYS as readonly string[]).includes(key);
}

/**
 * Resolve a setting value to a known variant. Falls back to `fallback`
 * (or the first registered variant if both are missing — should never happen
 * at runtime since the list is non-empty by construction).
 */
export function resolveHeroVariant(
  value: string | undefined,
  fallback: HeroVariantId,
): HeroVariant {
  const byValue = HERO_VARIANTS.find((v) => v.id === value);
  if (byValue) return byValue;
  const byFallback = HERO_VARIANTS.find((v) => v.id === fallback);
  if (byFallback) return byFallback;
  throw new Error("hero-variants registry is empty");
}
