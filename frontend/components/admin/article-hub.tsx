"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { EreAuditActions } from "@/components/admin/ere-audit-actions";
import { StatusBadge } from "@/components/admin/status-badge";
import { adminApi } from "@/lib/api-client";
import { stripBdi } from "@/lib/bidi";
import type { AdminArticlesListResponse } from "@/lib/types";

// Catalogue mode of the editorial hub: browse EVERY article (draft + published)
// and act on any of them — articles no longer "disappear" once audited/published.
// Read endpoints only here (GET /admin/articles); all writes go through the
// reused EreAuditActions panel. No ranking / ERE state is touched.

type Filter = "all" | "drafts" | "ready" | "published";

const CHIPS: { id: Filter; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "drafts", label: "Brouillons" },
  { id: "ready", label: "Prêts" },
  { id: "published", label: "Publiés" },
];

export function ArticleHub(): React.ReactElement {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [selectedId, setSelectedId] = React.useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-articles-hub", filter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "100" });
      // Backend filters on is_published only; "ready" is is_published=false +
      // a client-side flag filter below.
      if (filter === "drafts" || filter === "ready") params.set("is_published", "false");
      if (filter === "published") params.set("is_published", "true");
      return adminApi.get<AdminArticlesListResponse>(`/articles?${params.toString()}`);
    },
  });

  const counts = data?.counts;
  const items = React.useMemo(() => {
    const all = data?.items ?? [];
    return filter === "ready" ? all.filter((a) => a.proofread_ready_to_publish) : all;
  }, [data, filter]);

  const countFor = (f: Filter): number | null => {
    if (!counts) return null;
    if (f === "all") return counts.all;
    if (f === "drafts") return counts.drafts;
    if (f === "ready") return counts.ready;
    return counts.published;
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {CHIPS.map((c) => {
          const n = countFor(c.id);
          const active = filter === c.id;
          return (
            <button
              key={c.id}
              onClick={() => setFilter(c.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                active
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {c.label}
              {n !== null ? ` ${n}` : ""}
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Left: article list */}
        <div className="lg:col-span-4">
          <div className="max-h-[34rem] space-y-1 overflow-auto rounded-md border border-slate-200 p-2">
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            ) : items.length === 0 ? (
              <p className="p-2 text-sm text-slate-400">Aucun article.</p>
            ) : (
              items.map((a) => {
                const active = a.id === selectedId;
                return (
                  <button
                    key={a.id}
                    onClick={() => setSelectedId(a.id)}
                    className={`flex w-full items-center gap-2 rounded p-1.5 text-start ${
                      active ? "bg-indigo-50 ring-1 ring-indigo-200" : "hover:bg-slate-50"
                    }`}
                  >
                    {a.hero_image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={a.hero_image_url}
                        alt=""
                        className="h-10 w-10 flex-shrink-0 rounded object-cover"
                      />
                    ) : (
                      <div className="h-10 w-10 flex-shrink-0 rounded bg-slate-100" />
                    )}
                    <span
                      dir="rtl"
                      className="flex-1 truncate text-xs font-medium text-slate-700"
                    >
                      {stripBdi(a.title_darija)}
                    </span>
                    <StatusBadge isPublished={a.is_published} />
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right: preview + actions for the selected article */}
        <div className="lg:col-span-8">
          {selectedId === null ? (
            <div className="flex h-full min-h-[12rem] items-center justify-center rounded-md border border-dashed border-slate-200 text-sm text-slate-400">
              Sélectionnez un article pour le gérer.
            </div>
          ) : (
            <EreAuditActions key={selectedId} articleId={selectedId} variant="catalogue" />
          )}
        </div>
      </div>
    </div>
  );
}
