// ───────────────────────────────────────────────────────────────────
// LoginPage.tsx — RBAC Login til TimeLapse Pro
// ───────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Camera, Lock, User, Eye, EyeOff, AlertTriangle, Smartphone, Fingerprint } from 'lucide-react'
import { startAuthentication, WebAuthnAbortService } from '@simplewebauthn/browser'
import type { PublicKeyCredentialRequestOptionsJSON } from '@simplewebauthn/browser'
import { getApiUrl } from '../api/client'
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

  // Abort a pending passkey request when the page is left (tab closed,
  // reloaded, navigated away or unmounted). Safari runs one WebAuthn request
  // at a time per browsing session; an abandoned one can leave every later
  // Touch ID request in other tabs waiting (2026-09-25, Safari 27/macOS 27).
  const webauthnFlow = useRef<AbortController | null>(null)
  useEffect(() => {
    const abort = () => { webauthnFlow.current?.abort(); WebAuthnAbortService.cancelCeremony() }
    window.addEventListener('pagehide', abort)
    return () => { window.removeEventListener('pagehide', abort); abort() }
  }, [])

  // Touch ID login (Peter 2026-10-13: "Touch-id SKAL virke").
  //
  // Two rules, both from what Safari actually did:
  // 1. One passkey request at a time. Passkey AutoFill (conditional
  //    mediation, #288) is not used: with an AutoFill request pending, Safari
  //    ignored the button's request — every Safari button login failed from
  //    the moment AutoFill worked (#300, 2026-10-11) until it was removed.
  // 2. Ask for Touch ID immediately in the click. Safari only honours a
  //    passkey request made in direct response to the user's click; the old
  //    button first loaded a module and waited for login-begin, and Safari
  //    then silently dropped the request or put Safari into a cooldown.
  //    So the challenge is fetched ahead of time (usernameless, Touch ID
  //    identifies the user) and refreshed before it expires (server TTL 5 min).
  const PREFETCH_MAX_AGE_MS = 4 * 60_000
  const prefetched = useRef<{ options: PublicKeyCredentialRequestOptionsJSON; at: number } | null>(null)
  const prefetching = useRef<Promise<void> | null>(null)

  function prefetchPasskeyOptions(): Promise<void> {
    if (prefetching.current) return prefetching.current
    prefetching.current = fetch(`${getApiUrl()}/api/auth/webauthn/login-begin`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
    })
      .then(async r => {
        if (!r.ok) throw new Error(`login-begin ${r.status}`)
        prefetched.current = { options: await r.json(), at: Date.now() }
      })
      .catch(() => { prefetched.current = null })
      .finally(() => { prefetching.current = null })
    return prefetching.current
  }

  useEffect(() => {
    prefetchPasskeyOptions()
    const refresh = window.setInterval(prefetchPasskeyOptions, PREFETCH_MAX_AGE_MS - 30_000)
    const onVisible = () => {
      if (document.visibilityState === 'visible' &&
          (!prefetched.current || Date.now() - prefetched.current.at > PREFETCH_MAX_AGE_MS)) prefetchPasskeyOptions()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => { window.clearInterval(refresh); document.removeEventListener('visibilitychange', onVisible) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleWebAuthn() {
    setError(null)
    // One deadline for the whole ceremony: the button never spins forever if
    // Safari never shows the sheet (2026-09-25) — the user gets an error.
    const controller = new AbortController()
    webauthnFlow.current = controller
    let timer: ReturnType<typeof setTimeout> | undefined
    const deadline = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        controller.abort()
        WebAuthnAbortService.cancelCeremony()
        reject(new Error('Touch ID / Windows Hello svarede ikke. Prøv igen.'))
      }, 75_000)
    })
    deadline.catch(() => {})  // only surfaced through withDeadline()
    const withDeadline = <T,>(p: Promise<T>) => Promise.race([p, deadline])
    let options = prefetched.current
    prefetched.current = null   // a challenge is single use
    try {
      if (!options || Date.now() - options.at > PREFETCH_MAX_AGE_MS) {
        // Only if the page could not prefetch (e.g. offline when it loaded).
        setLoading(true)
        await withDeadline(prefetchPasskeyOptions())
        options = prefetched.current
        prefetched.current = null
        if (!options) throw new Error('Kunne ikke kontakte serveren. Tjek forbindelsen og prøv igen.')
      }
      // Page left meanwhile: never start a ceremony from an abandoned page.
      if (controller.signal.aborted) return
      // No await before this call when the challenge was prefetched: it must
      // run inside the click for Safari to show Touch ID.
      const ceremony = withDeadline(startAuthentication({ optionsJSON: options.options }))
      setLoading(true)
      const result = await ceremony
      const data = await withDeadline(fetch(`${getApiUrl()}/api/auth/webauthn/login-complete`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result),
        signal: controller.signal,
      }).then(r => { if (!r.ok) throw new Error('Touch ID-login blev ikke godkendt af serveren. Prøv igen.'); return r.json() }))
      const u = { username: data.username, role: data.role, customer_id: data.customer_id ?? null }
      acceptSessionUser(u)
      navigate(from, { replace: true })
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        setError(e?.name === 'NotAllowedError'
          ? 'Touch ID / Windows Hello blev annulleret eller fandt ingen passkey for dette domæne.'
          : (e?.message ?? 'Touch ID-login fejlede'))
      }
      prefetchPasskeyOptions()   // ready for the next click
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
