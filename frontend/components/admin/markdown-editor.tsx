"use client";

import * as React from "react";

import { ProofreadingRtlContent } from "@/components/admin/proofreading-rtl-content";
import { RtlContent } from "@/components/shared/rtl-content";
import { Textarea } from "@/components/ui/textarea";
import type { ProofreadSuggestion } from "@/lib/types";
import { cn } from "@/lib/utils";

interface MarkdownEditorProps {
  value: string;
  onChange: (next: string) => void;
  onBlur?: () => void;
  className?: string;
  placeholder?: string;
  /** When provided, the preview pane renders Grammarly-style inline
   *  highlights for each suggestion's `original` phrase. */
  suggestions?: ProofreadSuggestion[];
  /** Currently focused/hovered suggestion in the sidebar — its highlight
   *  is given a stronger ring so it stands out. */
  activeSuggestion?: number | null;
  /** Click handler for inline highlights — typically scrolls/opens the
   *  matching row in the sidebar. */
  onSuggestionClick?: (index: number) => void;
}

export function MarkdownEditor({
  value,
  onChange,
  onBlur,
  className,
  placeholder,
  suggestions,
  activeSuggestion,
  onSuggestionClick,
}: MarkdownEditorProps) {
  const [activeTab, setActiveTab] = React.useState<"editor" | "preview">("editor");

  return (
    <div className={cn("rounded-lg border border-[var(--color-border)] bg-white", className)}>
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] bg-slate-50 px-3 py-2 lg:hidden">
        <button
          type="button"
          onClick={() => setActiveTab("editor")}
          className={cn(
            "rounded-md px-3 py-1 text-xs font-medium transition-colors",
            activeTab === "editor"
              ? "bg-white shadow-sm"
              : "text-[var(--color-muted-foreground)]",
          )}
        >
          Éditeur
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("preview")}
          className={cn(
            "rounded-md px-3 py-1 text-xs font-medium transition-colors",
            activeTab === "preview"
              ? "bg-white shadow-sm"
              : "text-[var(--color-muted-foreground)]",
          )}
        >
          Aperçu RTL
        </button>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div
          className={cn(
            "border-b border-[var(--color-border)] lg:border-b-0 lg:border-r",
            activeTab === "editor" ? "block" : "hidden lg:block",
          )}
        >
          <div className="border-b border-[var(--color-border)] bg-slate-50 px-3 py-2 text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Markdown · darija
          </div>
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={onBlur}
            placeholder={placeholder}
            dir="auto"
            spellCheck={false}
            className="font-tajawal editor-scrollbar min-h-[60vh] w-full resize-none rounded-none border-0 px-4 py-3 text-base leading-relaxed shadow-none focus-visible:ring-0"
          />
        </div>
        <div
          className={cn(
            "max-h-[80vh] overflow-y-auto editor-scrollbar",
            activeTab === "preview" ? "block" : "hidden lg:block",
          )}
        >
          <div className="border-b border-[var(--color-border)] bg-slate-50 px-3 py-2 text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Aperçu (RTL)
          </div>
          <div className="p-4">
            {value.trim() ? (
              suggestions && suggestions.length > 0 ? (
                <ProofreadingRtlContent
                  markdown={value}
                  suggestions={suggestions}
                  activeIndex={activeSuggestion ?? null}
                  onSuggestionClick={onSuggestionClick}
                />
              ) : (
                <RtlContent markdown={value} />
              )
            ) : (
              <p className="text-sm text-[var(--color-muted-foreground)]">
                Tapez du markdown pour voir l&apos;aperçu en RTL.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
