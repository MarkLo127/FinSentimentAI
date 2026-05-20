import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ExternalLink, Loader2, Search, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import AddStockForm from '../components/AddStockForm'
import SentimentBadge from '../components/SentimentBadge'
import { Badge, Button, Card, Input } from '../components/ui'
import { relativeTime } from '../lib/format'
import { pickTitle } from '../lib/localizedAnalysis'
import { stageLabel } from '../lib/refreshLabels'
import {
  getLatestRefreshForSymbol,
  getRefreshJob,
  getStocks,
  listNews,
  startRefresh,
} from '../services/api'

export default function NewsList() {
  const { t, i18n } = useTranslation()
  const [params, setParams] = useSearchParams()
  const urlQ = params.get('q') ?? ''
  const urlSymbol = params.get('symbol') ?? ''
  const [localQ, setLocalQ] = useState(urlQ)
  const [activeJobId, setActiveJobId] = useState<number | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const autoTriggeredFor = useRef<string | null>(null)

  useEffect(() => {
    setLocalQ(urlQ)
  }, [urlQ])

  useEffect(() => {
    setActiveJobId(null)
    setAddOpen(false)
    autoTriggeredFor.current = null
  }, [urlQ, urlSymbol])

  const qc = useQueryClient()
  const newsQ = useQuery({
    queryKey: ['news', { q: urlQ, symbol: urlSymbol, limit: 50 }],
    queryFn: () =>
      listNews({
        q: urlQ || undefined,
        symbol: urlSymbol || undefined,
        limit: 50,
      }),
  })

  const stockMatchQ = useQuery({
    queryKey: ['stocks', { q: urlQ }],
    queryFn: () => getStocks({ q: urlQ, limit: 5 }),
    enabled: !!urlQ,
  })
  const matchingStock = stockMatchQ.data?.[0]

  const latestJobQ = useQuery({
    queryKey: ['refresh-job', 'latest', matchingStock?.symbol],
    queryFn: () => getLatestRefreshForSymbol(matchingStock!.symbol),
    enabled: !!matchingStock,
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
    mutationFn: (symbol: string) => startRefresh(symbol),
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
      qc.invalidateQueries({ queryKey: ['news'] })
      qc.invalidateQueries({ queryKey: ['market'] })
      qc.invalidateQueries({ queryKey: ['stock', j.symbol] })
    }
  }, [jobQ.data, qc])

  useEffect(() => {
    if (
      newsQ.data &&
      newsQ.data.length === 0 &&
      matchingStock &&
      autoTriggeredFor.current !== matchingStock.symbol &&
      activeJobId == null &&
      !latestJobQ.isLoading &&
      !startMut.isPending
    ) {
      const recent = latestJobQ.data
      if (recent && (recent.state === 'queued' || recent.state === 'running')) {
        return
      }
      autoTriggeredFor.current = matchingStock.symbol
      startMut.mutate(matchingStock.symbol)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    newsQ.data?.length,
    matchingStock?.symbol,
    activeJobId,
    latestJobQ.isLoading,
    latestJobQ.data?.state,
  ])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const next = new URLSearchParams(params)
    if (localQ) next.set('q', localQ)
    else next.delete('q')
    setParams(next)
  }

  function clearFilters() {
    setLocalQ('')
    setParams({})
  }

  const hasFilter = urlQ || urlSymbol
  const job = jobQ.data
  const showProgressBanner =
    job && (job.state === 'queued' || job.state === 'running' || job.state === 'failed')

  const searchAsSymbol = urlQ.trim().toUpperCase()
  const showAddStockCta =
    newsQ.data &&
    newsQ.data.length === 0 &&
    !matchingStock &&
    !!urlQ &&
    !stockMatchQ.isLoading &&
    !showProgressBanner

  return (
    <div className="max-w-5xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 space-y-4 sm:space-y-6">
      <header>
        <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold text-text">
          {t('news_list.title')}
        </h1>
        <p className="text-sm md:text-base text-text-muted mt-1">
          {t('news_list.subtitle')}
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2">
        <div className="flex-1 min-w-0">
          <Input
            type="text"
            value={localQ}
            onChange={(e) => setLocalQ(e.target.value)}
            placeholder={t('news_list.search_placeholder')}
            leftIcon={<Search size={16} />}
          />
        </div>
        <div className="flex gap-2 sm:flex-shrink-0">
          <Button
            type="submit"
            variant="primary"
            size="md"
            className="flex-1 sm:flex-initial"
          >
            {t('common.search')}
          </Button>
          {hasFilter && (
            <Button type="button" variant="ghost" size="md" onClick={clearFilters}>
              {t('common.clear')}
            </Button>
          )}
        </div>
      </form>

      {hasFilter && (
        <p className="text-sm text-text-muted">
          {t('news_list.filter_label')}
          {urlSymbol && (
            <Badge tone="info" size="sm" className="ml-2 font-mono">
              {urlSymbol}
            </Badge>
          )}
          {urlQ && (
            <Badge tone="neutral" size="sm" className="ml-2">
              「{urlQ}」
            </Badge>
          )}
        </p>
      )}

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
                {matchingStock && (
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    className="mt-3"
                    leftIcon={<Sparkles size={14} />}
                    onClick={() => {
                      autoTriggeredFor.current = matchingStock.symbol
                      startMut.mutate(matchingStock.symbol)
                    }}
                  >
                    {t('common.retry')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      <Card padding="md" className="p-0 overflow-hidden">
        {newsQ.isLoading && (
          <p className="p-6 text-text-subtle text-sm">{t('common.loading')}</p>
        )}
        {newsQ.error && (
          <p className="p-6 text-sentiment-negative text-sm">
            {t('common.failed_to_load')}：{String(newsQ.error)}
          </p>
        )}
        {showAddStockCta && (
          <div className="p-6 space-y-4">
            <div>
              <p className="text-sm text-text">
                {t('news_list.no_stock_prompt', { symbol: searchAsSymbol })}
              </p>
              <p className="text-xs text-text-subtle mt-1">
                {t('news_list.no_stock_hint')}
              </p>
            </div>
            {!addOpen ? (
              <Button
                type="button"
                variant="primary"
                size="md"
                leftIcon={<Sparkles size={16} />}
                onClick={() => setAddOpen(true)}
              >
                {t('news_list.add_and_analyze', { symbol: searchAsSymbol })}
              </Button>
            ) : (
              <AddStockForm
                defaultSymbol={searchAsSymbol}
                autoRefresh={true}
                onClose={() => setAddOpen(false)}
                onCreated={(_, job) => {
                  if (job) setActiveJobId(job.id)
                  qc.invalidateQueries({ queryKey: ['stocks', { q: urlQ }] })
                }}
              />
            )}
          </div>
        )}
        {newsQ.data && newsQ.data.length === 0 && !matchingStock && !urlQ && (
          <p className="p-6 text-text-subtle text-sm">{t('news_list.empty')}</p>
        )}
        {newsQ.data && newsQ.data.length === 0 && matchingStock && !showProgressBanner && (
          <div className="p-6 space-y-4">
            <p className="text-sm text-text-muted">
              {t('news_list.never_fetched', {
                symbol: matchingStock.symbol,
                name: matchingStock.name,
              })}
            </p>
            <Button
              type="button"
              variant="primary"
              size="md"
              leftIcon={<Sparkles size={16} />}
              onClick={() => startMut.mutate(matchingStock.symbol)}
              loading={startMut.isPending}
            >
              {t('news_list.fetch_now', { symbol: matchingStock.symbol })}
            </Button>
          </div>
        )}
        {newsQ.data && newsQ.data.length > 0 && (
          <ul className="divide-y divide-border">
            {newsQ.data.map((n) => (
              <li
                key={n.id}
                className="p-4 md:p-5 hover:bg-surface-2 transition-colors duration-150"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/news/${n.id}`}
                      className="block font-medium text-text hover:text-primary transition-colors line-clamp-2"
                    >
                      {pickTitle(n.sentiment, n.title, i18n.language)}
                    </Link>
                    {n.summary && (
                      <p className="text-sm text-text-muted mt-2 line-clamp-2">
                        {n.summary}
                      </p>
                    )}
                    <div className="mt-3 flex items-center gap-2 flex-wrap text-xs">
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
                      {n.sentiment?.is_clickbait && (
                        <Badge tone="warning" size="sm" icon={<AlertTriangle size={11} />}>
                          {t('sentiment.clickbait')}
                        </Badge>
                      )}
                      {n.fetched_via && n.fetched_via !== 'jina' && (
                        <span className="text-[10px] text-text-subtle">
                          ({n.fetched_via})
                        </span>
                      )}
                    </div>
                  </div>
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-subtle hover:text-text flex-shrink-0 mt-1 p-1 -m-1 rounded transition-colors"
                    aria-label={t('news_feed.open_original')}
                  >
                    <ExternalLink size={14} />
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
