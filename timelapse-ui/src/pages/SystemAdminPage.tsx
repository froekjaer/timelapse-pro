// ═══════════════════════════════════════════════════════════════
// SystemAdminPage.tsx
// Version: 1.1.0  |  12. april 2026
// ───────────────────────────────────────────────────────────────
// Changelog:
//   1.1.0  12-apr-2026  Relay test fix: cursor, puls rækkefølge, LAB status
//   1.0.0  12-apr-2026  Første version
// ═══════════════════════════════════════════════════════════════
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Terminal, Radio, Wifi, Camera, Save, CheckCircle,
         Power, PowerOff, RefreshCw, ChevronDown, ChevronRight, Database,
         Zap, Shield, HardDrive, Activity } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: { 'Content-Type': 'application/json' }, ...opts
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface Device {
  device_id: string; camera_name?: string; location_name?: string; status: string
  // R17 (2026-07-05): fleet-bred lab-mode-indikator, se /api/admin/devices
  debug_mode_enabled?: boolean
  debug_mode_enabled_at?: string | null
}
interface StorageRootStatus {
  id?: number
  logical_name?: string
  backend_type?: string
  access_mode?: string
  priority?: number
  active?: boolean
  expected_volume_uuid?: string | null
  actual_volume_uuid?: string | null
  uuid_matches?: boolean | null
  description?: string | null
  healthy?: boolean
  readable?: boolean
  label: string
  path: string
  configured: boolean
  required: boolean
  exists: boolean
  is_dir: boolean
  writable: boolean
  free_bytes?: number | null
  total_bytes?: number | null
  error?: string
}

interface SectionProps { title: string; icon: React.ReactNode; description: string; children: React.ReactNode; defaultOpen?: boolean }

function Section({ title, icon, description, children, defaultOpen = false }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 transition-colors text-left">
        <span className="text-gray-400">{icon}</span>
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-800">{title}</p>
          <p className="text-xs text-gray-400 mt-0.5">{description}</p>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-gray-300" /> : <ChevronRight className="w-4 h-4 text-gray-300" />}
      </button>
      {open && <div className="px-5 pb-5 pt-1 border-t border-gray-100">{children}</div>}
    </div>
  )
}

function Field({ label, description, unit, tooltip, children }: { label: string; description?: string; unit?: string; tooltip?: string; children: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2 mb-1">
        <label className="text-xs font-medium text-gray-600" title={tooltip}>{label}</label>
        {unit && <span className="text-xs text-gray-300">{unit}</span>}
      </div>
      {children}
      {description && <p className="text-xs text-gray-300 mt-1">{description}</p>}
    </div>
  )
}

