// Helpers for the bidi-wrapped strings produced by the backend Localizer.
// Latin tokens come pre-wrapped in <bdi>...</bdi>. In markdown bodies that's
// fine (rehype-raw parses them). In plain-text JSX we need to either render as
// HTML or strip the tags — strings rendered as `{value}` get escaped.

const BDI_RE = /<\/?bdi>/g;

/** Drop <bdi> wrappers, keep the inner text. Use for metadata, JSON-LD, og:* tags. */
export function stripBdi(text: string | null | undefined): string {
  if (!text) return "";
  return text.replace(BDI_RE, "");
}

/**
 * Trust-bounded helper for rendering values that contain only safe <bdi> tags
 * (which is what the Localizer produces). Anything else is escaped.
 */
export function bdiHtml(text: string | null | undefined): string {
  if (!text) return "";
  // Escape everything first, then unescape ONLY the bdi tag pair we trust.
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/&lt;bdi&gt;/g, "<bdi>")
    .replace(/&lt;\/bdi&gt;/g, "</bdi>");
}
