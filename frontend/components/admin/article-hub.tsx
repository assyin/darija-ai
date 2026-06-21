"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";

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
type Sort = "recent" | "score" | "status";

const CHIPS: { id: Filter; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "drafts", label: "Brouillons" },
  { id: "ready", label: "Prêts" },
  { id: "published", label: "Publiés" },
];

const SORTS: { id: Sort; label: string }[] = [
  { id: "recent", label: "Récent" },
  { id: "score", label: "Score ERE" },
  { id: "status", label: "Statut" },
];

export function ArticleHub(): React.ReactElement {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [sort, setSort] = React.useState<Sort>("recent");
  const [search, setSearch] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<number | null>(null);

  // Debounce the search box so we don't hit the API on every keystroke.
  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-articles-hub", filter, sort, debouncedSearch],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "100", sort });
      // Backend filters on is_published only; "ready" is is_published=false +
      // a client-side flag filter below.
      if (filter === "drafts" || filter === "ready") params.set("is_published", "false");
      if (filter === "published") params.set("is_published", "true");
      if (debouncedSearch) params.set("q", debouncedSearch);
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

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute inset-y-0 start-2 my-auto h-4 w-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher titre / source…"
            className="w-full rounded-md border border-slate-300 py-1.5 ps-8 pe-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          Tri
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700"
          >
            {SORTS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
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
                    {a.editorial_score !== null ? (
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          a.editorial_score >= 55
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                        title="Score ERE"
                      >
                        {a.editorial_score}
                      </span>
                    ) : null}
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
