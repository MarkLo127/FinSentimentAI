/** Read CSS variables at runtime so chart colors track the active theme.
 *  Recharts wants concrete hex/rgb strings, not CSS variable references. */
function readVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export interface ChartTokens {
  positive: string
  neutral: string
  negative: string
  grid: string
  axis: string
  tooltipBg: string
  tooltipBorder: string
  text: string
}

export function readChartTokens(): ChartTokens {
  return {
    positive: readVar('--color-positive', '#15803d'),
    neutral: readVar('--color-neutral', '#64748b'),
    negative: readVar('--color-negative', '#b91c1c'),
    grid: readVar('--color-border', '#e2e8f0'),
    axis: readVar('--color-text-muted', '#475569'),
    tooltipBg: readVar('--color-surface-raised', '#ffffff'),
    tooltipBorder: readVar('--color-border-strong', '#cbd5e1'),
    text: readVar('--color-text', '#0f172a'),
  }
}

/** Tiny hook that re-reads tokens whenever `.dark` is toggled on <html>. */
import { useEffect, useState } from 'react'

export function useChartTokens(): ChartTokens {
  const [tokens, setTokens] = useState<ChartTokens>(() => readChartTokens())
  useEffect(() => {
    const observer = new MutationObserver(() => setTokens(readChartTokens()))
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    })
    return () => observer.disconnect()
  }, [])
  return tokens
}
