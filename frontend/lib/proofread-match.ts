/**
 * Locate a proofreader suggestion's `original` inside a `haystack`, tolerant
 * to the common normalization mismatches that bite Arabic/Darija text:
 *
 *   - Arabic-Indic digits vs Latin digits (١٢٨ ↔ 128)
 *   - Bidi marks left over by middleware (U+200E, U+200F, U+202A-E)
 *   - Whitespace collapse / line break differences
 *   - Unicode NFC vs NFD composition
 *
 * Returns `null` when the phrase truly isn't there (e.g. a previous Apply
 * already rewrote it).
 */
export interface MatchResult {
  start: number;
  end: number;
}

const BIDI_RE = /[​-‏‪-‮⁦-⁩﻿]/g;

const ARABIC_INDIC_DIGITS: Record<string, string> = {
  "٠": "0",
  "١": "1",
  "٢": "2",
  "٣": "3",
  "٤": "4",
  "٥": "5",
  "٦": "6",
  "٧": "7",
  "٨": "8",
  "٩": "9",
  // Extended Arabic-Indic (Persian/Urdu)
  "۰": "0",
  "۱": "1",
  "۲": "2",
  "۳": "3",
  "۴": "4",
  "۵": "5",
  "۶": "6",
  "۷": "7",
  "۸": "8",
  "۹": "9",
};

function normalize(text: string): string {
  return text
    .normalize("NFC")
    .replace(BIDI_RE, "")
    .replace(/\s+/g, " ")
    .replace(/[٠-٩۰-۹]/g, (c) => ARABIC_INDIC_DIGITS[c] ?? c)
    .trim();
}

/**
 * Find `needle` in `haystack`. Returns indexes into the ORIGINAL (raw)
 * `haystack` (not the normalized form) so the caller can splice safely.
 *
 * Strategy:
 *  1. Strict indexOf (cheap, works ~80% of the time).
 *  2. If that fails, normalize haystack while tracking a `rawIndex` map
 *     from each normalized char back to the source index, then indexOf
 *     the normalized needle and translate the match back.
 */
export function findOriginal(
  haystack: string,
  needle: string,
): MatchResult | null {
  if (!needle) return null;
  const strict = haystack.indexOf(needle);
  if (strict >= 0) return { start: strict, end: strict + needle.length };

  // Build a normalized haystack alongside a mapping from normalized index
  // back to the source character index.
  const normChars: string[] = [];
  const map: number[] = []; // map[i] = source index of normChars[i]
  let lastWasSpace = false;

  for (let i = 0; i < haystack.length; i++) {
    const ch = haystack[i];
    if (!ch) continue;
    // Strip bidi marks entirely.
    if (/[​-‏‪-‮⁦-⁩﻿]/.test(ch)) continue;
    // Collapse whitespace runs into a single space.
    if (/\s/.test(ch)) {
      if (lastWasSpace) continue;
      normChars.push(" ");
      map.push(i);
      lastWasSpace = true;
      continue;
    }
    lastWasSpace = false;
    // NFC + digit transliteration.
    const norm = ARABIC_INDIC_DIGITS[ch] ?? ch.normalize("NFC");
    // Single-char NFC may expand to multiple chars; map each to the same source.
    for (const nc of norm) {
      normChars.push(nc);
      map.push(i);
    }
  }
  const normHaystack = normChars.join("");
  const normNeedle = normalize(needle);
  if (normNeedle.length === 0) return null;

  const at = normHaystack.indexOf(normNeedle);
  if (at < 0) return null;

  const start = map[at] ?? 0;
  const endNormIdx = at + normNeedle.length - 1;
  const endSrc = map[endNormIdx];
  if (endSrc === undefined) return null;
  return { start, end: endSrc + 1 };
}

/** Convenience: returns whether the needle is present (strict or fuzzy). */
export function hasOriginal(haystack: string, needle: string): boolean {
  return findOriginal(haystack, needle) !== null;
}
