"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { ArticleCard } from "@/components/admin/article-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ArticleAdmin } from "@/lib/types";

type Filter = "all" | "drafts" | "ready" | "published";

export default function ArticlesListPage() {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [query, setQuery] = React.useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["articles", filter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "50" });
      if (filter === "drafts") params.set("is_published", "false");
      if (filter === "published") params.set("is_published", "true");
      return adminApi.get<ArticleAdmin[]>(`/articles?${params}`);
    },
  });

  const all = data ?? [];
  const drafts = all.filter((a) => !a.is_published);
  const published = all.filter((a) => a.is_published);
  // "Ready to publish" = drafts that the AI Proofreader greenlighted. Per
  // CLAUDE.md §1 this stays a *hint* — the editor still clicks Publish.
  const ready = drafts.filter((a) => a.proofread_ready_to_publish);

  const visible = React.useMemo(() => {
    let list = all;
    if (filter === "drafts") list = drafts;
    if (filter === "ready") list = ready;
    if (filter === "published") list = published;
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter((a) =>
        a.title_darija.toLowerCase().includes(q) ||
        a.excerpt_darija.toLowerCase().includes(q) ||
        a.slug.toLowerCase().includes(q),
      );
    }
    return list;
  }, [all, drafts, ready, published, filter, query]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Articles</h1>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            {all.length} articles • {drafts.length} brouillons • {published.length} publiés
          </p>
        </div>
        <Input
          placeholder="Rechercher dans le titre ou l'extrait…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="sm:w-72"
        />
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>
          Tous <Badge variant="muted" className="ml-2">{all.length}</Badge>
        </FilterButton>
        <FilterButton active={filter === "drafts"} onClick={() => setFilter("drafts")}>
          Brouillons <Badge variant="muted" className="ml-2">{drafts.length}</Badge>
        </FilterButton>
        <FilterButton active={filter === "ready"} onClick={() => setFilter("ready")}>
          Prêts à publier{" "}
          <Badge
            variant={ready.length > 0 ? "success" : "muted"}
            className="ml-2"
          >
            {ready.length}
          </Badge>
        </FilterButton>
        <FilterButton active={filter === "published"} onClick={() => setFilter("published")}>
          Publiés <Badge variant="muted" className="ml-2">{published.length}</Badge>
        </FilterButton>
      </div>

      {isLoading && <ListSkeleton />}
      {isError && (
        <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          Erreur de chargement: {(error as Error).message}
        </p>
      )}
      {!isLoading && !isError && visible.length === 0 && (
        <p className="rounded-md border border-[var(--color-border)] bg-white px-6 py-10 text-center text-sm text-[var(--color-muted-foreground)]">
          Aucun article {filter === "drafts" ? "en brouillon" : filter === "published" ? "publié" : ""}.
        </p>
      )}
      {!isLoading && !isError && visible.length > 0 && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {visible.map((a) => (
            <ArticleCard key={a.id} article={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
      className={cn("h-9", active ? "" : "")}
    >
      {children}
    </Button>
  );
}

function ListSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="h-72 animate-pulse rounded-lg border border-[var(--color-border)] bg-white"
        />
      ))}
    </div>
  );
}
