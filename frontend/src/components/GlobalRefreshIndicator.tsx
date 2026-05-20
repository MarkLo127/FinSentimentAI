import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { stageLabel } from '../lib/refreshLabels'
import { listActiveRefreshJobs } from '../services/api'

/** Sticky strip under TopBar — visible whenever any refresh job is queued
 *  or running, regardless of which page the user is on. Disappears when no
 *  jobs are active. */
export default function GlobalRefreshIndicator() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['refresh-jobs', 'active'],
    queryFn: listActiveRefreshJobs,
    refetchInterval: 3000,
  })

  // When a job we were tracking disappears from the active list, it likely
  // succeeded (or failed) — invalidate news/market so any open page picks up
  // the new data immediately.
  const prevIdsRef = useRef<Set<number>>(new Set())
  useEffect(() => {
    const next = new Set((data ?? []).map((j) => j.id))
    const prev = prevIdsRef.current
    let changed = false
    for (const id of prev) {
      if (!next.has(id)) {
        changed = true
        break
      }
    }
    if (changed) {
      qc.invalidateQueries({ queryKey: ['news'] })
      qc.invalidateQueries({ queryKey: ['market'] })
      qc.invalidateQueries({ queryKey: ['stocks'] })
    }
    prevIdsRef.current = next
  }, [data, qc])

  if (!data || data.length === 0) return null

  return (
    <div className="border-b border-border bg-primary-soft/50">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium text-primary whitespace-nowrap">
          {t('refresh.indicator.tasks_running', { count: data.length })}
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {data.map((job) => (
            <Link
              key={job.id}
              to={`/news?q=${encodeURIComponent(job.symbol)}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface hover:bg-surface-2 border border-border text-text transition-colors duration-150"
              title={t('refresh.indicator.click_to_view')}
            >
              <Loader2 size={11} className="animate-spin flex-shrink-0 text-primary" />
              <span className="font-mono font-medium">{job.symbol}</span>
              {job.today_run_number && job.today_run_number > 1 && (
                <span className="px-1.5 rounded bg-primary-soft text-primary text-[10px] tabular-nums">
                  {t('refresh.run_number', { n: job.today_run_number })}
                </span>
              )}
              <span className="text-text-muted">{stageLabel(job, t)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
