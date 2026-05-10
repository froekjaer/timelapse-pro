import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Globe, Save, CheckCircle, RotateCcw } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts
  }).then(r => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
}

interface ConfigDefaults {
  schedule:    Record<string, unknown>
  camera:      Record<string, unknown>
  quality:     Record<string, unknown>
  storage:     Record<string, unknown>
  diagnostics: Record<string, unknown>
  system:      Record<string, unknown>
}

interface FieldDef {
  key:         string
  label:       string
  type:        'number' | 'text' | 'select' | 'boolean'
  options?:    string[]
  unit?:       string
  placeholder?: string
  description?: string
  default?:    string | number | boolean
}

const SECTIONS: { key: keyof ConfigDefaults; label: string; description: string; fields: FieldDef[] }[] = [
  {
    key: 'schedule',
    label: 'Optagelsesplan',
    description: 'Globale defaults for optagelsesinterval og tidsplan — overstyres af kunde, site og kamera.',
    fields: [
      { key: 'timezone',          label: 'Standard tidszone',    type: 'select', options: ['Europe/Copenhagen','Europe/London','Europe/Berlin','UTC'], default: 'Europe/Copenhagen' },
      { key: 'capture_mode',      label: 'Standard tilstand',    type: 'select', options: ['interval','fixed_times'], default: 'interval', description: 'Interval = hvert N min, Fixed = faste tidspunkter' },
      { key: 'interval_minutes',  label: 'Optagelsesinterval',   type: 'number', unit: 'min', placeholder: '60', default: 60, description: 'Minutter mellem hvert billede' },
    ]
  },
  {
    key: 'camera',
    label: 'Kamera',
    description: 'Globale kamera defaults — overstyres af kamera-niveau config_overrides.',
    fields: [
      { key: 'relay_on_seconds_before',  label: 'Varmetid',          type: 'number', unit: 'sek', placeholder: '10', default: 10, description: 'Sekunder relay tændes før capture' },
      { key: 'relay_off_seconds_after',  label: 'Nedkølingstid',     type: 'number', unit: 'sek', placeholder: '5',  default: 5,  description: 'Sekunder efter capture inden relay slukkes' },
      { key: 'delete_after_download',    label: 'Slet efter download', type: 'boolean', default: true, description: 'Slet billede fra kamera RAM efter download' },
    ]
  },
  {
    key: 'quality',
    label: 'Kvalitetskontrol',
    description: 'Tærskler for automatisk kvalitetstjek — billeder udenfor disse grænser markeres som fejl.',
    fields: [
      { key: 'check_enabled',    label: 'Kvalitetstjek aktivt',  type: 'boolean', default: true },
      { key: 'blur_threshold',   label: 'Skarphed minimum',      type: 'number', placeholder: '80',  default: 80,  description: 'Blur score under denne = for uskarpt' },
      { key: 'dark_threshold',   label: 'Mørk grænse',           type: 'number', placeholder: '25',  default: 25,  description: 'Lysstyrke under denne = for mørkt' },
      { key: 'bright_threshold', label: 'Lys grænse',            type: 'number', placeholder: '230', default: 230, description: 'Lysstyrke over denne = overbelyst' },
    ]
  },
  {
    key: 'storage',
    label: 'Lagring',
    description: 'Lokal lagring på edge enheden.',
    fields: [
      { key: 'local_path',         label: 'Capture sti',          type: 'text',   placeholder: '/data/captures', default: '/data/captures' },
      { key: 'circular_buffer_gb', label: 'Circular buffer',      type: 'number', unit: 'GB', placeholder: '50', default: 50, description: 'Maksimal lokal lagerplads — ældste billeder slettes' },
      { key: 'db_path',            label: 'Database sti',         type: 'text',   placeholder: '/data/timelapse_edge.db', default: '/data/timelapse_edge.db' },
    ]
  },
  {
    key: 'diagnostics',
    label: 'Diagnostik',
    description: 'Heartbeat, config polling og systemovervågning.',
    fields: [
      { key: 'heartbeat_interval_minutes',    label: 'Heartbeat interval',      type: 'number', unit: 'min', placeholder: '60', default: 60,  description: 'Minutter mellem diagnostik rapporter til headend' },
      { key: 'config_poll_interval_minutes',  label: 'Config poll interval',    type: 'number', unit: 'min', placeholder: '5',  default: 5,   description: 'Minutter mellem config-hentning fra headend (lav = hurtigere respons, høj = mindre trafik)' },
    ]
  },
  {
    key: 'system' as keyof ConfigDefaults,
    label: 'System',
    description: 'Interne system timeouts og recovery parametre.',
    fields: [
      { key: 'error_recovery_sleep_s', label: 'Fejl recovery pause',   type: 'number', unit: 'sek', placeholder: '30',  default: 30,  description: 'Sekunder at vente efter uventet fejl i hoved-loop' },
      { key: 'min_sleep_s',            label: 'Minimum sleep',          type: 'number', unit: 'sek', placeholder: '60',  default: 60,  description: 'Minimum sekunder at sove når næste capture ikke kendes' },
      { key: 'api_timeout_s',          label: 'API timeout',            type: 'number', unit: 'sek', placeholder: '15',  default: 15,  description: 'Sekunder før API kald til headend timeout' },
    ]
  },
]

