import { useState } from 'react'
import { Globe, Wifi, Users, Save, Check, Terminal, Bell } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getApiUrl } from '../api/client'
import { SiteLookConfigPanel } from '../components/SiteLookConfigPanel'
import { useAuth } from '../context/AuthContext'

const TIMEZONES = [
  { value: 'Europe/Copenhagen', label: 'Danmark (CET/CEST)' },
  { value: 'Europe/London',     label: 'UK (GMT/BST)' },
  { value: 'Europe/Berlin',     label: 'Tyskland (CET/CEST)' },
  { value: 'UTC',               label: 'UTC' },
  { value: 'America/New_York',  label: 'New York (EST/EDT)' },
]

const TZ_KEY = 'timelapse_timezone'

export function SettingsPage() {
  const { hasRole } = useAuth()
  const canAdminister = hasRole('super_admin', 'admin')
  const [tz, setTz]         = useState(() => localStorage.getItem(TZ_KEY) ?? 'Europe/Copenhagen')
  const [tzSaved, setTzSaved] = useState(false)

  const saveTz = () => {
    localStorage.setItem(TZ_KEY, tz)
    setTzSaved(true)
    setTimeout(() => setTzSaved(false), 2000)
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
            Browseren bruger deployment/same-origin til API-kald. Edge-facing base URL styres systemisk i databasen.
          </p>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Aktuel browser API</label>
              <div className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono bg-gray-50 text-gray-700 break-all">
                {getApiUrl()}
              </div>
            </div>
            {canAdminister && (
              <>
                <p className="text-xs text-gray-400">
                  Ret Headend Base URL under System Administration, hvis Edge-enheder skal have en anden offentlig adresse.
                </p>
                <Link to="/system-admin"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600">
                  <Wifi className="w-4 h-4" />
                  Åbn Headend indstillinger
                </Link>
              </>
            )}
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

        {canAdminister && (
          <>
            {/* System Admin */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center gap-2 mb-1">
                <Terminal className="w-5 h-5 text-orange-500" />
                <h2 className="text-base font-semibold text-gray-900">System Administration</h2>
              </div>
              <p className="text-sm text-gray-500 mb-4">GPIO, relay, timeouts og alle avancerede parametre</p>
              <Link to="/system-admin"
                className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 text-white text-sm rounded-lg hover:bg-orange-600">
                <Terminal className="w-4 h-4" />
                Åbn System Admin
              </Link>
            </div>

            {/* Notifikationer */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center gap-2 mb-1">
                <Bell className="w-5 h-5 text-sky-500" />
                <h2 className="text-base font-semibold text-gray-900">Alarm Notifikationer</h2>
              </div>
              <p className="text-sm text-gray-500 mb-4">Email, SMS og Teams — konfigurér hvornår og hvem der adviseres</p>
              <Link to="/notifications"
                className="inline-flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600">
                <Bell className="w-4 h-4" />
                Konfigurér notifikationer
              </Link>
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
          </>
        )}

      </div>

      {canAdminister && (
        <div className="mt-6">
          <SiteLookConfigPanel />
        </div>
      )}
    </div>
  )
}
