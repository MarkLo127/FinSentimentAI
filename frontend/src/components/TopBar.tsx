import { Home, LogOut, Newspaper, Settings as SettingsIcon, TrendingUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { ThemeToggle } from './ui'
import { cn } from '../lib/cn'
import { useAuth } from '../hooks/useAuth'
import LanguageSwitcher from './LanguageSwitcher'

const navItem = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex items-center justify-center h-10 px-3 sm:px-4 rounded-lg text-sm font-medium gap-1.5',
    'transition-colors duration-150',
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
    isActive
      ? 'bg-primary-soft text-primary'
      : 'text-text-muted hover:text-text hover:bg-surface-2',
  )

export default function TopBar() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 h-14 flex items-center justify-between gap-2 sm:gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-2 font-semibold text-text hover:opacity-80 transition-opacity whitespace-nowrap"
          aria-label="FinSentiment AI"
        >
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
            <TrendingUp size={16} />
          </span>
          <span className="hidden md:inline">FinSentiment AI</span>
        </Link>

        {user && (
          <nav className="flex items-center gap-0.5 sm:gap-1">
            <NavLink to="/" end className={navItem} aria-label={t('nav.dashboard')}>
              <Home size={18} className="sm:hidden" />
              <span className="hidden sm:inline">{t('nav.dashboard')}</span>
            </NavLink>
            <NavLink to="/news" className={navItem} aria-label={t('nav.news')}>
              <Newspaper size={18} className="sm:hidden" />
              <span className="hidden sm:inline">{t('nav.news')}</span>
            </NavLink>
            <NavLink to="/settings" className={navItem} aria-label={t('nav.settings')}>
              <SettingsIcon size={18} className="sm:hidden" />
              <span className="hidden sm:inline">{t('nav.settings')}</span>
            </NavLink>
          </nav>
        )}

        <div className="flex items-center gap-1 sm:gap-2">
          {user && (
            <>
              <span className="hidden sm:inline text-sm text-text-muted max-w-[10rem] truncate">
                {user.username}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className={navItem({ isActive: false })}
                aria-label={t('nav.logout')}
              >
                <LogOut size={18} className="sm:hidden" />
                <span className="hidden sm:inline">{t('nav.logout')}</span>
              </button>
            </>
          )}
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