function FieldInput({ field, value, onChange }: { field: FieldDef; value: unknown; onChange: (v: unknown) => void }) {
  const strVal = value != null ? String(value) : ''

  if (field.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" className="w-4 h-4 rounded"
          checked={!!value}
          onChange={e => onChange(e.target.checked)} />
        <span className="text-sm text-gray-600">{value ? 'Aktivt' : 'Deaktiveret'}</span>
      </label>
    )
  }
  if (field.type === 'select') {
    return (
      <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
        value={strVal} onChange={e => onChange(e.target.value)}>
        {field.options?.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    )
  }
  return (
    <input type={field.type === 'number' ? 'number' : 'text'}
      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
      placeholder={field.placeholder}
      value={strVal}
      onChange={e => onChange(field.type === 'number' ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value)} />
  )
}

export function GlobalConfigPage() {
  const [cfg, setCfg]           = useState<ConfigDefaults | null>(null)
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState<string | null>(null)

  useEffect(() => {
    api('/api/admin/config-defaults')
      .then(d => setCfg({
        system: {},
        ...d,
        diagnostics: d.diagnostics ?? {},
      }))
      .catch(() => setError('Kunne ikke hente globale defaults'))
      .finally(() => setLoading(false))
  }, [])

  function setField(section: keyof ConfigDefaults, key: string, value: unknown) {
    setCfg(prev => prev ? {
      ...prev,
      [section]: { ...prev[section], [key]: value }
    } : prev)
  }

  async function save() {
    if (!cfg) return
    setSaving(true)
    try {
      await api('/api/admin/config-defaults', {
        method: 'PUT',
        body: JSON.stringify(cfg)
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      setError('Kunne ikke gemme')
    } finally {
      setSaving(false)
    }
  }

  function resetDefaults() {
    if (!confirm('Nulstil alle globale defaults til fabriksindstillinger?')) return
    const defaults: ConfigDefaults = {
      schedule:    { timezone: 'Europe/Copenhagen', capture_mode: 'interval', interval_minutes: 60, active_hours: ['06:00', '21:00'] },
      camera:      { relay_on_seconds_before: 10, relay_off_seconds_after: 5, delete_after_download: true, gphoto2_port: 'usb:' },
      quality:     { check_enabled: true, blur_threshold: 80, dark_threshold: 25, bright_threshold: 230 },
      storage:     { local_path: '/data/captures', circular_buffer_gb: 50, db_path: '/data/timelapse_edge.db' },
      diagnostics: { heartbeat_interval_minutes: 60, config_poll_interval_minutes: 5 },
      system:      { error_recovery_sleep_s: 30, min_sleep_s: 60, api_timeout_s: 15 },
    }
    setCfg(defaults)
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/settings" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-sky-500" />
          <h1 className="text-xl font-semibold text-gray-900">Globale defaults</h1>
        </div>
      </div>

      {/* Forklaring */}
      <div className="bg-sky-50 border border-sky-100 rounded-xl p-4 mb-6">
        <p className="text-sm text-sky-700 font-medium mb-1">Hierarkisk konfigurationsmodel</p>
        <p className="text-xs text-sky-600">
          Globale defaults er lag 1 — de overskrives i denne rækkefølge:
        </p>
        <div className="flex items-center gap-2 mt-2 text-xs text-sky-600 font-mono flex-wrap">
          <span className="px-2 py-0.5 bg-sky-100 rounded font-bold text-sky-700">Global ← du er her</span>
          <span>→</span>
          <span className="px-2 py-0.5 bg-white border border-sky-200 rounded">Kunde</span>
          <span>→</span>
          <span className="px-2 py-0.5 bg-white border border-sky-200 rounded">Site</span>
          <span>→</span>
          <span className="px-2 py-0.5 bg-white border border-sky-200 rounded">Kamera</span>
          <span>→</span>
          <span className="px-2 py-0.5 bg-white border border-sky-200 rounded">Runtime</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      {/* Sektioner */}
      {cfg && SECTIONS.map(section => (
        <div key={section.key} className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">{section.label}</h2>
          <p className="text-xs text-gray-400 mb-4">{section.description}</p>
          <div className="space-y-4">
            {section.fields.map(field => (
              <div key={field.key}>
                <div className="flex items-center gap-2 mb-1">
                  <label className="text-xs text-gray-500 font-medium">{field.label}</label>
                  {field.unit && <span className="text-xs text-gray-300">{field.unit}</span>}
                  {field.default != null && cfg[section.key][field.key] != null &&
                   String(cfg[section.key][field.key]) !== String(field.default) && (
                    <span className="text-xs text-amber-500 font-medium">● Ændret fra default ({String(field.default)})</span>
                  )}
                </div>
                <FieldInput
                  field={field}
                  value={cfg[section.key][field.key]}
                  onChange={v => setField(section.key, field.key, v)} />
                {field.description && (
                  <p className="text-xs text-gray-300 mt-0.5">{field.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Gem og reset */}
      <div className="flex items-center justify-between">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>
        <button onClick={resetDefaults}
          className="flex items-center gap-2 px-4 py-2.5 text-gray-400 border border-gray-200 text-sm rounded-lg hover:bg-gray-50">
          <RotateCcw className="w-4 h-4" />
          Nulstil til fabrik
        </button>
      </div>
    </div>
  )
}
