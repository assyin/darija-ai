"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Clock } from "lucide-react";

import { bdiHtml, stripBdi } from "@/lib/bidi";
import type { ArticlePublic } from "@/lib/types";
import { cn } from "@/lib/utils";

type Variant = "featured" | "compact";

interface ArticleCardPublicProps {
  article: ArticlePublic;
  variant?: Variant;
}

export function ArticleCardPublic({ article, variant = "compact" }: ArticleCardPublicProps) {
  const t = useTranslations("article");
  const tCommon = useTranslations("common");
  const isFeatured = variant === "featured";
  const primaryCategory = article.categories[0];

  return (
    <Link
      href={`/articles/${article.slug}`}
      className={cn(
        "group flex flex-col overflow-hidden rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] transition-all duration-200",
        "hover:-translate-y-1 hover:border-[var(--color-primary)]/50 hover:shadow-[var(--shadow-card)]",
      )}
    >
      <div className="relative aspect-video w-full overflow-hidden bg-[var(--color-bg)]">
        {article.hero_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={article.hero_image_url}
            alt={article.hero_image_alt ?? article.title_darija}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[var(--color-muted)] zellige-overlay" />
        )}
        {primaryCategory && (
          <span className="absolute end-3 top-3 rounded-full bg-[var(--color-bg)]/90 backdrop-blur px-3 py-1 text-xs font-medium text-[var(--color-primary)]">
            {primaryCategory}
          </span>
        )}
      </div>

      <div className={cn("flex flex-1 flex-col gap-3", isFeatured ? "p-6" : "p-5")}>
        <h3
          dir="rtl"
          aria-label={stripBdi(article.title_darija)}
          className={cn(
            "font-arabic-display leading-snug line-clamp-2",
            isFeatured ? "text-2xl" : "text-lg",
          )}
          dangerouslySetInnerHTML={{ __html: bdiHtml(article.title_darija) }}
        />
        <p
          dir="rtl"
          className={cn(
            "font-arabic text-[var(--color-muted-foreground)] line-clamp-3",
            isFeatured ? "text-base" : "text-sm",
          )}
          dangerouslySetInnerHTML={{ __html: bdiHtml(article.excerpt_darija) }}
        />
        <div className="mt-auto flex items-center justify-between pt-2 text-xs text-[var(--color-muted)]">
          {article.reading_time_minutes != null ? (
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {t("reading_time", { minutes: article.reading_time_minutes })}
            </span>
          ) : <span />}
          <span className="font-medium text-[var(--color-primary)] group-hover:text-[var(--color-accent-dark)]">
            {tCommon("read_more")} →
          </span>
        </div>
      </div>
    </Link>
  );
}
