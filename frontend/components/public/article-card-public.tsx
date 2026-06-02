"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, Clock, ImageIcon } from "lucide-react";

import { localizeArticle } from "@/lib/article-localize";
import { bdiHtml, stripBdi } from "@/lib/bidi";
import type { ArticlePublic } from "@/lib/types";
import { cn } from "@/lib/utils";

type Variant = "featured" | "compact";
type Theme = "dark" | "light";

interface ArticleCardPublicProps {
  article: ArticlePublic;
  variant?: Variant;
  theme?: Theme;
}

/**
 * Public article card. Two themes:
 *   - `dark`  (default) — glass over dark page (home + /articles list).
 *   - `light` — paper card on light page (related section inside the light
 *     article detail page).
 *
 * Density variants (independent of theme):
 *   - `featured` — bigger padding + larger H3.
 *   - `compact`  — standard grid card.
 */
export function ArticleCardPublic({
  article,
  variant = "compact",
  theme = "dark",
}: ArticleCardPublicProps) {
  const t = useTranslations("article");
  const locale = useLocale();
  const localized = localizeArticle(article, locale);
  const tCommon = useTranslations("common");
  const isFeatured = variant === "featured";
  const isLight = theme === "light";
  const primaryCategory = article.categories[0];

  return (
    <Link
      href={`/articles/${article.slug}`}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1",
        isLight
          ? "border-zinc-200 bg-white hover:border-violet-300 hover:shadow-[0_18px_50px_-18px_rgba(168,85,247,0.25)]"
          : "border-white/10 bg-white/[0.04] backdrop-blur-xl hover:border-fuchsia-400/40 hover:bg-white/[0.07] hover:shadow-[0_24px_60px_-20px_rgba(168,85,247,0.45)]",
      )}
    >
      {/* Image */}
      <div className="relative aspect-video w-full overflow-hidden">
        {article.hero_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={article.hero_image_url}
            alt={article.hero_image_alt ?? stripBdi(localized.title)}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.05]"
          />
        ) : (
          <div className="zellige-overlay flex h-full w-full items-center justify-center bg-[#0a0418] text-white/30">
            <ImageIcon className="h-8 w-8" aria-hidden />
          </div>
        )}
        {/* Bottom fade so the image grounds into the card body */}
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-0 bg-gradient-to-t via-transparent to-transparent",
            isLight ? "from-white/40" : "from-[#0a0418]/85",
          )}
        />
        {primaryCategory && (
          <span
            className={cn(
              "absolute end-3 top-3 inline-flex items-center rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider backdrop-blur-xl",
              isLight
                ? "border border-violet-200 bg-white/90 text-violet-700"
                : "border border-white/15 bg-black/30 text-fuchsia-200",
            )}
          >
            {primaryCategory}
          </span>
        )}
      </div>

      {/* Body */}
      <div className={cn("flex flex-1 flex-col gap-3", isFeatured ? "p-6" : "p-5")}>
        <h3
          dir={localized.dir}
          aria-label={stripBdi(localized.title)}
          className={cn(
            "font-bold leading-snug line-clamp-2 transition-colors",
            localized.dir === "rtl" && "font-arabic-display",
            isLight
              ? "text-zinc-900 group-hover:text-violet-700"
              : "text-white group-hover:text-fuchsia-100",
            isFeatured ? "text-2xl" : "text-lg",
          )}
          dangerouslySetInnerHTML={{ __html: bdiHtml(localized.title) }}
        />
        <p
          dir={localized.dir}
          className={cn(
            "line-clamp-3",
            localized.dir === "rtl" && "font-arabic",
            isLight ? "text-zinc-600" : "text-white/65",
            isFeatured ? "text-base" : "text-sm",
          )}
          dangerouslySetInnerHTML={{ __html: bdiHtml(localized.excerpt) }}
        />

        <div className="mt-auto flex items-center justify-between gap-3 pt-2 text-xs">
          {article.reading_time_minutes != null ? (
            <span
              className={cn(
                "inline-flex items-center gap-1.5",
                isLight ? "text-zinc-500" : "text-white/50",
              )}
            >
              <Clock className="h-3.5 w-3.5" aria-hidden />
              {t("reading_time", { minutes: article.reading_time_minutes })}
            </span>
          ) : (
            <span />
          )}
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent">
              {tCommon("read_more")}
            </span>
            <ArrowLeft
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-x-1",
                isLight ? "text-violet-600" : "text-fuchsia-300",
              )}
              aria-hidden
            />
          </span>
        </div>
      </div>
    </Link>
  );
}
