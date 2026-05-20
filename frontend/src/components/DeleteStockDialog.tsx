import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { deleteStock, getStockImpact } from '../services/api'
import type { Stock, StockImpact } from '../types/api'
import { Button } from './ui'

interface Props {
  stock: Stock
  onClose: () => void
  onDeleted?: () => void
}

export default function DeleteStockDialog({ stock, onClose, onDeleted }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const impactQ = useQuery<StockImpact>({
    queryKey: ['stock-impact', stock.symbol],
    queryFn: () => getStockImpact(stock.symbol),
  })

  const mut = useMutation({
    mutationFn: () => deleteStock(stock.symbol),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stocks'] })
      qc.invalidateQueries({ queryKey: ['market'] })
      qc.invalidateQueries({ queryKey: ['news'] })
      onDeleted?.()
      onClose()
    },
  })

  // Close on Escape key
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-2xl shadow-elevated border border-border max-w-md w-full p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-sentiment-negative-soft text-sentiment-negative flex-shrink-0">
            <AlertTriangle size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-lg font-semibold text-text">
              {t('stock_delete.confirm_title')}{' '}
              <span className="font-mono">{stock.symbol}</span>?
            </h3>
          </div>
        </div>

        {impactQ.isLoading && (
          <p className="text-sm text-text-subtle">{t('stock_delete.calculating')}</p>
        )}
        {impactQ.data && (
          <div className="rounded-lg bg-sentiment-negative-soft border border-sentiment-negative/30 p-4 text-sm space-y-2">
            <p className="text-sentiment-negative font-medium">
              {t('stock_delete.will_remove')}
            </p>
            <ul className="text-text-muted text-xs space-y-1 ml-4 list-disc">
              <li>
                {t('stock_delete.impact.news', { count: impactQ.data.news_count })}
              </li>
              <li>
                {t('stock_delete.impact.comments', {
                  count: impactQ.data.comment_count,
                })}
              </li>
              <li>
                {t('stock_delete.impact.sentiment', {
                  count: impactQ.data.sentiment_count,
                })}
              </li>
              <li>
                {t('stock_delete.impact.summary', {
                  count: impactQ.data.market_summary_count,
                })}
              </li>
            </ul>
            <p className="text-sentiment-negative text-xs pt-1 font-semibold">
              {t('stock_delete.irreversible')}
            </p>
          </div>
        )}
        {mut.error && (
          <p className="text-xs text-sentiment-negative">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {(mut.error as any)?.response?.data?.detail ?? String(mut.error)}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" size="md" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            variant="danger"
            size="md"
            loading={mut.isPending}
            disabled={impactQ.isLoading}
            onClick={() => mut.mutate()}
          >
            {mut.isPending ? t('stock_delete.deleting') : t('stock_delete.confirm')}
          </Button>
        </div>
      </div>
    </div>
  )
}
