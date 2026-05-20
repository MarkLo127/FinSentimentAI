import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, Input } from '../components/ui'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const auth = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await auth.login({ username, password })
      nav('/', { replace: true })
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const status = (err as any)?.response?.status
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (err as any)?.response?.data?.detail
      if (status === 401) setError(t('login.err_invalid'))
      else setError(detail ?? String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto px-4 py-10 md:py-16">
      <Card padding="lg">
        <h1 className="text-2xl font-semibold text-text mb-6">{t('login.title')}</h1>
        <form onSubmit={submit} className="space-y-5">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium mb-2 text-text"
            >
              {t('login.username')}
            </label>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-2 text-text"
            >
              {t('login.password')}
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {error && (
            <p
              role="alert"
              className="text-sm text-sentiment-negative bg-sentiment-negative-soft border border-sentiment-negative/30 rounded-lg p-3"
            >
              {error}
            </p>
          )}
          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={busy}
          >
            {busy ? t('login.submitting') : t('login.submit')}
          </Button>
        </form>
        <p className="text-sm text-text-muted mt-6 text-center">
          {t('login.no_account')}{' '}
          <Link
            to="/register"
            className="text-primary font-medium hover:underline"
          >
            {t('login.go_register')}
          </Link>
        </p>
      </Card>
    </div>
  )
}
