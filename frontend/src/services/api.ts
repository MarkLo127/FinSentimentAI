import axios from 'axios'
import type {
  AuthToken,
  LoginPayload,
  MarketHistoryPoint,
  MarketTodayResponse,
  NewsDetail,
  NewsListItem,
  RefreshJob,
  RegisterPayload,
  SettingStatus,
  Stock,
  StockCreatePayload,
  StockDetail,
  StockImpact,
  StockTrendingItem,
  UserPublic,
} from '../types/api'

export const TOKEN_KEY = 'finsentiment.token'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({
  baseURL,
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ─── Stocks ────────────────────────────────────────────────────────────────
export interface ListStocksParams {
  q?: string
  limit?: number
}

export async function getStocks(params: ListStocksParams = {}): Promise<Stock[]> {
  const { data } = await api.get<Stock[]>('/stocks', { params })
  return data
}

export async function getStock(symbol: string, days = 30): Promise<StockDetail> {
  const { data } = await api.get<StockDetail>(`/stocks/${symbol}`, {
    params: { days },
  })
  return data
}

/** Kick off a background refresh for one stock; returns immediately with a
 *  job record. Poll `getRefreshJob(id)` for progress. The work continues on
 *  the backend even if the browser tab closes. */
export async function startRefresh(symbol: string): Promise<RefreshJob> {
  const { data } = await api.post<RefreshJob>(`/stocks/${symbol}/refresh`)
  return data
}

export async function createStock(payload: StockCreatePayload): Promise<Stock> {
  const { data } = await api.post<Stock>('/stocks', payload)
  return data
}

export async function deleteStock(symbol: string): Promise<void> {
  await api.delete(`/stocks/${symbol}`)
}

export async function getStockImpact(symbol: string): Promise<StockImpact> {
  const { data } = await api.get<StockImpact>(`/stocks/${symbol}/impact`)
  return data
}

// ─── Refresh jobs ──────────────────────────────────────────────────────────
export async function getRefreshJob(jobId: number): Promise<RefreshJob> {
  const { data } = await api.get<RefreshJob>(`/refresh-jobs/${jobId}`)
  return data
}

/** Used on NewsList mount to resume polling after a browser reload — if the
 *  most recent job for this symbol is still running, the page picks back up. */
export async function getLatestRefreshForSymbol(
  symbol: string,
): Promise<RefreshJob | null> {
  const { data } = await api.get<RefreshJob[]>('/refresh-jobs', {
    params: { symbol, limit: 1 },
  })
  return data.length > 0 ? data[0] : null
}

/** Powers the global indicator strip — every queued / running job across all
 *  symbols. Polled every few seconds; the strip hides when this returns []. */
export async function listActiveRefreshJobs(): Promise<RefreshJob[]> {
  const { data } = await api.get<RefreshJob[]>('/refresh-jobs', {
    params: { active: true, limit: 20 },
  })
  return data
}

// ─── Market ────────────────────────────────────────────────────────────────
export async function getMarketToday(): Promise<MarketTodayResponse> {
  const { data } = await api.get<MarketTodayResponse>('/market/today')
  return data
}

export async function getMarketHistory(days = 30): Promise<MarketHistoryPoint[]> {
  const { data } = await api.get<MarketHistoryPoint[]>('/market/history', {
    params: { days },
  })
  return data
}

export async function getMarketTrending(limit = 10): Promise<StockTrendingItem[]> {
  const { data } = await api.get<StockTrendingItem[]>('/market/trending', {
    params: { limit },
  })
  return data
}

// ─── News ──────────────────────────────────────────────────────────────────
export interface ListNewsParams {
  limit?: number
  symbol?: string
  q?: string
}

export async function listNews(params: ListNewsParams = {}): Promise<NewsListItem[]> {
  const { data } = await api.get<NewsListItem[]>('/news', { params })
  return data
}

export async function getNews(id: number): Promise<NewsDetail> {
  const { data } = await api.get<NewsDetail>(`/news/${id}`)
  return data
}

export type NewsTranslationLang = 'zh-TW' | 'en'

export interface NewsTranslationResult {
  title: string
  body: string
  cached: boolean
}

/** Lazy on-demand translation of a news article's title + body. The backend
 *  caches in `news_translations` keyed by (news_id, target_language). First
 *  call costs ~$0.01; subsequent calls are pure DB reads. */
export async function getNewsTranslation(
  id: number,
  lang: NewsTranslationLang,
): Promise<NewsTranslationResult> {
  const { data } = await api.get<NewsTranslationResult>(
    `/news/${id}/translation/${lang}`,
    {
      // First call streams a Claude translation (30-90 s for long articles).
      // Subsequent calls hit the news_translations cache and return in ms.
      // Override the default 15s axios timeout for this slow endpoint only.
      timeout: 120_000,
    },
  )
  return data
}

// ─── Auth ──────────────────────────────────────────────────────────────────
export async function register(payload: RegisterPayload): Promise<UserPublic> {
  const { data } = await api.post<UserPublic>('/auth/register', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<AuthToken> {
  const { data } = await api.post<AuthToken>('/auth/login', payload)
  return data
}

export async function getMe(): Promise<UserPublic> {
  const { data } = await api.get<UserPublic>('/users/me')
  return data
}

// ─── Admin / Settings ──────────────────────────────────────────────────────
export async function getSettingsStatus(): Promise<SettingStatus[]> {
  const { data } = await api.get<SettingStatus[]>('/admin/settings')
  return data
}

export async function setSetting(
  key: string,
  value: string,
): Promise<SettingStatus> {
  const { data } = await api.put<SettingStatus>(`/admin/settings/${key}`, { value })
  return data
}

export async function deleteSetting(key: string): Promise<void> {
  await api.delete(`/admin/settings/${key}`)
}
