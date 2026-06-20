"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { adminApi } from "@/lib/api-client";

// --- Types (mirror backend app/schemas/ere_dashboard.py) ---
interface Overview {
  total: number;
  selected: number;
  deferred: number;
  selected_pct: number;
  deferred_pct: number;
  avg_score: number;
  max_score: number;
  min_score: number;
  last_scored: string | null;
  model: string;
}
interface HistogramBin {
  bin: number;
  low: number;
  high: number;
  count: number;
}
interface ScoreBucket {
  bucket: string;
  count: number;
}
interface Distribution {
  histogram: HistogramBin[];
  buckets: ScoreBucket[];
  threshold: number;
}
interface EreArticle {
  id: number;
  title: string;
  source: string;
  score: number;
  decision: string;
  category: string;
  actors: number;
  computed_at: string | null;
}
interface ArticleList {
  data: EreArticle[];
  next_cursor: string | null;
}
interface Category {
  category: string;
  count: number;
  selected_pct: number;
  avg_score: number;
}
interface SourceRow {
  source: string;
  total: number;
  selected: number;
  deferred: number;
  avg_score: number;
}
interface PauseFlag {
  active: boolean;
  reason: string | null;
  tripped_at: string | null;
  ttl_seconds: number | null;
}
interface SpendGuard {
  today_spend_usd: string;
  month_spend_usd: string;
  daily_cap_usd: string;
  monthly_cap_usd: string;
  budget_pause: PauseFlag;
  emergency_pause: PauseFlag;
  next_auto_resume: string | null;
}
interface AuditQueueItem {
  id: number;
  title: string;
  source: string;
  score: number;
  decision: string;
  category: string;
  breakdown: Record<string, unknown>;
}
interface AuditMetrics {
  audited: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number;
  recall: number;
}

const CARD = "rounded-lg border border-slate-200 bg-white p-4 shadow-sm";
const TH = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-slate-500";
const TD = "px-3 py-2 text-sm text-slate-700";

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

