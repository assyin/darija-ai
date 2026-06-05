"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";

// --- Types matching backend/app/schemas/ai_logs.py ---------------------------

interface WindowTotals {
  calls: number;
  cost_usd: string;
}
interface ProviderModelBreakdown {
  provider: string;
  model: string;
  calls: number;
  cost_usd: string;
}
interface DailyPoint {
  day: string;
  calls: number;
  cost_usd: string;
}
interface TopArticle {
  raw_article_id: number;
  calls: number;
  cost_usd: string;
}
interface FailureCount {
  provider: string;
  model: string;
  failures: number;
}
interface AiCostSummary {
  today: WindowTotals;
  last_7_days: WindowTotals;
  month_to_date: WindowTotals;
  monthly_cap_usd: string;
  daily_threshold_usd: string;
  by_provider_model: ProviderModelBreakdown[];
  daily_series: DailyPoint[];
  top_articles: TopArticle[];
  recent_failures: FailureCount[];
}

// --- Helpers -----------------------------------------------------------------

function fmtUsd(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(n)) return "$0.00";
  // Keep 4 decimals for small values, 2 for large — the cost dashboard mixes
  // single-call costs ($0.0001) with monthly totals ($30+).
  return n >= 1
    ? `$${n.toFixed(2)}`
    : `$${n.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}`;
}

function fmtDay(iso: string): string {
  // "2026-06-04" → "4/6"
  const [, m, d] = iso.split("-");
  return `${parseInt(d ?? "0", 10)}/${parseInt(m ?? "0", 10)}`;
}

const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude (Localizer + Translator)",
  openai: "OpenAI (Proofreader)",
  replicate: "Replicate (Images)",
};

// --- Page --------------------------------------------------------------------

