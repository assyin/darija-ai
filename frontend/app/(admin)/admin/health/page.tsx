"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Cpu,
  HeartPulse,
  Languages,
  Loader2,
  Rss,
  Send,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/lib/api-client";

// Production Health — READ-ONLY whole-platform status. Same design system as the
// ERE dashboard (light slate cards, Badge status variants). No actions, no
// controls, no buttons: this page only OBSERVES. It mirrors the backend schema
// app/schemas/health_dashboard.py.

// --- Types (mirror backend app/schemas/health_dashboard.py) ---
type HealthState = "healthy" | "warning" | "critical";

interface PipelineStage {
  key: string;
  name: string;
  state: HealthState;
  description: string;
}
interface ActivityItem {
  key: string;
  label: string;
  last_at: string | null;
  age_seconds: number | null;
  state: HealthState;
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
  pipeline: PipelineStage[];
  activity: ActivityItem[];
  spendguard: SpendGuard;
  queues: QueueCounts;
}

const CARD = "rounded-lg border border-slate-200 bg-white p-4 shadow-sm";

// lucide icon per pipeline/activity stage — presentation lives on the frontend.
const STAGE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  rss_fetch: Rss,
  ai_processing: Cpu,
  translation: Languages,
  editorial_ranking: BarChart3,
  human_audit: UserCheck,
  publication: Send,
  spendguard: ShieldCheck,
};

const STATE_LABEL: Record<HealthState, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
};

// A left ring tint so a card's state reads at a glance (matches ERE color usage).
const STATE_RING: Record<HealthState, string> = {
  healthy: "ring-1 ring-emerald-200",
  warning: "ring-1 ring-amber-200",
  critical: "ring-1 ring-red-300",
};

function HealthBadge({ state }: { state: HealthState }): React.ReactElement {
  const variant = state === "healthy" ? "success" : state === "warning" ? "warning" : "destructive";
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

const STATE_TEXT: Record<HealthState, string> = {
  healthy: "text-emerald-700",
  warning: "text-amber-700",
  critical: "text-red-700",
};

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

function useHealth() {
  return useQuery({
    queryKey: ["health", "production"],
    queryFn: () => adminApi.get<ProductionHealth>("/health"),
    refetchInterval: 60_000,
  });
}

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
          État global de la plateforme — lecture seule. Généré à{" "}
          {data.generated_at.slice(0, 16).replace("T", " ")} · rafraîchi chaque minute.
        </p>
      </header>

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
              </div>
            );
          })}
        </div>
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
                <div className="mt-0.5 text-xs text-slate-400">
                  {a.last_at ? a.last_at.slice(0, 16).replace("T", " ") : "—"}
                </div>
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
              {sg.next_auto_resume
                ? sg.next_auto_resume.slice(0, 16).replace("T", " ")
                : "—"}
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
    </div>
  );
}
