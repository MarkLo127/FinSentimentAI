import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { listNews } from '../services/api'
import { relativeTime } from '../lib/format'
import { pickTitle } from '../lib/localizedAnalysis'
import SentimentBadge from './SentimentBadge'
import { Badge, Card, CardHeader } from './ui'

export default function LatestNewsFeed() {
  const { t, i18n } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['news', 'latest'],
    queryFn: () => listNews({ limit: 8 }),
    refetchInterval: 60_000,
  })

  return (
    <Card>
      <CardHeader
        title={t('news_feed.title')}
        action={
          <Link
            to="/news"
            className="inline-flex h-9 items-center px-3 rounded-lg text-sm text-text-muted hover:text-primary hover:bg-primary-soft/40 transition-colors"
          >
            {t('news_feed.view_all')}
          </Link>
        }
      />

      {isLoading && (
        <p className="text-text-subtle text-sm">{t('common.loading')}</p>
      )}
      {error && (
        <p className="text-sentiment-negative text-sm">
          {t('common.failed_to_load')}：{String(error)}
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-text-subtle text-sm">{t('news_feed.empty')}</p>
      )}
      {data && data.length > 0 && (
        <ul className="divide-y divide-border">
          {data.map((n) => (
            <li key={n.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/news/${n.id}`}
                    className="block text-sm md:text-base font-medium text-text hover:text-primary transition-colors line-clamp-2"
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
                    {n.sentiment?.is_clickbait && (
                      <Badge tone="warning" size="sm" icon={<AlertTriangle size={11} />}>
                        {t('sentiment.clickbait')}
                      </Badge>
                    )}
                  </div>
                </div>
                <a
                  href={n.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-text-subtle hover:text-text flex-shrink-0 p-1 -m-1 rounded transition-colors"
                  title={t('news_feed.open_original')}
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
  )
}
