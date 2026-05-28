import { useEffect, useState } from 'react'
import { Bot, ExternalLink, LockKeyhole, ShieldCheck } from 'lucide-react'
import { getApiUrl } from '../api/client'

interface OpenWebUIStatus {
  enabled: boolean
  url: string
  allowed: boolean
  mfa_verified: boolean
  required_role: string[]
  expires_minutes: number
  message: string
}

async function api(path: string, options?: RequestInit) {
  const res = await fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? 'Request fejlede')
  }
  return res.json()
}

export default function OpenWebUIPage() {
  const [status, setStatus] = useState<OpenWebUIStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [launching, setLaunching] = useState(false)

  useEffect(() => {
    api('/api/openwebui/access/status')
      .then(setStatus)
      .catch(e => setError(e instanceof Error ? e.message : 'Kunne ikke hente Open WebUI status'))
      .finally(() => setLoading(false))
  }, [])

  async function launch() {
    setLaunching(true)
    setError(null)
    try {
      const data = await api('/api/openwebui/access/issue', { method: 'POST', body: JSON.stringify({}) })
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kunne ikke åbne Open WebUI')
    } finally {
      setLaunching(false)
    }
  }

  if (loading) return <div className="p-6 text-sm text-slate-500">Henter Open WebUI adgang...</div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Bot className="w-5 h-5 text-sky-600" />
            Open WebUI
          </h1>
          <p className="text-sm text-slate-500 mt-1">Kontrolleret adgang til TimeLapse Pro co-pilot via MFA-verificeret session.</p>
        </div>
        <button
          onClick={launch}
          disabled={!status?.allowed || launching}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-slate-800"
        >
          <ExternalLink className="w-4 h-4" />
          {launching ? 'Åbner...' : 'Åbn Open WebUI'}
        </button>
      </div>

      {error && (
        <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-4">
        <div className="border border-slate-200 bg-white rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Session
          </div>
          <p className={`mt-3 text-sm ${status?.mfa_verified ? 'text-emerald-700' : 'text-amber-700'}`}>
            {status?.mfa_verified ? 'MFA verificeret' : 'MFA kræves før adgang'}
          </p>
        </div>

        <div className="border border-slate-200 bg-white rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <LockKeyhole className="w-4 h-4 text-sky-600" />
            Adgang
          </div>
          <p className="mt-3 text-sm text-slate-600">
            {status?.required_role.join(' eller ')} med kortlivet adgangscookie på {status?.expires_minutes} min.
          </p>
        </div>

        <div className="border border-slate-200 bg-white rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Bot className="w-4 h-4 text-violet-600" />
            Scope
          </div>
          <p className="mt-3 text-sm text-slate-600">
            Direkte Open WebUI adgang er låst af nginx og skal udstedes herfra.
          </p>
        </div>
      </div>

      {!status?.allowed && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg px-4 py-3 text-sm text-amber-800">
          Log ind med passkey/Windows Hello/Touch ID eller password plus TOTP MFA for at åbne Open WebUI.
        </div>
      )}
    </div>
  )
}
