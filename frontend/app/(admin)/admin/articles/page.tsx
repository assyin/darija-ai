"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { ArticleCard } from "@/components/admin/article-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { adminApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ArticleAdmin } from "@/lib/types";

type Filter = "all" | "drafts" | "ready" | "published";

interface BulkProofreadResult {
  evaluated: number;
  skipped: number;
  failed: number;
  ready_after: number;
  duration_seconds: number;
  cost_estimate_usd: string;
}

export default function ArticlesListPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [filter, setFilter] = React.useState<Filter>("all");
  const [query, setQuery] = React.useState("");
  const [bulkDialogOpen, setBulkDialogOpen] = React.useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["articles", filter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "50" });
      if (filter === "drafts") params.set("is_published", "false");
      if (filter === "published") params.set("is_published", "true");
      return adminApi.get<ArticleAdmin[]>(`/articles?${params}`);
    },
  });

  const bulkEvaluate = useMutation({
    mutationFn: () =>
      adminApi.post<BulkProofreadResult>("/articles/bulk-evaluate-proofread", {
        only_drafts: true,
        only_unevaluated: true,
      }),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["articles"] });
      setBulkDialogOpen(false);
      const summary = `${result.evaluated} évalués · ${result.ready_after} prêts à publier · ~$${result.cost_estimate_usd} en ${result.duration_seconds.toFixed(1)} s`;
      toast(summary, "success");
    },
    onError: (err) => {
      toast(`Erreur: ${(err as Error).message}`, "error");
    },
  });

  const all = data ?? [];
  const drafts = all.filter((a) => !a.is_published);
  const published = all.filter((a) => a.is_published);
  // "Ready to publish" = drafts that the AI Proofreader greenlighted. Per
  // CLAUDE.md §1 this stays a *hint* — the editor still clicks Publish.
  const ready = drafts.filter((a) => a.proofread_ready_to_publish);
  // Drafts that have never been scored — targets of the bulk-evaluate run.
  const unevaluatedDrafts = drafts.filter((a) => a.proofread_at == null);

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
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {unevaluatedDrafts.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setBulkDialogOpen(true)}
              disabled={bulkEvaluate.isPending}
              className="border-violet-300 text-violet-700 hover:bg-violet-50"
            >
              {bulkEvaluate.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              Évaluer {unevaluatedDrafts.length} brouillon
              {unevaluatedDrafts.length > 1 ? "s" : ""}
            </Button>
          )}
          <Input
            placeholder="Rechercher dans le titre ou l'extrait…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="sm:w-72"
          />
        </div>
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

      <Dialog open={bulkDialogOpen} onOpenChange={setBulkDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-600" />
              Évaluer {unevaluatedDrafts.length} brouillon
              {unevaluatedDrafts.length > 1 ? "s" : ""} avec le Correcteur IA ?
            </DialogTitle>
            <DialogDescription>
              Le Correcteur IA va scorer chaque brouillon qui n&apos;a pas encore
              été évalué. Ça prend ~10-20 secondes par lot et coûte environ{" "}
              <strong>${(unevaluatedDrafts.length * 0.0016).toFixed(3)}</strong> au
              total (~$0.0016 / article × 2 langues). Les drafts au-dessus du
              seuil seront automatiquement marqués &laquo; Prêts à publier &raquo;.
            </DialogDescription>
          </DialogHeader>
          {bulkEvaluate.isPending && (
            <div className="rounded-md border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-900">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Évaluation en cours… Garde l&apos;onglet ouvert.
              </div>
              <p className="mt-1.5 text-xs">
                Le traitement de {unevaluatedDrafts.length} brouillon
                {unevaluatedDrafts.length > 1 ? "s prend" : " prend"} environ{" "}
                {Math.max(10, Math.round(unevaluatedDrafts.length * 0.6))}{" "}
                secondes.
              </p>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setBulkDialogOpen(false)}
              disabled={bulkEvaluate.isPending}
            >
              Annuler
            </Button>
            <Button
              onClick={() => bulkEvaluate.mutate()}
              disabled={bulkEvaluate.isPending}
              className="bg-violet-600 hover:bg-violet-700"
            >
              {bulkEvaluate.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Lancer l&apos;évaluation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
