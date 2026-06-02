"use client";

import * as React from "react";
import {
  AlertCircle,
  Check,
  Loader2,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ProofreadResult, ProofreadSuggestion } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ProofreaderPanelProps {
  result: ProofreadResult | null;
  loading: boolean;
  error: string | null;
  stale: boolean;
  /** `null` until the user has ever evaluated. */
  hasEvaluated: boolean;
  /** Triggered when the user clicks Évaluer / Re-évaluer. */
  onEvaluate: () => void;
  /** Apply a suggestion (writes the replacement into the field's draft state). */
  onApply: (index: number, suggestion: ProofreadSuggestion) => void;
  /** Remove a suggestion from the panel without applying it. */
  onDismiss?: (index: number) => void;
  /** Highlight sync with the inline marks in the preview. */
  activeIndex?: number | null;
  onSelect?: (index: number | null) => void;
}

const CATEGORY_LABEL: Record<ProofreadSuggestion["category"], string> = {
  grammar: "Grammaire",
  naturalness: "Naturel",
  clarity: "Clarté",
  consistency: "Cohérence",
};

const SEVERITY_DOT: Record<ProofreadSuggestion["severity"], string> = {
  low: "bg-yellow-400",
  medium: "bg-orange-500",
  high: "bg-rose-600",
};

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-700 bg-emerald-50 ring-emerald-200";
  if (score >= 60) return "text-orange-700 bg-orange-50 ring-orange-200";
  return "text-rose-700 bg-rose-50 ring-rose-200";
}

export function ProofreaderPanel({
  result,
  loading,
  error,
  stale,
  hasEvaluated,
  onEvaluate,
  onApply,
  onDismiss,
  activeIndex = null,
  onSelect,
}: ProofreaderPanelProps) {
  return (
    <aside className="sticky top-4 flex max-h-[calc(100vh-2rem)] flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-white">
      <header className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--color-muted)]">
            Correcteur IA
          </p>
          <p className="mt-0.5 text-xs text-[var(--color-muted-foreground)]">
            {loading
              ? "Analyse en cours…"
              : stale
                ? "⚠ Texte modifié depuis"
                : result
                  ? `${result.cached ? "(cached) " : ""}${result.model}`
                  : "Cliquez sur Évaluer pour commencer"}
          </p>
        </div>
        {hasEvaluated && (
          <Button
            variant="outline"
            size="icon"
            onClick={onEvaluate}
            title={stale ? "Re-évaluer (texte modifié)" : "Re-évaluer"}
            disabled={loading}
            className={cn(stale && "border-fuchsia-400 text-fuchsia-600")}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {error && (
          <div className="mb-3 flex items-start gap-2 rounded-md bg-rose-50 px-3 py-2 text-xs text-rose-900">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Initial state — never evaluated */}
        {!hasEvaluated && !loading && (
          <div className="flex flex-col items-stretch gap-2 py-2 text-center">
            <p className="text-xs text-[var(--color-muted-foreground)]">
              L&apos;analyse coûte ~$0.0002 (gpt-4o-mini).
              <br />
              Cliquez quand vous êtes prêt.
            </p>
            <Button
              size="sm"
              onClick={onEvaluate}
              className="gap-2 bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white hover:brightness-110"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Évaluer le contenu
            </Button>
          </div>
        )}

        {/* First-time loading — show a placeholder */}
        {loading && !result && (
          <div className="flex items-center justify-center gap-2 py-6 text-xs text-[var(--color-muted-foreground)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Analyse de la traduction…
          </div>
        )}

        {result && (
          <>
            <div
              className={cn(
                "mb-3 flex items-baseline justify-between rounded-md px-3 py-2 ring-1 ring-inset",
                scoreColor(result.score),
              )}
            >
              <span className="text-3xl font-bold tabular-nums">
                {result.score}
              </span>
              <span className="text-xs font-medium opacity-70">/ 100</span>
            </div>
            {result.summary && (
              <p className="mb-3 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
                {result.summary}
              </p>
            )}
            {stale && (
              <div className="mb-3 rounded-md border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-2 text-[11px] text-fuchsia-900">
                Le texte a changé. <strong>Re-évaluer</strong> pour un score à
                jour.
              </div>
            )}

            {result.suggestions.length === 0 ? (
              <p className="rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                <Check className="mr-1 inline h-3.5 w-3.5" />
                Rien à signaler ✨
              </p>
            ) : (
              <ul className="space-y-2.5">
                {result.suggestions.map((s, i) => (
                  <SuggestionRow
                    key={`${i}-${s.original.slice(0, 16)}`}
                    suggestion={s}
                    isActive={activeIndex === i}
                    onApply={() => onApply(i, s)}
                    onDismiss={onDismiss ? () => onDismiss(i) : undefined}
                    onMouseEnter={() => onSelect?.(i)}
                    onMouseLeave={() => onSelect?.(null)}
                    onClick={() => onSelect?.(i)}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

interface SuggestionRowProps {
  suggestion: ProofreadSuggestion;
  isActive: boolean;
  onApply: () => void;
  onDismiss?: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
}

function SuggestionRow({
  suggestion,
  isActive,
  onApply,
  onDismiss,
  onMouseEnter,
  onMouseLeave,
  onClick,
}: SuggestionRowProps) {
  return (
    <li
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      className={cn(
        "rounded-md border border-[var(--color-border)] bg-slate-50 p-2.5 transition",
        isActive && "ring-2 ring-fuchsia-400",
      )}
    >
      <div className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide text-[var(--color-muted-foreground)]">
        <span className="inline-flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              SEVERITY_DOT[suggestion.severity],
            )}
          />
          {CATEGORY_LABEL[suggestion.category]}
        </span>
        <div className="flex items-center gap-1.5">
          {onDismiss && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDismiss();
              }}
              title="Ignorer cette suggestion"
              className="inline-flex h-5 w-5 items-center justify-center rounded text-[var(--color-muted-foreground)] hover:bg-slate-200 hover:text-rose-700"
            >
              <X className="h-3 w-3" />
            </button>
          )}
          {suggestion.suggestion && suggestion.suggestion !== suggestion.original && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onApply();
              }}
              className="rounded bg-fuchsia-600 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white hover:brightness-110"
            >
              Apply
            </button>
          )}
        </div>
      </div>
      <div className="mt-1.5 break-words text-sm">
        <span
          dir="auto"
          className="rounded bg-rose-100 px-1 text-rose-900 line-through decoration-rose-400/60"
        >
          {suggestion.original}
        </span>
        {suggestion.suggestion && (
          <>
            {" "}
            <span dir="auto" className="rounded bg-emerald-100 px-1 text-emerald-900">
              {suggestion.suggestion}
            </span>
          </>
        )}
      </div>
      {suggestion.reason && (
        <p className="mt-1 text-[11px] leading-relaxed text-[var(--color-muted-foreground)]">
          {suggestion.reason}
        </p>
      )}
    </li>
  );
}
