import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { getMarketTrending } from '../services/api'
import type { Stock, StockTrendingItem } from '../types/api'
import { formatScore, scoreColor } from '../lib/format'
import { cn } from '../lib/cn'
import AddStockForm from './AddStockForm'
import DeleteStockDialog from './DeleteStockDialog'
import { Button, Card, CardHeader, IconButton } from './ui'

export default function TopStockRanking() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data, isLoading, error } = useQuery({
    queryKey: ['market', 'trending'],
    queryFn: () => getMarketTrending(10),
  })
  const [confirming, setConfirming] = useState<Stock | null>(null)
  const [adding, setAdding] = useState(false)

  function openDelete(s: StockTrendingItem) {
    setConfirming({
      id: 0,
      symbol: s.symbol,
      name: s.name,
      exchange: null,
      sector: null,
    })
  }

  return (
    <Card>
      <CardHeader
        title={t('ranking.title')}
        meta={data && data.length > 0 ? data[0].summary_date : undefined}
        action={
          <Button
            type="button"
            size="sm"
            variant="primary"
            leftIcon={<Plus size={14} />}
            onClick={() => setAdding((a) => !a)}
          >
            {t('ranking.add')}
          </Button>
        }
      />

      {adding && (
        <div className="mb-4">
          <AddStockForm
            autoRefresh={false}
            onClose={() => setAdding(false)}
            onCreated={(s) => navigate(`/stocks/${s.symbol}`)}
          />
        </div>
      )}

      {isLoading && (
        <p className="text-text-subtle text-sm">{t('common.loading')}</p>
      )}
      {error && (
        <p className="text-sentiment-negative text-sm">
          {t('common.failed_to_load')}：{String(error)}
        </p>
      )}
      {data && data.length === 0 && !adding && (
        <p className="text-text-subtle text-sm">{t('ranking.empty')}</p>
      )}

      {/* Mobile: card list (<md) */}
      {data && data.length > 0 && (
        <ul className="md:hidden divide-y divide-border -mx-1">
          {data.map((s, idx) => (
            <li key={s.symbol} className="py-3 px-1">
              <div className="flex items-start gap-3">
                <span className="text-text-subtle font-mono tabular-nums text-sm w-6 flex-shrink-0 pt-0.5">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <Link
                      to={`/stocks/${s.symbol}`}
                      className="font-mono font-semibold text-primary underline-offset-2 hover:underline"
                    >
                      {s.symbol}
                    </Link>
                    <span
                      className={cn(
                        'font-mono font-semibold tabular-nums text-base',
                        scoreColor(s.sentiment_score),
                      )}
                    >
                      {formatScore(s.sentiment_score)}
                    </span>
                  </div>
                  <p className="text-sm text-text-muted truncate mb-2">
                    {s.name}
                  </p>
                  <div className="flex items-center gap-3 text-xs font-mono tabular-nums text-text-muted">
                    <span className="text-sentiment-positive">+{s.positive_count}</span>
                    <span className="text-sentiment-neutral">·{s.neutral_count}</span>
                    <span className="text-sentiment-negative">−{s.negative_count}</span>
                    <span className="text-text-subtle ml-auto">
                      Σ {s.total_count}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-2 ml-9 flex items-center gap-1">
                <Link
                  to={`/stocks/${s.symbol}`}
                  className="inline-flex items-center gap-1 h-8 px-3 rounded-md text-xs text-primary bg-primary-soft/60 hover:bg-primary-soft transition-colors"
                  title={t('ranking.view_aria', { symbol: s.symbol })}
                >
                  {t('ranking.view')}
                  <ArrowRight size={12} />
                </Link>
                <IconButton
                  size="sm"
                  variant="danger"
                  onClick={() => openDelete(s)}
                  title={t('ranking.delete_aria', { symbol: s.symbol })}
                  aria-label={t('ranking.delete_aria', { symbol: s.symbol })}
                >
                  <Trash2 size={14} />
                </IconButton>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Desktop: full table (md+) */}
      {data && data.length > 0 && (
        <div className="hidden md:block overflow-x-auto -mx-2 md:-mx-4">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs text-text-subtle uppercase tracking-wide">
                <th className="text-left font-medium py-2 px-2">
                  {t('ranking.col_rank')}
                </th>
                <th className="text-left font-medium py-2 px-2">
                  {t('ranking.col_symbol_name')}
                </th>
                <th className="text-right font-medium py-2 px-2 whitespace-nowrap">
                  {t('ranking.col_score')}
                </th>
                <th className="text-right font-medium py-2 px-2 text-sentiment-positive whitespace-nowrap">
                  {t('sentiment.positive')}
                </th>
                <th className="text-right font-medium py-2 px-2 text-sentiment-neutral whitespace-nowrap">
                  {t('sentiment.neutral')}
                </th>
                <th className="text-right font-medium py-2 px-2 text-sentiment-negative whitespace-nowrap">
                  {t('sentiment.negative')}
                </th>
                <th className="text-right font-medium py-2 px-2 whitespace-nowrap">
                  {t('ranking.col_count')}
                </th>
                <th className="text-right font-medium py-2 px-2 whitespace-nowrap">
                  {t('ranking.col_actions')}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((s, idx) => (
                <tr
                  key={s.symbol}
                  className="border-t border-border hover:bg-surface-2 transition-colors duration-150"
                >
                  <td className="py-3 px-2 text-text-subtle font-mono tabular-nums">
                    {idx + 1}
                  </td>
                  <td className="py-3 px-2 min-w-0">
                    <Link
                      to={`/stocks/${s.symbol}`}
                      className="font-mono font-medium text-primary underline-offset-2 hover:underline"
                    >
                      {s.symbol}
                    </Link>
                    <span className="ml-2 text-text-muted truncate">{s.name}</span>
                  </td>
                  <td
                    className={cn(
                      'py-3 px-2 text-right font-mono font-semibold tabular-nums whitespace-nowrap',
                      scoreColor(s.sentiment_score),
                    )}
                  >
                    {formatScore(s.sentiment_score)}
                  </td>
                  <td className="py-3 px-2 text-right text-sentiment-positive font-mono tabular-nums whitespace-nowrap">
                    {s.positive_count}
                  </td>
                  <td className="py-3 px-2 text-right text-sentiment-neutral font-mono tabular-nums whitespace-nowrap">
                    {s.neutral_count}
                  </td>
                  <td className="py-3 px-2 text-right text-sentiment-negative font-mono tabular-nums whitespace-nowrap">
                    {s.negative_count}
                  </td>
                  <td className="py-3 px-2 text-right text-text-muted font-mono tabular-nums whitespace-nowrap">
                    {s.total_count}
                  </td>
                  <td className="py-3 px-2 text-right whitespace-nowrap">
                    <div className="inline-flex items-center gap-1">
                      <Link
                        to={`/stocks/${s.symbol}`}
                        className="inline-flex items-center gap-1 h-8 px-2.5 rounded-md text-xs text-primary hover:bg-primary-soft transition-colors"
                        title={t('ranking.view_aria', { symbol: s.symbol })}
                      >
                        {t('ranking.view')}
                        <ArrowRight size={12} />
                      </Link>
                      <IconButton
                        size="sm"
                        variant="danger"
                        onClick={() => openDelete(s)}
                        title={t('ranking.delete_aria', { symbol: s.symbol })}
                        aria-label={t('ranking.delete_aria', { symbol: s.symbol })}
                      >
                        <Trash2 size={14} />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirming && (
        <DeleteStockDialog
          stock={confirming}
          onClose={() => setConfirming(null)}
        />
      )}
    </Card>
  )
}
