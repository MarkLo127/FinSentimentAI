import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Loader2, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import SentimentBadge from '../components/SentimentBadge'
import { Badge, Button, Card, CardHeader } from '../components/ui'
import { cn } from '../lib/cn'
import { useChartTokens } from '../lib/chartTokens'
import { useIsMobile } from '../lib/useMediaQuery'
import { formatScore, relativeTime, scoreColor } from '../lib/format'
import { pickTitle } from '../lib/localizedAnalysis'
import { stageLabel } from '../lib/refreshLabels'
import {
  getLatestRefreshForSymbol,
  getRefreshJob,
  getStock,
  listNews,
  startRefresh,
} from '../services/api'

type SentimentFilter = 'all' | 'positive' | 'neutral' | 'negative'

// Fixed lookback window — data is sparse enough that letting the user pick
// 7/30/90 doesn't add value; 90 always captures everything we have.
const RANGE_DAYS = 90

export default function StockDetail() {
  const { t, i18n } = useTranslation()
  const { symbol = '' } = useParams()
  const tokens = useChartTokens()
  const isMobile = useIsMobile()
  const [sentFilter, setSentFilter] = useState<SentimentFilter>('all')
  const [activeJobId, setActiveJobId] = useState<number | null>(null)
  const qc = useQueryClient()

  const stockQ = useQuery({
    queryKey: ['stock', symbol, RANGE_DAYS],
    queryFn: () => getStock(symbol, RANGE_DAYS),
    enabled: !!symbol,
  })
  const newsQ = useQuery({
    queryKey: ['news', { symbol, limit: 100 }],
    queryFn: () => listNews({ symbol, limit: 100 }),
    enabled: !!symbol,
  })

  const latestJobQ = useQuery({
    queryKey: ['refresh-job', 'latest', symbol],
    queryFn: () => getLatestRefreshForSymbol(symbol),
    enabled: !!symbol,
  })
  useEffect(() => {
    if (
      latestJobQ.data &&
      (latestJobQ.data.state === 'queued' || latestJobQ.data.state === 'running')
    ) {
      setActiveJobId(latestJobQ.data.id)
    }
  }, [latestJobQ.data])

  const startMut = useMutation({
    mutationFn: () => startRefresh(symbol),
    onSuccess: (job) => setActiveJobId(job.id),
  })

  const jobQ = useQuery({
    queryKey: ['refresh-job', activeJobId],
    queryFn: () => getRefreshJob(activeJobId!),
    enabled: activeJobId != null,
    refetchInterval: (q) => {
      const j = q.state.data
      if (!j) return 2000
      return j.state === 'queued' || j.state === 'running' ? 2000 : false
    },
  })

  const lastSucceededId = useRef<number | null>(null)
  useEffect(() => {
    const j = jobQ.data
    if (j && j.state === 'succeeded' && j.id !== lastSucceededId.current) {
      lastSucceededId.current = j.id
      qc.invalidateQueries({ queryKey: ['stock', symbol] })
      qc.invalidateQueries({ queryKey: ['news', { symbol, limit: 10 }] })
      qc.invalidateQueries({ queryKey: ['market'] })
    }
  }, [jobQ.data, qc, symbol])

  if (stockQ.isError) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <p className="text-sentiment-negative">
          {t('stock_detail.not_found', { symbol })}{' '}
          <Link to="/" className="underline text-primary">
            {t('stock_detail.back_home')}
          </Link>
        </p>
      </div>
    )
  }

  const stock = stockQ.data?.stock
  const trend = stockQ.data?.trend ?? []
  const job = jobQ.data
  const showProgressBanner =
    job && (job.state === 'queued' || job.state === 'running' || job.state === 'failed')

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 space-y-4 sm:space-y-6 md:space-y-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold break-words text-text">
            <span className="font-mono text-primary">{symbol}</span>
            {stock && (
              <span className="block sm:inline ml-0 sm:ml-3 text-text-muted">
                {stock.name}
              </span>
            )}
          </h1>
          {stock && (
            <p className="text-sm text-text-subtle mt-1">
              {stock.exchange} · {stock.sector ?? '—'}
            </p>
          )}
        </div>
        {stockQ.data?.sentiment_today != null && (
          <p
            className={cn(
              'text-xl sm:text-2xl md:text-3xl font-bold font-mono tabular-nums',
              scoreColor(stockQ.data.sentiment_today),
            )}
          >
            {formatScore(stockQ.data.sentiment_today)}
          </p>
        )}
      </header>

      {showProgressBanner && (
        <Card padding="sm" className="bg-primary-soft/40 border-primary/30">
          {(job.state === 'queued' || job.state === 'running') && (
            <div className="flex items-center gap-3 text-text">
              <Loader2 size={16} className="animate-spin flex-shrink-0 text-primary" />
              <div className="flex-1 min-w-0">
                <p className="text-sm">
                  <span className="font-mono font-medium">{job.symbol}</span>
                  {job.today_run_number && job.today_run_number > 1 && (
                    <Badge tone="info" size="sm" className="ml-2">
                      {t('refresh.run_number', { n: job.today_run_number })}
                    </Badge>
                  )}{' '}
                  — {stageLabel(job, t)}
                </p>
                <p className="text-xs text-text-muted mt-0.5">
                  {t('refresh.background_hint', { id: job.id })}
                </p>
              </div>
            </div>
          )}
          {job.state === 'failed' && (
            <div className="flex items-start gap-3">
              <AlertTriangle
                size={18}
                className="mt-0.5 flex-shrink-0 text-sentiment-negative"
              />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text">{t('refresh.failed')}</p>
                <p className="text-xs mt-0.5 text-text-muted">{job.error}</p>
                <Button
                  type="button"
                  size="sm"
                  variant="primary"
                  className="mt-3"
                  leftIcon={<Sparkles size={14} />}
                  onClick={() => startMut.mutate()}
                  loading={startMut.isPending}
                >
                  {t('common.retry')}
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Sentiment stats — daily grouped bars (pos / neutral / neg) */}
      <Card>
        <CardHeader title={t('stats.title')} />
        {stockQ.isLoading && (
          <p className="text-text-subtle h-64 flex items-center text-sm">
            {t('common.loading')}
          </p>
        )}
        {trend.length === 0 && !stockQ.isLoading && !showProgressBanner && (
          <div className="h-64 flex flex-col items-center justify-center gap-4">
            <p className="text-text-subtle text-sm">{t('stock_detail.no_data')}</p>
            <Button
              type="button"
              size="md"
              variant="primary"
              leftIcon={<Sparkles size={16} />}
              onClick={() => startMut.mutate()}
              loading={startMut.isPending}
            >
              {t('stock_detail.fetch_now', { symbol })}
            </Button>
          </div>
        )}
        {trend.length === 0 && showProgressBanner && (
          <p className="text-text-subtle h-64 flex items-center text-sm">
            {t('stock_detail.waiting_first_data')}
          </p>
        )}
        {trend.length > 0 && (
          <div className="h-56 sm:h-64 md:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={trend.map((p) => ({
                  label: p.summary_date.slice(5),
                  positive: p.positive_count,
                  neutral: p.neutral_count,
                  negative: p.negative_count,
                }))}
                margin={{ top: 10, right: isMobile ? 4 : 20, bottom: 0, left: isMobile ? -20 : -10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: isMobile ? 10 : 11, fill: tokens.axis }}
                  stroke={tokens.grid}
                  interval={isMobile ? Math.max(0, Math.floor(trend.length / 6) - 1) : 'preserveStartEnd'}
                  minTickGap={isMobile ? 8 : 4}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: isMobile ? 10 : 11, fill: tokens.axis }}
                  stroke={tokens.grid}
                  width={isMobile ? 28 : 40}
                />
                <Tooltip
                  cursor={{ fill: tokens.grid, opacity: 0.4 }}
                  contentStyle={{
                    borderRadius: 10,
                    fontSize: 12,
                    background: tokens.tooltipBg,
                    border: `1px solid ${tokens.tooltipBorder}`,
                    color: tokens.text,
                  }}
                  labelStyle={{ color: tokens.text }}
                  formatter={(v, name) => [v as number, t(`sentiment.${String(name)}`)]}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12, color: tokens.text }}
                  formatter={(value) => t(`sentiment.${value}`)}
                />
                <Bar dataKey="positive" fill={tokens.positive} radius={[4, 4, 0, 0]} />
                <Bar dataKey="neutral" fill={tokens.neutral} radius={[4, 4, 0, 0]} />
                <Bar dataKey="negative" fill={tokens.negative} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {trend.length > 0 && (
          <p className="text-xs text-text-subtle mt-2">{t('stats.hint')}</p>
        )}
      </Card>

      {/* Top keywords for the latest day */}
      {stockQ.data && stockQ.data.top_keywords.length > 0 && (
        <Card>
          <CardHeader title={t('stock_detail.drivers_latest')} />
          <ul className="flex flex-wrap gap-2">
            {stockQ.data.top_keywords.map((k) => (
              <li
                key={k}
                className="px-3 py-1.5 rounded-full bg-surface-2 border border-border text-sm text-text-muted"
              >
                {k}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Stock-specific news list */}
      <Card>
        <CardHeader
          title={t('stock_detail.recent_news')}
          meta={
            newsQ.data
              ? sentFilter === 'all'
                ? t('stock_detail.news_count', { n: newsQ.data.length })
                : t('stock_detail.news_count_filtered', {
                    shown: newsQ.data.filter(
                      (n) => n.sentiment?.sentiment_label === sentFilter,
                    ).length,
                    total: newsQ.data.length,
                  })
              : undefined
          }
        />

        {newsQ.data && newsQ.data.length > 0 && (() => {
          const counts = {
            all: newsQ.data.length,
            positive: newsQ.data.filter(
              (n) => n.sentiment?.sentiment_label === 'positive',
            ).length,
            neutral: newsQ.data.filter(
              (n) => n.sentiment?.sentiment_label === 'neutral',
            ).length,
            negative: newsQ.data.filter(
              (n) => n.sentiment?.sentiment_label === 'negative',
            ).length,
          }
          const chip = (key: SentimentFilter, label: string) => (
            <button
              key={key}
              type="button"
              onClick={() => setSentFilter(key)}
              className={cn(
                'inline-flex items-center h-9 px-3.5 rounded-lg text-sm font-medium whitespace-nowrap',
                'transition-colors duration-150',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
                sentFilter === key
                  ? 'bg-primary text-white'
                  : 'bg-surface-2 text-text-muted hover:text-text hover:bg-surface',
              )}
            >
              {label}
              <span className="ml-1.5 opacity-75 font-mono tabular-nums">
                ({counts[key]})
              </span>
            </button>
          )
          return (
            <div className="flex flex-wrap gap-2 mb-4">
              {chip('all', t('stock_detail.filter_all'))}
              {chip('positive', t('sentiment.positive'))}
              {chip('neutral', t('sentiment.neutral'))}
              {chip('negative', t('sentiment.negative'))}
            </div>
          )
        })()}

        {newsQ.isLoading && (
          <p className="text-text-subtle text-sm">{t('common.loading')}</p>
        )}
        {newsQ.data && newsQ.data.length === 0 && (
          <p className="text-text-subtle text-sm">{t('stock_detail.no_news')}</p>
        )}
        {newsQ.data && newsQ.data.length > 0 && (() => {
          const filtered =
            sentFilter === 'all'
              ? newsQ.data
              : newsQ.data.filter(
                  (n) => n.sentiment?.sentiment_label === sentFilter,
                )
          if (filtered.length === 0) {
            return (
              <p className="text-text-subtle text-sm">
                {t('stock_detail.no_news_for_filter')}
              </p>
            )
          }
          return (
            <ol className="divide-y divide-border">
              {filtered.map((n, idx) => (
                <li key={n.id} className="py-4 first:pt-0 last:pb-0 flex gap-3">
                  <span className="text-xs text-text-subtle font-mono tabular-nums pt-1 w-8 flex-shrink-0 text-right">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/news/${n.id}`}
                      className="block font-medium text-text hover:text-primary transition-colors line-clamp-2"
                    >
                      {pickTitle(n.sentiment, n.title, i18n.language)}
                    </Link>
                    <div className="mt-2 flex items-center gap-2 flex-wrap text-xs">
                      <span className="text-text-subtle uppercase font-mono">
                        {n.source}
                      </span>
                      <span className="text-border-strong">·</span>
                      <span className="text-text-muted">
                        {relativeTime(n.published_at ?? n.fetched_at, t, i18n.language)}
                      </span>
                      {n.sentiment && (
                        <SentimentBadge
                          label={n.sentiment.sentiment_label}
                          confidence={n.sentiment.confidence}
                          size="sm"
                        />
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )
        })()}
      </Card>
    </div>
  )
}
