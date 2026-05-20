import { useQuery } from '@tanstack/react-query'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getMarketToday } from '../services/api'
import { formatScore, scoreColor } from '../lib/format'
import { Card, CardHeader } from './ui'
import { cn } from '../lib/cn'

function changeIcon(change: number | null | undefined) {
  if (change == null) return <Minus size={18} />
  if (change > 0.01) return <TrendingUp size={18} />
  if (change < -0.01) return <TrendingDown size={18} />
  return <Minus size={18} />
}

export default function MarketSentimentCard() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['market', 'today'],
    queryFn: getMarketToday,
    refetchInterval: 60_000,
  })

  return (
    <Card>
      <CardHeader
        title={t('market.today_title')}
        meta={data?.today.summary_date}
      />

      {isLoading && (
        <p className="text-text-subtle text-sm">{t('common.loading')}</p>
      )}
      {error && (
        <p className="text-sentiment-negative text-sm">
          {t('common.failed_to_load')}：{String(error)}
        </p>
      )}
      {data && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-baseline gap-4">
            <p
              className={cn(
                'text-2xl sm:text-3xl md:text-4xl font-bold font-mono tabular-nums',
                scoreColor(data.today.sentiment_score),
              )}
            >
              {formatScore(data.today.sentiment_score)}
            </p>
            {data.change != null && (
              <p
                className={cn(
                  'inline-flex items-center gap-1 text-sm md:text-base font-mono font-medium',
                  scoreColor(data.change),
                )}
              >
                {changeIcon(data.change)}
                {formatScore(data.change)}
              </p>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3 pt-4 border-t border-border">
            <Stat
              label={t('market.positive')}
              value={data.today.positive_count}
              tone="positive"
            />
            <Stat
              label={t('market.neutral')}
              value={data.today.neutral_count}
              tone="neutral"
            />
            <Stat
              label={t('market.negative')}
              value={data.today.negative_count}
              tone="negative"
            />
          </div>
        </div>
      )}
    </Card>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'positive' | 'neutral' | 'negative'
}) {
  const toneClass = {
    positive: 'text-sentiment-positive',
    neutral: 'text-sentiment-neutral',
    negative: 'text-sentiment-negative',
  }[tone]
  return (
    <div className="text-center">
      <div className="text-xs text-text-subtle mb-1">{label}</div>
      <div
        className={cn('text-lg sm:text-xl md:text-2xl font-semibold font-mono tabular-nums', toneClass)}
      >
        {value}
      </div>
    </div>
  )
}
