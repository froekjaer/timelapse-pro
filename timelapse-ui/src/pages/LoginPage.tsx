// ───────────────────────────────────────────────────────────────────
// LoginPage.tsx — RBAC Login til TimeLapse Pro
// ───────────────────────────────────────────────────────────────────
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Camera, Lock, User, Eye, EyeOff, AlertTriangle, Smartphone, Fingerprint } from 'lucide-react'
import { startAuthentication, WebAuthnAbortService } from '@simplewebauthn/browser'
import type { PublicKeyCredentialRequestOptionsJSON } from '@simplewebauthn/browser'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login, verifyMfa, confirmMfaSetup, acceptSessionUser } = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()
  const from = (location.state as any)?.from?.pathname ?? '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw,   setShowPw]   = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [mfaSetupRequired, setMfaSetupRequired] = useState(false)
  const [mfaToken,    setMfaToken]    = useState('')
  const [mfaCode,     setMfaCode]     = useState('')
  const [mfaQr,       setMfaQr]       = useState('')
  const [mfaSecret,   setMfaSecret]   = useState('')
  const [remember,     setRemember]     = useState(false)
  // Safari only shows the Touch ID sheet reliably when navigator.credentials.get()
  // runs directly in the click handler, so login-begin options are prefetched
  // when the username is known and reused if still fresh on click.
  const webauthnPrefetch = useRef<{ username: string; at: number; opts: Promise<PublicKeyCredentialRequestOptionsJSON> } | null>(null)
  const usernameRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  function currentUsername() {
    return (usernameRef.current?.value ?? username).trim()
  }

  function currentPassword() {
    return passwordRef.current?.value ?? password
  }

  function resetMfaStep() {
    setMfaRequired(false)
    setMfaSetupRequired(false)
    setMfaToken('')
    setMfaCode('')
    setMfaQr('')
    setMfaSecret('')
    setError(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const typedUsername = currentUsername()
    const typedPassword = currentPassword()
    if (!mfaRequired && (!typedUsername || !typedPassword)) {
      setError('Indtast brugernavn og adgangskode')
      return
    }
    setLoading(true)
    try {
      if (mfaRequired) {
        await verifyMfa(mfaToken, mfaCode)
        navigate(from, { replace: true })
      } else if (mfaSetupRequired) {
        await confirmMfaSetup(mfaCode)
        navigate(from, { replace: true })
      } else {
        const result = await login(typedUsername, typedPassword)
        if (result?.mfa_required) {
          setMfaRequired(true)
          setMfaToken(result.mfa_token ?? '')
        } else if (result?.mfa_setup_required) {
          setMfaSetupRequired(true)
          const setup = await fetch(`${(await import('../api/client')).getApiUrl()}/api/auth/setup-mfa`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
          }).then(async r => {
            if (!r.ok) {
              const err = await r.json().catch(() => ({}))
              throw new Error(err.detail ?? 'Kunne ikke oprette MFA')
            }
            return r.json()
          })
          setMfaQr(setup.qr_code)
          setMfaSecret(setup.secret)
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

  async function fetchWebAuthnOptions(user: string): Promise<PublicKeyCredentialRequestOptionsJSON> {
    const r = await fetch(`${(await import('../api/client')).getApiUrl()}/api/auth/webauthn/login-begin`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user })
    })
    if (!r.ok) throw new Error('Ingen registreret enhed for denne bruger på dette domæne')
    return r.json()
  }

  function prefetchWebAuthnOptions() {
    const user = currentUsername()
    if (!user) return
    // One outstanding challenge per user server-side: don't let a second
    // prefetch overwrite the challenge the cached options were issued with.
    const cached = webauthnPrefetch.current
    if (cached && cached.username === user && Date.now() - cached.at < 30_000) return
    const opts = fetchWebAuthnOptions(user)
    opts.catch(() => {})  // surfaced on click, not here
    webauthnPrefetch.current = { username: user, at: Date.now(), opts }
  }

  async function handleWebAuthn() {
    const typedUsername = currentUsername()
    if (!typedUsername) { setError('Indtast brugernavn først'); return }
    setError(null); setLoading(true)
    const cached = webauthnPrefetch.current
    webauthnPrefetch.current = null
    const fresh = cached && cached.username === typedUsername && Date.now() - cached.at < 40_000
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      const opts = await (fresh ? cached!.opts : fetchWebAuthnOptions(typedUsername))

      // Never leave the button spinning if the browser neither shows the
      // sheet nor rejects (seen with Safari 27 / macOS 27, 2026-09-25).
      const timeoutMs = (opts.timeout ?? 60_000) + 5_000
      const result = await Promise.race([
        startAuthentication({ optionsJSON: opts }),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            WebAuthnAbortService.cancelCeremony()
            reject(new Error('Touch ID / Windows Hello svarede ikke. Prøv igen, eller log ind med adgangskode.'))
          }, timeoutMs)
        }),
      ])

      const data = await fetch(`${(await import('../api/client')).getApiUrl()}/api/auth/webauthn/login-complete`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...result, username: typedUsername })
      }).then(r => { if (!r.ok) throw new Error('Autentificering fejlede'); return r.json() })

      const u = { username: data.username, role: data.role, customer_id: data.customer_id ?? null }
      acceptSessionUser(u)
      navigate(from, { replace: true })
    } catch (e: any) {
      setError(e?.name === 'NotAllowedError'
        ? 'Touch ID / Windows Hello blev annulleret eller fandt ingen passkey for dette domæne.'
        : (e.message ?? 'WebAuthn fejlede'))
    } finally {
      clearTimeout(timer)
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
                ref={usernameRef}
                type="text"
                autoComplete="username"
                value={username}
                onChange={e => { if (mfaRequired || mfaSetupRequired) resetMfaStep(); setUsername(e.target.value) }}
                onInput={e => setUsername(e.currentTarget.value)}
                onBlur={prefetchWebAuthnOptions}
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
                ref={passwordRef}
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={e => { if (mfaRequired || mfaSetupRequired) resetMfaStep(); setPassword(e.target.value) }}
                onInput={e => setPassword(e.currentTarget.value)}
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
          {(mfaRequired || mfaSetupRequired) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                <span className="flex items-center gap-1.5">
                  <Smartphone className="w-4 h-4" />
                  {mfaSetupRequired ? 'Opret MFA' : 'Engangskode (Authenticator)'}
                </span>
              </label>
              {mfaSetupRequired && (
                <div className="mb-3 flex flex-col items-center gap-2 rounded-xl border border-sky-100 bg-sky-50 p-3">
                  {mfaQr ? (
                    <img src={mfaQr} alt="QR kode" className="h-40 w-40 rounded-lg border border-white bg-white" />
                  ) : (
                    <p className="text-xs text-sky-700">Henter QR-kode…</p>
                  )}
                  {mfaSecret && <p className="rounded bg-white px-2 py-1 font-mono text-xs text-slate-500">{mfaSecret}</p>}
                  <p className="text-xs text-sky-700">Scan QR-koden i din authenticator app og bekræft med koden.</p>
                </div>
              )}
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
              <p className="text-xs text-gray-400 mt-1">
                {mfaSetupRequired ? 'Indtast første kode for at aktivere MFA på kontoen.' : 'Åbn din authenticator app og indtast den 6-cifrede kode'}
              </p>
              <button type="button" onClick={resetMfaStep}
                className="mt-2 text-xs font-medium text-sky-600 hover:text-sky-700">
                Tilbage til brugernavn og adgangskode
              </button>
            </div>
          )}

          {/* Husk denne enhed */}
          {!mfaRequired && !mfaSetupRequired && (
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-sky-500 focus:ring-sky-400" />
              <span className="text-sm text-gray-500">Husk denne enhed i 30 dage</span>
            </label>
          )}

          {/* WebAuthn / biometrisk login */}
          <button type="button" onClick={handleWebAuthn} disabled={loading}
            onPointerEnter={prefetchWebAuthnOptions} onFocus={prefetchWebAuthnOptions}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50">
            <Fingerprint className="w-4 h-4 text-sky-500" />
            Log ind med Windows Hello / Touch ID
          </button>

          {/* Submit */}
          <button type="submit" disabled={loading}
            className="w-full py-2.5 bg-sky-500 hover:bg-sky-600 disabled:bg-sky-300
                       text-white text-sm font-medium rounded-lg transition-colors">
            {loading ? 'Logger ind…' : mfaSetupRequired ? 'Aktiver MFA' : 'Log ind'}
          </button>
        </form>
      </div>
    </div>
  )
}
