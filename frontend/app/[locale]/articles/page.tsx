import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArticleCardPublic } from "@/components/public/article-card-public";
import { publicApi } from "@/lib/api-client";

export default async function ArticlesListPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("articles_list");
  const articles = await publicApi.getArticles(100).catch(() => []);

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
