"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import type { ProofreadResult } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TitleScoreBadgeProps {
  result: ProofreadResult | null;
  loading: boolean;
  /** Disable visibility when the title is too short. */
  hidden?: boolean;
}

/**
 * Tiny inline badge that lives next to the title input. Color-codes the
 * score; native browser tooltip lists up to 3 top suggestions.
 */
export function TitleScoreBadge({
  result,
  loading,
  hidden = false,
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
  if (!result) return null;

  const tooltip = [
    `Score titre : ${result.score}/100`,
    result.summary,
    "",
    ...result.suggestions
      .slice(0, 3)
      .map((s) => `· ${s.original} → ${s.suggestion} (${s.reason})`),
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <span
      title={tooltip}
      className={cn(
        "inline-flex select-none items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
        scoreColor(result.score),
      )}
    >
      <span className="opacity-70">titre</span>
      <span className="tabular-nums">{result.score}</span>
    </span>
  );
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-700 bg-emerald-50 ring-emerald-200";
  if (score >= 60) return "text-orange-700 bg-orange-50 ring-orange-200";
  return "text-rose-700 bg-rose-50 ring-rose-200";
}
