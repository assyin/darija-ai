"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { AlertTriangle, CheckCircle2, Clock, FileText, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { StatusBadge } from "@/components/admin/status-badge";
import { adminApi } from "@/lib/api-client";
import { stripBdi } from "@/lib/bidi";
import { cn } from "@/lib/utils";
import type { ArticleAdmin, ArticleAdminDetail } from "@/lib/types";

interface ArticleCardProps {
  article: ArticleAdmin;
}

export function ArticleCard({ article }: ArticleCardProps) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [showPublishConfirm, setShowPublishConfirm] = React.useState(false);

  const updatedAgo = formatDistanceToNow(new Date(article.updated_at), {
    addSuffix: true,
    locale: fr,
  });

  const publishMutation = useMutation({
    mutationFn: () =>
      adminApi.post<ArticleAdminDetail>(`/articles/${article.id}/publish`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["articles"] });
      setShowPublishConfirm(false);
      toast("Article publié", "success");
    },
    onError: (err) => {
      setShowPublishConfirm(false);
      toast(`Erreur: ${(err as Error).message}`, "error");
    },
  });

  // Title/excerpt arrive with <bdi>…</bdi> wrappers around Latin terms — they
  // are intentional for the public RTL renderer but render as literal text in
  // a JSX `{value}` slot. Strip for the admin preview surface; the full article
  // editor keeps the wrappers and renders them via bdiHtml.
  const titleClean = stripBdi(article.title_darija);
  const excerptClean = stripBdi(article.excerpt_darija);

  // Surface the (rare) low-confidence publish path explicitly: the editor
  // gets a louder confirmation when the AI hasn't greenlighted the draft.
  const isReady = article.proofread_ready_to_publish;
  const lowConfidencePublish = !isReady;

  // Suppress the wrapping Link's navigation when clicking inside an action.
  const stopLink = (e: React.MouseEvent | React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <>
      <Link href={`/admin/articles/${article.id}`} className="group block">
        <Card className="h-full overflow-hidden transition-all hover:border-[var(--color-primary)]/50 hover:shadow-md">
          {article.hero_image_url ? (
            <div className="aspect-video w-full overflow-hidden bg-slate-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={article.hero_image_url}
                alt={article.hero_image_alt ?? ""}
                className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]"
              />
            </div>
          ) : (
            <div className="flex aspect-video w-full items-center justify-center bg-slate-100 text-slate-400">
              <FileText className="h-10 w-10" />
            </div>
          )}
          <div className="space-y-3 p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <StatusBadge isPublished={article.is_published} />
                {!article.is_published && isReady && (
                  <Badge
                    variant="success"
                    className="inline-flex items-center gap-1"
                    title="Le Correcteur IA a évalué les scores Darija + Français au-dessus du seuil. Tu peux publier en confiance."
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    Prêt à publier
                  </Badge>
                )}
              </div>
              <span className="text-xs text-[var(--color-muted-foreground)]">
                {updatedAgo}
              </span>
            </div>

            {/* Proofread score line — hidden when nothing has been scored
                 (pre-PR #25 drafts, or the proofreader silently failed). */}
            {(article.proofread_score_darija != null ||
              article.proofread_score_fr != null) && (
              <div className="flex items-center gap-2 text-[11px]">
                {article.proofread_score_darija != null && (
                  <ScorePill label="DR" score={article.proofread_score_darija} />
                )}
                {article.proofread_score_fr != null && (
                  <ScorePill label="FR" score={article.proofread_score_fr} />
                )}
              </div>
            )}

            <h3
              dir="rtl"
              className="font-tajawal text-lg font-bold leading-snug line-clamp-2"
            >
              {titleClean}
            </h3>
            <p
              dir="rtl"
              className="font-tajawal text-sm text-[var(--color-muted-foreground)] line-clamp-2"
            >
              {excerptClean}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-xs text-[var(--color-muted-foreground)]">
              {article.word_count != null && (
                <span>{article.word_count} mots</span>
              )}
              {article.reading_time_minutes != null && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {article.reading_time_minutes} min
                </span>
              )}
              {article.categories.slice(0, 2).map((cat) => (
                <Badge key={cat} variant="muted" className="text-[10px]">
                  {cat}
                </Badge>
              ))}
            </div>

            {/* Inline action row — only visible on drafts. Publishing
                always asks confirmation; the wording escalates when the
                AI Proofreader did NOT mark the draft as ready. */}
            {!article.is_published && (
              <div
                className="flex items-center justify-end gap-2 border-t border-[var(--color-border)] pt-3"
                onClick={stopLink}
                onPointerDown={stopLink}
              >
                <Button
                  type="button"
                  size="sm"
                  variant={isReady ? "default" : "outline"}
                  onClick={(e) => {
                    stopLink(e);
                    setShowPublishConfirm(true);
                  }}
                  disabled={publishMutation.isPending}
                  className={cn(
                    "h-8",
                    isReady &&
                      "bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500",
                  )}
                >
                  {publishMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <>Publier{isReady ? " maintenant" : "…"}</>
                  )}
                </Button>
              </div>
            )}
          </div>
        </Card>
      </Link>

      <Dialog open={showPublishConfirm} onOpenChange={setShowPublishConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {lowConfidencePublish && (
                <AlertTriangle className="h-5 w-5 text-amber-500" />
              )}
              Publier &laquo;{" "}
              <span className="truncate font-arabic" dir="rtl">
                {titleClean}
              </span>{" "}
              &raquo; ?
            </DialogTitle>
            <DialogDescription>
              {lowConfidencePublish ? (
                <>
                  Le Correcteur IA n&apos;a <strong>pas</strong> marqué ce brouillon
                  comme prêt — score Darija{" "}
                  <strong>{article.proofread_score_darija ?? "non évalué"}</strong>
                  {article.proofread_score_fr != null && (
                    <>
                      , score Français <strong>{article.proofread_score_fr}</strong>
                    </>
                  )}
                  . Tu peux quand même publier, mais relis-le d&apos;abord.
                </>
              ) : (
                <>
                  Il sera visible publiquement immédiatement. Tu peux le dépublier
                  à tout moment depuis la page de l&apos;article.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowPublishConfirm(false)}
              disabled={publishMutation.isPending}
            >
              Annuler
            </Button>
            {lowConfidencePublish && (
              <Button asChild variant="secondary">
                <Link href={`/admin/articles/${article.id}`}>Relire d&apos;abord</Link>
              </Button>
            )}
            <Button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
              className={cn(
                lowConfidencePublish
                  ? "bg-amber-600 hover:bg-amber-700"
                  : "bg-emerald-600 hover:bg-emerald-700",
              )}
            >
              {publishMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {lowConfidencePublish ? "Publier quand même" : "Publier maintenant"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ScorePill({ label, score }: { label: string; score: number }) {
  // 0-59 red, 60-84 amber, 85+ emerald — same buckets the Proofreader UI uses
  // elsewhere so the visual language stays consistent across the admin.
  const tone =
    score >= 85
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : score >= 60
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-red-200 bg-red-50 text-red-800";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium",
        tone,
      )}
      title={`Score Correcteur IA — ${label}`}
    >
      <span className="font-mono text-[10px] tracking-wide">{label}</span>
      <span>{score}</span>
    </span>
  );
}
