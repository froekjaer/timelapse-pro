// ───────────────────────────────────────────────────────────────────
// AuthContext.tsx — JWT auth state for TimeLapse Pro
// ───────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { getApiUrl } from '../api/client'

export interface User {
  username: string
  role: 'super_admin' | 'admin' | 'operator' | 'viewer'
}

interface AuthCtx {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  hasRole: (...roles: User['role'][]) => boolean
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,  setUser]  = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)

  // Restore from localStorage on mount
  useEffect(() => {
    const t = localStorage.getItem('tl_token')
    const u = localStorage.getItem('tl_user')
    if (t && u) {
      try {
        setToken(t)
        setUser(JSON.parse(u))
      } catch { /* ignore */ }
    }
  }, [])

  async function login(username: string, password: string) {
    const res = await fetch(`${getApiUrl()}/api/auth/login`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? 'Login fejlede')
    }
    const data = await res.json()
    const u: User = { username: data.user?.username ?? username, role: data.user?.role ?? 'viewer' }
    localStorage.setItem('tl_token', data.access_token)
    localStorage.setItem('tl_user', JSON.stringify(u))
    setToken(data.access_token)
    setUser(u)
  }

  function logout() {
    localStorage.removeItem('tl_token')
    localStorage.removeItem('tl_user')
    setToken(null)
    setUser(null)
  }

  const hasRole = (...roles: User['role'][]) => !!user && roles.includes(user.role)

  return (
    <Ctx.Provider value={{ user, token, login, logout, isAuthenticated: !!user, hasRole }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
