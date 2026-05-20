import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { applyTheme, getStoredTheme, resolveTheme, type Theme } from '../../lib/theme'
import IconButton from './IconButton'

export default function ThemeToggle({ ariaLabel }: { ariaLabel?: string }) {
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme())
  const [resolved, setResolved] = useState<'light' | 'dark'>(() =>
    resolveTheme(getStoredTheme()),
  )

  // Track system preference changes when user has not picked a specific theme.
  useEffect(() => {
    if (theme !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setResolved(media.matches ? 'dark' : 'light')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])

  useEffect(() => {
    setResolved(applyTheme(theme))
  }, [theme])

  function toggle() {
    setTheme(resolved === 'dark' ? 'light' : 'dark')
  }

  const isDark = resolved === 'dark'
  return (
    <IconButton
      onClick={toggle}
      aria-label={
        ariaLabel ?? (isDark ? 'Switch to light mode' : 'Switch to dark mode')
      }
      title={isDark ? 'Light mode' : 'Dark mode'}
      size="md"
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </IconButton>
  )
}
