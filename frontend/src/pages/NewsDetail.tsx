import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, ExternalLink, Globe, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import SentimentBadge from '../components/SentimentBadge'
import { Button, Card, CardHeader } from '../components/ui'
import { stripBoilerplate } from '../lib/cleanBody'
import { relativeTime } from '../lib/format'
import {
  pickDrivers,
  pickReasoning,
  pickTitle,
} from '../lib/localizedAnalysis'
import {
  getNews,
  getNewsTranslation,
  type NewsTranslationLang,
} from '../services/api'
import type { AnalysisMeta } from '../types/api'

export default function NewsDetail() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { id = '' } = useParams()
  const newsId = Number(id)
  const [showOriginal, setShowOriginal] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['news', newsId],
    queryFn: () => getNews(newsId),
    enabled: !!newsId,
  })

  const uiLang: NewsTranslationLang = i18n.language.toLowerCase().startsWith('zh')
    ? 'zh-TW'
    : 'en'
  const newsLang = (data?.language ?? '').toLowerCase()
  const uiPrefix = uiLang.toLowerCase().slice(0, 2)
  const needsTranslate = !!data && newsLang.length > 0 && !newsLang.startsWith(uiPrefix)

  const translationQ = useQuery({
    queryKey: ['news-translation', newsId, uiLang],
    queryFn: () => getNewsTranslation(newsId, uiLang),
    enabled: !!data && needsTranslate && !showOriginal,
    staleTime: Infinity,
    retry: 1,
    retryDelay: 2000,
  })

  function goBack() {
    if (window.history.length > 1) {
      navigate(-1)
    } else if (data?.stock_symbol) {
      navigate(`/stocks/${data.stock_symbol}`)
    } else {
      navigate('/news')
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 text-text-subtle text-sm">
        {t('common.loading')}
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="max-w-3xl mx-auto px-4 md:px-6 py-8">
        <p className="text-sentiment-negative">
          {t('news_detail.not_found', { id })}{' '}
          <Link to="/news" className="underline text-primary">
            {t('news_detail.back_to_list')}
          </Link>
        </p>
      </div>
    )
  }

  const meta = data.analysis_metadata as AnalysisMeta | null
  const lang = i18n.language
  const drivers = pickDrivers(meta, lang)
  const reasoning = pickReasoning(meta, lang)

  const translated = translationQ.data
  let displayTitle: string
  if (showOriginal) {
    displayTitle = data.title
  } else if (translated?.title) {
    displayTitle = translated.title
  } else {
    displayTitle = pickTitle(data.sentiment ?? null, data.title, lang)
  }

  let displayBody: string | null | undefined
  if (showOriginal || !translated) {
    displayBody = data.full_content
  } else {
    displayBody = translated.body
  }
  const bodyText = stripBoilerplate(displayBody) || data.summary || t('news_detail.no_body')

  const translatingNow = needsTranslate && !showOriginal && translationQ.isLoading
  const translationFailed = needsTranslate && !showOriginal && translationQ.isError
  const translatedShown = needsTranslate && !showOriginal && !!translated

  return (
    <div className="max-w-3xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 space-y-4 sm:space-y-6">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        leftIcon={<ArrowLeft size={14} />}
        onClick={goBack}
        className="-ml-2"
      >
        {t('news_detail.back')}
      </Button>

      {(translatingNow || translatedShown || translationFailed) && (
        <div className="rounded-lg bg-primary-soft/40 border border-primary/30 px-4 py-3 text-xs text-text flex flex-wrap items-center gap-2">
          {translatingNow && (
            <>
              <Loader2 size={12} className="animate-spin flex-shrink-0 text-primary" />
              <span>{t('news_detail.translating_long', { lang: newsLang || '—' })}</span>
            </>
          )}
          {translatedShown && (
            <>
              <Globe size={12} className="flex-shrink-0 text-primary" />
              <span>
                {t('news_detail.translated_from', { lang: newsLang || '—' })}
              </span>
              <button
                type="button"
                onClick={() => setShowOriginal(true)}
                className="ml-auto underline text-primary hover:text-primary-hover"
              >
                {t('news_detail.view_original')}
              </button>
            </>
          )}
          {translationFailed && (
            <>
              <AlertTriangle size={12} className="flex-shrink-0 text-sentiment-negative" />
              <span>{t('news_detail.translation_failed')}</span>
            </>
          )}
        </div>
      )}

      {showOriginal && needsTranslate && (
        <div className="rounded-lg bg-surface-2 border border-border px-4 py-3 text-xs text-text-muted flex flex-wrap items-center gap-2">
          <span>{t('news_detail.showing_original')}</span>
          <button
            type="button"
            onClick={() => setShowOriginal(false)}
            className="ml-auto underline text-primary hover:text-primary-hover"
          >
            {t('news_detail.view_translation')}
          </button>
        </div>
      )}

      <header className="space-y-3">
        <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold leading-tight break-words text-text">
          {displayTitle}
        </h1>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <span className="text-text-subtle uppercase font-mono text-xs">
            {data.source}
          </span>
          <span className="text-border-strong">·</span>
          <span className="text-text-muted">
            {relativeTime(data.published_at ?? data.fetched_at, t, i18n.language)}
          </span>
          {data.stock_symbol && (
            <>
              <span className="text-border-strong">·</span>
              <Link
                to={`/stocks/${data.stock_symbol}`}
                className="font-mono text-primary underline-offset-2 hover:underline"
              >
                ${data.stock_symbol}
              </Link>
            </>
          )}
          <a
            href={data.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
          >
            {t('news_detail.original_link')} <ExternalLink size={12} />
          </a>
        </div>
      </header>

      {/* Sentiment analysis card */}
      {data.sentiment && (
        <Card>
          <CardHeader
            title={t('news_detail.sentiment_title')}
            action={
              <SentimentBadge
                label={data.sentiment.sentiment_label}
                confidence={data.sentiment.confidence}
              />
            }
          />

          {meta?.is_clickbait && (
            <div className="flex items-start gap-3 p-4 bg-accent-soft border border-accent/30 rounded-lg text-sm text-text mb-4">
              <AlertTriangle size={18} className="mt-0.5 flex-shrink-0 text-accent" />
              <div>
                <p className="font-medium">{t('news_detail.clickbait_title')}</p>
                <p className="text-xs mt-1 text-text-muted">
                  {t('news_detail.clickbait_desc')}
                </p>
              </div>
            </div>
          )}

          <div className="space-y-4">
            {drivers.length > 0 && (
              <div>
                <h3 className="text-xs uppercase tracking-wide text-text-subtle mb-2">
                  {t('news_detail.drivers')}
                </h3>
                <ul className="flex flex-wrap gap-2">
                  {drivers.map((k) => (
                    <li
                      key={k}
                      className="px-3 py-1.5 rounded-full bg-surface-2 border border-border text-sm text-text-muted"
                    >
                      {k}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {reasoning && (
              <div>
                <h3 className="text-xs uppercase tracking-wide text-text-subtle mb-2">
                  {t('news_detail.reasoning')}
                </h3>
                <p className="text-sm text-text leading-relaxed break-words">
                  {reasoning}
                </p>
              </div>
            )}
          </div>

          <p className="text-[10px] text-text-subtle pt-4 mt-4 border-t border-border font-mono">
            model: {data.sentiment.model_version} · fetched_via:{' '}
            {data.fetched_via ?? '—'} ·{' '}
            {data.content_length != null ? `${data.content_length} chars` : '—'}
          </p>
        </Card>
      )}

      {/* Full body */}
      <Card>
        <CardHeader title={t('news_detail.full_body')} />
        {data.fetched_via === 'snippet' && (
          <div className="flex items-start gap-2 text-xs text-accent bg-accent-soft border border-accent/30 rounded-lg p-3 mb-4">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <span>{t('news_detail.snippet_warning')}</span>
          </div>
        )}
        <div className="whitespace-pre-wrap [overflow-wrap:anywhere] text-sm md:text-base leading-relaxed text-text max-w-2xl">
          {bodyText}
        </div>
      </Card>
    </div>
  )
}
