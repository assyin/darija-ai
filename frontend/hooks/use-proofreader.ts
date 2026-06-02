"use client";

import * as React from "react";

import { adminApi } from "@/lib/api-client";
import type {
  ProofreadField,
  ProofreadLang,
  ProofreadResult,
  ProofreadSuggestion,
} from "@/lib/types";

/**
 * Manual-trigger AI proofreader hook.
 *
 * The previous version auto-fired on every text change (debounced), which
 * spammed the API and racked up cost during normal editing. This version
 * only calls `POST /admin/articles/{id}/proofread` when the caller invokes
 * `evaluate()`. The result is kept until the next `evaluate()`; the caller
 * can locally dismiss a suggestion (Apply) without burning a fresh call, and
 * a stale flag tells the UI that the displayed score no longer matches the
 * current text.
 *
 * Severity weights are used to bump the displayed score client-side when
 * suggestions are applied — feels like Grammarly's live score without the
 * per-keystroke cost. The "true" recomputation happens on the next manual
 * Re-évaluer (which usually hits the Redis cache and is free).
 */
export interface UseProofreaderArgs {
  articleId: number;
  text: string;
  lang: ProofreadLang;
  field: ProofreadField;
  /** When false the hook is inert (evaluate() is a no-op). */
  enabled?: boolean;
}

export interface UseProofreaderState {
  /** Latest result, or null if never evaluated. */
  result: ProofreadResult | null;
  loading: boolean;
  error: string | null;
  /** `text` has changed since the last evaluation. */
  stale: boolean;
  /** Snapshot of the text at the moment `result` was produced. */
  textAtEval: string | null;
  /** Trigger an evaluation now. Idempotent if already in flight. */
  evaluate: () => void;
  /** Locally drop a suggestion (e.g. after Apply); bumps the displayed score. */
  dismissSuggestion: (index: number) => void;
}

const SEVERITY_WEIGHT = { low: 2, medium: 5, high: 9 } as const;

export function useProofreader({
  articleId,
  text,
  lang,
  field,
  enabled = true,
}: UseProofreaderArgs): UseProofreaderState {
  const [result, setResult] = React.useState<ProofreadResult | null>(null);
  const [textAtEval, setTextAtEval] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Latest abort controller so subsequent evaluate() calls cancel the previous.
  const aborterRef = React.useRef<AbortController | null>(null);

  const evaluate = React.useCallback(() => {
    if (!enabled) return;
    const trimmed = text.trim();
    if (trimmed.length === 0) return;

    aborterRef.current?.abort();
    const aborter = new AbortController();
    aborterRef.current = aborter;

    setLoading(true);
    setError(null);
    const evaluatedText = text;

    adminApi
      .post<ProofreadResult>(
        `/articles/${articleId}/proofread`,
        { text, lang, field },
        { signal: aborter.signal },
      )
      .then((r) => {
        if (aborter.signal.aborted) return;
        setResult(r);
        setTextAtEval(evaluatedText);
      })
      .catch((err: unknown) => {
        if (aborter.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      })
      .finally(() => {
        if (!aborter.signal.aborted) setLoading(false);
      });
  }, [enabled, articleId, text, lang, field]);

  const dismissSuggestion = React.useCallback((index: number) => {
    setResult((prev) => {
      if (!prev) return prev;
      const target: ProofreadSuggestion | undefined = prev.suggestions[index];
      if (!target) return prev;
      const remaining = prev.suggestions.filter((_, i) => i !== index);
      const bump = SEVERITY_WEIGHT[target.severity];
      const nextScore = Math.min(100, prev.score + bump);
      return { ...prev, suggestions: remaining, score: nextScore };
    });
  }, []);

  // "stale" = result exists but the text has drifted from the snapshot.
  const stale =
    result !== null && textAtEval !== null && text !== textAtEval;

  return {
    result,
    loading,
    error,
    stale,
    textAtEval,
    evaluate,
    dismissSuggestion,
  };
}
