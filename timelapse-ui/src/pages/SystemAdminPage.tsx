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
import { ArrowLeft, Terminal, Cpu, Radio, Wifi, Camera, Save, CheckCircle,
         Power, PowerOff, RefreshCw, AlertTriangle, ChevronDown, ChevronRight, Database,
         Zap, Shield, Clock, HardDrive, Activity } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: { 'Content-Type': 'application/json' }, ...opts
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface Device { device_id: string; camera_name?: string; location_name?: string; status: string }

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

function Field({ label, description, unit, children }: { label: string; description?: string; unit?: string; children: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2 mb-1">
        <label className="text-xs font-medium text-gray-600">{label}</label>
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
  const [savingSettings, setSavingSettings] = useState(false)
  const [savedSettings, setSavedSettings] = useState(false)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [cfg, setCfg]           = useState<any>(null)
  const [labActive, setLabActive] = useState(false)
  const [tunnelEnabled, setTunnelEnabled] = useState(false)
  const [tunnelPrimary, setTunnelPrimary] = useState('peter@timelapse.froekjaer.dk:22')
  const [tunnelRemotePort, setTunnelRemotePort] = useState('2201')
  const [tunnelKeyFile, setTunnelKeyFile] = useState('/opt/timelapse/edge/ssh/tunnel_key')
  const [tunnelAutoOnApiLoss, setTunnelAutoOnApiLoss] = useState(true)
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
  }, [])

  async function saveSettings() {
    setSavingSettings(true)
    try {
      await api('/api/admin/settings', { method: 'PUT', body: JSON.stringify(settings) })
      setSavedSettings(true)
      setTimeout(() => setSavedSettings(false), 2000)
    } catch { } finally { setSavingSettings(false) }
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
      setMultiCameraMode(dc.multi_camera_mode ?? 'single')
      const tun = dc.ssh_tunnel ?? {}
      setTunnelEnabled(!!tun.enabled)
      setTunnelPrimary(tun.primary ?? 'peter@timelapse.froekjaer.dk:22')
      setTunnelRemotePort(String(tun.remote_port ?? '2201'))
      setTunnelKeyFile(tun.key_file ?? '/opt/timelapse/edge/ssh/tunnel_key')
      setTunnelAutoOnApiLoss(tun.auto_on_api_loss !== false)
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
      local_port: 22,
      key_file: tunnelKeyFile,
      auto_on_api_loss: tunnelAutoOnApiLoss,
      auto_on_api_loss_threshold_s: 300,
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
    } catch { } finally {
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
            </option>
          ))}
        </select>
      </div>

      {/* Relay GPIO */}
      <Section title="Relay & GPIO" icon={<Radio className="w-4 h-4" />}
        description="Hardware GPIO pins til relæstyring og simuleringstilstand"
        defaultOpen={true}>
        <Field label="Kamera strømstyring"
          description="relay = GPIO styrer kameraforsyning; usb_powered = kameraet har konstant USB/batteri og går selv i standby">
          <select className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            value={cameraPowerMode} onChange={e => setCameraPowerMode(e.target.value)}>
            <option value="relay">relay</option>
            <option value="usb_powered">usb_powered</option>
          </select>
        </Field>
        <Field label="Kamera relay GPIO pin" unit="sysfs"
          description="GPIO nummer i sysfs (fx 356 = physical pin 7 på Orange Pi 4 Pro)">
          <Num value={relayGpioCamera} onChange={setRelayGpioCamera} placeholder="356" />
        </Field>
        <Field label="Modem relay GPIO pin" unit="sysfs"
          description="GPIO nummer til modem/4G relay (fx 361 = physical pin 11)">
          <Num value={relayGpioModem} onChange={setRelayGpioModem} placeholder="361" />
        </Field>
        <Field label="Relay varmetid" unit="sekunder"
          description="Sekunder relay er tændt inden kamera-connect forsøges">
          <Num value={relayOnBefore} onChange={setRelayOnBefore} placeholder="10" />
        </Field>
        <Field label="Relay nedkølingstid" unit="sekunder"
          description="Sekunder relay forbliver tændt efter capture er downloadet">
          <Num value={relayOffAfter} onChange={setRelayOffAfter} placeholder="5" />
        </Field>
        <Field label="Relay simulering"
          description="Aktivér for at køre uden fysisk relay (test/development)">
          <Toggle value={relaySimulate} onChange={setRelaySimulate} />
        </Field>
      </Section>

      {/* Relay tester */}
      <Section title="Relay test" icon={<Zap className="w-4 h-4" />}
        description="Test og toggle relay udgange manuelt — kræver LAB mode">
        {selectedDevice && <RelayTester deviceId={selectedDevice} labActive={labActive} />}
      </Section>

      {/* Kamera timeouts */}
      <Section title="Kamera timeouts" icon={<Camera className="w-4 h-4" />}
        description="Timeout parametre for gphoto2 capture og download">
        <Field label="Capture timeout" unit="sekunder"
          description="Maksimal ventetid på at gphoto2 trigger og downloader billede">
          <Num value={captureTimeout} onChange={setCaptureTimeout} placeholder="60" />
        </Field>
        <Field label="Download timeout" unit="sekunder"
          description="Maksimal ventetid på filoverførsel fra kamera til edge SSD">
          <Num value={downloadTimeout} onChange={setDownloadTimeout} placeholder="30" />
        </Field>
      </Section>

      {/* Modem */}
      <Section title="Modem & 4G" icon={<Wifi className="w-4 h-4" />}
        description="Automatisk power cycling af 4G modem ved forbindelsesfejl">
        <Field label="Power cycle efter N fejl"
          description="Antal på hinanden følgende upload-fejl inden modem power cycles">
          <Num value={modemCycleFailures} onChange={setModemCycleFailures} placeholder="3" />
        </Field>
        <Field label="Minimum interval mellem cycles" unit="sekunder"
          description="Minimumstid mellem to modem power cycles (undgår rapid cycling)">
          <Num value={modemMinInterval} onChange={setModemMinInterval} placeholder="600" />
        </Field>
        <Field label="Relay OFF tid ved cycle" unit="sekunder"
          description="Sekunder modem relay slukkes under power cycle">
          <Num value={modemOffSeconds} onChange={setModemOffSeconds} placeholder="5" />
        </Field>
        <Field label="Recovery ventetid efter cycle" unit="sekunder"
          description="Sekunder der ventes på modem boot efter relay er tændt igen">
          <Num value={modemRecoverSeconds} onChange={setModemRecoverSeconds} placeholder="15" />
        </Field>
      </Section>

      {/* Upload */}
      <Section title="SFTP upload" icon={<HardDrive className="w-4 h-4" />}
        description="Upload forsøg og retry logik">
        <Field label="Max upload forsøg"
          description="Antal gange upload forsøges inden capture markeres som fejlet">
          <Num value={uploadAttempts} onChange={setUploadAttempts} placeholder="5" />
        </Field>
      </Section>

      {/* Polling & heartbeat */}
      <Section title="Polling & heartbeat" icon={<Activity className="w-4 h-4" />}
        description="Kommunikationsintervaller med headend">
        <Field label="Config poll interval" unit="sekunder"
          description="Sekunder mellem hentning af ny config fra headend">
          <Num value={configPollS} onChange={setConfigPollS} placeholder="300" />
        </Field>
        <Field label="Heartbeat interval" unit="minutter"
          description="Minutter mellem diagnostik-uploads til headend">
          <Num value={heartbeatMin} onChange={setHeartbeatMin} placeholder="60" />
        </Field>
      </Section>

      {/* System recovery */}
      <Section title="System recovery" icon={<Shield className="w-4 h-4" />}
        description="Timeouts og recovery parametre for edge agenten">
        <Field label="Fejl recovery pause" unit="sekunder"
          description="Sekunder der ventes i hoved-loop efter uventet fejl">
          <Num value={errorSleepS} onChange={setErrorSleepS} placeholder="30" />
        </Field>
        <Field label="Minimum sleep" unit="sekunder"
          description="Minimum ventetid når næste capture ikke kendes">
          <Num value={minSleepS} onChange={setMinSleepS} placeholder="60" />
        </Field>
        <Field label="API timeout" unit="sekunder"
          description="Maksimal ventetid på svar fra headend API">
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
        <Field label="SFTP host" description="IP eller hostname på SFTP serveren">
          <Txt value={settings.sftp_host ?? ''} onChange={v => setSettings(s => ({...s, sftp_host: v}))} mono />
        </Field>
        <Field label="SFTP port" description="Port nummer (standard 22, TimeLapse Pro lab/prod 22222)">
          <Txt value={settings.sftp_port ?? ''} onChange={v => setSettings(s => ({...s, sftp_port: v}))} mono />
        </Field>
        <Field label="SFTP brugernavn">
          <Txt value={settings.sftp_user ?? ''} onChange={v => setSettings(s => ({...s, sftp_user: v}))} mono />
        </Field>
        <Field label="SFTP password">
          <input type="password" className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono"
            value={settings.sftp_password ?? ''} onChange={e => setSettings(s => ({...s, sftp_password: e.target.value}))} />
        </Field>
        <Field label="SFTP remote base" description="Sti på serveren hvor billeder uploades til">
          <Txt value={settings.sftp_remote_base ?? ''} onChange={v => setSettings(s => ({...s, sftp_remote_base: v}))} mono />
        </Field>
        <Field label="FFmpeg sti" description="Fuld sti til ffmpeg binary">
          <Txt value={settings.ffmpeg_path ?? ''} onChange={v => setSettings(s => ({...s, ffmpeg_path: v}))} mono />
        </Field>
        <Field label="Base URL" description="Headend URL som vises i edge config">
          <Txt value={settings.base_url ?? ''} onChange={v => setSettings(s => ({...s, base_url: v}))} mono />
        </Field>
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
        <Field label="GCS bucket" description="Navn uden 'gs://', fx 'timelapse-ai-batch'. Bruges til at uploade billeder og hente resultater under batch-jobs.">
          <Txt value={settings.gemini_gcs_bucket ?? ''} onChange={v => setSettings(s => ({...s, gemini_gcs_bucket: v}))} mono />
        </Field>
        <Field label="Bucket-region" description="SKAL matche jeres Vertex AI-region (fx 'europe-west1') — ellers stoppes batch-jobs for at undgå databehandling uden for EU (GDPR).">
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
        <Field label="Global secret (Base32)" description="Tom = brug fabriksstandard JBSWY3DPEHPK3PXP">
          <Txt value={settings.bt_totp_secret ?? ''} onChange={v => setSettings(s => ({...s, bt_totp_secret: v}))} mono />
        </Field>
        <Field label="Global SID" description="Label vist på edge login-side og i CMDB">
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
          description="Edge åbner tunnel til headend ved næste config-poll">
          <Toggle value={tunnelEnabled} onChange={setTunnelEnabled} />
        </Field>
        <Field label="Primær endpoint"
          description="Bruger og host som edge forbinder til (user@host:port)">
          <Txt value={tunnelPrimary} onChange={setTunnelPrimary} mono placeholder="peter@timelapse.froekjaer.dk:22" />
        </Field>
        <Field label="Remote port"
          description="Port der åbnes på headend — unik pr. device">
          <Num value={tunnelRemotePort} onChange={setTunnelRemotePort} placeholder="2201" />
        </Field>
        <Field label="Nøglefil (edge)"
          description="Sti til SSH privat nøgle på edge-enheden">
          <Txt value={tunnelKeyFile} onChange={setTunnelKeyFile} mono placeholder="/opt/timelapse/edge/ssh/tunnel_key" />
        </Field>
        <Field label="Auto-start ved API-tab"
          description="Start tunnel automatisk hvis headend API er utilgængeligt i 5 min">
          <Toggle value={tunnelAutoOnApiLoss} onChange={setTunnelAutoOnApiLoss} />
        </Field>
        <Field label="Forbyd tunnel"
          description="Denne enhed må aldrig oprette SSH tunnel (tilsidesætter enabled)">
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
