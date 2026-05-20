import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createStock, startRefresh } from '../services/api'
import type { RefreshJob, Stock } from '../types/api'
import { Button, Input } from './ui'

interface Props {
  defaultSymbol?: string
  /** If true, calls startRefresh() right after createStock and passes the
   *  resulting job back via onCreated so the caller can show a progress
   *  banner without an extra round-trip. */
  autoRefresh?: boolean
  onClose: () => void
  onCreated?: (stock: Stock, job?: RefreshJob) => void
}

export default function AddStockForm({
  defaultSymbol,
  autoRefresh = false,
  onClose,
  onCreated,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [symbol, setSymbol] = useState((defaultSymbol ?? '').toUpperCase())

  const mut = useMutation({
    mutationFn: async (): Promise<{ stock: Stock; job?: RefreshJob }> => {
      const stock = await createStock({ symbol, name: '' })
      let job: RefreshJob | undefined
      if (autoRefresh) {
        try {
          job = await startRefresh(stock.symbol)
        } catch {
          /* ignore — NewsList polls latest-job on mount as a backstop */
        }
      }
      return { stock, job }
    },
    onSuccess: ({ stock, job }) => {
      qc.invalidateQueries({ queryKey: ['stocks'] })
      qc.invalidateQueries({ queryKey: ['market'] })
      onCreated?.(stock, job)
      onClose()
    },
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!symbol.trim()) return
    mut.mutate()
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-border bg-surface-2 p-4 md:p-5 space-y-3"
    >
      <Input
        type="text"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value.toUpperCase())}
        placeholder={t('stock_form.symbol_placeholder')}
        required
        autoFocus={!defaultSymbol}
        className="font-mono"
      />
      <p className="text-xs text-text-subtle">{t('stock_form.auto_fill_hint')}</p>
      {mut.error && (
        <p className="text-xs text-sentiment-negative">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {(mut.error as any)?.response?.data?.detail ?? String(mut.error)}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="ghost" size="md" onClick={onClose}>
          {t('common.cancel')}
        </Button>
        <Button
          type="submit"
          variant="primary"
          size="md"
          loading={mut.isPending}
          disabled={!symbol.trim()}
        >
          {mut.isPending
            ? t('stock_form.adding')
            : autoRefresh
              ? t('stock_form.add_and_analyze', { symbol: symbol || '—' })
              : t('stock_form.submit')}
        </Button>
      </div>
    </form>
  )
}
