import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { Card } from '../components/ui'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const auth = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const configured = !!import.meta.env.VITE_GOOGLE_CLIENT_ID

  async function onGoogleSuccess(resp: CredentialResponse) {
    if (!resp.credential) {
      setError(t('login.err_google'))
      return
    }
    setError(null)
    setBusy(true)
    try {
      await auth.loginWithGoogle(resp.credential)
      nav('/', { replace: true })
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (err as any)?.response?.data?.detail
      setError(detail ?? t('login.err_google'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto px-4 py-10 md:py-16">
      <Card padding="lg">
        <h1 className="text-2xl font-semibold text-text mb-2">
          {t('login.title')}
        </h1>
        <p className="text-sm text-text-muted mb-6">{t('login.subtitle')}</p>

        <div className="flex justify-center">
          {configured ? (
            <GoogleLogin
              onSuccess={onGoogleSuccess}
              onError={() => setError(t('login.err_google'))}
              useOneTap={false}
              text="continue_with"
              shape="pill"
              theme="filled_blue"
              size="large"
            />
          ) : (
            <p
              role="alert"
              className="text-sm text-sentiment-negative bg-sentiment-negative-soft border border-sentiment-negative/30 rounded-lg p-3"
            >
              {t('login.err_unconfigured')}
            </p>
          )}
        </div>

        {busy && (
          <p className="text-sm text-text-muted mt-4 text-center">
            {t('login.signing_in')}
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="text-sm text-sentiment-negative bg-sentiment-negative-soft border border-sentiment-negative/30 rounded-lg p-3 mt-4"
          >
            {error}
          </p>
        )}
      </Card>
    </div>
  )
}