export default function CostsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin-ai-logs-summary"],
    queryFn: () => adminApi.get<AiCostSummary>("/ai-logs/summary"),
    // Lightly polling — admin keeps the tab open, costs trickle in as
    // articles get processed.
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Chargement…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        Impossible de charger les coûts. {error instanceof Error ? error.message : ""}
      </div>
    );
  }

  const monthlyCap = parseFloat(data.monthly_cap_usd);
  const monthSpent = parseFloat(data.month_to_date.cost_usd);
  const monthlyPct = monthlyCap > 0 ? Math.min(100, (monthSpent / monthlyCap) * 100) : 0;
  const dailyThreshold = parseFloat(data.daily_threshold_usd);
  const todaySpend = parseFloat(data.today.cost_usd);
  const overThreshold = todaySpend > dailyThreshold;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Coûts IA</h1>
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Dépenses Anthropic, OpenAI et Replicate sur la pipeline éditoriale.
          Mis à jour en temps réel (refresh auto toutes les 60 s).
        </p>
      </header>

      {overThreshold && (
        <div className="flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <strong>Seuil quotidien dépassé.</strong>{" "}
            La dépense d&apos;aujourd&apos;hui ({fmtUsd(todaySpend)}) excède le seuil
            d&apos;alerte ({fmtUsd(dailyThreshold)}). Une notification Sentry a été
            émise par le cron horaire.
          </div>
        </div>
      )}

      {/* Window totals — 3 cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Aujourd'hui" amount={data.today.cost_usd} calls={data.today.calls} />
        <Card
          title="7 derniers jours"
          amount={data.last_7_days.cost_usd}
          calls={data.last_7_days.calls}
        />
        <Card
          title="Ce mois-ci"
          amount={data.month_to_date.cost_usd}
          calls={data.month_to_date.calls}
          extra={
            <div className="mt-3">
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cn(
                    "h-full transition-all",
                    monthlyPct >= 90
                      ? "bg-red-500"
                      : monthlyPct >= 60
                        ? "bg-amber-500"
                        : "bg-emerald-500",
                  )}
                  style={{ width: `${monthlyPct}%` }}
                />
              </div>
              <p className="mt-1.5 text-xs text-[var(--color-muted-foreground)]">
                {monthlyPct.toFixed(1)}% du plafond mensuel ({fmtUsd(monthlyCap)})
              </p>
            </div>
          }
        />
      </div>

      {/* By provider/model */}
      <section className="rounded-lg border border-[var(--color-border)] bg-white">
        <div className="border-b border-[var(--color-border)] bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Par modèle (30 derniers jours)
          </p>
        </div>
        {data.by_provider_model.length === 0 ? (
          <EmptyState text="Aucune dépense sur les 30 derniers jours." />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
              <tr>
                <th className="px-4 py-2.5">Modèle</th>
                <th className="px-4 py-2.5">Utilisation</th>
                <th className="px-4 py-2.5 text-right">Appels</th>
                <th className="px-4 py-2.5 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {data.by_provider_model.map((r) => (
                <tr key={`${r.provider}-${r.model}`} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{r.model}</td>
                  <td className="px-4 py-3 text-xs text-[var(--color-muted-foreground)]">
                    {PROVIDER_LABELS[r.provider] ?? r.provider}
                  </td>
                  <td className="px-4 py-3 text-right">{r.calls}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmtUsd(r.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Daily chart — pure CSS bars */}
      <section className="rounded-lg border border-[var(--color-border)] bg-white p-4">
        <div className="mb-4 flex items-baseline justify-between">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
            14 derniers jours
          </p>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            Seuil quotidien : {fmtUsd(dailyThreshold)}
          </p>
        </div>
        <DailyBars series={data.daily_series} threshold={dailyThreshold} />
      </section>

      {/* Two-column: top articles + failures */}
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border border-[var(--color-border)] bg-white">
          <div className="border-b border-[var(--color-border)] bg-slate-50 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
              Top 10 articles les plus chers (30 j)
            </p>
          </div>
          {data.top_articles.length === 0 ? (
            <EmptyState text="Aucun article avec attribution de coût récente." />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                <tr>
                  <th className="px-4 py-2.5">Article brut</th>
                  <th className="px-4 py-2.5 text-right">Appels</th>
                  <th className="px-4 py-2.5 text-right">Coût</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {data.top_articles.map((a) => (
                  <tr key={a.raw_article_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">
                      #{a.raw_article_id}
                    </td>
                    <td className="px-4 py-3 text-right">{a.calls}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      {fmtUsd(a.cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="rounded-lg border border-[var(--color-border)] bg-white">
          <div className="border-b border-[var(--color-border)] bg-slate-50 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
              Échecs (7 derniers jours)
            </p>
          </div>
          {data.recent_failures.length === 0 ? (
            <EmptyState text="Aucun échec d'appel IA sur les 7 derniers jours. ✅" />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                <tr>
                  <th className="px-4 py-2.5">Provider</th>
                  <th className="px-4 py-2.5">Modèle</th>
                  <th className="px-4 py-2.5 text-right">Échecs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {data.recent_failures.map((f) => (
                  <tr key={`${f.provider}-${f.model}`} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Badge variant="warning">{f.provider}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{f.model}</td>
                    <td className="px-4 py-3 text-right font-medium">{f.failures}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <p className="text-xs text-[var(--color-muted-foreground)]">
        Source des données : table <code className="rounded bg-slate-100 px-1.5 py-0.5">ai_logs</code>
        — peuplée à partir du 4 juin 2026 (PR #22). Pas d&apos;historique antérieur.
        Voir{" "}
        <Link
          href="/admin/articles"
          className="text-[var(--color-primary)] underline"
        >
          articles
        </Link>{" "}
        pour le détail éditorial.
      </p>
    </div>
  );
}

// --- Subcomponents -----------------------------------------------------------

function Card({
  title,
  amount,
  calls,
  extra,
}: {
  title: string;
  amount: string;
  calls: number;
  extra?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
        {title}
      </p>
      <p className="mt-2 text-3xl font-bold tracking-tight">{fmtUsd(amount)}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
        {calls} appel{calls === 1 ? "" : "s"} IA
      </p>
      {extra}
    </div>
  );
}

function DailyBars({
  series,
  threshold,
}: {
  series: DailyPoint[];
  threshold: number;
}) {
  // Chart height in px; min 1px so even zero-cost days remain visible as a sliver.
  const heights = series.map((p) => parseFloat(p.cost_usd));
  const max = Math.max(threshold, ...heights, 0.01);
  return (
    <div className="relative">
      {/* Threshold line */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 border-t border-dashed border-amber-400"
        style={{ top: `${(1 - threshold / max) * 100}%` }}
      />
      <div className="flex h-32 items-end gap-1">
        {series.map((p) => {
          const h = parseFloat(p.cost_usd);
          const pct = max > 0 ? (h / max) * 100 : 0;
          const over = h > threshold;
          return (
            <div
              key={p.day}
              className="flex flex-1 flex-col items-center justify-end"
              title={`${p.day} — ${fmtUsd(p.cost_usd)} (${p.calls} appels)`}
            >
              <div
                className={cn(
                  "w-full rounded-t-sm transition-colors",
                  over ? "bg-amber-500" : "bg-[var(--color-primary)]",
                )}
                style={{ height: `${Math.max(2, pct)}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-1">
        {series.map((p) => (
          <div
            key={p.day}
            className="flex-1 text-center text-[10px] text-[var(--color-muted-foreground)]"
          >
            {fmtDay(p.day)}
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="px-4 py-8 text-center text-xs text-[var(--color-muted-foreground)]">
      {text}
    </div>
  );
}
