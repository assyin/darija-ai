"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BarChart3,
  CheckCircle2,
  Cpu,
  DollarSign,
  FileText,
  HeartPulse,
  Languages,
  Loader2,
  Minus,
  Rss,
  Send,
  Settings as SettingsIcon,
  ShieldCheck,
  UserCheck,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api-client";

// Production Health — READ-ONLY Operations Center. Same design system as the ERE
// dashboard (light slate cards, Badge status variants). No actions, no controls,
// no buttons: this page only OBSERVES. Mirrors backend app/schemas/health_dashboard.py.

// --- Types (mirror backend app/schemas/health_dashboard.py) ---
type HealthState = "healthy" | "warning" | "critical";
type TrendDirection = "up" | "down" | "stable";

interface OverallStatus {
  state: HealthState;
  title: string;
  detail: string;
}
interface PipelineStage {
  key: string;
  name: string;
  state: HealthState;
  description: string;
  reason: string | null;
}
interface FlowNode {
  key: string;
  name: string;
  value: number;
  caption: string;
  state: HealthState | null;
}
interface ActivityItem {
  key: string;
  label: string;
  last_at: string | null;
  age_seconds: number | null;
  state: HealthState;
}
interface Trend {
  key: string;
  label: string;
  current: number;
  previous: number;
  delta: number;
  direction: TrendDirection;
  basis: string;
}
interface RecentError {
  stage: string;
  provider: string | null;
  message: string;
  at: string;
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
interface QueueCounts {
  pending: number;
  processing: number;
  failed: number;
  rejected: number;
  draft: number;
  published: number;
}
interface ProductionHealth {
  generated_at: string;
  overall: OverallStatus;
  pipeline: PipelineStage[];
  flow: FlowNode[];
  activity: ActivityItem[];
  trends: Trend[];
  trends_unavailable: string[];
  recent_errors: RecentError[];
  spendguard: SpendGuard;
  queues: QueueCounts;
}

const CARD = "rounded-lg border border-slate-200 bg-white p-4 shadow-sm";

const STAGE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  rss_fetch: Rss,
  pending: Cpu,
  ai_processing: Cpu,
  translation: Languages,
  editorial_ranking: BarChart3,
  human_audit: UserCheck,
  draft: FileText,
  published: Send,
  spendguard: ShieldCheck,
};

const STATE_LABEL: Record<HealthState, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
};
const STATE_RING: Record<HealthState, string> = {
  healthy: "ring-1 ring-emerald-200",
  warning: "ring-1 ring-amber-200",
  critical: "ring-1 ring-red-300",
};
const STATE_TEXT: Record<HealthState, string> = {
  healthy: "text-emerald-700",
  warning: "text-amber-700",
  critical: "text-red-700",
};

function HealthBadge({ state }: { state: HealthState }): React.ReactElement {
  const variant = state === "healthy" ? "success" : state === "warning" ? "warning" : "destructive";
  // Text label + variant (not color-only) for accessibility.
  return <Badge variant={variant}>{STATE_LABEL[state]}</Badge>;
}

/** "3 minutes ago" / "2 hours ago" / "22 days ago" — never seen → "jamais". */
function formatAge(seconds: number | null): string {
  if (seconds === null) return "jamais";
  if (seconds < 60) return "à l'instant";
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins} minute${mins > 1 ? "s" : ""} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

function fmtTs(iso: string | null): string {
  return iso ? iso.slice(0, 16).replace("T", " ") : "—";
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }): React.ReactElement {
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
      {children}
    </h2>
  );
}

const BANNER: Record<
  HealthState,
  { cls: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  healthy: { cls: "border-emerald-300 bg-emerald-50 text-emerald-900", Icon: CheckCircle2 },
  warning: { cls: "border-amber-300 bg-amber-50 text-amber-900", Icon: AlertTriangle },
  critical: { cls: "border-red-300 bg-red-50 text-red-900", Icon: XCircle },
};

function Banner({
  overall,
  snapshot,
}: {
  overall: OverallStatus;
  snapshot: string;
}): React.ReactElement {
  const { cls, Icon } = BANNER[overall.state];
  return (
    <div className={`flex items-start gap-3 rounded-lg border px-5 py-4 ${cls}`} role="status">
      <Icon className="mt-0.5 h-6 w-6 shrink-0" />
      <div>
        <div className="text-lg font-bold">{overall.title}</div>
        <p className="text-sm">{overall.detail}</p>
        <p className="mt-1 text-xs opacity-70">Snapshot : {fmtTs(snapshot)}</p>
      </div>
    </div>
  );
}

