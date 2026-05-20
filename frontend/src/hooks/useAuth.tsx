import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { getMe, login as apiLogin, TOKEN_KEY } from '../services/api'
import type { LoginPayload, UserPublic } from '../types/api'

interface AuthContextValue {
  user: UserPublic | null
  isLoading: boolean
  login: (payload: LoginPayload) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem(TOKEN_KEY)

  const meQ = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    enabled: hasToken,
    retry: false,
    staleTime: 5 * 60_000,
  })

  // If /me 401s, clear the bad token so the UI shows logged-out state
  if (meQ.isError && hasToken) {
    localStorage.removeItem(TOKEN_KEY)
  }

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tok = await apiLogin(payload)
      localStorage.setItem(TOKEN_KEY, tok.access_token)
      await qc.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
    [qc],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    qc.removeQueries({ queryKey: ['auth', 'me'] })
    qc.setQueryData(['auth', 'me'], null)
  }, [qc])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQ.isError ? null : (meQ.data ?? null),
      isLoading: hasToken && meQ.isLoading,
      login,
      logout,
    }),
    [hasToken, meQ.data, meQ.isError, meQ.isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
