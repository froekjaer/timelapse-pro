import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Building2, MapPin, Camera, Save, Trash2, ChevronRight,
         CheckCircle, Beaker, Image, Settings } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: {
      'Content-Type': 'application/json',

    },
    ...opts
  }).then(r => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
}

interface CameraDevice {
  device_id: string
  site_id?: string
  camera_name?: string
  camera_index: number
  relay_gpio_camera: number
  relay_gpio_modem: number
  camera_model?: string
  status: string
  last_seen?: string
  first_seen?: string
  app_version?: string
  config_overrides: Record<string, unknown>
  customer_name?: string
  site_name?: string
  location_name?: string
}

interface CameraLocation {
  id: string
  camera_name: string
  site_id: string | null
  site_name: string | null
  customer_id: string | null
  customer_name: string | null
  model: string | null
  notes: string | null
}

interface CameraOption { id: string; camera_name: string; site_name?: string; customer_name?: string; customer_id?: string; site_id?: string }

interface ParamRow {
  key: string
  label: string
  section: string
  type: 'number' | 'text' | 'select' | 'boolean'
  options?: string[]
  unit?: string
  placeholder?: string
  description?: string
}

const CAMERA_PARAMS: ParamRow[] = [
  // Optagelse
  { key: 'schedule.interval_minutes', label: 'Optagelsesinterval', section: 'Optagelse', type: 'number', unit: 'min', placeholder: '60', description: 'Minutter mellem hvert billede' },
  { key: 'schedule.capture_mode',     label: 'Tilstand', section: 'Optagelse', type: 'select', options: ['interval', 'fixed_times'], description: 'Interval = hvert N min, Fixed = faste tidspunkter' },
  // Kamera
  { key: 'camera.iso',               label: 'ISO', section: 'Kamera', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400'], description: 'Lysfølsomhed — Auto anbefales til varierende lys' },
  { key: 'camera.shutter_speed',     label: 'Lukkerhastiged', section: 'Kamera', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500', '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'], description: 'Eksponeringstid i sekunder' },
  { key: 'camera.aperture',          label: 'Blænde', section: 'Kamera', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '8', '9', '10', '11', '13', '14', '16', '18', '20', '22'], description: 'f-tal — højere = skarpere baggrund' },
  { key: 'camera.whitebalance',      label: 'Hvidbalance', section: 'Kamera', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluorescent', 'Flash'], description: 'Auto anbefales til varierende vejr' },
  { key: 'camera.serial_number',     label: 'Kamera serienummer', section: 'Hardware', type: 'text', placeholder: 'fx d12b869bf88a4b719094a801bdaa41c7', description: 'gphoto2 serienummer — bruges til stabil USB port identificering ved multi-kamera' },
  { key: 'camera.power_mode',        label: 'Strømstyring', section: 'Hardware', type: 'select', options: ['relay', 'usb_powered'], description: 'relay = agenten tænder/slukker via GPIO; usb_powered = kameraet har konstant strøm og går selv i standby' },
  { key: 'camera.relay_gpio_pin',    label: 'Relay GPIO (kamera)', section: 'Hardware', type: 'number', placeholder: '356', description: 'GPIO pin til kamera relay' },
  { key: 'camera.relay_on_seconds_before', label: 'Varmetid (sekunder)', section: 'Hardware', type: 'number', placeholder: '10', description: 'Sekunder relay er tændt før capture' },
  { key: 'camera.relay_off_seconds_after', label: 'Nedkølingstid (sekunder)', section: 'Hardware', type: 'number', placeholder: '5', description: 'Sekunder relay er tændt efter capture' },
  // Orientering og montering
  { key: 'camera.azimuth_deg',       label: 'Azimut (retning)', section: 'Orientering', type: 'number', unit: '°', placeholder: '247', description: 'Retning kameraet peger — 0=Nord, 90=Øst, 180=Syd, 270=Vest' },
  { key: 'camera.tilt_deg',          label: 'Vertikal vinkel (tilt)', section: 'Orientering', type: 'number', unit: '°', placeholder: '-15', description: 'Negativ = skrå ned, 0 = vandret, positiv = skrå op' },
  { key: 'camera.mount_height_m',    label: 'Montagehøjde', section: 'Orientering', type: 'number', unit: 'm', placeholder: '8', description: 'Meter over terræn' },
  { key: 'camera.fov_horizontal_deg',label: 'Horisontalt FOV', section: 'Orientering', type: 'number', unit: '°', placeholder: '62', description: 'Synsfelt horisontalt — afhænger af linse og sensor' },
  { key: 'camera.fov_vertical_deg',  label: 'Vertikalt FOV', section: 'Orientering', type: 'number', unit: '°', placeholder: '40', description: 'Synsfelt vertikalt' },
  { key: 'camera.perspective',       label: 'Perspektiv', section: 'Orientering', type: 'select', options: ['eye_level', 'high_angle', 'low_angle', 'birds_eye', 'worms_eye'], description: 'Beskriver kameravinklen til billedredigering' },
  // Kvalitet
  { key: 'quality.blur_threshold',   label: 'Skarphed minimum', section: 'Kvalitet', type: 'number', placeholder: '80', description: 'Billeder under denne score markeres som fejl' },
  { key: 'quality.dark_threshold',   label: 'Mørk grænse', section: 'Kvalitet', type: 'number', placeholder: '25', description: 'Gennemsnitlig lysstyrke under denne = for mørkt' },
  { key: 'quality.bright_threshold', label: 'Lys grænse', section: 'Kvalitet', type: 'number', placeholder: '230', description: 'Gennemsnitlig lysstyrke over denne = overbelyst' },
  // Diagnostik
  { key: 'diagnostics.heartbeat_interval_minutes', label: 'Heartbeat interval', section: 'Diagnostik', type: 'number', unit: 'min', placeholder: '60', description: 'Minutter mellem diagnostik uploads' },
]

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const parts = path.split('.')
  let val: unknown = obj
  for (const p of parts) {
    if (val && typeof val === 'object') val = (val as Record<string, unknown>)[p]
    else return ''
  }
  return val != null ? String(val) : ''
}

function setNestedValue(obj: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const result = { ...obj }
  const parts = path.split('.')
  if (parts.length === 1) {
    result[parts[0]] = value
  } else {
    const section = parts[0]
    const rest = parts.slice(1).join('.')
    result[section] = setNestedValue((result[section] as Record<string, unknown>) || {}, rest, value)
  }
  return result
}

const TZ = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

export function CameraPage() {
  const { deviceId } = useParams<{ deviceId: string }>()
  const navigate = useNavigate()
  const [device, setDevice]           = useState<CameraDevice | null>(null)
  const [loading, setLoading]         = useState(true)
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError]             = useState<string | null>(null)

  // Editable fields
  const [cameraName, setCameraName]   = useState('')
  const [cameraIndex, setCameraIndex] = useState(0)
  const [relayCamera, setRelayCamera] = useState(356)
  const [relayModem, setRelayModem]   = useState(361)
  const [overrides, setOverrides]     = useState<Record<string, unknown>>({})
  const [sites, setSites]             = useState<{id:string, name:string, customer_name:string}[]>([])
  const [assignSiteId, setAssignSiteId] = useState('')
  const [assigning, setAssigning]     = useState(false)

  // ── Kamera lokation ──────────────────────────────────────────────────────
  const [cameraLocation, setCameraLocation] = useState<CameraLocation | null>(null)
  const [allCameras, setAllCameras]         = useState<CameraOption[]>([])
  const [reassignCamId, setReassignCamId]   = useState('')
  const [reassigning, setReassigning]       = useState(false)
  const [locationExpanded, setLocationExpanded] = useState(false)

  // ── BT TOTP QR ───────────────────────────────────────────────────────────
  const [btTotp, setBtTotp]               = useState<{secret:string,sid:string,source:string,qr_code:string,is_factory_default:boolean}|null>(null)
  const [btTotpLoading, setBtTotpLoading] = useState(false)
  const [btTotpRegen, setBtTotpRegen]     = useState(false)

  useEffect(() => {
    fetch(`${getApiUrl()}/api/admin/sites`).then(r=>r.json()).then((ss:any[]) => setSites(ss)).catch(()=>{})
    // Load all cameras for reassignment picker
    fetch(`${getApiUrl()}/api/admin/cameras`).then(r=>r.json()).then((cs:any[]) => setAllCameras(cs)).catch(()=>{})
  }, [])

  async function loadCameraLocation() {
    if (!deviceId) return
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/devices/${encodeURIComponent(deviceId)}/camera-location`, {
        headers: { 'Content-Type': 'application/json' },
      })
      if (r.ok) {
        const data = await r.json()
        setCameraLocation(data.camera ?? null)
      }
    } catch { /* silent */ }
  }

  useEffect(() => {
    if (!deviceId) return
    api(`/api/admin/devices/${pathSegment(deviceId)}`)
      .then((d: any) => {
        const dev = d.device ?? d
        setDevice(dev)
        setCameraName(dev.camera_name ?? '')
        setCameraIndex(dev.camera_index ?? 0)
        setRelayCamera(dev.relay_gpio_camera ?? 356)
        setRelayModem(dev.relay_gpio_modem ?? 361)
        try {
          setOverrides(JSON.parse(typeof dev.config_overrides === 'string'
            ? dev.config_overrides : JSON.stringify(dev.config_overrides || {})))
        } catch { setOverrides({}) }
      })
      .catch(() => setError('Kunne ikke hente enhed'))
      .finally(() => setLoading(false))
    loadCameraLocation()
  }, [deviceId])

  function setParam(path: string, value: string) {
    setOverrides(prev => setNestedValue(prev, path, value === '' ? null : value))
  }

  async function save() {
    setSaving(true)
    try {
      // Gem kamera info
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}/info`, {
        method: 'PUT',
        body: JSON.stringify({ camera_name: cameraName })
      })
      // Gem config_overrides (kamera-laget)
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}/overrides`, {
        method: 'PUT',
        body: JSON.stringify({
          camera_index:      cameraIndex,
          relay_gpio_camera: relayCamera,
          relay_gpio_modem:  relayModem,
          config_overrides:  overrides,
        })
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      setError('Kunne ikke gemme')
    } finally {
      setSaving(false)
    }
  }

  async function deleteDevice() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}`, { method: 'DELETE' })
      navigate('/')
    } catch {
      setError('Sletning fejlede')
      setConfirmDelete(false)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>
  if (!device) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-500">{error}</div>

  const sections = [...new Set(CAMERA_PARAMS.map(p => p.section))]
  const lastSeen = device.last_seen
    ? new Date(device.last_seen + 'Z').toLocaleString('da-DK', { timeZone: TZ(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '–'

  async function assignToSite() {
    if (!assignSiteId) return
    setAssigning(true)
    try {
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}/assign`, {
        method: 'PUT',
        body: JSON.stringify({ site_id: assignSiteId })
      })
      const d = await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}`)
      setDevice(d)
    } catch { } finally { setAssigning(false) }
  }

  async function loadBtTotp() {
    if (!cameraLocation?.id) return
    setBtTotpLoading(true)
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraLocation.id)}/bt-totp-qr`, {
        headers: { 'Content-Type': 'application/json' },
      })
      if (r.ok) setBtTotp(await r.json())
    } catch { /* silent */ }
    finally { setBtTotpLoading(false) }
  }

  async function regenerateBtTotp() {
    if (!cameraLocation?.id || !confirm('Generér nyt TOTP secret? Det nuværende QR-code bliver ugyldigt.')) return
    setBtTotpRegen(true)
    try {
      await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraLocation.id)}/bt-totp-regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      await loadBtTotp()
    } catch { /* silent */ }
    finally { setBtTotpRegen(false) }
  }

  async function reassignToCamera() {
    if (!reassignCamId || !deviceId) return
    setReassigning(true)
    try {
      await api(`/api/admin/cameras/${encodeURIComponent(reassignCamId)}/assign`, {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, assigned_by: 'admin-ui' }),
      })
      await loadCameraLocation()
      const d = await api(`/api/admin/devices/${pathSegment(deviceId)}`)
      setDevice(d.device ?? d)
      setReassignCamId('')
    } catch { setError('Omtildeling fejlede') }
    finally { setReassigning(false) }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6 text-sm text-gray-400">
        <Link to="/" className="p-1 rounded hover:bg-gray-100">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        {device.customer_name && (
          <>
            <Building2 className="w-3.5 h-3.5" />
            <span>{device.customer_name}</span>
            <ChevronRight className="w-3 h-3" />
          </>
        )}
        {device.site_name && (
          <>
            <MapPin className="w-3.5 h-3.5" />
            <span>{device.site_name}</span>
            <ChevronRight className="w-3 h-3" />
          </>
        )}
        <Camera className="w-3.5 h-3.5 text-sky-500" />
        <span className="text-gray-700 font-medium">{device.camera_name || device.device_id}</span>
      </div>

      {/* ── Kamera lokation ─────────────────────────────────────────────── */}
      {cameraLocation ? (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <Camera className="w-4 h-4 text-sky-500" />
              <span className="font-medium">{cameraLocation.camera_name}</span>
              {cameraLocation.site_name && (
                <span className="text-gray-400">
                  — {cameraLocation.customer_name && `${cameraLocation.customer_name} / `}{cameraLocation.site_name}
                </span>
              )}
            </div>
            <button
              onClick={() => setLocationExpanded(v => !v)}
              className="text-xs text-sky-600 hover:underline">
              {locationExpanded ? 'Luk' : 'Omasiign til anden lokation'}
            </button>
          </div>
          {locationExpanded && (
            <div className="mt-3 flex gap-2">
              <select className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
                value={reassignCamId} onChange={e => setReassignCamId(e.target.value)}>
                <option value="">Vælg kamera-lokation…</option>
                {allCameras
                  .filter(c => c.id !== cameraLocation.id)
                  .map(c => (
                    <option key={c.id} value={c.id}>
                      {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                    </option>
                  ))}
              </select>
              <button onClick={reassignToCamera} disabled={!reassignCamId || reassigning}
                className="px-3 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
                {reassigning ? '…' : 'Omasiign'}
              </button>
            </div>
          )}
          <p className="mt-2 text-xs text-gray-400">
            Billeder er knyttet til lokationen — overlever udskiftning af Edge-hardware.
          </p>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
          <p className="text-sm font-medium text-amber-800 mb-1">⚠️ Ikke tildelt en kamera-lokation</p>
          <p className="text-xs text-amber-600 mb-3">
            Vælg en eksisterende lokation eller tildel via site (nedenfor) for at knytte billeder til en stabil lokation.
          </p>
          <div className="flex gap-2">
            <select className="flex-1 border border-amber-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={reassignCamId} onChange={e => setReassignCamId(e.target.value)}>
              <option value="">Vælg kamera-lokation…</option>
              {allCameras.map(c => (
                <option key={c.id} value={c.id}>
                  {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                </option>
              ))}
            </select>
            <button onClick={reassignToCamera} disabled={!reassignCamId || reassigning}
              className="px-4 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 disabled:opacity-50">
              {reassigning ? 'Tildeler…' : 'Tildel'}
            </button>
          </div>
          {/* Fallback: site-baseret tildeling */}
          {(!device.site_name || !device.customer_name) && (
            <div className="mt-3 pt-3 border-t border-amber-200">
              <p className="text-xs text-amber-700 mb-2">Eller tildel direkte til site:</p>
              <div className="flex gap-2">
                <select className="flex-1 border border-amber-200 rounded-lg px-3 py-2 text-sm bg-white"
                  value={assignSiteId} onChange={e => setAssignSiteId(e.target.value)}>
                  <option value="">Vælg site…</option>
                  {sites.map(s => (
                    <option key={s.id} value={s.id}>{s.customer_name} — {s.name}</option>
                  ))}
                </select>
                <button onClick={assignToSite} disabled={!assignSiteId || assigning}
                  className="px-4 py-2 bg-amber-400 text-white text-sm rounded-lg hover:bg-amber-500 disabled:opacity-50">
                  {assigning ? 'Tildeler…' : 'Tildel site'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      {/* Status kort */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium mb-1 ${
            device.status === 'online' ? 'bg-emerald-50 text-emerald-600' :
            device.status === 'offline' ? 'bg-red-50 text-red-500' : 'bg-gray-100 text-gray-400'
          }`}>{device.status}</div>
          <p className="text-xs text-gray-400">Sidst set {lastSeen}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-sm font-mono text-gray-600 truncate">{device.device_id}</p>
          <p className="text-xs text-gray-400 mt-1">Device ID</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-sm text-gray-600">{device.camera_model || '–'}</p>
          <p className="text-xs text-gray-400 mt-1">Kameramodel</p>
        </div>
      </div>

      {/* Kamera identitet */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Kamera identitet</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Kamera navn</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="fx Kamera 1 — Nordøst"
              value={cameraName} onChange={e => setCameraName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Kamera index</label>
            <input type="number" min={0} max={7} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={cameraIndex} onChange={e => setCameraIndex(parseInt(e.target.value) || 0)} />
            <p className="text-xs text-gray-300 mt-1">0 = første kamera på enheden</p>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Relay GPIO (kamera)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={relayCamera} onChange={e => setRelayCamera(parseInt(e.target.value) || 356)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Relay GPIO (modem)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={relayModem} onChange={e => setRelayModem(parseInt(e.target.value) || 361)} />
          </div>
        </div>
      </div>

      {/* Kamera-niveau config overrides */}
      {sections.map(section => (
        <div key={section} className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">{section}</h2>
          <p className="text-xs text-gray-400 mb-4">
            Kamera-niveau override — overstyrer globale defaults, kunde og site indstillinger
          </p>
          <div className="space-y-4">
            {CAMERA_PARAMS.filter(p => p.section === section).map(param => {
              const val = getNestedValue(overrides, param.key)
              return (
                <div key={param.key}>
                  <div className="flex items-center gap-2 mb-1">
                    <label className="text-xs text-gray-500 font-medium">{param.label}</label>
                    {param.unit && <span className="text-xs text-gray-300">{param.unit}</span>}
                    {val && <span className="text-xs text-sky-500 font-medium">● Override aktiv</span>}
                  </div>
                  {param.type === 'select' ? (
                    <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                      value={val} onChange={e => setParam(param.key, e.target.value)}>
                      <option value="">— Arv fra overliggende lag —</option>
                      {param.options?.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input type={param.type} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                      placeholder={`${param.placeholder ?? ''} (tom = arv fra overliggende lag)`}
                      value={val} onChange={e => setParam(param.key, e.target.value)} />
                  )}
                  {param.description && (
                    <p className="text-xs text-gray-300 mt-0.5">{param.description}</p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* ── BT PAN TOTP QR-kode ──────────────────────────────────────────── */}
      {cameraLocation && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">BT PAN TOTP</h3>
              <p className="text-xs text-gray-400">QR-kode til lokal management adgang via Bluetooth</p>
            </div>
            <div className="flex gap-2">
              {!btTotp && (
                <button onClick={loadBtTotp} disabled={btTotpLoading}
                  className="px-3 py-1.5 text-xs bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
                  {btTotpLoading ? 'Henter…' : 'Vis QR-kode'}
                </button>
              )}
              {btTotp && (
                <button onClick={regenerateBtTotp} disabled={btTotpRegen}
                  className="px-3 py-1.5 text-xs bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50">
                  {btTotpRegen ? 'Genererer…' : 'Regenerér'}
                </button>
              )}
            </div>
          </div>
          {btTotp && (
            <div className="flex gap-4 items-start">
              <img src={btTotp.qr_code} alt="TOTP QR" className="w-36 h-36 rounded-lg border border-gray-100" />
              <div className="flex-1 text-xs space-y-2">
                {(() => {
                  const srcLabel: Record<string,string> = {
                    'factory-default': '🔑 Fabriksstandard',
                    'global':          '🌐 Global',
                    'kunde':           '🏢 Kunde',
                    'site':            '📍 Site',
                    'kamera':          '📷 Kamera',
                  }
                  const srcColor: Record<string,string> = {
                    'factory-default': 'bg-gray-50 text-gray-600 border-gray-200',
                    'global':          'bg-purple-50 text-purple-700 border-purple-200',
                    'kunde':           'bg-blue-50 text-blue-700 border-blue-200',
                    'site':            'bg-teal-50 text-teal-700 border-teal-200',
                    'kamera':          'bg-green-50 text-green-700 border-green-200',
                  }
                  const src = btTotp!.source
                  return (
                    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium border ${srcColor[src] ?? srcColor['factory-default']}`}>
                      {srcLabel[src] ?? src}
                    </div>
                  )
                })()}
                <p className="text-gray-500 mt-1">
                  Scan med Google Authenticator eller tilsvarende.
                  {btTotp!.source === 'factory-default' && ' Gælder alle enheder — ændres i config_defaults eller hierarki-overrides.'}
                  {btTotp!.source === 'kunde' && ' Gælder alle kameraer hos denne kunde.'}
                  {btTotp!.source === 'site' && ' Gælder alle kameraer på dette site.'}
                  {btTotp!.source === 'kamera' && ' Specifik for dette kamera.'}
                </p>
                <p className="text-gray-400 font-mono">SID: {btTotp.sid}</p>
                <p className="text-gray-300 text-xs break-all">Secret: {btTotp.secret}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Hurtige links */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <Link to={`/devices/${pathSegment(deviceId ?? '')}`}
          className="flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
          <Image className="w-5 h-5 text-gray-400" />
          <div>
            <p className="text-sm font-medium text-gray-700">Billeder og captures</p>
            <p className="text-xs text-gray-400">Se tidslinje og lightbox</p>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-300 ml-auto" />
        </Link>
        <Link to={`/devices/${pathSegment(deviceId ?? '')}/lab`}
          className="flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
          <Beaker className="w-5 h-5 text-purple-400" />
          <div>
            <p className="text-sm font-medium text-gray-700">LAB mode</p>
            <p className="text-xs text-gray-400">Live preview og parametre</p>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-300 ml-auto" />
        </Link>
      </div>

      {/* Gem og slet */}
      <div className="flex items-center justify-between">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>
        <button onClick={deleteDevice}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors ${
            confirmDelete ? 'bg-red-500 text-white border-red-500' : 'text-red-400 border-red-200 hover:bg-red-50'
          }`}>
          <Trash2 className="w-4 h-4" />
          {confirmDelete ? 'Bekræft sletning' : 'Slet kamera'}
        </button>
      </div>
      {confirmDelete && (
        <p className="text-xs text-red-400 mt-2 text-right">
          Klik igen for at bekræfte — dette kan ikke fortrydes!
        </p>
      )}
    </div>
  )
}
