"use client";

import * as React from "react";

import { adminApi } from "@/lib/api-client";
import type {
  ProofreadField,
  ProofreadLang,
  ProofreadResult,
} from "@/lib/types";

/**
 * Debounced AI proofreader hook.
 *
 * Calls `POST /admin/articles/{id}/proofread` after the user stops editing
 * for `delayMs`. The hook is idle until the text reaches `minChars` (titles
 * fire faster than bodies) — avoids noisy calls while typing a 4-word draft.
 *
 * Cancels in-flight calls when the input changes again (race-safe).
 * The backend caches identical inputs 24 h, so re-evaluations are free.
 */
export interface UseProofreaderArgs {
  articleId: number;
  text: string;
  lang: ProofreadLang;
  field: ProofreadField;
  delayMs?: number;
  minChars?: number;
  enabled?: boolean;
}

export interface UseProofreaderState {
  result: ProofreadResult | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useProofreader({
  articleId,
  text,
  lang,
  field,
  delayMs = 2000,
  minChars = 8,
  enabled = true,
}: UseProofreaderArgs): UseProofreaderState {
  const [rawResult, setRawResult] = React.useState<ProofreadResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [nonce, setNonce] = React.useState(0);

  const trimmedLen = text.trim().length;
  const tooShort = trimmedLen < minChars;
  const active = enabled && !tooShort;

  React.useEffect(() => {
    if (!active) return;

    const aborter = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      adminApi
        .post<ProofreadResult>(
          `/articles/${articleId}/proofread`,
          { text, lang, field },
          { signal: aborter.signal },
        )
        .then((r) => setRawResult(r))
        .catch((err: unknown) => {
          if (aborter.signal.aborted) return;
          const message = err instanceof Error ? err.message : "Unknown error";
          setError(message);
        })
        .finally(() => {
          if (!aborter.signal.aborted) setLoading(false);
        });
    }, delayMs);

    return () => {
      clearTimeout(timer);
      aborter.abort();
    };
  }, [articleId, text, lang, field, delayMs, active, nonce]);

  const refetch = React.useCallback(() => setNonce((n) => n + 1), []);

  // Derive the visible result instead of clearing state inside the effect —
  // when the input drops below the threshold, simply hide the stale result
  // without writing to state during render.
  const result = tooShort ? null : rawResult;
  const visibleError = tooShort ? null : error;

  return { result, loading, error: visibleError, refetch };
}
