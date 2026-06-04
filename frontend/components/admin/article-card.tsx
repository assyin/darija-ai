"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { CheckCircle2, Clock, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/admin/status-badge";
import { cn } from "@/lib/utils";
import type { ArticleAdmin } from "@/lib/types";

interface ArticleCardProps {
  article: ArticleAdmin;
}

export function ArticleCard({ article }: ArticleCardProps) {
  const updatedAgo = formatDistanceToNow(new Date(article.updated_at), {
    addSuffix: true,
    locale: fr,
  });
  return (
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
              {!article.is_published && article.proofread_ready_to_publish && (
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

          {/* Proofread score line — surfaces transparency about WHY a draft
               is marked "ready" (or not). Hidden when nothing has been
               scored yet (pre-PR #25 articles, or proofreader failed). */}
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
            {article.title_darija}
          </h3>
          <p
            dir="rtl"
            className="font-tajawal text-sm text-[var(--color-muted-foreground)] line-clamp-2"
          >
            {article.excerpt_darija}
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
        </div>
      </Card>
    </Link>
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
