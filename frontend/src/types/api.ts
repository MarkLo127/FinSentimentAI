// Mirrors backend/schemas/*.py — keep in sync when editing either side.
// (Eventually consider auto-generating via `openapi-typescript` against
// http://localhost:8000/openapi.json.)

export type SentimentLabel = 'positive' | 'negative' | 'neutral'

export interface Stock {
  id: number
  symbol: string
  name: string
  exchange: string | null
  sector: string | null
}

export interface SentimentSnippet {
  sentiment_label: SentimentLabel
  confidence: number
  model_version: string
  is_clickbait: boolean | null
  /** Legacy single-language drivers (Phase 6 and earlier records). */
  key_drivers: string[] | null
  /** Bilingual fields — Phase 7+; null on older rows. */
  title_zh?: string | null
  title_en?: string | null
  key_drivers_zh?: string[] | null
  key_drivers_en?: string[] | null
}

/** Loosely-typed view of `NewsDetail.analysis_metadata` — JSONB blob that
 *  always has `label / confidence / is_clickbait` plus the bilingual fields
 *  on newer records, and the flat legacy keys on older ones. */
export interface AnalysisMeta {
  is_clickbait?: boolean
  key_drivers?: string[]
  reasoning?: string
  title_zh?: string
  title_en?: string
  key_drivers_zh?: string[]
  key_drivers_en?: string[]
  reasoning_zh?: string
  reasoning_en?: string
  fetched_via?: string
  source?: string
  platform?: string
}

export interface NewsListItem {
  id: number
  stock_id: number | null
  title: string
  url: string
  source: string
  language: string
  summary: string | null
  fetched_via: string | null
  content_length: number | null
  published_at: string | null
  fetched_at: string
  sentiment: SentimentSnippet | null
}

export interface NewsDetail extends NewsListItem {
  stock_symbol: string | null
  full_content: string | null
  analysis_metadata: Record<string, unknown> | null
}

export interface MarketHistoryPoint {
  summary_date: string
  sentiment_score: number | null
  positive_count: number
  negative_count: number
  neutral_count: number
  total_count: number
}

export interface MarketTodayResponse {
  today: MarketHistoryPoint
  yesterday: MarketHistoryPoint | null
  change: number | null
}

export interface StockTrendingItem {
  symbol: string
  name: string
  sentiment_score: number | null
  positive_count: number
  negative_count: number
  neutral_count: number
  /** Today's pos+neg+neu count (from market_summary). */
  total_count: number
  /** Lifetime news count for this stock — what the UI shows in 篇數 column. */
  news_count: number
  summary_date: string
  top_keywords: string[] | null
}

export interface StockSentimentPoint {
  summary_date: string
  sentiment_score: number | null
  positive_count: number
  negative_count: number
  neutral_count: number
  total_count: number
}

export interface StockDetail {
  stock: Stock
  sentiment_today: number | null
  trend: StockSentimentPoint[]
  top_keywords: string[]
}

// ─── Auth ──────────────────────────────────────────────────────────────────
export interface UserPublic {
  id: number
  username: string
  email: string
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  expires_in: number
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}

export interface LoginPayload {
  username: string
  password: string
}

// ─── Settings (admin) ───────────────────────────────────────────────────────
export interface SettingStatus {
  key: string
  set_in_db: boolean
  set_in_env: boolean
  is_set: boolean
  updated_at: string | null
}

// ─── On-demand stock refresh (async job + polling) ─────────────────────────
export type RefreshJobState = 'queued' | 'running' | 'succeeded' | 'failed'

export interface RefreshJob {
  id: number
  symbol: string
  state: RefreshJobState
  progress_stage: string | null
  started_at: string | null
  completed_at: string | null
  new_news: number
  new_comments: number
  sentiment_analyzed: number
  error: string | null
  created_at: string
  /** Computed: this job's 1-indexed ordinal among the same symbol's jobs
   *  created today. Lets the UI show "今日第 N 次分析". */
  today_run_number?: number
}

// ─── Stock CRUD ─────────────────────────────────────────────────────────────
export interface StockCreatePayload {
  symbol: string
  /** Optional — when blank, the backend looks up name/exchange/sector via
   *  Finnhub's profile API and falls back to symbol-as-name. */
  name?: string
  exchange?: string | null
  sector?: string | null
}

export interface StockImpact {
  news_count: number
  comment_count: number
  sentiment_count: number
  market_summary_count: number
}
