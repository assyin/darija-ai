"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { adminApi } from "@/lib/api-client";
import type { ArticleAdminDetail, ArticleUpdate } from "@/lib/types";

// Inline article actions for the ERE Human Audit preview. Reuses the existing
// /admin/articles/{id} endpoints (load / patch / publish / unpublish / proofread)
// — no new backend logic, no ranking change. Publish is ALWAYS human-triggered
// (two-click confirm) and fully decoupled from the KEEP/REJECT audit verdict.

interface ProofreadScore {
  score: number;
  grammar_score: number | null;
  naturalness_score: number | null;
  summary: string;
}

const BTN = "h-8 px-2.5 text-xs";

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : "échec";
}

export function EreAuditActions({ articleId }: { articleId: number }): React.ReactElement {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data: article, isLoading } = useQuery({
    queryKey: ["ere-audit-article", articleId],
    queryFn: () => adminApi.get<ArticleAdminDetail>(`/articles/${articleId}`),
  });
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState<ArticleUpdate>({});
  const [pr, setPr] = React.useState<{ lang: string; r: ProofreadScore } | null>(null);
  const [confirmPub, setConfirmPub] = React.useState(false);

  const onArticle = (next: ArticleAdminDetail) => {
    qc.setQueryData(["ere-audit-article", articleId], next);
    void qc.invalidateQueries({ queryKey: ["articles"] });
  };

  const save = useMutation({
    mutationFn: (patch: ArticleUpdate) =>
      adminApi.patch<ArticleAdminDetail>(`/articles/${articleId}`, patch),
    onSuccess: (next) => {
      onArticle(next);
      setEditing(false);
      setDraft({});
      toast("Sauvegardé", "success");
    },
    onError: (e) => toast(`Erreur: ${errMsg(e)}`, "error"),
  });
  const publish = useMutation({
    mutationFn: () => adminApi.post<ArticleAdminDetail>(`/articles/${articleId}/publish`),
    onSuccess: (next) => {
      onArticle(next);
      setConfirmPub(false);
      toast("Article publié", "success");
    },
    onError: (e) => {
      setConfirmPub(false);
      toast(`Erreur: ${errMsg(e)}`, "error");
    },
  });
  const unpublish = useMutation({
    mutationFn: () => adminApi.post<ArticleAdminDetail>(`/articles/${articleId}/unpublish`),
    onSuccess: (next) => {
      onArticle(next);
      toast("Article dépublié", "success");
    },
    onError: (e) => toast(`Erreur: ${errMsg(e)}`, "error"),
  });
  const proofread = useMutation({
    mutationFn: (v: { lang: "darija" | "french"; text: string }) =>
      adminApi.post<ProofreadScore>(`/articles/${articleId}/proofread`, {
        text: v.text,
        lang: v.lang,
        field: "body",
      }),
    onSuccess: (r, v) => {
      setPr({ lang: v.lang, r });
      toast(`Proofread ${v.lang}: ${r.score}/100`, "success");
    },
    onError: (e) => toast(`Erreur: ${errMsg(e)}`, "error"),
  });

  if (isLoading || !article) {
    return (
      <div className="flex items-center gap-1 text-xs text-slate-400">
        <Loader2 className="h-3 w-3 animate-spin" /> Chargement de l&apos;article…
      </div>
    );
  }

  const fr = article.content_fr;
  const copy = () => {
    const parts = [`# ${article.title_darija}`, "", article.content_darija];
    if (fr) parts.push("", "---", "", `# ${article.title_fr ?? ""}`, "", fr);
    void navigator.clipboard
      .writeText(parts.join("\n"))
      .then(() => toast("Article copié", "success"));
  };

  return (
    <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Article
        </span>
        <Badge variant={article.is_published ? "success" : "muted"}>
          {article.is_published ? "published" : "draft"}
        </Badge>
        <Button variant="outline" className={BTN} onClick={copy}>
          Copier
        </Button>
        <Button
          variant="outline"
          className={BTN}
          disabled={proofread.isPending}
          onClick={() => proofread.mutate({ lang: "darija", text: article.content_darija })}
        >
          Proofread DA
        </Button>
        {fr ? (
          <Button
            variant="outline"
            className={BTN}
            disabled={proofread.isPending}
            onClick={() => proofread.mutate({ lang: "french", text: fr })}
          >
            Proofread FR
          </Button>
        ) : null}
        <Button
          variant="outline"
          className={BTN}
          onClick={() => {
            setEditing((e) => !e);
            setDraft({});
          }}
        >
          {editing ? "Annuler" : "Corriger"}
        </Button>
        {article.is_published ? (
          <>
            <a
              className={`${BTN} inline-flex items-center rounded-md border border-emerald-200 bg-white font-medium text-emerald-700 hover:bg-emerald-50`}
              target="_blank"
              rel="noopener noreferrer"
              href={`/articles/${article.slug}`}
            >
              Voir l&apos;article ↗
            </a>
            <Button
              variant="destructive"
              className={BTN}
              disabled={unpublish.isPending}
              onClick={() => unpublish.mutate()}
            >
              Dépublier
            </Button>
          </>
        ) : confirmPub ? (
          <Button
            className={`${BTN} bg-amber-600 text-white hover:bg-amber-700`}
            disabled={publish.isPending}
            onClick={() => publish.mutate()}
          >
            Confirmer la publication ?
          </Button>
        ) : (
          <Button
            className={`${BTN} bg-emerald-600 text-white hover:bg-emerald-700`}
            onClick={() => setConfirmPub(true)}
          >
            Publier
          </Button>
        )}
      </div>

      {pr ? (
        <div className="text-xs text-slate-600">
          Proofread <b>{pr.lang}</b>: <b>{pr.r.score}/100</b> · naturalness{" "}
          {pr.r.naturalness_score ?? "—"} · grammar {pr.r.grammar_score ?? "—"} — {pr.r.summary}
        </div>
      ) : null}

      {editing ? (
        <div className="space-y-2">
          <input
            dir="rtl"
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            defaultValue={article.title_darija}
            onChange={(e) => setDraft((d) => ({ ...d, title_darija: e.target.value }))}
          />
          <textarea
            dir="rtl"
            rows={8}
            className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs"
            defaultValue={article.content_darija}
            onChange={(e) => setDraft((d) => ({ ...d, content_darija: e.target.value }))}
          />
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            placeholder="Titre FR"
            defaultValue={article.title_fr ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, title_fr: e.target.value }))}
          />
          <textarea
            rows={8}
            placeholder="Contenu FR"
            className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs"
            defaultValue={article.content_fr ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, content_fr: e.target.value }))}
          />
          <Button
            className={BTN}
            disabled={save.isPending || Object.keys(draft).length === 0}
            onClick={() => save.mutate(draft)}
          >
            Sauvegarder les corrections
          </Button>
        </div>
      ) : null}
    </div>
  );
}
