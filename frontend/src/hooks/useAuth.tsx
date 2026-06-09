import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { getMe, googleLogin as apiGoogleLogin, TOKEN_KEY } from '../services/api'
import type { UserPublic } from '../types/api'

interface AuthContextValue {
  user: UserPublic | null
  isLoading: boolean
  /** Exchange a Google ID-token credential for our app JWT and persist it. */
  loginWithGoogle: (credential: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readToken(): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  // Track the token in React state so writes from loginWithGoogle / logout —
  // and 401-driven clears from the axios interceptor — re-render this provider
  // (which sits OUTSIDE RouterProvider, so router navigation alone doesn't).
  const [token, setToken] = useState<string | null>(() => readToken())
  const hasToken = !!token

  // Stay in sync with localStorage edits from other tabs OR the response
  // interceptor's hard-clear path on 401.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === TOKEN_KEY) setToken(e.newValue)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const meQ = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    enabled: hasToken,
    retry: false,
    staleTime: 5 * 60_000,
  })

  // If /me 401s, drop the bad token so the UI flips to logged-out.
  useEffect(() => {
    if (meQ.isError && hasToken) {
      localStorage.removeItem(TOKEN_KEY)
      setToken(null)
    }
  }, [meQ.isError, hasToken])

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const tok = await apiGoogleLogin(credential)
      localStorage.setItem(TOKEN_KEY, tok.access_token)
      setToken(tok.access_token)
      await qc.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
    [qc],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    qc.removeQueries({ queryKey: ['auth', 'me'] })
    qc.setQueryData(['auth', 'me'], null)
  }, [qc])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQ.isError ? null : (meQ.data ?? null),
      isLoading: hasToken && meQ.isLoading,
      loginWithGoogle,
      logout,
    }),
    [hasToken, meQ.data, meQ.isError, meQ.isLoading, loginWithGoogle, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
