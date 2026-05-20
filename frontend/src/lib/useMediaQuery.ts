import { useEffect, useState } from 'react'

/** Returns true when `query` currently matches. Updates on resize / device
 *  rotation. SSR-safe (returns false on the first render before mount). */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia(query).matches
  })
  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    onChange()
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])
  return matches
}

/** True when the viewport is below Tailwind's `md` breakpoint (768px). */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 767px)')
}
