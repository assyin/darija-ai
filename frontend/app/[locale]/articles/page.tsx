import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import type { ArticlePublic } from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

async function fetchArticles(): Promise<ArticlePublic[]> {
  try {
    const res = await fetch(`${API_BASE}/articles?limit=100`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    return (await res.json()) as ArticlePublic[];
  } catch {
    return [];
  }
}

export default async function ArticlesListPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("articles_list");
  const articles = await fetchArticles();

  return (
    <div className="container-wide py-16">
      <header className="mb-12 max-w-2xl">
        <h1 dir="rtl" className="font-arabic-display text-4xl md:text-5xl">
          {t("page_title")}
        </h1>
        <p
          dir="rtl"
          className="font-arabic mt-4 text-lg text-[var(--color-muted-foreground)]"
        >
          {t("page_subtitle")}
        </p>
        <p
          dir="rtl"
          className="font-arabic mt-2 text-sm text-[var(--color-muted)]"
        >
          {t("count", { count: articles.length })}
        </p>
      </header>

      {articles.length === 0 ? (
        <p
          dir="rtl"
          className="font-arabic rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-8 py-16 text-center text-[var(--color-muted-foreground)]"
        >
          {t("no_results")}
        </p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {articles.map((a) => (
            <ArticleCardPublic key={a.id} article={a} variant="compact" />
          ))}
        </div>
      )}
    </div>
  );
}
