import type { AnalysisMeta, SentimentSnippet } from '../types/api'

function isZh(lang: string): boolean {
  return lang.toLowerCase().startsWith('zh')
}

/** Pick the right reasoning string for the user's UI language. Falls back
 *  to the other language, then to the flat legacy `reasoning` field on
 *  pre-Phase-7 records. Returns undefined when nothing is available. */
export function pickReasoning(
  meta: AnalysisMeta | null | undefined,
  lang: string,
): string | undefined {
  if (!meta) return undefined
  if (isZh(lang))
    return meta.reasoning_zh || meta.reasoning_en || meta.reasoning
  return meta.reasoning_en || meta.reasoning || meta.reasoning_zh
}

/** Pick the matching key_drivers list; same fallback chain as pickReasoning. */
export function pickDrivers(
  meta: AnalysisMeta | null | undefined,
  lang: string,
): string[] {
  if (!meta) return []
  if (isZh(lang))
    return (
      meta.key_drivers_zh ?? meta.key_drivers_en ?? meta.key_drivers ?? []
    )
  return meta.key_drivers_en ?? meta.key_drivers ?? meta.key_drivers_zh ?? []
}

/** Pick the title to display in news listings. Comes from
 *  `SentimentSnippet.title_zh/title_en` (populated from analysis_metadata).
 *  Falls back to the original news title for legacy rows or when the
 *  article wasn't analyzed. */
export function pickTitle(
  snippet: SentimentSnippet | null | undefined,
  fallback: string,
  lang: string,
): string {
  if (!snippet) return fallback
  if (isZh(lang)) return snippet.title_zh || snippet.title_en || fallback
  return snippet.title_en || snippet.title_zh || fallback
}
