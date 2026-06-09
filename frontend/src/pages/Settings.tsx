import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Eye, EyeOff, Loader2, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, Card, IconButton, Input } from '../components/ui'
import { deleteSetting, getSettingsStatus, setSetting } from '../services/api'
import type { SettingStatus } from '../types/api'

const KEY_META: Record<string, { labelKey: string; helpKey: string; signupUrl: string }> = {
  ANTHROPIC_API_KEY: {
    labelKey: 'settings.keys.anthropic.label',
    helpKey: 'settings.keys.anthropic.help',
    signupUrl: 'https://console.anthropic.com/',
  },
  MARKETAUX_API_KEY: {
    labelKey: 'settings.keys.marketaux.label',
    helpKey: 'settings.keys.marketaux.help',
    signupUrl: 'https://www.marketaux.com/',
  },
  FINNHUB_API_KEY: {
    labelKey: 'settings.keys.finnhub.label',
    helpKey: 'settings.keys.finnhub.help',
    signupUrl: 'https://finnhub.io/',
  },
  NEWSAPI_KEY: {
    labelKey: 'settings.keys.newsapi.label',
    helpKey: 'settings.keys.newsapi.help',
    signupUrl: 'https://newsapi.org/',
  },
  ALPHA_VANTAGE_KEY: {
    labelKey: 'settings.keys.alpha_vantage.label',
    helpKey: 'settings.keys.alpha_vantage.help',
    signupUrl: 'https://www.alphavantage.co/support/#api-key',
  },
  JINA_API_KEY: {
    labelKey: 'settings.keys.jina.label',
    helpKey: 'settings.keys.jina.help',
    signupUrl: 'https://jina.ai/',
  },
}

const AUTOSAVE_DEBOUNCE_MS = 900

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

