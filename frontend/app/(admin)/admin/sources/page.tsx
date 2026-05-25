"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface SourceLite {
  id: number;
  name: string;
  rss_url: string | null;
  scraping_url: string | null;
  is_active: boolean;
  needs_html_enrichment: boolean;
  last_fetched_at: string | null;
}

export default function SourcesPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Sources RSS</h1>
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Liste des flux ingérés par le scraper. Édition à venir.
        </p>
      </header>

      <div className="rounded-lg border border-[var(--color-border)] bg-white">
        <div className="border-b border-[var(--color-border)] bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
            5 sources configurées
          </p>
        </div>
        <SourceTable />
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>TODO</strong> — endpoint d&apos;administration des sources et
        bouton &laquo; Lancer scraping maintenant &raquo; à câbler côté backend
        (sera fait dans un sprint ultérieur).
      </div>
    </div>
  );
}

function SourceTable() {
  // Hardcoded snapshot of the seed_sources output. Will be replaced with a
  // /api/v1/admin/sources GET when the backend endpoint is added.
  const sources: SourceLite[] = [
    { id: 1, name: "Unite.AI", rss_url: "https://www.unite.ai/feed/", scraping_url: null, is_active: true, needs_html_enrichment: false, last_fetched_at: null },
    { id: 2, name: "VentureBeat AI", rss_url: "https://venturebeat.com/category/ai/feed/", scraping_url: null, is_active: true, needs_html_enrichment: false, last_fetched_at: null },
    { id: 3, name: "TechCrunch AI", rss_url: "https://techcrunch.com/category/artificial-intelligence/feed/", scraping_url: null, is_active: true, needs_html_enrichment: true, last_fetched_at: null },
    { id: 4, name: "Hugging Face Blog", rss_url: "https://huggingface.co/blog/feed.xml", scraping_url: null, is_active: true, needs_html_enrichment: true, last_fetched_at: null },
    { id: 5, name: "Anthropic News", rss_url: null, scraping_url: "https://www.anthropic.com/news", is_active: true, needs_html_enrichment: false, last_fetched_at: null },
  ];

  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
        <tr>
          <th className="px-4 py-2.5">Nom</th>
          <th className="px-4 py-2.5">URL</th>
          <th className="px-4 py-2.5">Active</th>
          <th className="px-4 py-2.5">Enrichissement HTML</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[var(--color-border)]">
        {sources.map((s) => (
          <tr key={s.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 font-medium">{s.name}</td>
            <td className="max-w-xs truncate px-4 py-3 text-xs text-[var(--color-muted-foreground)]">
              {s.rss_url ?? s.scraping_url ?? "—"}
            </td>
            <td className="px-4 py-3">
              {s.is_active ? (
                <Badge variant="success">Active</Badge>
              ) : (
                <Badge variant="muted">Inactive</Badge>
              )}
            </td>
            <td className="px-4 py-3">
              {s.needs_html_enrichment ? (
                <Badge variant="warning">Requis</Badge>
              ) : (
                <span className="text-xs text-[var(--color-muted-foreground)]">
                  Non
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// (Loader2 imported in case we add live data — unused now intentionally.)
void Loader2;
