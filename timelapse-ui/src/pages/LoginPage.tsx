// ───────────────────────────────────────────────────────────────────
// LoginPage.tsx — RBAC Login til TimeLapse Pro
// ───────────────────────────────────────────────────────────────────
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Camera, Lock, User, Eye, EyeOff, AlertTriangle, Smartphone } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login, verifyMfa } = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()
  const from = (location.state as any)?.from?.pathname ?? '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw,   setShowPw]   = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [mfaToken,    setMfaToken]    = useState('')
  const [mfaCode,     setMfaCode]     = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mfaRequired) {
        await verifyMfa(mfaToken, mfaCode)
        navigate(from, { replace: true })
      } else {
        const result = await login(username.trim(), password)
        if (result?.mfa_required) {
          setMfaRequired(true)
          setMfaToken(result.mfa_token ?? '')
        } else {
          navigate(from, { replace: true })
        }
      }
    } catch (err: any) {
      setError(err.message ?? 'Ukendt fejl')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-sky-500 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <Camera className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">TimeLapse Pro</h1>
          <p className="text-slate-400 text-sm mt-1">Log ind for at fortsætte</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-6 space-y-4">

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2.5 rounded-lg">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Brugernavn */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Brugernavn</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm
                           focus:outline-none focus:ring-2 focus:ring-sky-300"
                placeholder="admin"
                required
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Adgangskode</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full pl-9 pr-10 py-2.5 border border-gray-200 rounded-lg text-sm
                           focus:outline-none focus:ring-2 focus:ring-sky-300"
                placeholder="••••••••"
                required
              />
              <button type="button" onClick={() => setShowPw(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* MFA TOTP felt */}
          {mfaRequired && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                <span className="flex items-center gap-1.5"><Smartphone className="w-4 h-4" /> Engangskode (Authenticator)</span>
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                value={mfaCode}
                onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono text-center text-lg tracking-widest"
                autoFocus
              />
              <p className="text-xs text-gray-400 mt-1">Åbn din authenticator app og indtast den 6-cifrede kode</p>
            </div>
          )}

          {/* Submit */}
          <button type="submit" disabled={loading || !username || !password}
            className="w-full py-2.5 bg-sky-500 hover:bg-sky-600 disabled:bg-sky-300
                       text-white text-sm font-medium rounded-lg transition-colors">
            {loading ? 'Logger ind…' : 'Log ind'}
          </button>

          <p className="text-center text-xs text-gray-400">
            Standard: <span className="font-mono">admin / changeme</span>
          </p>
        </form>
      </div>
    </div>
  )
}
