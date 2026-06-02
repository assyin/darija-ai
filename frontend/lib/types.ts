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
}

export interface ArticleAdminDetail extends ArticleAdmin {
  content_darija: string;
  meta_title: string | null;
  meta_description: string | null;
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
}

export interface ArticlePublicDetail extends ArticlePublic {
  content_darija: string;
  meta_title: string | null;
  meta_description: string | null;
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
