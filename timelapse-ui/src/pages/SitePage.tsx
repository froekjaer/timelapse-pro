import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, MapPin, Building2, Camera, Save, Trash2, ChevronRight, CheckCircle } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

const AI_MODES = ['off', 'monitor', 'assist', 'autonomous', 'npu_first', 'lab']

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

interface Site {
  id: string
  customer_id: string
  customer_name: string
  name: string
  address?: string
  gps_lat?: number
  gps_lon?: number
  gps_alt?: number
  timezone: string
  config_overrides: Record<string, unknown>
  notes?: string
  devices: Device[]
}

interface Device {
  device_id: string
  camera_name?: string
  camera_index: number
  status: string
  last_seen?: string
}

interface CameraLocation {
  id: string
  camera_name?: string
  model?: string
  serial_number?: string
  current_device_id?: string | null
  assigned_at?: string | null
}

const TZ = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function triFrom(value: unknown) {
  return value === true ? 'true' : value === false ? 'false' : ''
}

function triTo(value: string) {
  return value === 'true' ? true : value === 'false' ? false : undefined
}

function buildQualityOverride(
  existingConfig: Record<string, unknown> | undefined,
  fields: {
    edgeAiEnabled: string
    edgeAiMode: string
    preferNpu: string
    runner: string
    modelPath: string
    vendorBinary: string
    adaptiveExposure: string
    evStep: string
    driftFocusEnabled: string
    driftFocusZ: string
    driftExposureEnabled: string
    driftExposureZ: string
    driftWbEnabled: string
    driftWbZ: string
  }
) {
  const quality = { ...((existingConfig?.quality as Record<string, any> | undefined) ?? {}) }
  const edgeAi = { ...((quality.edge_ai as Record<string, any> | undefined) ?? {}) }
  const adaptive = { ...((quality.adaptive_exposure as Record<string, any> | undefined) ?? {}) }
  const drift = { ...((quality.drift_detection as Record<string, any> | undefined) ?? {}) }
  const driftFocus = { ...((drift.focus as Record<string, any> | undefined) ?? {}) }
  const driftExposure = { ...((drift.exposure as Record<string, any> | undefined) ?? {}) }
  const driftWb = { ...((drift.white_balance as Record<string, any> | undefined) ?? {}) }

  for (const key of ['enabled', 'mode', 'prefer_npu', 'runner', 'model_path', 'vendor_binary']) delete edgeAi[key]
  for (const key of ['enabled', 'step_ev']) delete adaptive[key]
  for (const obj of [driftFocus, driftExposure, driftWb]) {
    delete obj.enabled
    delete obj.z_threshold
  }

  const enabled = triTo(fields.edgeAiEnabled)
  const preferNpu = triTo(fields.preferNpu)
  if (enabled !== undefined) edgeAi.enabled = enabled
  if (fields.edgeAiMode) edgeAi.mode = fields.edgeAiMode
  if (preferNpu !== undefined) edgeAi.prefer_npu = preferNpu
  if (fields.runner.trim()) edgeAi.runner = fields.runner.trim()
  if (fields.modelPath.trim()) edgeAi.model_path = fields.modelPath.trim()
  if (fields.vendorBinary.trim()) edgeAi.vendor_binary = fields.vendorBinary.trim()

  const adaptiveEnabled = triTo(fields.adaptiveExposure)
  if (adaptiveEnabled !== undefined) adaptive.enabled = adaptiveEnabled
  if (fields.evStep.trim()) adaptive.step_ev = Number(fields.evStep)

  const driftFocusEnabled = triTo(fields.driftFocusEnabled)
  if (driftFocusEnabled !== undefined) driftFocus.enabled = driftFocusEnabled
  if (fields.driftFocusZ.trim()) driftFocus.z_threshold = Number(fields.driftFocusZ)

  const driftExposureEnabled = triTo(fields.driftExposureEnabled)
  if (driftExposureEnabled !== undefined) driftExposure.enabled = driftExposureEnabled
  if (fields.driftExposureZ.trim()) driftExposure.z_threshold = Number(fields.driftExposureZ)

  const driftWbEnabled = triTo(fields.driftWbEnabled)
  if (driftWbEnabled !== undefined) driftWb.enabled = driftWbEnabled
  if (fields.driftWbZ.trim()) driftWb.z_threshold = Number(fields.driftWbZ)

  if (Object.keys(edgeAi).length) quality.edge_ai = edgeAi
  else delete quality.edge_ai
  if (Object.keys(adaptive).length) quality.adaptive_exposure = adaptive
  else delete quality.adaptive_exposure
  if (Object.keys(driftFocus).length) drift.focus = driftFocus
  else delete drift.focus
  if (Object.keys(driftExposure).length) drift.exposure = driftExposure
  else delete drift.exposure
  if (Object.keys(driftWb).length) drift.white_balance = driftWb
  else delete drift.white_balance
  if (Object.keys(drift).length) quality.drift_detection = drift
  else delete quality.drift_detection
  return quality
}