function DecisionBadge({ decision }: { decision: string }): React.ReactElement {
  return (
    <Badge variant={decision === "selected" ? "success" : "muted"}>{decision}</Badge>
  );
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }): React.ReactElement {
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

function ArticleTable({
  rows,
  showActors = true,
}: {
  rows: EreArticle[];
  showActors?: boolean;
}): React.ReactElement {
  if (rows.length === 0) {
    return <p className="px-3 py-4 text-sm text-slate-500">Aucun article.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-slate-50">
          <tr>
            <th className={TH}>ID</th>
            <th className={TH}>Title</th>
            <th className={TH}>Source</th>
            <th className={TH}>Score</th>
            <th className={TH}>Decision</th>
            <th className={TH}>Category</th>
            {showActors ? <th className={TH}>Actors</th> : null}
            <th className={TH}>Computed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              <td className={TD}>{r.id}</td>
              <td className={`${TD} max-w-md truncate`} title={r.title}>
                {r.title}
              </td>
              <td className={TD}>{r.source}</td>
              <td className={`${TD} font-semibold`}>{r.score}</td>
              <td className={TD}>
                <DecisionBadge decision={r.decision} />
              </td>
              <td className={TD}>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                  {r.category}
                </span>
              </td>
              {showActors ? <td className={TD}>{r.actors}</td> : null}
              <td className={`${TD} text-xs text-slate-400`}>
                {r.computed_at ? r.computed_at.slice(0, 16).replace("T", " ") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function useEre<T>(key: string, path: string, intervalMs?: number) {
  return useQuery({
    queryKey: ["ere", key],
    queryFn: () => adminApi.get<T>(path),
    refetchInterval: intervalMs,
  });
}

export default function EreDashboard(): React.ReactElement {
  // Filters for the Selected / Deferred explorer tables.
  const [source, setSource] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [scoreMin, setScoreMin] = React.useState("0");
  const [scoreMax, setScoreMax] = React.useState("100");

  const filterQs = React.useMemo(() => {
    const p = new URLSearchParams();
    if (source) p.set("source", source);
    if (category) p.set("category", category);
    p.set("score_min", scoreMin || "0");
    p.set("score_max", scoreMax || "100");
    return p.toString();
  }, [source, category, scoreMin, scoreMax]);

  const overview = useEre<Overview>("overview", "/ere/overview");
  const distribution = useEre<Distribution>("distribution", "/ere/distribution");
  const categories = useEre<{ data: Category[] }>("categories", "/ere/categories");
  const sources = useEre<{ data: SourceRow[] }>("sources", "/ere/sources");
  const spend = useEre<SpendGuard>("spendguard", "/ere/spendguard", 60_000);
  const selected = useEre<ArticleList>(
    `selected-${filterQs}`,
    `/ere/articles?decision=selected&limit=50&${filterQs}`,
  );
  const deferred = useEre<ArticleList>(
    `deferred-${filterQs}`,
    `/ere/articles?decision=deferred&limit=50&${filterQs}`,
  );
  const borderline = useEre<ArticleList>(
    "borderline",
    "/ere/articles?score_min=50&score_max=60&limit=100",
  );

  // --- Human Audit V1 (writes only into editorial_audits) ---
  const qc = useQueryClient();
  const auditQueue = useEre<{ data: AuditQueueItem[]; next_cursor: string | null }>(
    "audit-queue",
    "/ere/audit/queue?limit=20",
  );
  const auditMetrics = useEre<AuditMetrics>("audit-metrics", "/ere/audit/metrics");
  const [auditNotes, setAuditNotes] = React.useState("");
  const verdictMutation = useMutation({
    mutationFn: (vars: { article_id: number; human_verdict: "KEEP" | "REJECT"; notes: string }) =>
      adminApi.post("/ere/audit/verdict", vars),
    onSuccess: () => {
      setAuditNotes("");
      void qc.invalidateQueries({ queryKey: ["ere", "audit-queue"] });
      void qc.invalidateQueries({ queryKey: ["ere", "audit-metrics"] });
    },
  });
  const currentAudit = auditQueue.data?.data[0];
  const submitVerdict = (verdict: "KEEP" | "REJECT") => {
    if (!currentAudit) return;
    verdictMutation.mutate({ article_id: currentAudit.id, human_verdict: verdict, notes: auditNotes });
  };

  const histMax = Math.max(1, ...(distribution.data?.histogram.map((h) => h.count) ?? [1]));
  const bucketMax = Math.max(1, ...(distribution.data?.buckets.map((b) => b.count) ?? [1]));
  const catMax = Math.max(1, ...(categories.data?.data.map((c) => c.count) ?? [1]));
  const topSelected = (selected.data?.data ?? []).slice(0, 25);

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            ERE v1.1 — Shadow Observability
          </h1>
          <p className="text-sm text-slate-500">
            Read-only. Importance model{" "}
            <span className="font-mono">{overview.data?.model ?? "v1_1"}</span>. No enforce, no
            auto-publish.
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="warning">SHADOW</Badge>
          <Badge variant="muted">enforce OFF</Badge>
        </div>
      </header>

      {/* §1 Executive Overview */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          1 · Executive Overview
        </h2>
        {overview.isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        ) : overview.data ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total scored" value={overview.data.total} />
            <StatCard
              label="Selected"
              value={`${overview.data.selected} (${fmtPct(overview.data.selected_pct)})`}
            />
            <StatCard
              label="Deferred"
              value={`${overview.data.deferred} (${fmtPct(overview.data.deferred_pct)})`}
            />
            <StatCard label="Avg score" value={overview.data.avg_score} />
            <StatCard
              label="Min / Max"
              value={`${overview.data.min_score} / ${overview.data.max_score}`}
            />
            <StatCard
              label="Last scored"
              value={
                <span className="text-sm font-medium">
                  {overview.data.last_scored?.slice(0, 16).replace("T", " ") ?? "—"}
                </span>
              }
            />
            <StatCard label="Model" value={<span className="font-mono text-lg">{overview.data.model}</span>} />
          </div>
        ) : (
          <p className="text-sm text-red-600">Erreur de chargement.</p>
        )}
      </section>

      {/* Human Audit V1 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-indigo-600">
          ✍️ Human Audit — review ERE shadow decisions
        </h2>
        {auditMetrics.data ? (
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Audited" value={auditMetrics.data.audited} />
            <StatCard label="Precision" value={fmtPct(auditMetrics.data.precision * 100)} />
            <StatCard label="Recall" value={fmtPct(auditMetrics.data.recall * 100)} />
            <StatCard label="False positives" value={auditMetrics.data.fp} />
            <StatCard label="False negatives" value={auditMetrics.data.fn} />
          </div>
        ) : null}

        {auditQueue.isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        ) : currentAudit ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                <span className="truncate" title={currentAudit.title}>
                  {currentAudit.title}
                </span>
                <span className="ms-3 shrink-0 text-sm font-normal text-slate-500">
                  {auditQueue.data?.data.length ?? 0} in queue
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-slate-500">{currentAudit.source}</span>
                <span className="font-semibold">score {currentAudit.score}</span>
                <DecisionBadge decision={currentAudit.decision} />
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                  {currentAudit.category}
                </span>
              </div>
              <details className="text-xs">
                <summary className="cursor-pointer text-slate-500">Score breakdown</summary>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                  {JSON.stringify(currentAudit.breakdown, null, 2)}
                </pre>
              </details>
              <textarea
                className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                rows={2}
                placeholder="Notes (optional)…"
                value={auditNotes}
                onChange={(e) => setAuditNotes(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  className="bg-emerald-600 text-white hover:bg-emerald-700"
                  disabled={verdictMutation.isPending}
                  onClick={() => submitVerdict("KEEP")}
                >
                  KEEP
                </Button>
                <Button
                  variant="destructive"
                  disabled={verdictMutation.isPending}
                  onClick={() => submitVerdict("REJECT")}
                >
                  REJECT
                </Button>
                {verdictMutation.isError ? (
                  <span className="self-center text-sm text-red-600">
                    Save failed — retry.
                  </span>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
            ✅ Queue empty — all scored articles have been audited.
          </div>
        )}
      </section>

      {/* §2 Score Distribution */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          2 · Score Distribution (threshold 55)
        </h2>
        {distribution.data ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className={CARD}>
              <div className="relative flex h-40 items-end gap-px">
                {distribution.data.histogram.map((h) => {
                  const isThreshold = h.low <= 55 && 55 < h.high;
                  return (
                    <div key={h.bin} className="flex flex-1 flex-col items-center justify-end" title={`${h.low}-${h.high}: ${h.count}`}>
                      <div
                        className={`w-full rounded-t-sm ${isThreshold ? "bg-amber-500" : "bg-blue-500"}`}
                        style={{ height: `${Math.max(2, (h.count / histMax) * 100)}%` }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-slate-400">
                <span>0</span>
                <span>← 55 →</span>
                <span>100</span>
              </div>
            </div>
            <div className={CARD}>
              <div className="space-y-2">
                {distribution.data.buckets.map((b) => {
                  const cross = b.bucket === "55-69" || b.bucket === "70-84" || b.bucket === "85-100";
                  return (
                    <div key={b.bucket} className="flex items-center gap-2 text-xs">
                      <span className="w-14 text-slate-500">{b.bucket}</span>
                      <div className="h-3 flex-1 rounded bg-slate-100">
                        <div
                          className={`h-3 rounded ${cross ? "bg-emerald-500" : "bg-slate-400"}`}
                          style={{ width: `${(b.count / bucketMax) * 100}%` }}
                        />
                      </div>
                      <span className="w-8 text-right font-medium text-slate-600">{b.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        )}
      </section>

      {/* §10 SpendGuard (read-only widgets) */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          10 · SpendGuard (read-only)
        </h2>
        {spend.data ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
            <StatCard label="Today" value={`$${Number(spend.data.today_spend_usd).toFixed(2)}`} />
            <StatCard label="Daily cap" value={`$${Number(spend.data.daily_cap_usd).toFixed(2)}`} />
            <StatCard label="Month" value={`$${Number(spend.data.month_spend_usd).toFixed(2)}`} />
            <StatCard label="Monthly cap" value={`$${Number(spend.data.monthly_cap_usd).toFixed(2)}`} />
            <div className={CARD}>
              <div className="text-xs font-medium uppercase tracking-wider text-slate-500">Budget pause</div>
              <div className="mt-1">
                {spend.data.budget_pause.active ? (
                  <Badge variant="warning">active</Badge>
                ) : (
                  <Badge variant="muted">clear</Badge>
                )}
              </div>
            </div>
            <div className={CARD}>
              <div className="text-xs font-medium uppercase tracking-wider text-slate-500">Emergency</div>
              <div className="mt-1">
                {spend.data.emergency_pause.active ? (
                  <Badge variant="destructive">active</Badge>
                ) : (
                  <Badge variant="muted">clear</Badge>
                )}
              </div>
            </div>
            {spend.data.next_auto_resume ? (
              <div className={`${CARD} col-span-2 md:col-span-4 lg:col-span-6`}>
                <span className="text-xs text-slate-500">Next auto-resume: </span>
                <span className="font-mono text-sm text-slate-700">
                  {spend.data.next_auto_resume.slice(0, 16).replace("T", " ")} UTC
                </span>
              </div>
            ) : null}
          </div>
        ) : (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        )}
      </section>

      {/* §5 Strategic Categories */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          5 · Strategic Categories
        </h2>
        {categories.data ? (
          <div className={CARD}>
            <div className="space-y-2">
              {categories.data.data.map((c) => (
                <div key={c.category} className="flex items-center gap-3 text-sm">
                  <span className="w-40 font-mono text-xs text-slate-600">{c.category}</span>
                  <div className="h-4 flex-1 rounded bg-slate-100">
                    <div
                      className="h-4 rounded bg-indigo-500"
                      style={{ width: `${(c.count / catMax) * 100}%` }}
                    />
                  </div>
                  <span className="w-12 text-right text-slate-500">n={c.count}</span>
                  <span className="w-20 text-right text-slate-500">sel {fmtPct(c.selected_pct)}</span>
                  <span className="w-16 text-right text-slate-500">avg {c.avg_score}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        )}
      </section>

      {/* §6 Sources Performance */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          6 · Sources Performance
        </h2>
        <Card>
          <CardContent className="p-0">
            {sources.data ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className={TH}>Source</th>
                      <th className={TH}>Total</th>
                      <th className={TH}>Selected</th>
                      <th className={TH}>Deferred</th>
                      <th className={TH}>Avg score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sources.data.data.map((s) => (
                      <tr key={s.source} className="hover:bg-slate-50">
                        <td className={TD}>{s.source}</td>
                        <td className={TD}>{s.total}</td>
                        <td className={TD}>{s.selected}</td>
                        <td className={TD}>{s.deferred}</td>
                        <td className={`${TD} font-semibold`}>{s.avg_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Loader2 className="m-4 h-5 w-5 animate-spin text-slate-400" />
            )}
          </CardContent>
        </Card>
      </section>

      {/* §8 Borderline 50-60 */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-amber-600">
          8 · ⭐ Borderline Zone (50–60) — calibration candidates
        </h2>
        <Card>
          <CardContent className="p-0">
            {borderline.data ? <ArticleTable rows={borderline.data.data} /> : null}
          </CardContent>
        </Card>
      </section>

      {/* §7 Top Selected */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          7 · Top Selected (25)
        </h2>
        <Card>
          <CardContent className="p-0">
            <ArticleTable rows={topSelected} showActors={false} />
          </CardContent>
        </Card>
      </section>

      {/* Filters + §3/§4 tables */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          3 / 4 · Selected & Deferred (filtered)
        </h2>
        <div className={`${CARD} mb-3 flex flex-wrap items-end gap-3`}>
          <label className="text-xs text-slate-500">
            Source
            <select
              className="mt-1 block rounded border border-slate-300 px-2 py-1 text-sm"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="">All</option>
              {(sources.data?.data ?? []).map((s) => (
                <option key={s.source} value={s.source}>
                  {s.source}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Category
            <select
              className="mt-1 block rounded border border-slate-300 px-2 py-1 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All</option>
              {(categories.data?.data ?? []).map((c) => (
                <option key={c.category} value={c.category}>
                  {c.category}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500">
            Score min
            <input
              type="number"
              className="mt-1 block w-20 rounded border border-slate-300 px-2 py-1 text-sm"
              value={scoreMin}
              onChange={(e) => setScoreMin(e.target.value)}
            />
          </label>
          <label className="text-xs text-slate-500">
            Score max
            <input
              type="number"
              className="mt-1 block w-20 rounded border border-slate-300 px-2 py-1 text-sm"
              value={scoreMax}
              onChange={(e) => setScoreMax(e.target.value)}
            />
          </label>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Selected ({selected.data?.data.length ?? 0})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {selected.data ? <ArticleTable rows={selected.data.data} /> : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Deferred ({deferred.data?.data.length ?? 0})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {deferred.data ? <ArticleTable rows={deferred.data.data} /> : null}
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Coming Soon */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Coming Soon
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {["Precision tracking", "Recall tracking", "Enforce mode", "Auto-publish"].map(
            (label) => (
              <div
                key={label}
                className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center text-sm text-slate-400"
              >
                {label}
                <div className="mt-1 text-[10px] uppercase tracking-wider">Coming soon</div>
              </div>
            ),
          )}
        </div>
      </section>
    </div>
  );
}
