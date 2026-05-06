"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { Clock, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/admin/status-badge";
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
            <StatusBadge isPublished={article.is_published} />
            <span className="text-xs text-[var(--color-muted-foreground)]">
              {updatedAgo}
            </span>
          </div>
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