function SettingRow({ row, onSaved }: { row: SettingStatus; onSaved: () => void }) {
  const { t, i18n } = useTranslation()
  const meta = KEY_META[row.key]
  const label = meta ? t(meta.labelKey) : row.key
  const help = meta ? t(meta.helpKey) : ''
  const signupUrl = meta?.signupUrl ?? ''
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const [status, setStatus] = useState<SaveStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  // Track the last successfully-saved trimmed string so blur after a save
  // doesn't re-POST the same value, and the debounce can't double-fire.
  const lastSavedRef = useRef<string>('')
  const debounceRef = useRef<number | null>(null)
  const savedFlashRef = useRef<number | null>(null)

  const doSave = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim()
      if (!trimmed || trimmed === lastSavedRef.current) return
      setStatus('saving')
      setError(null)
      try {
        await setSetting(row.key, trimmed)
        lastSavedRef.current = trimmed
        // Wipe the input post-save so the secret isn't lingering on screen,
        // and so the placeholder flips to "paste new value to overwrite".
        setValue('')
        setStatus('saved')
        onSaved()
        if (savedFlashRef.current) window.clearTimeout(savedFlashRef.current)
        savedFlashRef.current = window.setTimeout(() => setStatus('idle'), 2000)
      } catch (err: unknown) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setError((err as any)?.response?.data?.detail ?? String(err))
        setStatus('error')
      }
    },
    [row.key, onSaved],
  )

  // Debounced autosave: ~900 ms after the last keystroke / paste.
  useEffect(() => {
    if (!value.trim()) return
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      void doSave(value)
    }, AUTOSAVE_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
    }
  }, [value, doSave])

  useEffect(() => {
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
      if (savedFlashRef.current) window.clearTimeout(savedFlashRef.current)
    }
  }, [])

  function onBlur() {
    // Field lost focus → flush immediately, skipping the rest of the debounce.
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    void doSave(value)
  }

  async function clear() {
    setError(null)
    setStatus('saving')
    try {
      await deleteSetting(row.key)
      lastSavedRef.current = ''
      setStatus('idle')
      onSaved()
    } catch (err: unknown) {
      setError(String(err))
      setStatus('error')
    }
  }

  return (
    <Card padding="md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-text">{label}</h3>
            <span className="font-mono text-xs text-text-subtle">{row.key}</span>
            {row.set_in_db && (
              <Badge tone="positive" size="sm" icon={<Check size={11} />}>
                DB
              </Badge>
            )}
            {!row.set_in_db && row.set_in_env && (
              <Badge tone="neutral" size="sm">
                env
              </Badge>
            )}
            {!row.is_set && (
              <Badge tone="warning" size="sm">
                {t('settings.unset')}
              </Badge>
            )}
          </div>
          <p className="text-xs text-text-muted mt-1.5 leading-relaxed">
            {help}{' '}
            {signupUrl && (
              <a
                href={signupUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {t('settings.get_key')} →
              </a>
            )}
          </p>
          {row.updated_at && (
            <p className="text-[10px] text-text-subtle mt-2 font-mono">
              {t('settings.last_updated')}：
              {new Date(row.updated_at).toLocaleString(i18n.language)}
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-2">
        <div className="flex-1 min-w-0">
          <Input
            type={show ? 'text' : 'password'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={onBlur}
            placeholder={
              row.is_set
                ? t('settings.placeholder_overwrite')
                : t('settings.placeholder_new')
            }
            autoComplete="off"
            spellCheck={false}
            className="font-mono"
            rightSlot={
              <IconButton
                size="sm"
                variant="ghost"
                onClick={() => setShow((s) => !s)}
                aria-label={show ? t('settings.hide') : t('settings.show')}
              >
                {show ? <EyeOff size={14} /> : <Eye size={14} />}
              </IconButton>
            }
          />
        </div>
        <div className="flex items-center gap-2 sm:flex-shrink-0">
          {row.set_in_db && (
            <IconButton
              size="md"
              variant="ghost"
              onClick={clear}
              disabled={status === 'saving'}
              title={t('settings.clear_db_title')}
              aria-label={t('settings.clear_db_title')}
            >
              <X size={16} />
            </IconButton>
          )}
        </div>
      </div>

      {status === 'saving' && (
        <p className="mt-2 text-xs text-text-muted flex items-center gap-1.5">
          <Loader2 size={12} className="animate-spin" />
          {t('settings.autosaving')}
        </p>
      )}
      {status === 'saved' && (
        <p className="mt-2 text-xs text-sentiment-positive flex items-center gap-1.5">
          <Check size={12} />
          {t('settings.autosaved')}
        </p>
      )}
      {error && <p className="mt-2 text-xs text-sentiment-negative">{error}</p>}
    </Card>
  )
}

export default function Settings() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: getSettingsStatus,
  })

  return (
    <div className="max-w-3xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 space-y-4 sm:space-y-6">
      <header>
        <h1 className="text-xl sm:text-2xl md:text-3xl font-semibold text-text">
          {t('settings.title')}
        </h1>
        <p className="text-sm md:text-base text-text-muted mt-1">
          {t('settings.subtitle')}
        </p>
        <p className="text-xs text-text-subtle mt-2">{t('settings.autosave_hint')}</p>
      </header>

      {isLoading && (
        <p className="text-text-subtle text-sm">{t('common.loading')}</p>
      )}
      {error && (
        <p className="text-sentiment-negative text-sm">
          {t('common.failed_to_load')}：{String(error)}
        </p>
      )}

      {data && (
        <div className="space-y-3">
          {data.map((row) => (
            <SettingRow
              key={row.key}
              row={row}
              onSaved={() =>
                qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
              }
            />
          ))}
        </div>
      )}

      <Card padding="md" className="bg-accent-soft border-accent/30">
        <div className="flex items-start gap-3">
          <AlertTriangle size={18} className="mt-0.5 flex-shrink-0 text-accent" />
          <div className="text-sm">
            <p className="font-medium text-text">{t('settings.security_title')}</p>
            <p className="text-xs mt-1 text-text-muted leading-relaxed">
              {t('settings.security_body')}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