export function SitePage() {
  const { siteId } = useParams<{ siteId: string }>()
  const navigate = useNavigate()
  const [site, setSite] = useState<Site | null>(null)
  const [cameraLocations, setCameraLocations] = useState<CameraLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Editable fields
  const [name, setName] = useState('')
  const [sftpUser, setSftpUser] = useState('')
  const [sftpRemoteBase, setSftpRemoteBase] = useState('')
  const [sftpPassword, setSftpPassword] = useState('')
  const [sftpPort, setSftpPort] = useState('22222')
  const [address, setAddress] = useState('')
  const [gpsLat, setGpsLat] = useState('')
  const [gpsLon, setGpsLon] = useState('')
  const [gpsAlt, setGpsAlt] = useState('')
  const [timezone, setTimezone] = useState('Europe/Copenhagen')
  const [notes, setNotes] = useState('')
  const [btTotpSecret, setBtTotpSecret] = useState('')
  const [btTotpSid, setBtTotpSid]       = useState('')
  const [edgeAiEnabled, setEdgeAiEnabled] = useState('')
  const [edgeAiMode, setEdgeAiMode]       = useState('')
  const [preferNpu, setPreferNpu]         = useState('')
  const [edgeAiRunner, setEdgeAiRunner]   = useState('')
  const [edgeAiModel, setEdgeAiModel]     = useState('')
  const [edgeAiVendorBinary, setEdgeAiVendorBinary] = useState('')
  const [adaptiveExposure, setAdaptiveExposure] = useState('')
  const [evStep, setEvStep]               = useState('')
  const [driftFocusEnabled, setDriftFocusEnabled]       = useState('')
  const [driftFocusZ, setDriftFocusZ]                   = useState('')
  const [driftExposureEnabled, setDriftExposureEnabled] = useState('')
  const [driftExposureZ, setDriftExposureZ]             = useState('')
  const [driftWbEnabled, setDriftWbEnabled]             = useState('')
  const [driftWbZ, setDriftWbZ]                         = useState('')

  useEffect(() => {
    if (!siteId) return
    Promise.all([
      api(`/api/admin/sites/${siteId}`),
      api(`/api/admin/cameras?site_id=${encodeURIComponent(siteId)}`),
    ])
      .then(([d, cameras]) => {
        setSite(d)
        setCameraLocations(Array.isArray(cameras) ? cameras : [])
        setName(d.name ?? '')
        setAddress(d.address ?? '')
        setGpsLat(d.gps_lat ?? '')
        setGpsLon(d.gps_lon ?? '')
        setGpsAlt(d.gps_alt ?? '')
        setTimezone(d.timezone ?? 'Europe/Copenhagen')
        setNotes(d.notes ?? '')
        const sftp = d.config_overrides?.sftp ?? {}
        setSftpUser(sftp.username ?? '')
        setSftpPassword(sftp.password ?? '')
        setSftpPort(String(sftp.port ?? '22222'))
        setSftpRemoteBase(sftp.remote_base ?? '')
        const btTotp = d.config_overrides?.bt_totp ?? {}
        setBtTotpSecret(btTotp.secret ?? '')
        setBtTotpSid(btTotp.sid ?? '')
        const quality = d.config_overrides?.quality ?? {}
        const edgeAi = quality.edge_ai ?? {}
        const adaptive = quality.adaptive_exposure ?? {}
        setEdgeAiEnabled(triFrom(edgeAi.enabled))
        setEdgeAiMode(edgeAi.mode ?? '')
        setPreferNpu(triFrom(edgeAi.prefer_npu))
        setEdgeAiRunner(edgeAi.runner ?? '')
        setEdgeAiModel(edgeAi.model_path ?? '')
        setEdgeAiVendorBinary(edgeAi.vendor_binary ?? '')
        setAdaptiveExposure(triFrom(adaptive.enabled))
        setEvStep(adaptive.step_ev != null ? String(adaptive.step_ev) : '')
        const drift = quality.drift_detection ?? {}
        const driftFocus = drift.focus ?? {}
        const driftExposure = drift.exposure ?? {}
        const driftWb = drift.white_balance ?? {}
        setDriftFocusEnabled(triFrom(driftFocus.enabled))
        setDriftFocusZ(driftFocus.z_threshold != null ? String(driftFocus.z_threshold) : '')
        setDriftExposureEnabled(triFrom(driftExposure.enabled))
        setDriftExposureZ(driftExposure.z_threshold != null ? String(driftExposure.z_threshold) : '')
        setDriftWbEnabled(triFrom(driftWb.enabled))
        setDriftWbZ(driftWb.z_threshold != null ? String(driftWb.z_threshold) : '')
      })
      .catch(() => setError('Kunne ikke hente site'))
      .finally(() => setLoading(false))
  }, [siteId])

  async function save() {
    setSaving(true)
    try {
      const quality = buildQualityOverride(site?.config_overrides, {
        edgeAiEnabled,
        edgeAiMode,
        preferNpu,
        runner: edgeAiRunner,
        modelPath: edgeAiModel,
        vendorBinary: edgeAiVendorBinary,
        adaptiveExposure,
        evStep,
        driftFocusEnabled,
        driftFocusZ,
        driftExposureEnabled,
        driftExposureZ,
        driftWbEnabled,
        driftWbZ,
      })
      const config_overrides: Record<string, unknown> = {
        ...(site?.config_overrides ?? {}),
        sftp: {
          username: sftpUser,
          password: sftpPassword,
          port: parseInt(sftpPort),
          remote_base: sftpRemoteBase,
        },
        bt_totp: btTotpSecret ? { secret: btTotpSecret, sid: btTotpSid || 'site' } : {},
      }
      if (Object.keys(quality).length) config_overrides.quality = quality
      else delete config_overrides.quality
      await api(`/api/admin/sites/${siteId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name, address,
          gps_lat: gpsLat ? parseFloat(gpsLat) : null,
          gps_lon: gpsLon ? parseFloat(gpsLon) : null,
          gps_alt: gpsAlt ? parseFloat(gpsAlt) : null,
          timezone, notes,
          config_overrides
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

  async function deleteSite() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    setDeleting(true)
    try {
      await api(`/api/admin/sites/${siteId}`, { method: 'DELETE' })
      navigate('/')
    } catch (e: any) {
      setError(e.message === '400' ? 'Kan ikke slette — enheder eksisterer på dette site' : 'Sletning fejlede')
      setConfirmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>
  if (error && !site) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-500">{error}</div>
  if (!site) return null

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Building2 className="w-4 h-4" />
          <Link to="/" className="hover:text-gray-600">{site.customer_name}</Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <MapPin className="w-4 h-4" />
          <span className="text-gray-700 font-medium">{site.name}</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Site info */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Site oplysninger</h2>
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Site navn</label>
              <span className="text-xs text-gray-300 cursor-help" title="Navn på lokationen. Bruges til identifikation i rapporter og CMDB.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Adresse</label>
              <span className="text-xs text-gray-300 cursor-help" title="Fysisk adresse på lokationen. Bruges til navigering og dokumentation.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Vejnavn 1, 1234 By"
              value={address} onChange={e => setAddress(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Tidszone</label>
              <span className="text-xs text-gray-300 cursor-help" title="Tidszone for dette site. Sikrer at captures sker på korrekte lokale tider. Vigtig for tværl-okale sites.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={timezone} onChange={e => setTimezone(e.target.value)}>
              <option value="Europe/Copenhagen">Europe/Copenhagen (dansk tid)</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Berlin">Europe/Berlin</option>
              <option value="UTC">UTC</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Noter</label>
              <span className="text-xs text-gray-300 cursor-help" title="Interne noter om dette site. Kun synligt for admin-brugere.">ⓘ</span>
            </div>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2}
              placeholder="Interne noter om dette site..."
              value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
        </div>
      </div>

      {/* SFTP */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">SFTP adgang</h2>
        <p className="text-xs text-gray-400 mb-4">Credentials til edge-nodernes upload på dette site</p>
        <div className="space-y-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">SFTP brugernavn</label>
              <span className="text-xs text-gray-300 cursor-help" title="Brugernavn til SFTP server hvor edge-enheder uploader billeder. Unik pr. site.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="sftp_nvj17c"
              value={sftpUser} onChange={e => setSftpUser(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">SFTP password</label>
              <span className="text-xs text-gray-300 cursor-help" title="Password til SFTP auth. Gemmes sikkert og deles med edge-enheder.">ⓘ</span>
            </div>
            <input type="password" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={sftpPassword} onChange={e => setSftpPassword(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Remote base sti</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti på SFTP server hvor billeder gemmes. Typisk /Users/Shared/timelapse/incoming/.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="/Users/Shared/timelapse/incoming/sftp_nvj17c"
              value={sftpRemoteBase} onChange={e => setSftpRemoteBase(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Port</label>
              <span className="text-xs text-gray-300 cursor-help" title="SFTP server port. Standard 22222 for sikker SFTP. Skal matche server config.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="22222"
              value={sftpPort} onChange={e => setSftpPort(e.target.value)} />
          </div>
        </div>
      </div>

      {/* BT PAN TOTP — site-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">BT PAN TOTP — site-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Gælder alle kameraer på dette site (overstyrer kunde/global, overstyres af kamera-lag).
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Secret (Base32)</label>
              <span className="text-xs text-gray-300 cursor-help" title="TOTP secret til Bluetooth PAN auth. Base32 encoded. Tom = arv fra kunde/global. Overstyres af kamera.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Tom = ingen site-override"
              value={btTotpSecret} onChange={e => setBtTotpSecret(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">SID</label>
              <span className="text-xs text-gray-300 cursor-help" title="Unikt site ID til TOTP authentication. Identificerer siteet i TOTP systemet. Tom = brug site navn.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="site-label"
              value={btTotpSid} onChange={e => setBtTotpSid(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Edge AI — site-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Edge QA AI — site-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Blank betyder arv fra kunde/globalt niveau. Kamera kan stadig overstyre.
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Edge AI</label>
              <span className="text-xs text-gray-300 cursor-help" title="Aktiverer AI-baseret kvalitetsanalyse på edge. Sløring, mørk, lens obstruction. Anbefales altid.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiEnabled} onChange={e => setEdgeAiEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">AI mode</label>
              <span className="text-xs text-gray-300 cursor-help" title="AI adfærd: off, monitor (log kun), assist (advar), autonomous (rett), npu_first, lab. Assist anbefales.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiMode} onChange={e => setEdgeAiMode(e.target.value)}>
              <option value="">Arv</option>
              {AI_MODES.map(mode => <option key={mode} value={mode}>{mode}</option>)}
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Foretræk NPU</label>
              <span className="text-xs text-gray-300 cursor-help" title="Brug hardware accelerator (NPU) frem for CPU. Hurtigere og mindre strøm. Anbefales til NPU-hardware.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={preferNpu} onChange={e => setPreferNpu(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Ja</option>
              <option value="false">Nej</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Adaptiv EV</label>
              <span className="text-xs text-gray-300 cursor-help" title="Auto-juster EV baseret på brightness. Kompenserer for skygge, sol, overskyet. Anbefales ved variable lys.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={adaptiveExposure} onChange={e => setAdaptiveExposure(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
        </div>
        <div className="space-y-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">EV trin</label>
              <span className="text-xs text-gray-300 cursor-help" title="EV step per justering (0.1-3.0). Mindre = finere justering men flere cycles. Typisk 0.3-0.7.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={evStep} onChange={e => setEvStep(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">NPU runner</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til NPU runner script. Standard path er korrekt for default installation.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiRunner} onChange={e => setEdgeAiRunner(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">NPU modelsti</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til NPU model fil (.nb format). Tom = brug built-in model. Ændres kun ved custom models.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiModel} onChange={e => setEdgeAiModel(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">VIPLite wrapper</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til vendor NPU wrapper (VIPLite). Tom = brug built-in wrapper. Ændres kun ved custom driver.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiVendorBinary} onChange={e => setEdgeAiVendorBinary(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Drift-detektion — site-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Drift-detektion — site-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Alarmerer hvis fokus/eksponering/hvidbalance systematisk skifter over tid for et kamera. Blank betyder arv.
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Fokus-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis skarphed systematisk falder. Detekterer manuel fokus der glider (vibration, temperatur).">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftFocusEnabled} onChange={e => setDriftFocusEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Fokus-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.0-4.0). Lavere = mere følsom. Typisk 2.0-3.0.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftFocusZ} onChange={e => setDriftFocusZ(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Eksponerings-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis eksponering systematisk skifter. Detekterer støv, tåge, sæson ændringer.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftExposureEnabled} onChange={e => setDriftExposureEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Eksponerings-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.5-4.0). Højere end focus da lysstyrke varierer mere.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftExposureZ} onChange={e => setDriftExposureZ(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Hvidbalance-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis hvidbalance systematisk skifter. Kræver at edge-optimizer rapporterer hvidbalance-data.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftWbEnabled} onChange={e => setDriftWbEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Hvidbalance-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.0-3.0). Typisk 2.0-3.0.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftWbZ} onChange={e => setDriftWbZ(e.target.value)} />
          </div>
        </div>
      </div>

      {/* GPS */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">GPS og lokation</h2>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Breddegrad (lat)</label>
              <span className="text-xs text-gray-300 cursor-help" title="GPS breddegrad i decimal format. Positiv for nordlige halvkugle, negativ for sydlige. Eksempel: 55.676098.">ⓘ</span>
            </div>
            <input type="number" step="0.000001" placeholder="55.676098"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={gpsLat} onChange={e => setGpsLat(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Længdegrad (lon)</label>
              <span className="text-xs text-gray-300 cursor-help" title="GPS længdegrad i decimal format. Positiv for østlig, negativ for vestlig. Eksempel: 9.535400.">ⓘ</span>
            </div>
            <input type="number" step="0.000001" placeholder="9.535400"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={gpsLon} onChange={e => setGpsLon(e.target.value)} />
          </div>
        </div>
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-1">
            <label className="text-xs text-gray-400">Højde (meter over hav)</label>
            <span className="text-xs text-gray-300 cursor-help" title="GPS højde i meter over havets overflade. Positiv over hav, negativ under. Bruges til AI skala beregning.">ⓘ</span>
          </div>
          <input type="number" step="1" placeholder="0"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            value={gpsAlt} onChange={e => setGpsAlt(e.target.value)} />
        </div>
        {gpsLat && gpsLon && (
          <a href={`https://www.openstreetmap.org/?mlat=${gpsLat}&mlon=${gpsLon}&zoom=17`}
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-sky-500 hover:text-sky-700">
            🗺️ Vis på OpenStreetMap
          </a>
        )}
      </div>

      {/* Fysiske Edge-enheder og logiske kameralokationer er forskellige ting.
          En kameralokation skal derfor være synlig, også før en Edge er tildelt. */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-700">Kameraer og Edge-enheder</h2>
            <p className="text-xs text-gray-400 mt-0.5">Kameralokationer bevares, også når de endnu ikke har en Edge.</p>
          </div>
          <span className="text-xs text-gray-400">{cameraLocations.length} kamera{cameraLocations.length !== 1 ? 'er' : ''} · {site.devices.length} Edge</span>
        </div>
        {cameraLocations.length === 0 ? (
          <p className="text-sm text-gray-400 italic">Ingen kameralokationer registreret på dette site</p>
        ) : (
          <div className="space-y-2 mb-4">
            {cameraLocations.map(camera => {
              const assigned = Boolean(camera.current_device_id)
              return (
                <div key={camera.id} className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 rounded-lg">
                  <div className="w-8 h-8 rounded-lg bg-sky-50 flex items-center justify-center flex-shrink-0">
                    <Camera className="w-4 h-4 text-sky-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{camera.camera_name || 'Unavngivet kamera'}</p>
                    <p className="text-xs text-gray-400 font-mono truncate">{camera.id}</p>
                  </div>
                  <div className="text-right text-xs">
                    <span className={`inline-flex px-2 py-0.5 rounded-full font-medium ${
                      assigned ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
                    }`}>{assigned ? 'Edge tildelt' : 'Afventer Edge'}</span>
                    {assigned && <p className="font-mono text-gray-400 mt-1">{camera.current_device_id}</p>}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="border-t border-gray-100 pt-4">
          <p className="text-xs font-medium text-gray-500 mb-2">Fysiske Edge-enheder</p>
        {site.devices.length === 0 ? (
          <p className="text-sm text-gray-400 italic">Ingen Edge er tildelt endnu. Klargør en ny Edge i Backup → Generer Edge, og bind den derefter til den ønskede kameralokation.</p>
        ) : (
          <div className="space-y-2">
            {site.devices.map(d => {
              const lastSeen = d.last_seen
                ? new Date(d.last_seen + 'Z').toLocaleString('da-DK', { timeZone: TZ(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
                : null
              return (
                <Link key={d.device_id} to={`/devices/${pathSegment(d.device_id)}`}
                  className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors group">
                  <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                    <Camera className="w-4 h-4 text-slate-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">
                      {d.camera_name || `Kamera ${d.camera_index + 1}`}
                    </p>
                    <p className="text-xs text-gray-400 font-mono">{d.device_id}</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {lastSeen && <span className="text-gray-400 hidden sm:block">{lastSeen}</span>}
                    <span className={`px-2 py-0.5 rounded-full font-medium ${
                      d.status === 'online' ? 'bg-emerald-50 text-emerald-600' :
                      d.status === 'offline' ? 'bg-red-50 text-red-500' :
                      'bg-gray-100 text-gray-400'
                    }`}>{d.status}</span>
                    <ChevronRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-gray-400" />
                  </div>
                </Link>
              )
            })}
          </div>
        )}
        </div>
      </div>

      {/* Gem og slet */}
      <div className="flex items-center justify-between">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>

        <button onClick={deleteSite} disabled={deleting}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors ${
            confirmDelete
              ? 'bg-red-500 text-white border-red-500 hover:bg-red-600'
              : 'text-red-400 border-red-200 hover:bg-red-50'
          }`}>
          <Trash2 className="w-4 h-4" />
          {confirmDelete ? 'Bekræft sletning' : 'Slet site'}
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
