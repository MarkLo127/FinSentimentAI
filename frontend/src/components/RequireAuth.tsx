import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

/** Route guard: every app page now requires a logged-in user so each person's
 *  watchlist, keys, and analysis stay isolated. Redirects to /login otherwise. */
export default function RequireAuth() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="p-8 text-center text-text-muted">載入中…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
