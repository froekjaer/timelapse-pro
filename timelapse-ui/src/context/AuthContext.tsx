// ───────────────────────────────────────────────────────────────────
// AuthContext.tsx — JWT auth state for TimeLapse Pro
// ───────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { getApiUrl } from '../api/client'

export interface User {
  username:    string
  role:        'super_admin' | 'admin' | 'operator' | 'viewer'
  customer_id: string | null
}

interface MfaResult { mfa_required?: boolean; mfa_token?: string }

interface AuthCtx {
  user: User | null
  token: string | null
  login:     (username: string, password: string) => Promise<MfaResult | void>
  logout:    () => void
  verifyMfa: (mfa_token: string, code: string) => Promise<void>
  isAuthenticated: boolean
  loading: boolean
  hasRole: (...roles: User['role'][]) => boolean
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,  setUser]  = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore user fra /api/auth/me ved mount (cookie valideres af backend)
  useEffect(() => {
    const u = localStorage.getItem('tl_user')
    if (u) {
      try { setUser(JSON.parse(u)) } catch { /* ignore */ }
    }
    // Verificér cookie stadig er gyldig
    fetch(`${getApiUrl()}/api/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setUser({ username: d.username, role: d.role, customer_id: d.customer_id })
          localStorage.setItem('tl_user', JSON.stringify(d))
        } else {
          // Behold bruger fra localStorage — cookie valideres ved næste API-kald
          // Ryd kun hvis ingen bruger i localStorage
          if (!localStorage.getItem('tl_user')) {
            setUser(null)
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function login(username: string, password: string) {
    const res = await fetch(`${getApiUrl()}/api/auth/login`, {
      method:      'POST',
      credentials: 'include',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? 'Login fejlede')
    }
    const data = await res.json()
    if (data.mfa_required) {
      return { mfa_required: true, mfa_token: data.mfa_token }
    }
    const u: User = { username: data.username ?? username, role: data.role ?? 'viewer', customer_id: data.customer_id ?? null }
    localStorage.setItem('tl_user', JSON.stringify(u))
    setUser(u)
    return {}
  }

  async function verifyMfa(mfa_token: string, code: string) {
    const res = await fetch(`${getApiUrl()}/api/auth/verify-mfa`, {
      method:      'POST',
      credentials: 'include',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({ mfa_token, code }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? 'Forkert kode')
    }
    const data = await res.json()
    const u: User = { username: data.username, role: data.role, customer_id: data.customer_id ?? null }
    localStorage.setItem('tl_user', JSON.stringify(u))
    setUser(u)
  }

  function logout() {
    fetch(`${getApiUrl()}/api/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {})
    localStorage.removeItem('tl_user')
    setToken(null)
    setUser(null)
  }

  const hasRole = (...roles: User['role'][]) => !!user && roles.includes(user.role)

  return (
    <Ctx.Provider value={{ user, token, login, logout, verifyMfa, isAuthenticated: !!user, hasRole, loading }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
