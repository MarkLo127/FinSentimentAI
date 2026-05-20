import type { TFunction } from 'i18next'

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-text-subtle'
  if (score > 0.1) return 'text-sentiment-positive'
  if (score < -0.1) return 'text-sentiment-negative'
  return 'text-sentiment-neutral'
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return '—'
  const sign = score > 0 ? '+' : ''
  return `${sign}${score.toFixed(3)}`
}

/** Compact relative-time formatter. If `t` is not provided, falls back to
 *  zh-TW labels (keeps callers that haven't been translated working). */
export function relativeTime(
  iso: string | null | undefined,
  t?: TFunction,
  locale?: string,
): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const diffMin = Math.round((Date.now() - then) / 60_000)
  if (t) {
    if (diffMin < 1) return t('time.just_now')
    if (diffMin < 60) return t('time.minutes_ago', { n: diffMin })
    const diffH = Math.round(diffMin / 60)
    if (diffH < 24) return t('time.hours_ago', { n: diffH })
    const diffD = Math.round(diffH / 24)
    if (diffD < 30) return t('time.days_ago', { n: diffD })
    return new Date(iso).toLocaleDateString(locale ?? 'zh-TW')
  }
  if (diffMin < 1) return '剛剛'
  if (diffMin < 60) return `${diffMin} 分鐘前`
  const diffH = Math.round(diffMin / 60)
  if (diffH < 24) return `${diffH} 小時前`
  const diffD = Math.round(diffH / 24)
  if (diffD < 30) return `${diffD} 天前`
  return new Date(iso).toLocaleDateString(locale ?? 'zh-TW')
}
