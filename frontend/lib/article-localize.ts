import type { ArticlePublic, ArticlePublicDetail } from "@/lib/types";

/**
 * Pick the active-locale version of an article's text fields, falling back to
 * Darija when a French translation hasn't been authored yet. Returns `dir`
 * matching the actual *content* (not the locale) so a Darija fallback shown
 * on `/fr` still renders RTL, never broken bidi.
 */
export interface LocalizedArticle {
  title: string;
  excerpt: string;
  content?: string;
  metaTitle: string | null;
  metaDescription: string | null;
  /** "rtl" when the picked content is Darija, "ltr" when it's French. */
  dir: "rtl" | "ltr";
  /** "ar-MA" or "fr" — matches the picked content language, useful for
   *  `<html lang>` overrides on the article detail page. */
  contentLang: "ar-MA" | "fr";
  /** `true` when the user requested FR but no FR translation existed. */
  isFallback: boolean;
}

function isArticleDetail(
  a: ArticlePublic | ArticlePublicDetail,
): a is ArticlePublicDetail {
  return "content_darija" in a;
}

export function localizeArticle(
  article: ArticlePublic | ArticlePublicDetail,
  locale: string,
): LocalizedArticle {
  const wantsFrench = locale === "fr";
  const hasFrenchTitle = Boolean(article.title_fr && article.title_fr.trim());

  if (wantsFrench && hasFrenchTitle) {
    return {
      title: article.title_fr ?? article.title_darija,
      excerpt: article.excerpt_fr?.trim()
        ? article.excerpt_fr
        : article.excerpt_darija,
      content: isArticleDetail(article)
        ? article.content_fr?.trim() || article.content_darija
        : undefined,
      metaTitle: isArticleDetail(article)
        ? article.meta_title_fr ?? article.meta_title
        : null,
      metaDescription: isArticleDetail(article)
        ? article.meta_description_fr ?? article.meta_description
        : null,
      dir: "ltr",
      contentLang: "fr",
      isFallback: false,
    };
  }

  return {
    title: article.title_darija,
    excerpt: article.excerpt_darija,
    content: isArticleDetail(article) ? article.content_darija : undefined,
    metaTitle: isArticleDetail(article) ? article.meta_title : null,
    metaDescription: isArticleDetail(article)
      ? article.meta_description
      : null,
    dir: "rtl",
    contentLang: "ar-MA",
    isFallback: wantsFrench && !hasFrenchTitle,
  };
}
