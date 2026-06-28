import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle, Globe, Layers, RotateCcw, Save } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  }).then(async r => {
    if (!r.ok) throw new Error(await r.text().catch(() => `${r.status}`))
    return r.json()
  })
}

type ConfigObject = Record<string, any>
type LayerKey = 'global' | 'customer' | 'site' | 'camera'

interface ConfigDefaults {
  schedule: ConfigObject
  camera: ConfigObject
  quality: ConfigObject
  storage: ConfigObject
  diagnostics: ConfigObject
  system: ConfigObject
  session_policy: ConfigObject
}

interface EntityOption {
  id: string
  name?: string
  camera_name?: string
  customer_id?: string
  customer_name?: string
  site_id?: string
  site_name?: string
}

interface ResolvedField {
  path: string
  section: string
  key: string
  values: Record<LayerKey, any>
  effective_value: any
  inherited_value: any
  source: LayerKey | 'factory'
  changed_from_global: boolean
  overridden: boolean
}

interface Resolution {
  context: {
    customer_id?: string | null
    customer_name?: string | null
    site_id?: string | null
    site_name?: string | null
    camera_id?: string | null
    camera_name?: string | null
    device_id?: string | null
  }
  layers: Array<{ key: LayerKey; label: string; entity_id: string | null; entity_name: string | null; config: ConfigObject }>
  effective_config: ConfigObject
  fields: ResolvedField[]
}

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'text' | 'select' | 'boolean'
  options?: string[]
  unit?: string
  placeholder?: string
  description?: string
  default?: string | number | boolean
}