function Num({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono"
    value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
}

function Txt({ value, onChange, placeholder, mono }: { value: string; onChange: (v: string) => void; placeholder?: string; mono?: boolean }) {
  return <input type="text" className={`w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm ${mono ? 'font-mono' : ''}`}
    value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
}

function Toggle({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer mt-1">
      <div onClick={() => onChange(!value)}
        className={`w-10 h-5 rounded-full transition-colors flex items-center px-0.5 ${value ? 'bg-sky-500' : 'bg-gray-200'}`}>
        <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${value ? 'translate-x-5' : ''}`} />
      </div>
      <span className="text-xs text-gray-500">{label ?? (value ? 'Aktivt' : 'Deaktiveret')}</span>
    </label>
  )
}

// Relay tester komponent
function RelayTester({ deviceId, labActive }: { deviceId: string; labActive: boolean }) {
  const [camOn, setCamOn] = useState(false)
  const [modOn, setModOn] = useState(false)
  const [busy, setBusy]   = useState(false)
  const [msg, setMsg]     = useState('')

  async function sendRelayCmd(relay: 'camera' | 'modem', state: boolean) {
    await api(`/api/lab/${pathSegment(deviceId)}/relay`, {
      method: 'POST',
      body: JSON.stringify({ relay, state })
    })
    // Vent på edge processer kommandoen (~2 sek)
    await new Promise(r => setTimeout(r, 2000))
  }

  async function toggleRelay(relay: 'camera' | 'modem', on: boolean) {
    setBusy(true)
    setMsg(`${relay === 'camera' ? 'Kamera' : 'Modem'} relay ${on ? 'tændes' : 'slukkes'}…`)
    try {
      await sendRelayCmd(relay, on)
      if (relay === 'camera') setCamOn(on)
      else setModOn(on)
      setMsg(`${relay === 'camera' ? 'Kamera' : 'Modem'} relay ${on ? 'TIL ✓' : 'FRA ✓'}`)
      setTimeout(() => setMsg(''), 2000)
    } catch {
      setMsg('Fejl — er LAB mode aktiv?')
    } finally {
      setBusy(false)
    }
  }

  async function pulse(relay: 'camera' | 'modem') {
    setBusy(true)
    try {
      // Tænd relay
      setMsg(`${relay === 'camera' ? 'Kamera' : 'Modem'} relay tændes…`)
      await sendRelayCmd(relay, true)
      if (relay === 'camera') setCamOn(true)
      else setModOn(true)
      // Hold tændt i 3 sek
      setMsg(`Relay TIL — venter 3 sek…`)
      await new Promise(r => setTimeout(r, 3000))
      // Sluk relay
      setMsg(`Relay slukkes…`)
      await sendRelayCmd(relay, false)
      if (relay === 'camera') setCamOn(false)
      else setModOn(false)
      setMsg('Puls komplet ✓')
      setTimeout(() => setMsg(''), 2000)
    } catch {
      setMsg('Fejl')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {msg && (
        <div className="px-3 py-2 bg-sky-50 border border-sky-100 rounded-lg text-xs text-sky-700 font-medium">{msg}</div>
      )}
      {!labActive && (
        <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
          ⚠️ LAB mode er ikke aktiv — aktiver LAB mode på enheden først
        </p>
      )}
      {labActive && (
        <p className="text-xs text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">
          ✅ LAB mode aktiv — relay kan styres
        </p>
      )}
      {/* Kamera relay */}
      <div className="bg-gray-50 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Camera className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Kamera relay</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${camOn ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-200 text-gray-400'}`}>
              {camOn ? 'TIL' : 'FRA'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button disabled={busy || camOn} onClick={() => toggleRelay('camera', true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <Power className="w-3.5 h-3.5" /> TIL
          </button>
          <button disabled={busy || !camOn} onClick={() => toggleRelay('camera', false)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <PowerOff className="w-3.5 h-3.5" /> FRA
          </button>
          <button disabled={busy} onClick={() => pulse('camera')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <Zap className="w-3.5 h-3.5" /> Puls 3s
          </button>
        </div>
      </div>
      {/* Modem relay */}
      <div className="bg-gray-50 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Wifi className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Modem relay</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${modOn ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-200 text-gray-400'}`}>
              {modOn ? 'TIL' : 'FRA'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button disabled={busy || modOn} onClick={() => toggleRelay('modem', true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <Power className="w-3.5 h-3.5" /> TIL
          </button>
          <button disabled={busy || !modOn} onClick={() => toggleRelay('modem', false)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <PowerOff className="w-3.5 h-3.5" /> FRA
          </button>
          <button disabled={busy} onClick={() => pulse('modem')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
            <Zap className="w-3.5 h-3.5" /> Puls 3s
          </button>
        </div>
      </div>
    </div>
  )
}

export function SystemAdminPage() {
  const [devices, setDevices]   = useState<Device[]>([])
  const [selectedDevice, setSelectedDevice] = useState('')
  const [settings, setSettings] = useState<Record<string,string>>({})
  const [installedModels, setInstalledModels] = useState<{name:string; size:number}[]>([])
  const [storageRoots, setStorageRoots] = useState<StorageRootStatus[]>([])
  const [savingStorage, setSavingStorage] = useState<number | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)
  const [savedSettings, setSavedSettings] = useState(false)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [, setCfg]              = useState<any>(null)
  const [labActive, setLabActive] = useState(false)
  const [serviceAccessEnabled, setServiceAccessEnabled] = useState(true)
  const [localLiveViewEnabled, setLocalLiveViewEnabled] = useState(true)
  const [liveViewMaxDurationS, setLiveViewMaxDurationS] = useState('180')
  const [continuousLiveViewAllowed, setContinuousLiveViewAllowed] = useState(false)
  const [interactiveShellEnabled, setInteractiveShellEnabled] = useState(false)
  const [savingServiceAccess, setSavingServiceAccess] = useState(false)
  const [serviceAccessSaved, setServiceAccessSaved] = useState(false)
  const [tunnelEnabled, setTunnelEnabled] = useState(false)
  const [tunnelPrimary, setTunnelPrimary] = useState('')
  const [tunnelRemotePort, setTunnelRemotePort] = useState('2201')
  const [tunnelLocalPort, setTunnelLocalPort] = useState('22')
  const [tunnelKeyFile, setTunnelKeyFile] = useState('')
  const [tunnelAutoOnApiLoss, setTunnelAutoOnApiLoss] = useState(true)
  const [tunnelAutoOnApiLossThresholdS, setTunnelAutoOnApiLossThresholdS] = useState('300')
  const [tunnelDeny, setTunnelDeny] = useState(false)
  const [tunnelSaved, setTunnelSaved] = useState(false)
  const [multiCameraMode, setMultiCameraMode] = useState('single')
  const [nodeCameras, setNodeCameras] = useState<{camera_index:number, relay_gpio_camera:number, camera_name:string, serial_number:string}[]>([])
  const [savingMultiCam, setSavingMultiCam] = useState(false)
  const [restarting, setRestarting] = useState(false)
  const [restartMsg, setRestartMsg] = useState('')

  // Config state
  const [relayGpioCamera, setRelayGpioCamera] = useState('356')
  const [relayGpioModem, setRelayGpioModem]   = useState('361')
  const [relaySimulate, setRelaySimulate]     = useState(false)
  const [cameraPowerMode, setCameraPowerMode] = useState('relay')
  const [relayOnBefore, setRelayOnBefore]     = useState('10')
  const [relayOffAfter, setRelayOffAfter]     = useState('5')
  const [captureTimeout, setCaptureTimeout]   = useState('60')
  const [downloadTimeout, setDownloadTimeout] = useState('30')
  const [modemGpio, setModemGpio]             = useState('361')
  const [modemCycleFailures, setModemCycleFailures] = useState('3')
  const [modemMinInterval, setModemMinInterval]     = useState('600')
  const [modemOffSeconds, setModemOffSeconds]       = useState('5')
  const [modemRecoverSeconds, setModemRecoverSeconds] = useState('15')
  const [uploadAttempts, setUploadAttempts]   = useState('5')
  const [configPollS, setConfigPollS]         = useState('300')
  const [heartbeatMin, setHeartbeatMin]       = useState('60')
  const [errorSleepS, setErrorSleepS]         = useState('30')
  const [minSleepS, setMinSleepS]             = useState('60')
  const [apiTimeoutS, setApiTimeoutS]         = useState('15')

  useEffect(() => {
    api('/api/admin/settings').then((s: any) => setSettings(s)).catch(() => {})
    api('/api/ai/settings').then((s: any) => setInstalledModels(s.installed_models || [])).catch(() => {})
    loadStorage()
  }, [])

  async function loadStorage() {
    const result = await api('/api/admin/storage/bindings').catch(() => null)
    setStorageRoots(result?.bindings ?? [])
  }

  async function bootstrapStorage() {
    setSavingStorage(0)
    try { await api('/api/admin/storage/bootstrap', { method: 'POST' }); await loadStorage() }
    finally { setSavingStorage(null) }
  }

  async function saveStorage(root: StorageRootStatus) {
    if (!root.id) return
    setSavingStorage(root.id)
    try {
      await api(`/api/admin/storage/bindings/${root.id}`, { method: 'PUT', body: JSON.stringify(root) })
      await loadStorage()
    } finally { setSavingStorage(null) }
  }

  async function saveSettings() {
    setSavingSettings(true)
    try {
      await api('/api/admin/settings', { method: 'PUT', body: JSON.stringify(settings) })
      await loadStorage()
      setSavedSettings(true)
      setTimeout(() => setSavedSettings(false), 2000)
    } catch { /* bevidst ignoreret — finally rydder UI-tilstanden uanset */ } finally { setSavingSettings(false) }
  }

  useEffect(() => {
    api('/api/admin/devices').then((d: any) => {
      const devs = d.devices ?? d
      setDevices(devs)
      if (devs.length > 0) setSelectedDevice(devs[0].device_id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedDevice) return
    api(`/api/admin/devices/${pathSegment(selectedDevice)}`).then((d: any) => {
      const dc = d.device_config ?? {}
      setLabActive(!!(dc.debug_mode?.enabled))
      const serviceAccess = dc.service_access ?? {}
      setServiceAccessEnabled(serviceAccess.enabled !== false)
      setLocalLiveViewEnabled(serviceAccess.live_view_enabled !== false)
      setLiveViewMaxDurationS(String(serviceAccess.live_view_max_duration_s ?? 180))
      setContinuousLiveViewAllowed(!!serviceAccess.allow_continuous_live_view)
      setInteractiveShellEnabled(!!serviceAccess.interactive_shell_enabled)
      setMultiCameraMode(dc.multi_camera_mode ?? 'single')
      const tun = dc.ssh_tunnel ?? {}
      setTunnelEnabled(!!tun.enabled)
      setTunnelPrimary(tun.primary ?? '')
      setTunnelRemotePort(String(tun.remote_port ?? '2201'))
      setTunnelLocalPort(String(tun.local_port ?? '22'))
      setTunnelKeyFile(tun.key_file ?? '')
      setTunnelAutoOnApiLoss(tun.auto_on_api_loss !== false)
      setTunnelAutoOnApiLossThresholdS(String(tun.auto_on_api_loss_threshold_s ?? '300'))
      setTunnelDeny(!!tun.deny)
      setNodeCameras(dc.node_cameras ?? [])
    }).catch(() => {})
    api(`/api/config/${pathSegment(selectedDevice)}`).then((c: any) => {
      setCfg(c)
      const cam  = c.camera  ?? {}
      const mod  = c.modem   ?? {}
      const diag = c.diagnostics ?? {}
      const sys  = c.system  ?? {}
      const sftp = c.sftp    ?? {}
      setRelayGpioCamera(String(cam.relay_gpio_pin ?? 356))
      setRelayGpioModem(String(mod.modem_relay_gpio_pin ?? 361))
      setRelaySimulate(!!cam.relay_simulate)
      setCameraPowerMode(String(cam.power_mode ?? 'relay'))
      setRelayOnBefore(String(cam.relay_on_seconds_before ?? 10))
      setRelayOffAfter(String(cam.relay_off_seconds_after ?? 5))
      setCaptureTimeout(String(cam.capture_timeout ?? 60))
      setDownloadTimeout(String(cam.download_timeout ?? 30))
      setModemGpio(String(mod.modem_relay_gpio_pin ?? 361))
      setModemCycleFailures(String(mod.modem_cycle_after_failures ?? 3))
      setModemMinInterval(String(mod.modem_min_cycle_interval_s ?? 600))
      setModemOffSeconds(String(mod.modem_power_cycle_off_s ?? 5))
      setModemRecoverSeconds(String(mod.modem_power_cycle_recover_s ?? 15))
      setUploadAttempts(String(sftp.upload_attempts ?? 5))
      setConfigPollS(String(diag.config_poll_interval_minutes ? diag.config_poll_interval_minutes * 60 : 300))
      setHeartbeatMin(String(diag.heartbeat_interval_minutes ?? 60))
      setErrorSleepS(String(sys.error_recovery_sleep_s ?? 30))
      setMinSleepS(String(sys.min_sleep_s ?? 60))
      setApiTimeoutS(String(sys.api_timeout_s ?? 15))
    }).catch(() => {})
  }, [selectedDevice])

  async function saveMultiCamera() {
    setSavingMultiCam(true)
    try {
      await api(`/api/node/${pathSegment(selectedDevice)}/multi-camera-config`, {
        method: 'PUT',
        body: JSON.stringify({
          multi_camera_mode: multiCameraMode,
          node_cameras: nodeCameras,
        })
      })
      // Auto-bootstrap sibling devices
      if (multiCameraMode === 'auto_bootstrap') {
        for (const cam of nodeCameras) {
          await api(`/api/node/${pathSegment(selectedDevice)}/bootstrap-camera`, {
            method: 'POST',
            body: JSON.stringify(cam)
          })
        }
      }
      alert('Multi-kamera config gemt og devices bootstrapped ✓')
    } catch {
      alert('Fejl ved gemning')
    } finally {
      setSavingMultiCam(false)
    }
  }

  async function saveServiceAccess() {
    if (!selectedDevice) return
    setSavingServiceAccess(true)
    try {
      await api(`/api/admin/devices/${pathSegment(selectedDevice)}/service-access`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: serviceAccessEnabled,
          live_view_enabled: localLiveViewEnabled,
          live_view_max_duration_s: parseInt(liveViewMaxDurationS),
          allow_continuous_live_view: continuousLiveViewAllowed,
          interactive_shell_enabled: interactiveShellEnabled,
        }),
      })
      if (!serviceAccessEnabled) setLabActive(false)
      setServiceAccessSaved(true)
      setTimeout(() => setServiceAccessSaved(false), 2500)
    } finally {
      setSavingServiceAccess(false)
    }
  }

  function addNodeCamera() {
    setNodeCameras(prev => [...prev, {
      camera_index: prev.length + 1,
      relay_gpio_camera: 357,
      camera_name: `Kamera ${prev.length + 2}`,
      serial_number: ''
    }])
  }

  function updateNodeCamera(idx: number, field: string, value: string | number) {
    setNodeCameras(prev => prev.map((c, i) => i === idx ? {...c, [field]: value} : c))
  }

  function removeNodeCamera(idx: number) {
    setNodeCameras(prev => prev.filter((_, i) => i !== idx))
  }

  const fmtBytes = (value?: number | null) => {
    if (!value || value < 0) return '—'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let n = value
    let u = 0
    while (n >= 1024 && u < units.length - 1) {
      n /= 1024
      u += 1
    }
    return `${n.toFixed(u < 2 ? 0 : 1)} ${units[u]}`
  }

  async function saveTunnel() {
    if (!selectedDevice) return
    const apiUrl = (await import('../api/client')).getApiUrl()
    const res = await fetch(`${apiUrl}/api/admin/devices/${pathSegment(selectedDevice)}`)
    const data = await res.json()
    const existing = data.device?.device_config ?? {}
    const cfg = typeof existing === 'string' ? JSON.parse(existing) : existing
    cfg.ssh_tunnel = {
      enabled: tunnelEnabled,
      primary: tunnelPrimary,
      remote_port: parseInt(tunnelRemotePort),
      local_port: parseInt(tunnelLocalPort),
      key_file: tunnelKeyFile,
      auto_on_api_loss: tunnelAutoOnApiLoss,
      auto_on_api_loss_threshold_s: parseInt(tunnelAutoOnApiLossThresholdS),
      deny: tunnelDeny,
    }
    await fetch(`${apiUrl}/api/admin/devices/${pathSegment(selectedDevice)}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssh_tunnel: cfg.ssh_tunnel }),
    })
    setTunnelSaved(true)
    setTimeout(() => setTunnelSaved(false), 2000)
  }

  async function save() {
    setSaving(true)
    try {
      await api(`/api/admin/devices/${pathSegment(selectedDevice)}/overrides`, {
        method: 'PUT',
        body: JSON.stringify({
          config_overrides: {
            camera: {
              power_mode:            cameraPowerMode,
              relay_gpio_pin:        parseInt(relayGpioCamera),
              relay_simulate:        relaySimulate,
              relay_on_seconds_before: parseInt(relayOnBefore),
              relay_off_seconds_after: parseInt(relayOffAfter),
              capture_timeout:       parseInt(captureTimeout),
              download_timeout:      parseInt(downloadTimeout),
            },
            modem: {
              modem_relay_gpio_pin:        parseInt(modemGpio),
              modem_cycle_after_failures:  parseInt(modemCycleFailures),
              modem_min_cycle_interval_s:  parseInt(modemMinInterval),
              modem_power_cycle_off_s:     parseInt(modemOffSeconds),
              modem_power_cycle_recover_s: parseInt(modemRecoverSeconds),
            },
            sftp: { upload_attempts: parseInt(uploadAttempts) },
            diagnostics: {
              heartbeat_interval_minutes:   parseInt(heartbeatMin),
              config_poll_interval_minutes: Math.round(parseInt(configPollS) / 60),
            },
            system: {
              error_recovery_sleep_s: parseInt(errorSleepS),
              min_sleep_s:            parseInt(minSleepS),
              api_timeout_s:          parseInt(apiTimeoutS),
            },
          }
        })
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch { /* bevidst ignoreret — finally rydder UI-tilstanden uanset */ } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/settings" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-orange-500" />
          <h1 className="text-xl font-semibold text-gray-900">System Administration</h1>
        </div>
      </div>

      {/* Enhedsvalg */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
        <label className="text-xs text-gray-400 block mb-1">Konfigurer enhed</label>
        <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)}>
          {devices.map(d => (
            <option key={d.device_id} value={d.device_id}>
              {d.camera_name || d.location_name || d.device_id} ({d.device_id})
              {d.debug_mode_enabled ? ' — \u{1F9EA} LAB AKTIV' : ''}
            </option>
          ))}
        </select>
        {devices.some(d => d.debug_mode_enabled) && (
          <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 mt-2">
            {'⚠️'} {devices.filter(d => d.debug_mode_enabled).length} enhed(er) har LAB mode aktiv lige nu
            (relæ konstant tændt, normal optagelse springes over). Slukkes automatisk efter et
            konfigureret antal timer hvis ikke stoppet manuelt.
          </p>
        )}
      </div>

      {/* Relay GPIO */}
      <Section title="Relay & GPIO" icon={<Radio className="w-4 h-4" />}
        description="Hardware GPIO pins til relæstyring og simuleringstilstand"
        defaultOpen={true}>
        <Field label="Kamera strømstyring"
          description="relay = GPIO styrer kameraforsyning; usb_powered = kameraet har konstant USB/batteri og går selv i standby"
          tooltip="Strømstyringsmode: Relay (GPIO slukker/tænder kameraet mellem captures, battery saving) eller USB (kameraet tændt altid, går i standby selv). Relay anbefales for kamera levetid. USB kræver konstant forbindelse.">
          <select className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            value={cameraPowerMode} onChange={e => setCameraPowerMode(e.target.value)}>
            <option value="relay">relay</option>
            <option value="usb_powered">usb_powered</option>
          </select>
        </Field>
        <Field label="Kamera relay GPIO pin" unit="sysfs"
          description="GPIO nummer i sysfs (fx 356 = physical pin 7 på Orange Pi 4 Pro)"
          tooltip="GPIO pin nummer i sysfs notation til kamera relay. Fx 356 = physical pin 7 på Orange Pi 4 Pro. Skal matche hardware wiring. Forkert pin kan forårsage ukontrolleret adfærd.">
          <Num value={relayGpioCamera} onChange={setRelayGpioCamera} placeholder="356" />
        </Field>
        <Field label="Modem relay GPIO pin" unit="sysfs"
          description="GPIO nummer til modem/4G relay (fx 361 = physical pin 11)"
          tooltip="GPIO pin nummer til modem/4G relay i sysfs notation. Fx 361 = physical pin 11 på Orange Pi. Bruges til power cycling af modem ved forbindelsesfejl. Forkert pin kan skade hardwaren.">
          <Num value={relayGpioModem} onChange={setRelayGpioModem} placeholder="361" />
        </Field>
        <Field label="Relay varmetid" unit="sekunder"
          description="Sekunder relay er tændt inden kamera-connect forsøges"
          tooltip="Sekunder kameraet skal være tændt før gphoto2 connect. Kameraet skal varme op og stabilisere fx/iso. For kort tid kan give ustabile billeder. Typisk 5-15 sekunder afhængig af kameramodel.">
          <Num value={relayOnBefore} onChange={setRelayOnBefore} placeholder="10" />
        </Field>
        <Field label="Relay nedkølingstid" unit="sekunder"
          description="Sekunder relay forbliver tændt efter capture er downloadet"
          tooltip="Sekunder relay forbliver tændt efter download for at sikker shutdown. Kameraet skal afslutte write operationer og lukke filesystem sikkert. For kort tid kan risikere SD card korruption. Typisk 3-10 sekunder.">
          <Num value={relayOffAfter} onChange={setRelayOffAfter} placeholder="5" />
        </Field>
        <Field label="Relay simulering"
          description="Aktivér for at køre uden fysisk relay (test/development)"
          tooltip="Simuler relay uden fysisk hardware til test/dev. Kameraet antages at være tændt altid. Ingen GPIO kontrol udføres. Kun til test på dev-maskiner uden relay hardware.">
          <Toggle value={relaySimulate} onChange={setRelaySimulate} />
        </Field>
      </Section>

      {/* Relay tester */}
      <Section title="Relay test" icon={<Zap className="w-4 h-4" />}
        description="Test og toggle relay udgange manuelt — kræver LAB mode">
        {selectedDevice && <RelayTester deviceId={selectedDevice} labActive={labActive} />}
      </Section>

      <Section title="Lokal serviceadgang" icon={<Shield className="w-4 h-4" />}
        description="Central sikkerhedsramme for LAB, debugging og serviceteknikerens Live View"
        defaultOpen={true}>
        <Field label="Lokal serviceadgang"
          description="Når den slås fra, deaktiveres LAB-mode og en aktiv lokal Live View stoppes ved næste policy-kontrol.">
          <Toggle value={serviceAccessEnabled} onChange={setServiceAccessEnabled}
            label={serviceAccessEnabled ? 'Tilladt' : 'Centralt deaktiveret'} />
        </Field>
        <Field label="Live View i lokal tekniker-UI">
          <Toggle value={localLiveViewEnabled} onChange={setLocalLiveViewEnabled}
            label={localLiveViewEnabled ? 'Tilladt' : 'Deaktiveret'} />
        </Field>
        <Field label="Maksimal Live View-varighed" unit="sekunder"
          description="Teknikeren kan lokalt vælge en kortere varighed. Gyldigt interval er 30 sekunder til 24 timer.">
          <Num value={liveViewMaxDurationS} onChange={setLiveViewMaxDurationS} placeholder="180" />
        </Field>
        <Field label="Kontinuerlig Live View"
          description="Kræver eksplicit tilladelse. Streamen fortsætter indtil lokal Stop eller centralt nødstop.">
          <Toggle value={continuousLiveViewAllowed} onChange={setContinuousLiveViewAllowed}
            label={continuousLiveViewAllowed ? 'Tilladt' : 'Ikke tilladt'} />
        </Field>
        <Field label="Interaktiv shell i lokal tekniker-UI"
          description="Giver en autentificeret servicetekniker en lokal bash-session. Brug kun under kontrolleret service og slå fra efter arbejdet.">
          <Toggle value={interactiveShellEnabled} onChange={setInteractiveShellEnabled}
            label={interactiveShellEnabled ? 'Tilladt' : 'Deaktiveret'} />
        </Field>
        <button onClick={saveServiceAccess} disabled={savingServiceAccess}
          className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg disabled:opacity-50">
          {savingServiceAccess ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {serviceAccessSaved ? 'Gemt' : 'Gem service-policy'}
        </button>
        {!serviceAccessEnabled && (
          <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            LAB og lokal Live View er centralt deaktiveret på denne Edge.
          </p>
        )}
      </Section>

      {/* Kamera timeouts */}
      <Section title="Kamera timeouts" icon={<Camera className="w-4 h-4" />}
        description="Timeout parametre for gphoto2 capture og download">
        <Field label="Capture timeout" unit="sekunder"
          description="Maksimal ventetid på at gphoto2 trigger og downloader billede"
          tooltip="Maksimal ventetid på gphoto2 capture kommando og download. Kameraet skal trigge, capture, og overføre billede. For lav værdi kan afbryde lange exposures. Typisk 30-120 sekunder. Højt ved dårlig USB/kabler.">
          <Num value={captureTimeout} onChange={setCaptureTimeout} placeholder="60" />
        </Field>
        <Field label="Download timeout" unit="sekunder"
          description="Maksimal ventetid på filoverførsel fra kamera til edge SSD"
          tooltip="Maksimal ventetid på filoverførsel fra kamera til edge SSD. Store RAW filer kan tage 10-30 sekunder via USB 2.0. For lav værdi kan give fejl på store captures. Typisk 30-60 sekunder for JPEG, 60-120 for RAW.">
          <Num value={downloadTimeout} onChange={setDownloadTimeout} placeholder="30" />
        </Field>
      </Section>

      {/* Modem */}
      <Section title="Modem & 4G" icon={<Wifi className="w-4 h-4" />}
        description="Automatisk power cycling af 4G modem ved forbindelsesfejl">
        <Field label="Power cycle efter N fejl"
          description="Antal på hinanden følgende upload-fejl inden modem power cycles"
          tooltip="Antal consecutive upload fejl før modem power cycles. Højt tal = tålmodig men langsom recovery. Lavt tal = hurtig recovery men risiko for unødvendige cycles. Typisk 3-5 afhængig af netværk stabilitet. For midlertidige netværks problemer.">
          <Num value={modemCycleFailures} onChange={setModemCycleFailures} placeholder="3" />
        </Field>
        <Field label="Minimum interval mellem cycles" unit="sekunder"
          description="Minimumstid mellem to modem power cycles (undgår rapid cycling)"
          tooltip="Minimum sekunder mellem modem power cycles for at undgå rapid cycling. Højt tal beskytter modem men forlænger downtime. Typisk 300-900 sekunder (5-15 min). Forhindrer evig loop ved vedvarende netværks problemer.">
          <Num value={modemMinInterval} onChange={setModemMinInterval} placeholder="600" />
        </Field>
        <Field label="Relay OFF tid ved cycle" unit="sekunder"
          description="Sekunder modem relay slukkes under power cycle"
          tooltip="Sekunder modem er slukket under power cycle for fuld reset. Modem skal helt lukke ned og tømme kapacitiv energi. For kort tid kan give ufuldstændig reset. Typisk 5-10 sekunder for 4G modems.">
          <Num value={modemOffSeconds} onChange={setModemOffSeconds} placeholder="5" />
        </Field>
        <Field label="Recovery ventetid efter cycle" unit="sekunder"
          description="Sekunder der ventes på modem boot efter relay er tændt igen"
          tooltip="Sekunder der ventes på modem boot og network registration efter relay er tændt. Modem skal boote, finde netværk, og autentificere. For kort tid kan give premature upload forsøg. Typisk 15-30 sekunder for 4G modems.">
          <Num value={modemRecoverSeconds} onChange={setModemRecoverSeconds} placeholder="15" />
        </Field>
      </Section>

      {/* Upload */}
      <Section title="SFTP upload" icon={<HardDrive className="w-4 h-4" />}
        description="Upload forsøg og retry logik">
        <Field label="Max upload forsøg"
          description="Antal gange upload forsøges inden capture markeres som fejlet"
          tooltip="Antal gange SFTP upload forsøges inden capture markeres som fejlet. Højt tal = bedre chance ved midlertidige netværks problemer men langsommere fejl detection. Typisk 3-10 forsøg. Hver retry har eksponentiel backoff.">
          <Num value={uploadAttempts} onChange={setUploadAttempts} placeholder="5" />
        </Field>
      </Section>

      {/* Polling & heartbeat */}
      <Section title="Polling & heartbeat" icon={<Activity className="w-4 h-4" />}
        description="Kommunikationsintervaller med headend">
        <Field label="Config poll interval" unit="sekunder"
          description="Sekunder mellem hentning af ny config fra headend"
          tooltip="Sekunder mellem config pull fra headend for at opdatere parametre. Lav værdi = hurtigere config udrulning men mere netværk traffic. Høj værdi = langsommere udrulning men mindre load. Typisk 180-600 sekunder (3-10 min). Ændringer træder ikke i kraft før næste poll.">
          <Num value={configPollS} onChange={setConfigPollS} placeholder="300" />
        </Field>
        <Field label="Heartbeat interval" unit="minutter"
          description="Minutter mellem diagnostik-uploads til headend"
          tooltip="Minutter mellem diagnostik heartbeat uploads til headend. Indeholder device health, storage status, og fejl logs. Lav værdi = bedre overvågning men mere bandwidth. Høj værdi = mindre bandwidth men langsommere alarm detection. Typisk 30-120 minutter.">
          <Num value={heartbeatMin} onChange={setHeartbeatMin} placeholder="60" />
        </Field>
      </Section>

      {/* System recovery */}
      <Section title="System recovery" icon={<Shield className="w-4 h-4" />}
        description="Timeouts og recovery parametre for edge agenten">
        <Field label="Fejl recovery pause" unit="sekunder"
          description="Sekunder der ventes i hoved-loop efter uventet fejl"
          tooltip="Sekunder der ventes efter uventet fejl før retry. Forhindrer rapid fejl loops der kan dræne batteri eller blokere system. Typisk 15-60 sekunder afhængig af fejl type. For lang pause kan forsinke recovery. For kort pause kan forårsage CPU overload ved vedvarende fejl.">
          <Num value={errorSleepS} onChange={setErrorSleepS} placeholder="30" />
        </Field>
        <Field label="Minimum sleep" unit="sekunder"
          description="Minimum ventetid når næste capture ikke kendes"
          tooltip="Minimum ventetid når næste capture schedule ikke kendes (fx offline mode). Kameraet slukkes mellem captures for battery saving. For kort pause kan dræne batteri unødvendigt. Typisk 30-120 sekunder. Kortere ved aktiv debug mode.">
          <Num value={minSleepS} onChange={setMinSleepS} placeholder="60" />
        </Field>
        <Field label="API timeout" unit="sekunder"
          description="Maksimal ventetid på svar fra headend API"
          tooltip="Maksimal ventetid på svar fra headend API før timeout. For lav værdi kan give fejlagtige timeouts ved langsomme netværk. Høj værdi kan forsinke fejl detection. Typisk 10-30 sekunder. Højt ved dårlige 4G forbindelser.">
          <Num value={apiTimeoutS} onChange={setApiTimeoutS} placeholder="15" />
        </Field>
      </Section>

      {/* Multi-kamera */}
      <Section title="Multi-kamera" icon={<Camera className="w-4 h-4" />}
        description="Konfigurer flere kameraer på denne edge node med burst capture">
        <div className="space-y-4">
          <Field label="Tilstand" description="Auto-bootstrap opretter automatisk sibling devices i headend">
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={multiCameraMode} onChange={e => setMultiCameraMode(e.target.value)}>
              <option value="single">Enkelt kamera (default)</option>
              <option value="auto_bootstrap">Auto-bootstrap fra node config</option>
              <option value="manual">Manuel (devices oprettet manuelt)</option>
            </select>
          </Field>

          {multiCameraMode !== 'single' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-gray-600">Ekstra kameraer på denne node</label>
                <button onClick={addNodeCamera}
                  className="text-xs text-sky-500 hover:text-sky-700 flex items-center gap-1 cursor-pointer">
                  + Tilføj kamera
                </button>
              </div>
              <div className="space-y-3">
                {nodeCameras.map((cam, idx) => (
                  <div key={idx} className="bg-gray-50 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-600">Kamera {cam.camera_index}</span>
                      <button onClick={() => removeNodeCamera(idx)}
                        className="text-xs text-red-400 hover:text-red-600 cursor-pointer">Fjern</button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-gray-400 block mb-1">Navn</label>
                        <input type="text" className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs"
                          value={cam.camera_name}
                          onChange={e => updateNodeCamera(idx, 'camera_name', e.target.value)} />
                      </div>
                      <div>
                        <label className="text-xs text-gray-400 block mb-1">Relay GPIO</label>
                        <input type="number" className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs font-mono"
                          value={cam.relay_gpio_camera}
                          onChange={e => updateNodeCamera(idx, 'relay_gpio_camera', parseInt(e.target.value))} />
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Serienummer (fra gphoto2)</label>
                      <input type="text" className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs font-mono"
                        placeholder="fx 37c165ee384b488f85fa1604415e71f8"
                        value={cam.serial_number}
                        onChange={e => updateNodeCamera(idx, 'serial_number', e.target.value)} />
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={saveMultiCamera} disabled={savingMultiCam}
                className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50 cursor-pointer">
                {savingMultiCam ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {savingMultiCam ? 'Gemmer og bootstrapper…' : 'Gem multi-kamera config'}
              </button>
            </div>
          )}
        </div>
      </Section>

      {/* Headend Settings */}
      <Section title="Headend indstillinger" icon={<Database className="w-4 h-4" />}
        description="SFTP, ffmpeg og system URLs — gemmes i databasen">
        <Field label="SFTP upload aktiv" description="Aktiverer sekundær upload til kundens/NAS'ens SFTP-indløbsmappe"
          tooltip="Aktiverer automatisk SFTP upload af captures til kunde/NAS indløbsmappe. Captures uploades efter headend modtagelse. Kræver gyldige SFTP credentials. Deaktiveres ved auth problemer for at undgå låste accounts.">
          <Toggle
            value={(settings.sftp_enabled ?? 'false').toLowerCase() === 'true'}
            onChange={v => setSettings(s => ({...s, sftp_enabled: v ? 'true' : 'false'}))}
          />
        </Field>
        <Field label="SFTP host" description="IP eller hostname på SFTP serveren"
          tooltip="IP adresse eller hostname på kundens SFTP server. Kan være local IP (NAS) eller public hostname. Port specificeres separat. Mål være reachable fra headend. DNS issues kan forsinke upload.">
          <Txt value={settings.sftp_host ?? ''} onChange={v => setSettings(s => ({...s, sftp_host: v}))} mono />
        </Field>
        <Field label="SFTP port" description="Port nummer (standard 22, TimeLapse Pro lab/prod 22222)"
          tooltip="SFTP port nummer. Standard er 22 for SFTP. TimeLapse Pro lab/prod bruger 22222 for sikkerhed. Skal matche server konfiguration. Forkert port giver connection timeout.">
          <Txt value={settings.sftp_port ?? ''} onChange={v => setSettings(s => ({...s, sftp_port: v}))} mono />
        </Field>
        <Field label="SFTP brugernavn"
          tooltip="SFTP brugernavn til authentication. Skal have write adgang til remote base mappe. Gemmes krypteret i databasen. Forkert credentials blokerer alle uploads.">
          <Txt value={settings.sftp_user ?? ''} onChange={v => setSettings(s => ({...s, sftp_user: v}))} mono />
        </Field>
        <Field label="SFTP password"
          tooltip="SFTP password til authentication. Gemmes krypteret i databasen. Brug key-based auth for bedre sikkerhed hvis muligt. Forkert password kan låse konto ved for mange login forsøg.">
          <input type="password" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono"
            value={settings.sftp_password ?? ''} onChange={e => setSettings(s => ({...s, sftp_password: e.target.value}))} />
        </Field>
        <Field label="SFTP remote base" description="Sti på serveren hvor billeder uploades til"
          tooltip="Sti på SFTP server hvor captures uploades til. Fx /timelapse/incoming/. Brugeren skal have write adgang til denne mappe. Sti oprettes hvis den ikke findes og brugeren har rettigheder.">
          <Txt value={settings.sftp_remote_base ?? ''} onChange={v => setSettings(s => ({...s, sftp_remote_base: v}))} mono />
        </Field>
        <Field label="Canonical image root" description="Headendens aktive root til visning, thumbnails, imports og LAB-preview"
          tooltip="Headendens aktive image root til læsning af captures. Bruges til UI visning, thumbnail generation, imports, og LAB preview. Skal være eksisterende mappe med læse adgang. Ændringer kræver genstart for at tage effekt.">
          <Txt value={settings.sftp_base ?? ''} onChange={v => setSettings(s => ({...s, sftp_base: v}))} mono />
        </Field>
        <Field label="Legacy/search image roots" description="Komma- eller linjeskiftseparerede gamle roots som stadig skal kunne læses"
          tooltip="Komma- eller linjeskiftseparerede gamle image roots der stadig skal være søgbare. Bruges til migration og backward compatibility. Data herfra er read-only. Tom = kun canonical root.">
          <Txt value={settings.sftp_legacy_roots ?? ''} onChange={v => setSettings(s => ({...s, sftp_legacy_roots: v}))} mono />
        </Field>
        <Field label="Backup NAS path" description="Off-host/NAS root til headend- og edge-backups"
          tooltip="Off-host/NAS sti til headend og edge backups. Backups gemmes her for disaster recovery. Skal have tilstrækkelig plads (typisk TB scale). Backup schedule configureres separat. NAS skal være reachable.">
          <Txt value={settings.backup_nas_path ?? ''} onChange={v => setSettings(s => ({...s, backup_nas_path: v}))} mono />
        </Field>
        <Field label="Edge image artifact dir" description="Mappe til byggede rootfs/disk images og manifester"
          tooltip="Mappe til byggede edge rootfs/disk images og deployment manifester. Bruges til OS image distribution. Skal have write adgang og plads til images (GB scale). Ændringer kræver genstart for at tage effekt.">
          <Txt value={settings.edge_image_artifact_dir ?? ''} onChange={v => setSettings(s => ({...s, edge_image_artifact_dir: v}))} mono />
        </Field>
        <Field label="FFmpeg sti" description="Fuld sti til ffmpeg binary"
          tooltip="Fuld sti til ffmpeg binary til video generation og billedkonvertering. Fx /usr/bin/ffmpeg eller /opt/homebrew/bin/ffmpeg. Skal være eksekverbar af headend process. Kræves til video export og post-processing.">
          <Txt value={settings.ffmpeg_path ?? ''} onChange={v => setSettings(s => ({...s, ffmpeg_path: v}))} mono />
        </Field>
        <Field label="Base URL" description="Headend URL som vises i edge config"
          tooltip="Headend base URL som vises i edge config og bruges til API kald. Edge enheder forbinder til denne URL. Skal være reachable fra onsite. Skift til public URL ved remote deployment.">
          <Txt value={settings.base_url ?? ''} onChange={v => setSettings(s => ({...s, base_url: v}))} mono />
        </Field>
        <Field label="Upload backlog pr. retry" description="Hvor mange ventende billedfiler Edge må uploade pr. retry-loop"
          tooltip="Maksimalt antal ventende billedfiler Edge må uploade pr. retry loop. Forhindrer oversvømmelse af server ved cache backlog. Højt tal = hurtigere backlog clearing men mere server load. Typisk 50-200 filer.">
          <Txt value={settings.upload_slot_max_pending_per_window ?? ''} onChange={v => setSettings(s => ({...s, upload_slot_max_pending_per_window: v}))} mono />
        </Field>
        <Field label="Upload slot enforcement" description="true begrænser uploads til tildelte tidsvinduer; false uploader når Edge er online"
          tooltip="Upload slot styring: true begrænser uploads til tildelte tidsvinduer (upload slot policy), false uploader når som helst Edge er online. Slot enforcement bruges til at styre bandwidth usage og omkostninger.">
          <Txt value={settings.upload_slot_enforced ?? ''} onChange={v => setSettings(s => ({...s, upload_slot_enforced: v}))} mono />
        </Field>
        <Field label="Ældste-først backlog-sweep (thumbnails + AI-tags)" description="Fanger importerede/gamle billeder der aldrig når det seneste-først-tjek"
          tooltip="Kører hvert 30. minut og genererer manglende thumbnails samt sender manglende AI-tags til analyse, ældste billede først — modsat de eksisterende automatikker, der kun ser på de seneste captures. Fanger importerede historiske billeder og billeder taget før AI-tagging fandtes. OBS: AI-analyse kan koste penge (cloud Gemini) eller belaste server (lokal Ollama) afhængig af jeres AI-strategi — slå kun til når I har taget stilling til omfanget af jeres historiske backlog. Default fra.">
          <Toggle
            value={(settings.legacy_backlog_sweep_enabled ?? 'false').toLowerCase() === 'true'}
            onChange={v => setSettings(s => ({...s, legacy_backlog_sweep_enabled: v ? 'true' : 'false'}))}
          />
        </Field>
        <Field label="WebAuthn RP ID" description="Domæne for passkeys/FIDO2, fx headendens hostname uden protokol"
          tooltip="Relying Party ID for WebAuthn/passkeys. Typisk headendens hostname uden protokol (fx timelapse.example.com). Skal matche browser origin for security. Forkert ID vil blokere passkey login.">
          <Txt value={settings.webauthn_rp_id ?? ''} onChange={v => setSettings(s => ({...s, webauthn_rp_id: v}))} mono />
        </Field>
        <Field label="WebAuthn origin" description="Eksakt browser-origin for passkeys, inkl. protokol og evt. port"
          tooltip="Eksakt browser origin for WebAuthn. Inkluderer protokol og evt. port (fx https://timelapse.example.com eller https://timelapse.example.com:8443). Skal matche rp_id for security. Forkert origin blokerer passkey login.">
          <Txt value={settings.webauthn_origin ?? ''} onChange={v => setSettings(s => ({...s, webauthn_origin: v}))} mono />
        </Field>
        <Field label="Open WebUI URL" description="Offentlig URL der åbnes fra TimeLapse Pro"
          tooltip="Offentlig URL til Open WebUI AI assistent. Åbnes i ny tab fra TimeLapse Pro. Skal være reachable fra browseren. Bruger samme authentication som TimeLapse Pro for SSO.">
          <Txt value={settings.openwebui_public_url ?? ''} onChange={v => setSettings(s => ({...s, openwebui_public_url: v}))} mono />
        </Field>
        <Field label="Open WebUI cookie domain" description="Tom = host-only cookie; udfyld kun ved delt domæne"
          tooltip="Cookie domain for Open WebUI SSO. Tom = host-only cookie (sikrest). Udfyld kun ved delt domæne (fx .example.com) for cross-subdomain SSO. Forkert domain kan blokere authentication.">
          <Txt value={settings.openwebui_cookie_domain ?? ''} onChange={v => setSettings(s => ({...s, openwebui_cookie_domain: v}))} mono />
        </Field>
        <Field label="Ollama URL" description="Lokal modelserver til billed- og tekst-AI"
          tooltip="URL til lokal Ollama modelserver til AI billedanalyse og tekst processing. Bruges til local AI mode uden cloud afhængighed. Skal være reachable fra headend. Hvis tom, cloud AI (Gemini) bruges i stedet.">
          <Txt value={settings.ollama_url ?? ''} onChange={v => setSettings(s => ({...s, ollama_url: v}))} mono />
        </Field>
        <Field label="Ollama vision model" description="Standard lokal vision-model"
          tooltip="Standard Ollama vision model til billedanalyse. Fx qwen2.5vl:7b eller llama3.2-vision:11b. Skal være pulled på Ollama server. Mindre modeller = hurtigere men mindre præcis. Større = bedre kvalitet men langsommere.">
          <select
            value={settings.ollama_vision_model ?? ''}
            onChange={e => setSettings(s => ({...s, ollama_vision_model: e.target.value}))}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 bg-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">{installedModels.length === 0 ? 'Ingen modeller fundet...' : '— Vælg model —'}</option>
            {installedModels.map(m => (
              <option key={m.name} value={m.name}>
                {m.name} ({(m.size / 1024 / 1024 / 1024).toFixed(1)} GB)
              </option>
            ))}
            {settings.ollama_vision_model && !installedModels.find(m => m.name === settings.ollama_vision_model) && (
              <option value={settings.ollama_vision_model}>{settings.ollama_vision_model} (ikke installeret)</option>
            )}
          </select>
        </Field>
        <Field label="Ollama tekstmodel" description="Standard lokal tekstmodel til SIEM/CMDB"
          tooltip="Standard Ollama tekstmodel til SIEM log analyse og CMDB queries. Fx llama3.2:latest. Skal være pulled på Ollama server. Mindre modeller = hurtigere men mindre smarte. Større = bedre reasoning men langsommere.">
          <select
            value={settings.ollama_text_model ?? ''}
            onChange={e => setSettings(s => ({...s, ollama_text_model: e.target.value}))}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 bg-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">{installedModels.length === 0 ? 'Ingen modeller fundet...' : '— Vælg model —'}</option>
            {installedModels.map(m => (
              <option key={m.name} value={m.name}>
                {m.name} ({(m.size / 1024 / 1024 / 1024).toFixed(1)} GB)
              </option>
            ))}
            {settings.ollama_text_model && !installedModels.find(m => m.name === settings.ollama_text_model) && (
              <option value={settings.ollama_text_model}>{settings.ollama_text_model} (ikke installeret)</option>
            )}
          </select>
        </Field>
        <Field label="Vision fallback-modeller" description="Midlertidig lav-memory visionmodel (kommasepareret)"
          tooltip="Vision-modeller der prøves hvis standardmodellen fejler eller ved lav memory-mode. Kommasepareret liste, fx qwen3-vl:8b,minicpm-v:8b. Vælges fra installede modeller — du kan også tilføje/fjerne manuelt.">
          <select
            value=""
            onChange={e => {
              if (!e.target.value) return
              const current = (settings.ollama_fallback_models ?? '').split(',').map(s => s.trim()).filter(Boolean)
              if (!current.includes(e.target.value)) {
                setSettings(s => ({...s, ollama_fallback_models: [...current, e.target.value].join(',')}))
              }
            }}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 bg-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">— Tilføj fallback model —</option>
            {installedModels
              .filter(m => !(settings.ollama_fallback_models ?? '').split(',').map(s => s.trim()).includes(m.name))
              .map(m => (
                <option key={m.name} value={m.name}>
                  {m.name} ({(m.size / 1024 / 1024 / 1024).toFixed(1)} GB)
                </option>
              ))}
          </select>
          {(settings.ollama_fallback_models ?? '').split(',').filter(Boolean).length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {(settings.ollama_fallback_models ?? '').split(',').map(s => s.trim()).filter(Boolean).map(name => (
                <span key={name} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-50 text-blue-700 text-xs font-mono">
                  {name}
                  <button
                    type="button"
                    onClick={() => setSettings(s => ({
                      ...s,
                      ollama_fallback_models: (s.ollama_fallback_models ?? '').split(',').map(x => x.trim()).filter(x => x && x !== name).join(',')
                    }))}
                    className="text-blue-400 hover:text-red-500"
                  >✕</button>
                </span>
              ))}
            </div>
          )}
        </Field>
        <Field label="Ollama vision timeout" unit="sekunder"
          tooltip="Maksimal ventetid på Ollama vision model inference. Store vision modeller kan tage 10-60 sekunder. For lav værdi kan give timeout og fejlet analyse. Høj værdi kan forsinke feedback til bruger. Typisk 30-120 sekunder.">
          <Txt value={settings.ollama_vision_timeout_s ?? ''} onChange={v => setSettings(s => ({...s, ollama_vision_timeout_s: v}))} mono />
        </Field>
        <div className="mt-5 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-gray-800">Logiske lagerplaceringer</p>
            <p className="text-xs text-gray-400">Skift disk eller NAS ved at rette stien her. Resten af systemet bruger det logiske navn.</p>
          </div>
          {storageRoots.length === 0 && <button onClick={bootstrapStorage} disabled={savingStorage !== null}
            className="px-3 py-2 rounded-lg bg-sky-500 text-white text-xs font-medium disabled:opacity-50">
            Opret fra nuværende opsætning
          </button>}
        </div>
        {storageRoots.length > 0 && (
          <div className="mt-3 rounded-lg border border-gray-200 overflow-hidden">
            {storageRoots.map(root => {
              const ok = !!root.healthy
              return (
                <div key={root.id} className="px-3 py-3 border-b border-gray-100 last:border-0">
                 <div className="flex items-start gap-3">
                  <span className={`mt-1 w-2 h-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold text-gray-700">{root.logical_name}</p>
                      <p className="text-xs text-gray-400">{fmtBytes(root.free_bytes)} fri</p>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-2 mt-2">
                      <input aria-label={`Sti for ${root.logical_name}`} value={root.path || ''}
                        onChange={e => setStorageRoots(rows => rows.map(item => item.id === root.id ? {...item, path: e.target.value} : item))}
                        className="min-w-0 flex-1 border border-gray-200 rounded-md px-2 py-1.5 text-xs font-mono" />
                      <button onClick={() => saveStorage(root)} disabled={savingStorage !== null}
                        className="px-3 py-1.5 rounded-md bg-gray-800 text-white text-xs disabled:opacity-50">
                        {savingStorage === root.id ? 'Kontrollerer…' : 'Gem og kontrollér'}
                      </button>
                    </div>
                    <p className="mt-1 text-xs text-gray-400">{root.backend_type?.toUpperCase()} · {root.access_mode === 'read_write' ? 'Læs og skriv' : 'Kun læsning'} · prioritet {root.priority}</p>
                    {root.expected_volume_uuid && <p className={`text-xs font-mono mt-1 ${root.uuid_matches === false ? 'text-red-600' : 'text-gray-400'}`}>
                      Disk-ID: {root.actual_volume_uuid || 'kan ikke aflæses'} {root.uuid_matches === false ? '· forkert disk' : ''}
                    </p>}
                    {!ok && <p className="text-xs text-amber-600 mt-1">{root.error || 'Placeringen mangler eller har ikke de nødvendige rettigheder'}</p>}
                  </div>
                 </div>
                </div>
              )
            })}
          </div>
        )}
        <div className="flex justify-end mt-3">
          <button onClick={saveSettings} disabled={savingSettings}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {savedSettings ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {savedSettings ? 'Gemt!' : savingSettings ? 'Gemmer…' : 'Gem indstillinger'}
          </button>
        </div>
      </Section>

      {/* Gemini Batch (Vertex AI / GCS) — kun relevant ved service-account auth */}
      <Section title="Gemini Batch — Vertex AI / Cloud Storage" icon={<Database className="w-4 h-4" />}
        description="Kun nødvendigt hvis I bruger Vertex AI (service account) til Gemini. AI Studio (API-nøgle) bruger Files API i stedet og kræver ikke dette.">
        <Field label="GCS bucket" description="Navn uden 'gs://', fx 'timelapse-ai-batch'. Bruges til at uploade billeder og hente resultater under batch-jobs."
          tooltip="Google Cloud Storage bucket navn til Gemini batch processing. Skal oprettes manuelt og have appropriate IAM permissions. Navn uden gs:// prefix (fx timelapse-ai-batch). Service account skal have Storage Object Admin.">
          <Txt value={settings.gemini_gcs_bucket ?? ''} onChange={v => setSettings(s => ({...s, gemini_gcs_bucket: v}))} mono />
        </Field>
        <Field label="Bucket-region" description="SKAL matche jeres Vertex AI-region (fx 'europe-west1') — ellers stoppes batch-jobs for at undgå databehandling uden for EU (GDPR)."
          tooltip="GCS bucket region SKAL matche Vertex AI region for at undgå data crossing region boundaries (GDPR). Fx europe-west1 for EU data. Forkert region kan stoppe batch-jobs for compliance. Service account og bucket skal være i samme region.">
          <Txt value={settings.gemini_gcs_bucket_region ?? ''} onChange={v => setSettings(s => ({...s, gemini_gcs_bucket_region: v}))} mono />
        </Field>
        <p className="text-xs text-amber-600 mt-1">
          ⚠ Bucket skal oprettes manuelt i Google Cloud Console/gcloud, og jeres Vertex AI service account skal have rollen "Storage Object Admin" på den.
        </p>
        <div className="flex justify-end mt-3">
          <button onClick={saveSettings} disabled={savingSettings}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {savedSettings ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {savedSettings ? 'Gemt!' : savingSettings ? 'Gemmer…' : 'Gem GCS-indstillinger'}
          </button>
        </div>
      </Section>

      {/* BT PAN TOTP — globalt lag (laveste prioritet, lige over fabriksstandard) */}
      <Section title="BT PAN TOTP — global rotation" icon={<Database className="w-4 h-4" />}
        description="Gælder ALLE enheder uden mere specifikt kunde/site/kamera-override. Brug ved kompromitteret secret.">
        <Field label="Global secret (Base32)" description="Tom = brug fabriksstandard JBSWY3DPEHPK3PXP"
          tooltip="Global BT PAN TOTP secret i Base32 format. Gælder alle enheder uden specifikke overrides. Tom bruger fabriksstandard (JBSWY3DPEHPK3PXP = HELLO WORLD). Bruges til technician authentication via QR codes. KUN roter ved kompromittering.">
          <Txt value={settings.bt_totp_secret ?? ''} onChange={v => setSettings(s => ({...s, bt_totp_secret: v}))} mono />
        </Field>
        <Field label="Global SID" description="Label vist på edge login-side og i CMDB"
          tooltip="Global System Identifier vist på edge login-side og i CMDB. Identificerer hvilket TOTP system der bruges. Fx 'TimeLapse PRO Production' eller 'Site A'. Hjælper teknikere med at vælge rigtige credentials ved onsite login.">
          <Txt value={settings.bt_totp_sid ?? ''} onChange={v => setSettings(s => ({...s, bt_totp_sid: v}))} mono />
        </Field>
        <p className="text-xs text-amber-600 mt-1">
          ⚠ Træder først i kraft når hver enhed eksplicit synkroniserer ("Opdater TOTP fra CMDB" i lokal mgmt-UI).
          Informér teknikere om nyt QR inden rotation.
        </p>
        <div className="flex justify-end mt-3">
          <button onClick={saveSettings} disabled={savingSettings}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 disabled:opacity-50">
            {savedSettings ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {savedSettings ? 'Gemt!' : savingSettings ? 'Gemmer…' : 'Gem global TOTP'}
          </button>
        </div>
      </Section>

      {/* Headend genstart */}
      <Section title="Headend genstart" icon={<Power className="w-4 h-4" />}
        description="Genstart headend-processen via launchd (tager ~5 sekunder)">
        <div className="flex items-center gap-4 pt-2">
          <button
            onClick={async () => {
              if (!confirm('Genstart headend nu? Forbindelsen afbrydes kortvarigt.')) return
              setRestarting(true); setRestartMsg('')
              try {
                await api('/admin/restart-headend', { method: 'POST' })
                setRestartMsg('Genstart igangsat — forbind igen om ~10 sekunder')
              } catch {
                setRestartMsg('Fejl — headend svarer ikke eller har allerede genstartet')
              } finally {
                setRestarting(false)
              }
            }}
            disabled={restarting}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${restarting ? 'animate-spin' : ''}`} />
            {restarting ? 'Genstarter…' : 'Genstart headend'}
          </button>
          {restartMsg && <p className="text-xs text-gray-500">{restartMsg}</p>}
        </div>
      </Section>

      {/* SSH Tunnel */}
      <Section title="SSH Tunnel" icon={<Terminal className="w-4 h-4" />}
        description="Reverse SSH tunnel til remote adgang — edge initierer forbindelsen">
        <Field label="Aktiver tunnel"
          description="Edge åbner tunnel til headend ved næste config-poll"
          tooltip="Aktiver reverse SSH tunnel fra edge til headend for remote adgang. Edge initierer forbindelsen (firewall friendly). Tunnel oprettes ved næste config poll. Kræver gyldig endpoint og nøglefil.">
          <Toggle value={tunnelEnabled} onChange={setTunnelEnabled} />
        </Field>
        <Field label="Primær endpoint"
          description="Bruger og host som edge forbinder til (user@host:port)"
          tooltip="SSH endpoint som edge forbinder til i formatet user@host:port. Edge authenticerer med key_file. Headend skal have tilsvarende public key i authorized_keys. Forkerte credentials giver connection timeout.">
          <Txt value={tunnelPrimary} onChange={setTunnelPrimary} mono placeholder="user@headend.example:22" />
        </Field>
        <Field label="Remote port"
          description="Port der åbnes på headend — unik pr. device"
          tooltip="Port på headend der åbnes for tunnel ind til edge SSH. Skal være unik pr. device for at undgå konflikter. Fx 2201, 2202, osv. Skal være åben i headend firewall. Forkert port kan forårsage port conflict.">
          <Num value={tunnelRemotePort} onChange={setTunnelRemotePort} placeholder="2201" />
        </Field>
        <Field label="Lokal port på Edge"
          description="Port på Edge som tunnelen videresender til"
          tooltip="SSH port på edge enhed som tunnelen videresender til. Typisk 22 for standard SSH. Skal matche SSH daemon config på edge. Forkert port kan give tunnel til non-existent service.">
          <Num value={tunnelLocalPort} onChange={setTunnelLocalPort} placeholder="22" />
        </Field>
        <Field label="Nøglefil (edge)"
          description="Sti til SSH privat nøgle på edge-enheden"
          tooltip="Sti til SSH privat nøgle på edge enhed til tunnel authentication. Fx /root/.ssh/tunnel_key. Nøglen skal være tilgængelig på edge og matching public key skal være på headend. Forkert sti kan forhindre tunnel oprettelse.">
          <Txt value={tunnelKeyFile} onChange={setTunnelKeyFile} mono placeholder="/path/to/tunnel_key" />
        </Field>
        <Field label="Auto-start ved API-tab"
          description="Start tunnel automatisk hvis headend API er utilgængeligt"
          tooltip="Start SSH tunnel automatisk hvis headend API er utilgængelig i N sekunder. Bruges til remote recovery ved netværks problemer. Aktiveret som fallback mekanisme. Kræver at enabled er true.">
          <Toggle value={tunnelAutoOnApiLoss} onChange={setTunnelAutoOnApiLoss} />
        </Field>
        <Field label="Auto-start tærskel" unit="sekunder"
          description="Hvor længe API skal være utilgængelig før tunnel startes"
          tooltip="Sekunder headend API skal være utilgængelig før tunnel auto-startes. For lav værdi kan give unødvendige tunnels ved midlertidige netværks glitches. Høj værdi kan forsinke recovery. Typisk 300-600 sekunder.">
          <Num value={tunnelAutoOnApiLossThresholdS} onChange={setTunnelAutoOnApiLossThresholdS} placeholder="300" />
        </Field>
        <Field label="Forbyd tunnel"
          description="Denne enhed må aldrig oprette SSH tunnel (tilsidesætter enabled)"
          tooltip="Forbyd SSH tunnel for denne enhed uanset enabled setting. Bruges til sites med sikkerhedspolitik der forbyder remote adgang. Tilsidesætter både enabled og auto_on_api_loss.">
          <Toggle value={tunnelDeny} onChange={setTunnelDeny} />
        </Field>
        <div className="flex justify-end mt-3">
          <button onClick={saveTunnel}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors ${
              tunnelSaved
                ? 'bg-emerald-500 text-white'
                : 'bg-sky-500 hover:bg-sky-600 text-white'
            }`}>
            {tunnelSaved ? '✓ Gemt!' : 'Gem tunnel config'}
          </button>
        </div>
      </Section>

      {/* Gem */}
      <div className="flex items-center justify-between mt-2">
        <p className="text-xs text-gray-400">Ændringer gemmes i kamera-laget (lag 4) og slår igennem ved næste config-pull</p>
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-orange-500 text-white text-sm rounded-lg hover:bg-orange-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>
      </div>
    </div>
  )
}
