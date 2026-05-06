"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api-client";
import type { BulkUpdateItem, SettingCategory, SiteSettingAdmin } from "@/lib/types";

const CATEGORY_LABELS: Record<SettingCategory, string> = {
  contact: "Contact",
  social: "Réseaux sociaux",
  branding: "Marque",
  seo: "SEO",
  cta: "CTA",
  admin: "Admin",
};

const CATEGORY_ORDER: SettingCategory[] = [
  "contact",
  "social",
  "branding",
  "seo",
  "cta",
  "admin",
];

export default function SettingsPage() {
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api.get<SiteSettingAdmin[]>("/admin/settings"),
  });

  const [drafts, setDrafts] = React.useState<Record<string, string>>({});

  const bulkSave = useMutation({
    mutationFn: (updates: BulkUpdateItem[]) =>
      api.post<SiteSettingAdmin[]>("/admin/settings/bulk", { updates }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-settings"] });
      setDrafts({});
      toast("Paramètres enregistrés", "success");
    },
    onError: (err) => toast(`Erreur: ${(err as Error).message}`, "error"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
        <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
      </div>
    );
  }
  if (isError) {
    return (
      <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        Erreur: {(error as Error).message}
      </p>
    );
  }

  const settings = data ?? [];
  const byCategory: Record<SettingCategory, SiteSettingAdmin[]> = {
    contact: [], social: [], branding: [], seo: [], cta: [], admin: [],
  };
  for (const s of settings) byCategory[s.category]?.push(s);

  function setValue(key: string, value: string) {
    setDrafts((prev) => ({ ...prev, [key]: value }));
  }

  const updates: BulkUpdateItem[] = Object.entries(drafts).map(([key, value]) => ({
    key,
    value,
  }));
  const dirty = updates.length > 0;

  return (
    <div className="space-y-6 pb-20">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Paramètres</h1>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            Configuration éditable du site (contact, marque, SEO, CTA…). Aucun déploiement requis.
          </p>
        </div>
      </header>

      <Tabs defaultValue="contact">
        <TabsList>
          {CATEGORY_ORDER.map((c) => (
            <TabsTrigger key={c} value={c}>
              {CATEGORY_LABELS[c]} ({byCategory[c].length})
            </TabsTrigger>
          ))}
        </TabsList>
        {CATEGORY_ORDER.map((c) => (
          <TabsContent key={c} value={c}>
            <div className="space-y-5 rounded-lg border border-[var(--color-border)] bg-white p-6">
              {byCategory[c].length === 0 && (
                <p className="text-sm text-[var(--color-muted-foreground)]">
                  Aucun paramètre dans cette catégorie.
                </p>
              )}
              {byCategory[c].map((s) => (
                <SettingField
                  key={s.key}
                  setting={s}
                  value={drafts[s.key] ?? s.value}
                  onChange={(v) => setValue(s.key, v)}
                />
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-[var(--color-border)] bg-white/95 backdrop-blur lg:left-60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="text-xs text-[var(--color-muted-foreground)]">
            {bulkSave.isPending
              ? "Enregistrement…"
              : dirty
                ? `${updates.length} modification${updates.length > 1 ? "s" : ""} non enregistrée${updates.length > 1 ? "s" : ""}`
                : "Tout est à jour"}
          </div>
          <Button
            size="sm"
            onClick={() => bulkSave.mutate(updates)}
            disabled={!dirty || bulkSave.isPending}
          >
            {bulkSave.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Enregistrer tout
          </Button>
        </div>
      </div>
    </div>
  );
}

function SettingField({
  setting,
  value,
  onChange,
}: {
  setting: SiteSettingAdmin;
  value: string;
  onChange: (next: string) => void;
}) {
  const id = `setting-${setting.key}`;
  const inputType =
    setting.value_type === "url"
      ? "url"
      : setting.value_type === "phone"
        ? "tel"
        : setting.value_type === "email"
          ? "email"
          : setting.value_type === "integer"
            ? "number"
            : "text";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <Label htmlFor={id} className="text-sm">
          {setting.label_fr || setting.key}
        </Label>
        <code className="text-xs text-[var(--color-muted-foreground)]">
          {setting.key}
        </code>
        {!setting.is_public && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase text-amber-900">
            privé
          </span>
        )}
      </div>
      {setting.description && (
        <p className="text-xs text-[var(--color-muted-foreground)]">
          {setting.description}
        </p>
      )}
      {setting.value_type === "markdown" || setting.value_type === "html" ? (
        <Textarea
          id={id}
          rows={10}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="font-mono text-xs"
          maxLength={2000}
        />
      ) : (
        <Input
          id={id}
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={2000}
          placeholder={
            setting.value_type === "phone"
              ? "+212 6XX XXX XXX"
              : setting.value_type === "url"
                ? "https://…"
                : undefined
          }
        />
      )}
    </div>
  );
}