const SECTIONS: { key: keyof ConfigDefaults; label: string; description: string; fields: FieldDef[] }[] = [
  {
    key: 'schedule',
    label: 'Optagelsesplan',
    description: 'Frekvens, tidszone og optagelseslogik.',
    fields: [
      { key: 'timezone', label: 'Tidszone', type: 'select', options: ['Europe/Copenhagen', 'Europe/London', 'Europe/Berlin', 'UTC'], default: 'Europe/Copenhagen' },
      { key: 'capture_mode', label: 'Tilstand', type: 'select', options: ['interval', 'fixed_times'], default: 'interval' },
      { key: 'interval_minutes', label: 'Interval', type: 'number', unit: 'min', placeholder: '60', default: 60 },
    ],
  },
  {
    key: 'camera',
    label: 'Kamera',
    description: 'Kamerastyring, eksponering, strøm og orientering.',
    fields: [
      { key: 'power_mode', label: 'Strømstyring', type: 'select', options: ['relay', 'usb_powered'], default: 'relay' },
      { key: 'iso', label: 'ISO', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400'] },
      { key: 'shutter_speed', label: 'Lukker', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500', '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'] },
      { key: 'aperture', label: 'Blænde', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '8', '9', '10', '11', '13', '14', '16', '18', '20', '22'] },
      { key: 'whitebalance', label: 'Hvidbalance', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluorescent', 'Flash'] },
      { key: 'relay_gpio_pin', label: 'Relay GPIO', type: 'number', placeholder: '356' },
      { key: 'relay_on_seconds_before', label: 'Varmetid', type: 'number', unit: 'sek', placeholder: '10', default: 10 },
      { key: 'relay_off_seconds_after', label: 'Nedkøling', type: 'number', unit: 'sek', placeholder: '5', default: 5 },
      { key: 'delete_after_download', label: 'Slet på kamera', type: 'boolean', default: true },
      { key: 'gphoto2_port', label: 'gPhoto2 port', type: 'text', placeholder: 'usb:', default: 'usb:' },
      { key: 'azimuth_deg', label: 'Azimut', type: 'number', unit: '°', placeholder: '247' },
      { key: 'tilt_deg', label: 'Tilt', type: 'number', unit: '°', placeholder: '-15' },
      { key: 'mount_height_m', label: 'Montagehøjde', type: 'number', unit: 'm', placeholder: '8' },
      { key: 'fov_horizontal_deg', label: 'Horisontalt FOV', type: 'number', unit: '°', placeholder: '62' },
      { key: 'fov_vertical_deg', label: 'Vertikalt FOV', type: 'number', unit: '°', placeholder: '40' },
      { key: 'perspective', label: 'Perspektiv', type: 'select', options: ['eye_level', 'high_angle', 'low_angle', 'birds_eye', 'worms_eye'] },
    ],
  },
  {
    key: 'quality',
    label: 'Kvalitet',
    description: 'Automatisk kvalitetstjek af billeder.',
    fields: [
      { key: 'check_enabled', label: 'Aktivt', type: 'boolean', default: true },
      { key: 'blur_threshold', label: 'Skarphed min.', type: 'number', placeholder: '80', default: 80 },
      { key: 'dark_threshold', label: 'Mørk grænse', type: 'number', placeholder: '25', default: 25 },
      { key: 'bright_threshold', label: 'Lys grænse', type: 'number', placeholder: '230', default: 230 },
      { key: 'adaptive_exposure.enabled', label: 'Adaptiv EV', type: 'boolean', default: false },
      { key: 'adaptive_exposure.target_brightness', label: 'Mål-lys', type: 'number', placeholder: '118', default: 118 },
      { key: 'adaptive_exposure.brightness_tolerance', label: 'Lys tolerance', type: 'number', placeholder: '32', default: 32 },
      { key: 'adaptive_exposure.step_ev', label: 'EV trin', type: 'number', placeholder: '0.3', default: 0.3 },
      { key: 'adaptive_exposure.min_ev', label: 'EV min.', type: 'number', placeholder: '-2.0', default: -2.0 },
      { key: 'adaptive_exposure.max_ev', label: 'EV max.', type: 'number', placeholder: '2.0', default: 2.0 },
      { key: 'edge_ai.enabled', label: 'Edge QA AI', type: 'boolean', default: true },
      { key: 'edge_ai.mode', label: 'AI mode', type: 'select', options: ['off', 'monitor', 'assist', 'autonomous', 'npu_first', 'lab'], default: 'assist' },
      { key: 'edge_ai.prefer_npu', label: 'Foretræk NPU', type: 'boolean', default: true },
      { key: 'edge_ai.runner', label: 'NPU runner', type: 'text', placeholder: '/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py' },
      { key: 'edge_ai.model_path', label: 'NPU model', type: 'text', placeholder: '/opt/timelapse/models/edge_qa.nb' },
      { key: 'edge_ai.vendor_binary', label: 'VIPLite wrapper', type: 'text', placeholder: '/opt/timelapse/bin/edge_qa_viplite' },
    ],
  },
  {
    key: 'storage',
    label: 'Edge-lagring',
    description: 'Lokal buffer og database på Edge.',
    fields: [
      { key: 'local_path', label: 'Capture sti', type: 'text', placeholder: '/data/captures', default: '/data/captures' },
      { key: 'circular_buffer_gb', label: 'Buffer', type: 'number', unit: 'GB', placeholder: '50', default: 50 },
      { key: 'db_path', label: 'DB sti', type: 'text', placeholder: '/data/timelapse_edge.db', default: '/data/timelapse_edge.db' },
    ],
  },
  {
    key: 'diagnostics',
    label: 'Diagnostik',
    description: 'Heartbeat, config-poll og rapportering.',
    fields: [
      { key: 'heartbeat_interval_minutes', label: 'Heartbeat', type: 'number', unit: 'min', placeholder: '60', default: 60 },
      { key: 'config_poll_interval_minutes', label: 'Config poll', type: 'number', unit: 'min', placeholder: '5', default: 5 },
      { key: 'update_poll_interval_minutes', label: 'Update poll', type: 'number', unit: 'min', placeholder: '5' },
      { key: 'inventory_report_interval_hours', label: 'Inventory', type: 'number', unit: 'timer', placeholder: '24' },
    ],
  },
  {
    key: 'system',
    label: 'System',
    description: 'Timeouts og recovery-parametre.',
    fields: [
      { key: 'error_recovery_sleep_s', label: 'Recovery pause', type: 'number', unit: 'sek', placeholder: '30', default: 30 },
      { key: 'min_sleep_s', label: 'Minimum sleep', type: 'number', unit: 'sek', placeholder: '60', default: 60 },
      { key: 'api_timeout_s', label: 'API timeout', type: 'number', unit: 'sek', placeholder: '15', default: 15 },
    ],
  },
]

const FIELD_LOOKUP = new Map(SECTIONS.flatMap(section => section.fields.map(field => [`${section.key}.${field.key}`, field])))

function getNested(obj: ConfigObject, path: string): any {
  return path.split('.').reduce<any>((acc, part) => (acc && typeof acc === 'object' ? acc[part] : undefined), obj)
}

function setNested(obj: ConfigObject, path: string, value: any): ConfigObject {
  const result = { ...obj }
  const parts = path.split('.')
  let cursor: ConfigObject = result
  parts.forEach((part, index) => {
    if (index === parts.length - 1) cursor[part] = value
    else {
      cursor[part] = { ...(cursor[part] ?? {}) }
      cursor = cursor[part]
    }
  })
  return result
}

function formatValue(value: any): string {
  if (value === undefined || value === null || value === '') return 'Arver'
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nej'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function normaliseInput(field: FieldDef | undefined, value: string, checked?: boolean) {
  if (field?.type === 'boolean') return checked ? true : null
  if (value === '') return null
  if (field?.type === 'number') return Number(value)
  return value
}

function sourceClass(source: string, layer: LayerKey, changedFromGlobal: boolean) {
  if (source === layer) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (changedFromGlobal) return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-gray-200 bg-white text-gray-600'
}

export function GlobalConfigPage() {
  const [defaults, setDefaults] = useState<ConfigDefaults | null>(null)
  const [customers, setCustomers] = useState<EntityOption[]>([])
  const [sites, setSites] = useState<EntityOption[]>([])
  const [cameras, setCameras] = useState<EntityOption[]>([])
  const [selectedCustomer, setSelectedCustomer] = useState('')
  const [selectedSite, setSelectedSite] = useState('')
  const [selectedCamera, setSelectedCamera] = useState('')
  const [editLayer, setEditLayer] = useState<LayerKey>('global')
  const [resolution, setResolution] = useState<Resolution | null>(null)
  const [draft, setDraft] = useState<ConfigObject>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const filteredSites = useMemo(
    () => sites.filter(site => !selectedCustomer || site.customer_id === selectedCustomer),
    [sites, selectedCustomer],
  )
  const filteredCameras = useMemo(
    () => cameras.filter(camera =>
      (!selectedCustomer || camera.customer_id === selectedCustomer) &&
      (!selectedSite || camera.site_id === selectedSite)
    ),
    [cameras, selectedCustomer, selectedSite],
  )

  async function loadBase() {
    setLoading(true)
    try {
      const [d, c, s, cams] = await Promise.all([
        api('/api/admin/config-defaults'),
        api('/api/admin/customers'),
        api('/api/admin/sites'),
        api('/api/admin/cameras'),
      ])
      setDefaults({ system: {}, session_policy: {}, ...d })
      setCustomers(Array.isArray(c) ? c : [])
      setSites(Array.isArray(s) ? s : [])
      setCameras(Array.isArray(cams) ? cams : [])
    } catch (e: any) {
      setError(`Kunne ikke hente konfiguration (${e.message})`)
    } finally {
      setLoading(false)
    }
  }

  async function loadResolution() {
    const params = new URLSearchParams()
    if (selectedCamera) params.set('camera_id', selectedCamera)
    else if (selectedSite) params.set('site_id', selectedSite)
    else if (selectedCustomer) params.set('customer_id', selectedCustomer)
    try {
      const data = await api(`/api/admin/config-resolution${params.toString() ? `?${params}` : ''}`)
      setResolution(data)
      const layer = data.layers?.find((l: any) => l.key === editLayer)
      setDraft(layer?.config ?? {})
    } catch (e: any) {
      setError(`Kunne ikke resolver konfiguration (${e.message})`)
    }
  }

  useEffect(() => { loadBase() }, [])
  useEffect(() => { if (!loading) loadResolution() }, [loading, selectedCustomer, selectedSite, selectedCamera])
  useEffect(() => {
    const layer = resolution?.layers.find(l => l.key === editLayer)
    setDraft(layer?.config ?? {})
  }, [editLayer, resolution])

  function setDraftField(path: string, value: any) {
    setDraft(prev => setNested(prev, path, value))
  }

  function layerEntityId() {
    if (editLayer === 'global') return 'global'
    const layer = resolution?.layers.find(l => l.key === editLayer)
    return layer?.entity_id || ''
  }

  async function saveLayer() {
    const entityId = layerEntityId()
    if (!entityId) {
      setError(`Vælg en ${editLayer === 'customer' ? 'kunde' : editLayer === 'site' ? 'site' : 'kamera-lokation'} før du gemmer.`)
      return
    }
    setSaving(true)
    try {
      await api(`/api/admin/config-overrides/${editLayer}/${encodeURIComponent(entityId)}`, {
        method: 'PUT',
        body: JSON.stringify({ mode: editLayer === 'global' ? 'replace' : 'merge', config_overrides: draft }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 1800)
      await loadResolution()
    } catch (e: any) {
      setError(`Kunne ikke gemme (${e.message})`)
    } finally {
      setSaving(false)
    }
  }

  function resetGlobalFactory() {
    if (!defaults || !confirm('Nulstil globale defaults til fabriksværdier i editoren? Gem bagefter for at aktivere.')) return
    const factory: ConfigDefaults = {
      schedule: { timezone: 'Europe/Copenhagen', capture_mode: 'interval', interval_minutes: 60, active_hours: ['06:00', '21:00'] },
      camera: { power_mode: 'relay', relay_gpio_pin: 356, relay_on_seconds_before: 10, relay_off_seconds_after: 5, delete_after_download: true, gphoto2_port: 'usb:' },
      quality: {
        check_enabled: true,
        blur_threshold: 80,
        dark_threshold: 25,
        bright_threshold: 230,
        adaptive_exposure: {
          enabled: false,
          target_brightness: 118,
          brightness_tolerance: 32,
          step_ev: 0.3,
          min_ev: -2.0,
          max_ev: 2.0,
        },
        edge_ai: {
          enabled: true,
          mode: 'assist',
          prefer_npu: true,
          runner: '/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py',
          model_path: '',
          vendor_binary: '',
        },
      },
      storage: { local_path: '/data/captures', circular_buffer_gb: 50, db_path: '/data/timelapse_edge.db' },
      diagnostics: { heartbeat_interval_minutes: 60, config_poll_interval_minutes: 5, update_poll_interval_minutes: 5, inventory_report_interval_hours: 24 },
      system: { error_recovery_sleep_s: 30, min_sleep_s: 60, api_timeout_s: 15 },
      session_policy: { session_duration_hours: 12, remember_me_days: 30, absolute_max_days: 90, rolling_enabled: true, remember_me_allowed: true, mfa_required: false, webauthn_required: false },
    }
    setEditLayer('global')
    setDraft(factory)
  }

  if (loading) return <div className="max-w-6xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>

  const knownFieldPaths = new Set(SECTIONS.flatMap(section => section.fields.map(field => `${section.key}.${field.key}`)))
  const knownFields = resolution?.fields.filter(field => knownFieldPaths.has(field.path)) ?? []
  const extraFields = resolution?.fields.filter(field => !knownFieldPaths.has(field.path)) ?? []
  const tableFields = [...knownFields, ...extraFields]

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/settings" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <Globe className="w-5 h-5 text-sky-500" />
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Global Config</h1>
          <p className="text-xs text-gray-400">Global → kunde → site → kamera. Underliggende lag vinder.</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Kunde</label>
            <select value={selectedCustomer} onChange={e => { setSelectedCustomer(e.target.value); setSelectedSite(''); setSelectedCamera('') }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="">Global kontekst</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Site</label>
            <select value={selectedSite} onChange={e => { setSelectedSite(e.target.value); setSelectedCamera('') }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" disabled={!selectedCustomer && filteredSites.length === 0}>
              <option value="">Arv fra kunde/global</option>
              {filteredSites.map(s => <option key={s.id} value={s.id}>{s.customer_name ? `${s.customer_name} / ` : ''}{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Kamera-lokation</label>
            <select value={selectedCamera} onChange={e => setSelectedCamera(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" disabled={!selectedSite && filteredCameras.length === 0}>
              <option value="">Arv fra site/kunde/global</option>
              {filteredCameras.map(c => (
                <option key={c.id} value={c.id}>
                  {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Rediger lag</label>
            <select value={editLayer} onChange={e => setEditLayer(e.target.value as LayerKey)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="global">Global</option>
              <option value="customer" disabled={!resolution?.context.customer_id}>Kunde</option>
              <option value="site" disabled={!resolution?.context.site_id}>Site</option>
              <option value="camera" disabled={!resolution?.context.camera_id}>Kamera</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-sky-50 border border-sky-100 rounded-xl px-4 py-3 mb-5">
        <div className="flex items-center gap-2 text-sm font-medium text-sky-900">
          <Layers className="w-4 h-4" />
          Effektiv kontekst
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {resolution?.layers.map(layer => (
            <span key={layer.key} className={`px-2 py-1 rounded-lg border ${
              layer.key === editLayer ? 'bg-white border-sky-300 text-sky-700' : 'bg-sky-100 border-sky-100 text-sky-700'
            }`}>
              {layer.label}: {layer.entity_name || (layer.key === 'global' ? 'Globale defaults' : 'ikke valgt')}
            </span>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Arv og overrides</h2>
            <p className="text-xs text-gray-400">Grøn = sat på valgte lag. Gul = afviger fra global default.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={saveLayer} disabled={saving}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-500 text-white text-xs hover:bg-sky-600 disabled:opacity-50">
              {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
              {saved ? 'Gemt' : saving ? 'Gemmer' : 'Gem lag'}
            </button>
            {editLayer === 'global' && (
              <button onClick={resetGlobalFactory}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-gray-500 text-xs hover:bg-gray-50">
                <RotateCcw className="w-4 h-4" />
                Fabrik
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="text-left font-medium px-4 py-2 w-56">Parameter</th>
                <th className="text-left font-medium px-4 py-2">Global</th>
                <th className="text-left font-medium px-4 py-2">Kunde</th>
                <th className="text-left font-medium px-4 py-2">Site</th>
                <th className="text-left font-medium px-4 py-2">Kamera</th>
                <th className="text-left font-medium px-4 py-2">Aktuel</th>
                <th className="text-left font-medium px-4 py-2 w-64">Rediger valgt lag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tableFields.map(field => {
                const def = FIELD_LOOKUP.get(field.path)
                const draftValue = getNested(draft, field.path)
                return (
                  <tr key={field.path} className={field.changed_from_global ? 'bg-amber-50/30' : ''}>
                    <td className="px-4 py-3 align-top">
                      <div className="font-medium text-gray-800">{def?.label ?? field.key}</div>
                      <div className="text-[11px] text-gray-400 font-mono">{field.path}</div>
                      {!def && <div className="text-[11px] text-amber-600 mt-1">Dynamisk parameter</div>}
                    </td>
                    {(['global', 'customer', 'site', 'camera'] as LayerKey[]).map(layer => (
                      <td key={layer} className="px-4 py-3 align-top">
                        <span className={`inline-flex max-w-48 truncate rounded-lg border px-2 py-1 text-xs ${sourceClass(field.source, layer, field.changed_from_global)}`}>
                          {formatValue(field.values[layer])}
                        </span>
                      </td>
                    ))}
                    <td className="px-4 py-3 align-top">
                      <div className="text-gray-900">{formatValue(field.effective_value)}</div>
                      <div className="text-[11px] text-gray-400">fra {field.source}</div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      {def?.type === 'boolean' ? (
                        <label className="inline-flex items-center gap-2 text-xs text-gray-600">
                          <input type="checkbox" checked={draftValue === true}
                            onChange={e => setDraftField(field.path, normaliseInput(def, '', e.target.checked))}
                            className="w-4 h-4 rounded" />
                          Aktiv
                        </label>
                      ) : def?.type === 'select' ? (
                        <select value={draftValue ?? ''} onChange={e => setDraftField(field.path, normaliseInput(def, e.target.value))}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                          <option value="">Arv</option>
                          {def.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      ) : (
                        <input type={def?.type === 'number' ? 'number' : 'text'} value={draftValue ?? ''}
                          placeholder="Arv"
                          onChange={e => setDraftField(field.path, def ? normaliseInput(def, e.target.value) : (e.target.value === '' ? null : e.target.value))}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs" />
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
