"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import type { ProofreadSuggestion } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * RTL markdown renderer that *also* inlines proofreader highlights.
 *
 * For every rendered text node, we look up suggestions whose `original` string
 * appears verbatim and wrap each match in a clickable `<mark>` styled by
 * severity (yellow → orange → red). Hover shows the suggestion's reason in
 * the browser tooltip; click bubbles up via `onSuggestionClick(index)` so the
 * sidebar can scroll to / open the matching row.
 *
 * Falls back to a plain renderer when there are no suggestions — zero cost
 * for the happy path.
 */
interface ProofreadingRtlContentProps {
  markdown: string;
  suggestions: ProofreadSuggestion[];
  onSuggestionClick?: (index: number) => void;
  activeIndex?: number | null;
  className?: string;
  /** Render direction. "rtl" for Darija, "ltr" for French. */
  dir?: "rtl" | "ltr";
}

const SEVERITY_CLS: Record<ProofreadSuggestion["severity"], string> = {
  low: "bg-yellow-100 text-yellow-900 ring-yellow-300/60 hover:bg-yellow-200",
  medium: "bg-orange-100 text-orange-900 ring-orange-300/70 hover:bg-orange-200",
  high: "bg-rose-100 text-rose-900 ring-rose-300/70 hover:bg-rose-200",
};

export function ProofreadingRtlContent({
  markdown,
  suggestions,
  onSuggestionClick,
  activeIndex = null,
  className,
  dir = "rtl",
}: ProofreadingRtlContentProps) {
  // Pre-compute non-empty originals once.
  const nonEmpty = React.useMemo(
    () =>
      suggestions
        .map((s, i) => ({ ...s, index: i }))
        .filter((s) => s.original.trim().length > 0),
    [suggestions],
  );

  const renderText = React.useCallback(
    (text: string): React.ReactNode => {
      if (!text || nonEmpty.length === 0) return text;
      return highlightFragments(
        text,
        nonEmpty,
        onSuggestionClick,
        activeIndex,
      );
    },
    [nonEmpty, onSuggestionClick, activeIndex],
  );

  // Walk react-markdown's children: anywhere a string appears, run renderText.
  const wrap = React.useCallback(
    (children: React.ReactNode): React.ReactNode =>
      React.Children.map(children, (child) =>
        typeof child === "string" ? renderText(child) : child,
      ),
    [renderText],
  );

  return (
    <div
      className={cn(dir === "rtl" ? "prose-rtl" : "prose-ltr", className)}
      dir={dir}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          p: ({ children }) => <p>{wrap(children)}</p>,
          li: ({ children }) => <li>{wrap(children)}</li>,
          h1: ({ children }) => <h1>{wrap(children)}</h1>,
          h2: ({ children }) => <h2>{wrap(children)}</h2>,
          h3: ({ children }) => <h3>{wrap(children)}</h3>,
          strong: ({ children }) => <strong>{wrap(children)}</strong>,
          em: ({ children }) => <em>{wrap(children)}</em>,
          blockquote: ({ children }) => <blockquote>{wrap(children)}</blockquote>,
          td: ({ children }) => <td>{wrap(children)}</td>,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Walk a plain text string, splitting it at every occurrence of every
 * suggestion's `original`. Each match becomes a `<mark>`; surrounding text
 * stays plain.
 *
 * We greedily match the longest originals first so overlapping suggestions
 * don't fight (e.g. "machine learning" before "machine"). Ties broken by
 * earliest occurrence.
 */
function highlightFragments(
  text: string,
  suggestions: (ProofreadSuggestion & { index: number })[],
  onClick: ((index: number) => void) | undefined,
  activeIndex: number | null,
): React.ReactNode {
  type Hit = { start: number; end: number; sIndex: number };

  // Find all hits.
  const hits: Hit[] = [];
  for (const s of suggestions) {
    const needle = s.original;
    if (needle.length === 0) continue;
    let from = 0;
    while (from <= text.length - needle.length) {
      const at = text.indexOf(needle, from);
      if (at < 0) break;
      hits.push({ start: at, end: at + needle.length, sIndex: s.index });
      from = at + needle.length;
    }
  }
  if (hits.length === 0) return text;

  // Sort by start ASC, then by length DESC (longer match wins on ties).
  hits.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - b.start - (a.end - a.start);
  });

  // Greedy non-overlap pass.
  const chosen: Hit[] = [];
  let cursor = 0;
  for (const h of hits) {
    if (h.start < cursor) continue;
    chosen.push(h);
    cursor = h.end;
  }

  const out: React.ReactNode[] = [];
  let pos = 0;
  chosen.forEach((h, i) => {
    if (h.start > pos) out.push(text.slice(pos, h.start));
    const s = suggestions.find((x) => x.index === h.sIndex);
    const isActive = activeIndex === h.sIndex;
    out.push(
      <mark
        key={`m-${i}-${h.start}`}
        title={
          s ? `${s.reason}${s.suggestion ? "\n→ " + s.suggestion : ""}` : ""
        }
        onClick={onClick ? () => onClick(h.sIndex) : undefined}
        className={cn(
          "cursor-pointer rounded px-0.5 ring-1 ring-inset transition",
          s ? SEVERITY_CLS[s.severity] : "",
          isActive && "ring-2 ring-fuchsia-500",
        )}
      >
        {text.slice(h.start, h.end)}
      </mark>,
    );
    pos = h.end;
  });
  if (pos < text.length) out.push(text.slice(pos));
  return out;
}
