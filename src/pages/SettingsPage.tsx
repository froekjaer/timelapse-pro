import { useState, useEffect } from 'react'
import { Globe, Wifi, Users, Save, Check, AlertCircle, CheckCircle } from 'lucide-react'
import { getApiUrl, API_STORAGE_KEY, DEFAULT_API_URL, testConnection } from '../api/client'

const TIMEZONES = [
  { value: 'Europe/Copenhagen', label: 'Danmark (CET/CEST)' },
  { value: 'Europe/London',     label: 'UK (GMT/BST)' },
  { value: 'Europe/Berlin',     label: 'Tyskland (CET/CEST)' },
  { value: 'UTC',               label: 'UTC' },
  { value: 'America/New_York',  label: 'New York (EST/EDT)' },
]

const TZ_KEY = 'timelapse_timezone'

export function SettingsPage() {
  const [tz, setTz]         = useState(() => localStorage.getItem(TZ_KEY) ?? 'Europe/Copenhagen')
  const [tzSaved, setTzSaved] = useState(false)

  const [apiUrl, setApiUrl]     = useState(() => getApiUrl())
  const [apiSaved, setApiSaved] = useState(false)
  const [apiStatus, setApiStatus] = useState<'idle' | 'testing' | 'ok' | 'error'>('idle')
  const [apiError, setApiError]   = useState('')

  const saveTz = () => {
    localStorage.setItem(TZ_KEY, tz)
    setTzSaved(true)
    setTimeout(() => setTzSaved(false), 2000)
  }

  const testApi = async (url: string) => {
    setApiStatus('testing')
    setApiError('')
    try {
      localStorage.setItem(API_STORAGE_KEY, url)
      const res = await testConnection()
      setApiStatus('ok')
    } catch (e: any) {
      setApiStatus('error')
      setApiError(e?.message ?? 'Forbindelsesfejl')
      localStorage.setItem(API_STORAGE_KEY, url)
    }
  }

  const saveApi = async () => {
    await testApi(apiUrl)
    setApiSaved(true)
    setTimeout(() => setApiSaved(false), 3000)
  }

  const now = new Date().toLocaleString('da-DK', {
    timeZone: tz,
    weekday: 'long', day: 'numeric', month: 'long',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">Indstillinger</h1>
      <p className="text-sm text-gray-500 mb-8">System- og brugerkonfiguration</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Headend API */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-1">
            <Wifi className="w-5 h-5 text-sky-500" />
            <h2 className="text-base font-semibold text-gray-900">Headend API</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            IP-adresse eller domænenavn til headend-serveren.
          </p>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">URL (inkl. port)</label>
              <input
                type="text"
                value={apiUrl}
                onChange={e => setApiUrl(e.target.value)}
                placeholder="http://192.168.86.132:8000"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-300"
              />
              <p className="text-xs text-gray-400 mt-1">
                Eksempler: http://192.168.86.132:8000 · https://timelapse.example.com
              </p>
            </div>

            {apiStatus === 'ok' && (
              <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                Forbundet til headend
              </div>
            )}
            {apiStatus === 'error' && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {apiError || 'Kunne ikke forbinde'}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => testApi(apiUrl)}
                disabled={apiStatus === 'testing'}
                className="px-3 py-2 rounded-lg text-sm border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
              >
                {apiStatus === 'testing' ? 'Tester…' : 'Test forbindelse'}
              </button>
              <button
                onClick={saveApi}
                disabled={apiStatus === 'testing'}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  apiSaved ? 'bg-emerald-500 text-white' : 'bg-sky-500 hover:bg-sky-600 text-white'
                } disabled:opacity-50`}
              >
                {apiSaved ? <><Check className="w-4 h-4" /> Gemt</> : <><Save className="w-4 h-4" /> Gem</>}
              </button>
            </div>
            <p className="text-xs text-gray-400">
              Aktuel: <span className="font-mono">{getApiUrl()}</span>
            </p>
          </div>
        </div>

        {/* Tidszone */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-1">
            <Globe className="w-5 h-5 text-sky-500" />
            <h2 className="text-base font-semibold text-gray-900">Tidszone</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Tidszone for visning af capture-tidspunkter.
          </p>
          <div className="space-y-3">
            <select
              value={tz}
              onChange={e => setTz(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300"
            >
              {TIMEZONES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-sm text-gray-600">
              <span className="text-gray-400 text-xs block mb-0.5">Lokal tid nu:</span>
              {now}
            </div>
            <button
              onClick={saveTz}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tzSaved ? 'bg-emerald-500 text-white' : 'bg-sky-500 hover:bg-sky-600 text-white'
              }`}
            >
              {tzSaved ? <><Check className="w-4 h-4" /> Gemt</> : <><Save className="w-4 h-4" /> Gem tidszone</>}
            </button>
          </div>
        </div>

        {/* RBAC placeholder */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 opacity-60">
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-5 h-5 text-gray-400" />
            <h2 className="text-base font-semibold text-gray-900">Brugerstyring (RBAC)</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">Roller og adgangsrettigheder</p>
          <div className="space-y-2">
            {['Admin — fuld adgang', 'Operatør — læs + config', 'Kunde — kun egne data'].map(r => (
              <div key={r} className="flex items-center gap-2 text-sm text-gray-400">
                <span className="w-2 h-2 rounded-full bg-gray-300" />
                {r}
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-4">Kommer i Fase 3</p>
        </div>

      </div>
    </div>
  )
}
