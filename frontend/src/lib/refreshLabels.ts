import type { TFunction } from 'i18next'
import type { RefreshJob } from '../types/api'

export function stageLabel(job: RefreshJob, t: TFunction): string {
  if (job.state === 'queued') return t('refresh.queued')
  if (job.state === 'running') {
    const stage = job.progress_stage ?? ''
    if (stage === 'fetching') return t('refresh.fetching')
    if (stage === 'analyzing') return t('refresh.analyzing')
    if (stage === 'summarizing') return t('refresh.summarizing')
    return t('refresh.running')
  }
  return ''
}
