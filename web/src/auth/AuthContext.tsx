import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as api from '../api'
import type { User } from '../types'

const TOKEN_STORAGE_KEY = 'invoice-system.token'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string, otp?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    api.setAuthToken(null)
    setUser(null)
  }, [])

  // One place reacts to a 401 from any call, anywhere - see CLAUDE.md.
  useEffect(() => {
    api.setUnauthorizedHandler(clearSession)
    return () => api.setUnauthorizedHandler(null)
  }, [clearSession])

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (!stored) {
      setLoading(false)
      return
    }
    api.setAuthToken(stored)
    api
      .me()
      .then(setUser)
      .catch(() => clearSession())
      .finally(() => setLoading(false))
  }, [clearSession])

  const login = useCallback(async (email: string, password: string, otp?: string) => {
    const result = await api.login(email, password, otp)
    localStorage.setItem(TOKEN_STORAGE_KEY, result.token)
    api.setAuthToken(result.token)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    api.logout().catch(() => {
      /* best-effort revoke - clear the local session regardless */
    })
    clearSession()
  }, [clearSession])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
