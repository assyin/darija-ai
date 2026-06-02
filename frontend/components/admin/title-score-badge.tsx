"use client";

import * as React from "react";
import { Loader2, Sparkles } from "lucide-react";

import type { ProofreadResult } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TitleScoreBadgeProps {
  result: ProofreadResult | null;
  loading: boolean;
  stale: boolean;
  /** Disable the whole control when the title is too short. */
  hidden?: boolean;
  /** Triggered when the user clicks Évaluer / Re-évaluer. */
  onEvaluate: () => void;
}

/**
 * Inline title evaluator. Pre-eval: a small "Évaluer" button.
 * Post-eval: a color-coded score chip with native tooltip listing
 * up to 3 suggestions. After the title is edited, the chip flips into
 * a "Re-évaluer" affordance.
 */
export function TitleScoreBadge({
  result,
  loading,
  stale,
  hidden = false,
  onEvaluate,
}: TitleScoreBadgeProps) {
  if (hidden) return null;

  if (loading && !result) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-[var(--color-muted-foreground)]">
        <Loader2 className="h-3 w-3 animate-spin" />
        analyse
      </span>
    );
  }

  if (!result) {
    return (
      <button
        type="button"
        onClick={onEvaluate}
        className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] bg-white px-2 py-0.5 text-[11px] font-medium text-[var(--color-muted-foreground)] transition hover:border-fuchsia-300 hover:text-fuchsia-700"
        title="Évaluer le titre avec le correcteur IA"
      >
        <Sparkles className="h-3 w-3" />
        Évaluer titre
      </button>
    );
  }

  const tooltip = [
    `Score titre : ${result.score}/100`,
    result.summary,
    stale ? "\n⚠ Titre modifié — cliquez pour re-évaluer." : "",
    ...result.suggestions
      .slice(0, 3)
      .map((s) => `· ${s.original} → ${s.suggestion} (${s.reason})`),
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <button
      type="button"
      onClick={onEvaluate}
      title={tooltip}
      disabled={loading}
      className={cn(
        "inline-flex select-none items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset transition",
        scoreColor(result.score),
        stale && "ring-fuchsia-400 ring-2",
        loading && "opacity-60",
      )}
    >
      <span className="opacity-70">titre</span>
      {loading ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <span className="tabular-nums">{result.score}</span>
      )}
      {stale && !loading && <span className="opacity-70">·↻</span>}
    </button>
  );
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-700 bg-emerald-50 ring-emerald-200";
  if (score >= 60) return "text-orange-700 bg-orange-50 ring-orange-200";
  return "text-rose-700 bg-rose-50 ring-rose-200";
}
