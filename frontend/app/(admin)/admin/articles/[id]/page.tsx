"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ImagePlus, Loader2, MoreVertical, Save, Send } from "lucide-react";

import { MarkdownEditor } from "@/components/admin/markdown-editor";
import { ProofreaderPanel } from "@/components/admin/proofreader-panel";
import { StatusBadge } from "@/components/admin/status-badge";
import { TitleScoreBadge } from "@/components/admin/title-score-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useProofreader } from "@/hooks/use-proofreader";
import { adminApi, ApiError } from "@/lib/api-client";
import { findOriginal } from "@/lib/proofread-match";
import type {
  ArticleAdminDetail,
  ArticleUpdate,
  ProofreadLang,
  ProofreadSuggestion,
} from "@/lib/types";

export default function ArticleEditorPage() {
  const params = useParams();
  const id = Number(params?.id);
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data: article, isLoading, isError, error } = useQuery({
    queryKey: ["article", id],
    queryFn: () => adminApi.get<ArticleAdminDetail>(`/articles/${id}`),
    enabled: Number.isFinite(id),
  });

  const [draft, setDraft] = React.useState<ArticleUpdate>({});
  const [showPublish, setShowPublish] = React.useState(false);
  const [showUnpublish, setShowUnpublish] = React.useState(false);

  // AI proofreader state — Phase 1: darija only ("french" tab present but
  // inert until Phase 2 introduces title_fr / content_fr columns).
  const [lang, setLang] = React.useState<ProofreadLang>("darija");
  const [activeSuggestion, setActiveSuggestion] = React.useState<number | null>(
    null,
  );

  // Reset the edit draft when a different article loads. Render-time reset —
  // the React-recommended alternative to calling setState inside an effect.
  const [trackedId, setTrackedId] = React.useState(article?.id);
  if (article && article.id !== trackedId) {
    setTrackedId(article.id);
    setDraft({});
  }

  const merged: ArticleAdminDetail | undefined = React.useMemo(
    () => (article ? ({ ...article, ...draft } as ArticleAdminDetail) : undefined),
    [article, draft],
  );

  const saveMutation = useMutation({
    mutationFn: (patch: ArticleUpdate) =>
      adminApi.patch<ArticleAdminDetail>(`/articles/${id}`, patch),
    onSuccess: (next) => {
      qc.setQueryData(["article", id], next);
      qc.invalidateQueries({ queryKey: ["articles"] });
      setDraft({});
      toast("Sauvegardé", "success");
    },
    onError: (err) => toast(`Erreur: ${(err as Error).message}`, "error"),
  });

  const publishMutation = useMutation({
    mutationFn: () => adminApi.post<ArticleAdminDetail>(`/articles/${id}/publish`),
    onSuccess: (next) => {
      qc.setQueryData(["article", id], next);
      qc.invalidateQueries({ queryKey: ["articles"] });
      setShowPublish(false);
      toast("Article publié", "success");
    },
    onError: (err) => {
      setShowPublish(false);
      toast(`Erreur: ${(err as Error).message}`, "error");
    },
  });

  const unpublishMutation = useMutation({
    mutationFn: () => adminApi.post<ArticleAdminDetail>(`/articles/${id}/unpublish`),
    onSuccess: (next) => {
      qc.setQueryData(["article", id], next);
      qc.invalidateQueries({ queryKey: ["articles"] });
      setShowUnpublish(false);
      toast("Article dépublié", "success");
    },
    onError: (err) => {
      setShowUnpublish(false);
      toast(`Erreur: ${(err as Error).message}`, "error");
    },
  });

  const regenerateImageMutation = useMutation({
    mutationFn: () =>
      adminApi.post<ArticleAdminDetail>(`/articles/${id}/regenerate-image`),
    onSuccess: (next) => {
      qc.setQueryData(["article", id], next);
      qc.invalidateQueries({ queryKey: ["articles"] });
      toast("Image régénérée", "success");
    },
    onError: (err) => toast(`Erreur image: ${(err as Error).message}`, "error"),
  });

  function patch<K extends keyof ArticleUpdate>(key: K, value: ArticleUpdate[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  // Proofreader hooks — manual trigger (no auto-fire, see use-proofreader.ts).
  // FR is inert in Phase 1 until title_fr/content_fr columns land.
  const titleProofread = useProofreader({
    articleId: id,
    text: merged?.title_darija ?? "",
    lang,
    field: "title",
    enabled: lang === "darija",
  });
  const bodyProofread = useProofreader({
    articleId: id,
    text: merged?.content_darija ?? "",
    lang,
    field: "body",
    enabled: lang === "darija",
  });

  const applySuggestion = React.useCallback(
    (
      key: "title_darija" | "content_darija",
      index: number,
      s: ProofreadSuggestion,
      dismiss: (i: number) => void,
    ) => {
      if (!merged) return;
      const haystack = merged[key];
      if (!haystack || !s.original) return;
      // Robust matcher — tolerates Arabic-Indic vs Latin digits, bidi marks,
      // whitespace collapse, NFC vs NFD. See lib/proofread-match.ts.
      const hit = findOriginal(haystack, s.original);
      if (hit === null) {
        toast(
          `Phrase introuvable : « ${s.original.slice(0, 50)}… ». Re-évaluer pour rafraîchir, ou Ignorer cette suggestion.`,
          "error",
        );
        return;
      }
      const next =
        haystack.slice(0, hit.start) + s.suggestion + haystack.slice(hit.end);
      patch(key, next);
      // Drop the suggestion from the panel and bump the displayed score —
      // avoids a fresh API call until the user manually re-évalue.
      dismiss(index);
    },
    [merged, toast],
  );

  function flushFor<K extends keyof ArticleUpdate>(key: K) {
    return () => {
      const value = draft[key];
      if (value === undefined) return;
      const current = article ? (article as unknown as Record<string, unknown>)[key as string] : undefined;
      if (current !== undefined && value === current) return;
      saveMutation.mutate({ [key]: value } as ArticleUpdate);
    };
  }

  if (!Number.isFinite(id)) {
    return <p className="text-sm text-red-700">ID invalide.</p>;
  }
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
        <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
      </div>
    );
  }
  if (isError || !merged) {
    const status = error instanceof ApiError ? error.status : null;
    return (
      <div className="space-y-3">
        <Link href="/admin/articles" className="text-sm text-[var(--color-primary)]">
          ← Articles
        </Link>
        <p className="text-sm text-red-700">
          {status === 404 ? "Article introuvable." : `Erreur: ${(error as Error).message}`}
        </p>
      </div>
    );
  }

  const dirty = Object.keys(draft).length > 0;

  return (
    <div className="space-y-6 pb-24">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <Link
            href="/admin/articles"
            className="inline-flex items-center gap-1 text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Articles
          </Link>
          <div className="flex items-center gap-3">
            <StatusBadge isPublished={merged.is_published} />
            <span className="text-xs text-[var(--color-muted-foreground)]">
              ID #{merged.id} · {merged.word_count ?? 0} mots ·{" "}
              {merged.reading_time_minutes ?? 0} min
            </span>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {merged.is_published && (
              <DropdownMenuItem onSelect={() => setShowUnpublish(true)}>
                Dépublier
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => router.push("/admin/articles")}>
              Fermer
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      {/* Lang tabs — FR inert in Phase 1 (no FR columns yet). */}
      <div className="inline-flex rounded-lg border border-[var(--color-border)] bg-slate-50 p-0.5 text-xs">
        {(["darija", "french"] as const).map((opt) => {
          const disabled = opt === "french";
          return (
            <button
              key={opt}
              type="button"
              disabled={disabled}
              onClick={() => setLang(opt)}
              title={disabled ? "Disponible en Phase 2 (champs FR)" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 font-medium transition",
                lang === opt
                  ? "bg-white text-[var(--color-fg)] shadow-sm"
                  : "text-[var(--color-muted-foreground)] hover:text-[var(--color-fg)]",
                disabled && "cursor-not-allowed opacity-50 hover:text-[var(--color-muted-foreground)]",
              )}
            >
              {opt === "darija" ? "Darija" : "Français"}
            </button>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Titre (darija)</Label>
              <TitleScoreBadge
                result={titleProofread.result}
                loading={titleProofread.loading}
                stale={titleProofread.stale}
                hidden={(merged.title_darija ?? "").trim().length < 6}
                onEvaluate={titleProofread.evaluate}
              />
            </div>
            <Input
              dir="rtl"
              value={merged.title_darija}
              onChange={(e) => patch("title_darija", e.target.value)}
              onBlur={flushFor("title_darija")}
              className="font-tajawal text-lg"
            />
          </section>

          <section className="space-y-2">
            <Label>Extrait</Label>
            <Textarea
              dir="rtl"
              rows={2}
              value={merged.excerpt_darija}
              onChange={(e) => patch("excerpt_darija", e.target.value)}
              onBlur={flushFor("excerpt_darija")}
              className="font-tajawal"
            />
          </section>

          <section className="space-y-2">
            <Label>Contenu (Markdown)</Label>
            <MarkdownEditor
              value={merged.content_darija}
              onChange={(v) => patch("content_darija", v)}
              onBlur={flushFor("content_darija")}
              suggestions={bodyProofread.result?.suggestions ?? []}
              activeSuggestion={activeSuggestion}
              onSuggestionClick={(i) => setActiveSuggestion(i)}
            />
          </section>
        </div>

        <ProofreaderPanel
          result={bodyProofread.result}
          loading={bodyProofread.loading}
          error={bodyProofread.error}
          stale={bodyProofread.stale}
          hasEvaluated={bodyProofread.result !== null}
          onEvaluate={bodyProofread.evaluate}
          onApply={(index, s) =>
            applySuggestion("content_darija", index, s, bodyProofread.dismissSuggestion)
          }
          onDismiss={bodyProofread.dismissSuggestion}
          activeIndex={activeSuggestion}
          onSelect={setActiveSuggestion}
        />
      </div>

      <details className="rounded-lg border border-[var(--color-border)] bg-white">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
          Métadonnées
        </summary>
        <div className="space-y-4 border-t border-[var(--color-border)] p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Slug">
              <Input
                value={merged.slug}
                onChange={(e) => patch("slug", e.target.value)}
                onBlur={flushFor("slug")}
              />
            </Field>
            <Field label="Image (URL)">
              <Input
                value={merged.hero_image_url ?? ""}
                disabled
                className="bg-slate-50 text-[var(--color-muted-foreground)]"
              />
            </Field>
            <Field label="Texte alternatif image">
              <Input
                value={merged.hero_image_alt ?? ""}
                onChange={(e) => patch("hero_image_alt", e.target.value)}
                onBlur={flushFor("hero_image_alt")}
              />
            </Field>
            <Field label="Meta title (SEO)">
              <Input
                value={merged.meta_title ?? ""}
                onChange={(e) => patch("meta_title", e.target.value)}
                onBlur={flushFor("meta_title")}
              />
            </Field>
            <Field label="Meta description (SEO)" className="sm:col-span-2">
              <Textarea
                rows={2}
                value={merged.meta_description ?? ""}
                onChange={(e) => patch("meta_description", e.target.value)}
                onBlur={flushFor("meta_description")}
              />
            </Field>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {merged.categories.map((c) => (
              <Badge key={c} variant="muted">
                {c}
              </Badge>
            ))}
            {merged.tags.map((t) => (
              <Badge key={t} variant="outline">
                #{t}
              </Badge>
            ))}
          </div>
          {merged.hero_image_url && (
            <div className="aspect-video w-full max-w-md overflow-hidden rounded-md border border-[var(--color-border)] bg-slate-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={merged.hero_image_url}
                alt={merged.hero_image_alt ?? ""}
                className="h-full w-full object-cover"
              />
            </div>
          )}
        </div>
      </details>

      {/* Sticky action footer */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-[var(--color-border)] bg-white/95 backdrop-blur lg:left-60">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-6 py-3">
          <div className="text-xs text-[var(--color-muted-foreground)]">
            {saveMutation.isPending
              ? "Sauvegarde…"
              : dirty
                ? "Modifications non enregistrées"
                : "Tout est sauvegardé"}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => regenerateImageMutation.mutate()}
              disabled={regenerateImageMutation.isPending}
            >
              {regenerateImageMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ImagePlus className="h-4 w-4" />
              )}
              Régénérer image
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!dirty) return;
                saveMutation.mutate(draft);
              }}
              disabled={!dirty || saveMutation.isPending}
            >
              <Save className="h-4 w-4" />
              Sauvegarder
            </Button>
            {!merged.is_published && (
              <Button size="sm" onClick={() => setShowPublish(true)}>
                <Send className="h-4 w-4" />
                Publier
              </Button>
            )}
          </div>
        </div>
      </div>

      <Dialog open={showPublish} onOpenChange={setShowPublish}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Publier cet article ?</DialogTitle>
            <DialogDescription>
              Il sera visible publiquement et la distribution sociale sera déclenchée.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPublish(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
            >
              {publishMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Publier maintenant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showUnpublish} onOpenChange={setShowUnpublish}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dépublier cet article ?</DialogTitle>
            <DialogDescription>
              Il redeviendra brouillon et ne sera plus visible publiquement.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUnpublish(false)}>
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={() => unpublishMutation.mutate()}
              disabled={unpublishMutation.isPending}
            >
              {unpublishMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Dépublier
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">
        {label}
      </Label>
      {children}
    </div>
  );
}
