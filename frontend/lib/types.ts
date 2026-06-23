// TypeScript shapes that mirror the FastAPI Pydantic schemas.

export type ValueType =
  | "string"
  | "url"
  | "phone"
  | "email"
  | "html"
  | "markdown"
  | "boolean"
  | "integer";

export type SettingCategory =
  | "contact"
  | "branding"
  | "cta"
  | "social"
  | "seo"
  | "admin";

export interface SiteSettingAdmin {
  key: string;
  value: string;
  value_type: ValueType;
  category: SettingCategory;
  label_fr: string;
  description: string | null;
  is_public: boolean;
  updated_at: string;
}

export interface BulkUpdateItem {
  key: string;
  value: string;
}

export interface ArticleAdmin {
  id: number;
  raw_article_id: number;
  slug: string;
  title_darija: string;
  excerpt_darija: string;
  hero_image_url: string | null;
  hero_image_alt: string | null;
  categories: string[];
  tags: string[];
  word_count: number | null;
  reading_time_minutes: number | null;
  is_published: boolean;
  published_at: string | null;
  views_count: number;
  created_at: string;
  updated_at: string;
  /** French summary fields — null until the admin authors them. */
  title_fr: string | null;
  excerpt_fr: string | null;
  /** Auto-flag mode (CLAUDE.md §1 unchanged: hints only, never auto-publish).
   *  Populated by the pipeline after the Proofreader runs on the body. */
  proofread_score_darija: number | null;
  proofread_score_fr: number | null;
  proofread_at: string | null;
  proofread_ready_to_publish: boolean;
  /** ERE editorial score from the linked raw article (read-only context). */
  editorial_score: number | null;
}

export interface AdminArticlesCounts {
  /** Total live (non-soft-deleted) articles. */
  all: number;
  /** Articles with is_published = false. */
  drafts: number;
  /** Drafts the Proofreader flagged ready to publish. */
  ready: number;
  /** Articles with is_published = true. */
  published: number;
  /** Soft-deleted articles (deleted_at IS NOT NULL). */
  archived: number;
}

export interface AdminArticlesListResponse {
  items: ArticleAdmin[];
  counts: AdminArticlesCounts;
}

export interface ArticleAdminDetail extends ArticleAdmin {
  content_darija: string;
  meta_title: string | null;
  meta_description: string | null;
  /** Full French content for the editor. Null until authored. */
  content_fr: string | null;
  meta_title_fr: string | null;
  meta_description_fr: string | null;
}

export interface ArticleUpdate {
  title_darija?: string;
  excerpt_darija?: string;
  content_darija?: string;
  slug?: string;
  meta_title?: string;
  meta_description?: string;
  hero_image_alt?: string;
  categories?: string[];
  tags?: string[];
  /** French variants — set to empty string to clear. */
  title_fr?: string;
  excerpt_fr?: string;
  content_fr?: string;
  meta_title_fr?: string;
  meta_description_fr?: string;
}

export interface ArticlePublic {
  id: number;
  slug: string;
  title_darija: string;
  excerpt_darija: string;
  hero_image_url: string | null;
  hero_image_alt: string | null;
  categories: string[];
  tags: string[];
  word_count: number | null;
  reading_time_minutes: number | null;
  published_at: string | null;
  /** Exposed so sitemap.xml can emit accurate <lastmod>. */
  updated_at: string | null;
  title_fr: string | null;
  excerpt_fr: string | null;
}

export interface ArticlePublicDetail extends ArticlePublic {
  content_darija: string;
  meta_title: string | null;
  meta_description: string | null;
  content_fr: string | null;
  meta_title_fr: string | null;
  meta_description_fr: string | null;
}

// ── Proofreader (AI translation corrector) ────────────────────────────────

export type ProofreadLang = "darija" | "french";
export type ProofreadField = "title" | "excerpt" | "body";
export type ProofreadSeverity = "low" | "medium" | "high";
export type ProofreadCategory =
  | "grammar"
  | "naturalness"
  | "clarity"
  | "consistency";

export interface ProofreadSuggestion {
  original: string;
  suggestion: string;
  reason: string;
  severity: ProofreadSeverity;
  category: ProofreadCategory;
}

export interface ProofreadResult {
  score: number;
  /** Prompt v2+: per-dimension sub-scores. Server returns null when the
   *  cached entry was produced by v1 or the model dropped them. */
  grammar_score: number | null;
  naturalness_score: number | null;
  clarity_score: number | null;
  consistency_score: number | null;
  summary: string;
  suggestions: ProofreadSuggestion[];
  lang: ProofreadLang;
  field: ProofreadField;
  model: string;
  cached: boolean;
}

export interface ProofreadRequest {
  text: string;
  lang: ProofreadLang;
  field: ProofreadField;
}

export interface Source {
  id: number;
  name: string;
  rss_url: string | null;
  scraping_url: string | null;
  is_active: boolean;
  needs_html_enrichment: boolean;
  last_fetched_at: string | null;
  created_at: string;
}