const TREND_ICON: Record<TrendDirection, React.ComponentType<{ className?: string }>> = {
  up: ArrowUp,
  down: ArrowDown,
  stable: Minus,
};
const TREND_SIGN: Record<TrendDirection, string> = { up: "↑", down: "↓", stable: "=" };
const TREND_COLOR: Record<TrendDirection, string> = {
  up: "text-emerald-700",
  down: "text-amber-700",
  stable: "text-slate-500",
};

function TrendCard({ t }: { t: Trend }): React.ReactElement {
  const Icon = TREND_ICON[t.direction];
  const sign = t.delta > 0 ? "+" : "";
  return (
    <div className={CARD}>
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{t.label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-slate-900">{t.current}</span>
        <span className={`flex items-center gap-0.5 text-sm font-semibold ${TREND_COLOR[t.direction]}`}>
          <Icon className="h-4 w-4" aria-hidden />
          <span aria-label={`${t.direction} ${sign}${t.delta}`}>
            {TREND_SIGN[t.direction]} {sign}
            {t.delta}
          </span>
        </span>
      </div>
      <div className="mt-0.5 text-xs text-slate-400">vs {t.previous} (24 h précédentes)</div>
    </div>
  );
}

function useHealth() {
  return useQuery({
    queryKey: ["health", "production"],
    queryFn: () => adminApi.get<ProductionHealth>("/health"),
    refetchInterval: 60_000,
  });
}

const NAV_LINKS: { href: string; label: string; icon: React.ComponentType<{ className?: string }> }[] =
  [
    { href: "/admin/ere", label: "ERE Dashboard", icon: BarChart3 },
    { href: "/admin/ere", label: "Human Audit", icon: UserCheck },
    { href: "/admin/articles", label: "Articles / Drafts", icon: FileText },
    { href: "/admin/costs", label: "AI Costs", icon: DollarSign },
    { href: "/admin/settings", label: "Settings", icon: SettingsIcon },
  ];

export default function HealthDashboard(): React.ReactElement {
  const { data, isLoading, isError, error } = useHealth();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        Chargement de l&apos;état de la plateforme…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        Erreur de chargement: {error instanceof Error ? error.message : "inconnue"}
      </p>
    );
  }

  const sg = data.spendguard;
  const sgState: HealthState = sg.emergency_pause.active
    ? "critical"
    : sg.budget_pause.active
      ? "warning"
      : "healthy";
  const sgCurrent = sg.emergency_pause.active
    ? "Emergency Pause"
    : sg.budget_pause.active
      ? "Budget Pause"
      : "Running";
  const pauseReason = sg.emergency_pause.reason ?? sg.budget_pause.reason ?? "—";

  return (
    <div className="space-y-8">
      <header>
        <div className="flex items-center gap-2">
          <HeartPulse className="h-7 w-7 text-[var(--color-primary)]" />
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Production Health</h1>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Centre d&apos;opérations — lecture seule. Rafraîchi chaque minute.
        </p>
      </header>

      {/* Global platform status banner */}
      <Banner overall={data.overall} snapshot={data.generated_at} />

      {/* Pipeline Flow — spot the blockage at a glance */}
      <section>
        <SectionTitle>Pipeline Flow</SectionTitle>
        <div className="flex items-stretch gap-2 overflow-x-auto pb-2">
          {data.flow.map((n, i) => {
            const Icon = STAGE_ICONS[n.key] ?? Activity;
            return (
              <React.Fragment key={n.key}>
                <div
                  className={`min-w-[7.5rem] flex-1 rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm ${
                    n.state ? STATE_RING[n.state] : ""
                  }`}
                >
                  <Icon className="mx-auto h-4 w-4 text-slate-400" />
                  <div className="mt-1 text-xs font-medium text-slate-600">{n.name}</div>
                  <div className="text-xl font-bold text-slate-900">{n.value}</div>
                  <div className="text-[10px] text-slate-400">{n.caption}</div>
                </div>
                {i < data.flow.length - 1 ? (
                  <ArrowRight className="my-auto h-4 w-4 shrink-0 text-slate-300" aria-hidden />
                ) : null}
              </React.Fragment>
            );
          })}
        </div>
      </section>

      {/* SECTION 1 — Pipeline Status */}
      <section>
        <SectionTitle>Pipeline Status</SectionTitle>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.pipeline.map((stage) => {
            const Icon = STAGE_ICONS[stage.key] ?? Activity;
            return (
              <div key={stage.key} className={`${CARD} ${STATE_RING[stage.state]}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-slate-500" />
                    <span className="font-semibold text-slate-900">{stage.name}</span>
                  </div>
                  <HealthBadge state={stage.state} />
                </div>
                <p className="mt-2 text-xs text-slate-500">{stage.description}</p>
                {stage.reason ? (
                  <p className={`mt-1 text-xs font-medium ${STATE_TEXT[stage.state]}`}>
                    {stage.reason}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      {/* Queue Trends (honest throughput only) */}
      <section>
        <SectionTitle>Queue Trends (24 h)</SectionTitle>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.trends.map((t) => (
            <TrendCard key={t.key} t={t} />
          ))}
        </div>
        {data.trends_unavailable.length > 0 ? (
          <p className="mt-2 text-xs text-slate-400">
            Pas d&apos;historique 24 h fiable pour les profondeurs de file (
            {data.trends_unavailable.join(", ")}) — aucun delta trompeur n&apos;est affiché.
            Nécessiterait une table de snapshots (hors périmètre).
          </p>
        ) : null}
      </section>

      {/* SECTION 2 — Last Activity */}
      <section>
        <SectionTitle>Last Activity</SectionTitle>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.activity.map((a) => {
            const Icon = STAGE_ICONS[a.key] ?? Activity;
            return (
              <div key={a.key} className={CARD}>
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-slate-400" />
                  <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    {a.label}
                  </span>
                </div>
                <div className={`mt-1 text-lg font-bold ${STATE_TEXT[a.state]}`}>
                  {formatAge(a.age_seconds)}
                </div>
                <div className="mt-0.5 text-xs text-slate-400">{fmtTs(a.last_at)}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* SECTION 3 — SpendGuard Status */}
      <section>
        <SectionTitle>SpendGuard Status</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          <div className={`${CARD} ${STATE_RING[sgState]}`}>
            <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Current State
            </div>
            <div className={`mt-1 text-lg font-bold ${STATE_TEXT[sgState]}`}>{sgCurrent}</div>
          </div>
          <StatCard label="Today Spend" value={`$${Number(sg.today_spend_usd).toFixed(4)}`} />
          <StatCard label="Month Spend" value={`$${Number(sg.month_spend_usd).toFixed(2)}`} />
          <StatCard label="Daily Cap" value={`$${Number(sg.daily_cap_usd).toFixed(2)}`} />
          <StatCard label="Monthly Cap" value={`$${Number(sg.monthly_cap_usd).toFixed(2)}`} />
          <div className={CARD}>
            <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Pause Reason
            </div>
            <div className="mt-1 text-sm font-semibold text-slate-700">{pauseReason}</div>
          </div>
          <div className={CARD}>
            <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Next Auto Resume
            </div>
            <div className="mt-1 text-sm font-semibold text-slate-700">
              {fmtTs(sg.next_auto_resume)}
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 4 — Processing Queues */}
      <section>
        <SectionTitle>Processing Queues</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <StatCard label="Pending" value={data.queues.pending} />
          <StatCard label="Processing" value={data.queues.processing} />
          <StatCard label="Failed" value={data.queues.failed} />
          <StatCard label="Rejected" value={data.queues.rejected} />
          <StatCard label="Draft" value={data.queues.draft} />
          <StatCard label="Published" value={data.queues.published} />
        </div>
      </section>

      {/* Last Relevant Error */}
      <section>
        <SectionTitle>Recent Error</SectionTitle>
        {data.recent_errors.length === 0 ? (
          <div className={`${CARD} text-sm text-slate-400`}>
            No recent structured error available.
          </div>
        ) : (
          <div className="space-y-2">
            {data.recent_errors.map((e, i) => (
              <div key={i} className={`${CARD} border-red-200`}>
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <Badge variant="destructive">{e.stage}</Badge>
                  {e.provider ? <span className="font-medium">{e.provider}</span> : null}
                  <span className="text-slate-400">{fmtTs(e.at)}</span>
                </div>
                <p className="mt-1 break-words font-mono text-xs text-red-700">{e.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Quick Navigation (read-only links) */}
      <section>
        <SectionTitle>Quick Navigation</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {NAV_LINKS.map((l) => {
            const Icon = l.icon;
            return (
              <Link
                key={l.label}
                href={l.href}
                className={`${CARD} flex items-center gap-2 transition-colors hover:bg-slate-50`}
              >
                <Icon className="h-4 w-4 text-slate-500" />
                <span className="text-sm font-medium text-slate-700">{l.label}</span>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
