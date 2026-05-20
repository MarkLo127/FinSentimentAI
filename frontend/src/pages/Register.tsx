import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, Input } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { register as apiRegister } from '../services/api'

export default function Register() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const auth = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await apiRegister({ username, email, password })
      await auth.login({ username, password })
      nav('/', { replace: true })
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const status = (err as any)?.response?.status
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (err as any)?.response?.data?.detail
      if (status === 409) setError(t('register.err_dup'))
      else if (status === 422) setError(t('register.err_format'))
      else setError(detail ?? String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto px-4 py-10 md:py-16">
      <Card padding="lg">
        <h1 className="text-2xl font-semibold text-text mb-6">{t('register.title')}</h1>
        <form onSubmit={submit} className="space-y-5">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium mb-2 text-text"
            >
              {t('register.username')}{' '}
              <span className="text-xs text-text-subtle font-normal">
                {t('register.username_hint')}
              </span>
            </label>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              minLength={3}
              maxLength={50}
              pattern="[A-Za-z0-9_-]+"
            />
          </div>
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-2 text-text"
            >
              {t('register.email')}
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-2 text-text"
            >
              {t('register.password')}{' '}
              <span className="text-xs text-text-subtle font-normal">
                {t('register.password_hint')}
              </span>
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
              minLength={8}
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
            {busy ? t('register.submitting') : t('register.submit')}
          </Button>
        </form>
        <p className="text-sm text-text-muted mt-6 text-center">
          {t('register.have_account')}{' '}
          <Link
            to="/login"
            className="text-primary font-medium hover:underline"
          >
            {t('register.go_login')}
          </Link>
        </p>
      </Card>
    </div>
  )
}
