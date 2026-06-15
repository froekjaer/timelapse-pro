import { type Dispatch, type SetStateAction, useEffect, useRef, useState } from 'react'
import {
  AlertCircle, CheckCircle, Clock, Database, Download, FileCheck,
  HardDrive, Package, RefreshCw, Server, ShieldCheck, Wifi, Wrench, XCircle
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  })
}

interface BackupStatus {
  running: boolean
  progress: string[]
  ready: boolean
  error: string | null
  filename: string | null
}

interface ResilienceAssessment {
  generated_at: string
  summary: {
    devices: number
    inventory_rows: number
    headend_backup_ready: boolean
    nas_ready: boolean
    active_bootstrap_tokens: number
    update_artifacts: number
    change_tickets: number
    counts: Record<string, number>
  }
  headend_dr: {
    latest_backup_file: string | null
    latest_backup_exists: boolean
    nas_path: string | null
    auto_interval: string | null
    warm_standby_status: string
  }
  edge_restore: Array<{
    device_id: string
    hardware_model: string | null
    firmware_version: string | null
    os_name: string | null
    kernel_version: string | null
    app_version: string | null
    package_manager: string | null
    has_os_packages: boolean
    has_venv_packages: boolean
    has_software_inventory: boolean
    inventory_reported_at: string | null
    device_exists: boolean
    backup_requested?: boolean
    backup_requested_at?: string | null
    backup_complete?: {
      filename?: string
      size_kb?: number
      path?: string
      sha256?: string
      transport?: string
      at?: string
    } | null
  }>
  iso_blueprint: {
    status: string
    call_home: string
    ready_to_accept_new_edge?: boolean
    active_bootstrap_tokens?: number
    latest_image?: {
      artifact_id: string
      version: string
      sha256: string
      signed_by: string | null
      signed_at: string | null
      created_at: string | null
      sbom_ref: string | null
    } | null
    hardening: string[]
    required_outputs: string[]
  }
  controls: Array<{
    status: 'pass' | 'warning' | 'fail' | string
    title: string
    evidence: string
    domains: string[]
    recommendation: string
  }>
}

type Tab = 'headend' | 'edge' | 'iso' | 'compliance'

interface EdgeProvisioningForm {
  device_id: string
  customer_id: string
  customer_name: string
  site_id: string
  site_name: string
  camera_id: string
  camera_name: string
  note: string
  expires_hours: number
  headend_url: string
}

interface LocOption { id: string; name: string }

/** Cascading dropdown: Kunde → Site → Kamera/Lokation med "Tilføj ny..." */
function LocationPicker({
  form,
  setForm,
}: {
  form: EdgeProvisioningForm
  setForm: Dispatch<SetStateAction<EdgeProvisioningForm>>
}) {
  const [customers, setCustomers] = useState<LocOption[]>([])
  const [sites, setSites]         = useState<LocOption[]>([])
  const [cameras, setCameras]     = useState<LocOption[]>([])
  const [loading, setLoading]     = useState(false)

  // Load customers on mount
  useEffect(() => {
    api('/admin/customers')
      .then(r => r.ok ? r.json() : [])
      .then((cs: any[]) => setCustomers(cs.map(c => ({ id: c.id, name: c.name }))))
      .catch(() => {})
  }, [])

  // Load sites when customer changes
  useEffect(() => {
    if (!form.customer_id || form.customer_id === '__new__') {
      setSites([]); setCameras([])
      return
    }
    api(`/admin/sites?customer_id=${encodeURIComponent(form.customer_id)}`)
      .then(r => r.ok ? r.json() : [])
      .then((ss: any[]) => {
        const filtered = ss.filter((s: any) => s.customer_id === form.customer_id)
        setSites(filtered.map((s: any) => ({ id: s.id, name: s.name })))
      })
      .catch(() => setSites([]))
    setCameras([])
    setForm(f => ({ ...f, site_id: '', site_name: '', camera_id: '', camera_name: '' }))
  }, [form.customer_id])

  // Load cameras when site changes
  useEffect(() => {
    if (!form.site_id || form.site_id === '__new__') {
      setCameras([]); return
    }
    api(`/admin/cameras?site_id=${encodeURIComponent(form.site_id)}`)
      .then(r => r.ok ? r.json() : [])
      .then((cs: any[]) => setCameras(cs.map((c: any) => ({ id: c.id, name: c.camera_name }))))
      .catch(() => setCameras([]))
    setForm(f => ({ ...f, camera_id: '', camera_name: '' }))
  }, [form.site_id])

  const selCls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-300"
  const inpCls = "w-full border border-sky-300 rounded-lg px-3 py-2 text-sm bg-sky-50 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-300"

  return (
    <div className="md:col-span-2 space-y-3">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Kamera lokation</p>
      {/* Kunde */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Kunde</label>
        <select className={selCls} value={form.customer_id}
          onChange={e => {
            const id = e.target.value
            const name = id === '__new__' ? '' : (customers.find(c => c.id === id)?.name ?? '')
            setForm(f => ({ ...f, customer_id: id, customer_name: name, site_id: '', site_name: '', camera_id: '', camera_name: '' }))
          }}>
          <option value="">— vælg eksisterende —</option>
          {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          <option value="__new__">+ Tilføj ny kunde…</option>
        </select>
        {form.customer_id === '__new__' && (
          <input className={`${inpCls} mt-2`} placeholder="Kundenavn" value={form.customer_name}
            onChange={e => setForm(f => ({ ...f, customer_name: e.target.value }))} />
        )}
      </div>
      {/* Site */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Site</label>
        <select className={selCls} value={form.site_id} disabled={!form.customer_id}
          onChange={e => {
            const id = e.target.value
            const name = id === '__new__' ? '' : (sites.find(s => s.id === id)?.name ?? '')
            setForm(f => ({ ...f, site_id: id, site_name: name, camera_id: '', camera_name: '' }))
          }}>
          <option value="">— vælg site —</option>
          {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          {form.customer_id && <option value="__new__">+ Tilføj nyt site…</option>}
        </select>
        {form.site_id === '__new__' && (
          <input className={`${inpCls} mt-2`} placeholder="Site-navn (f.eks. Kontor, Byggeplads NVJ17c)" value={form.site_name}
            onChange={e => setForm(f => ({ ...f, site_name: e.target.value }))} />
        )}
      </div>
      {/* Kamera / Lokation */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Kamera / lokation</label>
        <select className={selCls} value={form.camera_id} disabled={!form.site_id}
          onChange={e => {
            const id = e.target.value
            const name = id === '__new__' ? '' : (cameras.find(c => c.id === id)?.name ?? '')
            setForm(f => ({ ...f, camera_id: id, camera_name: name }))
          }}>
          <option value="">— vælg kamera/lokation —</option>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          {form.site_id && <option value="__new__">+ Tilføj ny lokation…</option>}
        </select>
        {form.camera_id === '__new__' && (
          <input className={`${inpCls} mt-2`} placeholder="Lokationsnavn (f.eks. Kamera 1, Facade Nord)" value={form.camera_name}
            onChange={e => setForm(f => ({ ...f, camera_name: e.target.value }))} />
        )}
        <p className="mt-1 text-xs text-gray-400">
          Kamera-lokationen er den fysiske position. Den overlever udskiftning af Edge-hardware.
        </p>
      </div>
    </div>
  )
}

interface EdgeProvisioningResult {
  status: string
  device_id: string
  headend_url: string
  token: string
  expires_at: string
  bootstrap_yaml: string
  next_steps: string[]
}

function fmt(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function statusStyle(status: string) {
  if (status === 'pass') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (status === 'fail') return 'bg-red-50 text-red-700 border-red-200'
  return 'bg-amber-50 text-amber-700 border-amber-200'
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'pass') return <CheckCircle className="w-4 h-4 text-emerald-500" />
  if (status === 'fail') return <XCircle className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

const tabs: { key: Tab; label: string; icon: any }[] = [
  { key: 'headend', label: 'Headend DR', icon: Server },
  { key: 'edge', label: 'Edge restore', icon: HardDrive },
  { key: 'iso', label: 'Edge ISO', icon: Wrench },
  { key: 'compliance', label: 'Compliance', icon: ShieldCheck },
]

export function BackupPage() {
  const [tab, setTab] = useState<Tab>('headend')
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [assessment, setAssessment] = useState<ResilienceAssessment | null>(null)
  const [nasPath, setNasPath] = useState('')
  const [autoInterval, setAutoInterval] = useState('manual')
  const [settingsSaved, setSettingsSaved] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [edgeBusy, setEdgeBusy] = useState<string | null>(null)
  const [provisioningBusy, setProvisioningBusy] = useState(false)
  const [provisioningResult, setProvisioningResult] = useState<EdgeProvisioningResult | null>(null)
  const [buildImageBusy, setBuildImageBusy] = useState(false)
  const [buildImageError, setBuildImageError] = useState<string | null>(null)
  const [diskBuildStatus, setDiskBuildStatus] = useState<{
    running: boolean; progress: string[]; error: string | null
    result: {
      artifact_id: string; filename: string; sha256: string; signed_by: string
      size_bytes: number; sbom_os_count: number; sbom_venv_count: number
      mode?: string; token_baked_in?: boolean
      flash_instructions?: { linux_mac: string; windows: string; note: string }
    } | null
    ready: boolean; target?: string; mode?: string
  } | null>(null)
  const diskBuildPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [diskBuildTarget, setDiskBuildTarget] = useState('orangepi4pro')
  const [diskBuildMode, setDiskBuildMode] = useState<'rootfs' | 'flashable'>('rootfs')
  const [diskBuildToken, setDiskBuildToken] = useState('')
  const [diskBuildWifiSsid, setDiskBuildWifiSsid] = useState('')
  const [diskBuildWifiPassword, setDiskBuildWifiPassword] = useState('')
  const [diskBuildWifiCountry, setDiskBuildWifiCountry] = useState('DK')
  const STATIC_TARGETS: Array<{ id: string; display_name: string; arch: string; flashable: boolean; install_script: boolean }> = [
    { id: 'orangepi4pro',    display_name: 'OrangePi 4 Pro',           arch: 'arm64', flashable: true,  install_script: false },
    { id: 'orangepi-pc-plus',display_name: 'OrangePi PC Plus',         arch: 'armhf', flashable: true,  install_script: false },
    { id: 'rpi4',            display_name: 'Raspberry Pi 4 Model B',   arch: 'arm64', flashable: true,  install_script: false },
    { id: 'rpi5',            display_name: 'Raspberry Pi 5',           arch: 'arm64', flashable: true,  install_script: false },
    { id: 'jetson-orin-nano',display_name: 'NVIDIA Jetson Orin Nano',  arch: 'arm64', flashable: false, install_script: true  },
  ]
  const [availableTargets, setAvailableTargets] = useState<Array<{
    id: string; display_name: string; arch: string; flashable: boolean; install_script: boolean
  }>>(STATIC_TARGETS)

  const fetchTargets = () => {
    api('/admin/edge-provisioning/targets')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.targets?.length) setAvailableTargets(d.targets) })
      .catch(() => {})
  }
  useEffect(() => { fetchTargets() }, [])
  const [provisioningForm, setProvisioningForm] = useState<EdgeProvisioningForm>({
    device_id: '',
    customer_id: '',
    customer_name: '',
    site_id: '',
    site_name: '',
    camera_id: '',
    camera_name: '',
    note: '',
    expires_hours: 48,
    headend_url: '',
  })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadAll()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  async function loadAll() {
    await Promise.all([loadSettings(), loadStatus(), loadAssessment()])
  }

  async function loadSettings() {
    const r = await api('/admin/backup/settings')
    if (!r.ok) return
    const d = await r.json()
    setNasPath(d.backup_nas_path ?? '')
    setAutoInterval(d.backup_auto_interval ?? 'manual')
  }

  async function loadStatus() {
    const r = await api('/admin/backup/status')
    if (r.ok) setStatus(await r.json())
  }

  async function loadAssessment() {
    const r = await api('/admin/resilience/assessment')
    if (r.ok) setAssessment(await r.json())
  }

  function startPolling() {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      await loadStatus()
      const r = await api('/admin/backup/status')
      if (r.ok) {
        const d = await r.json()
        setStatus(d)
        if (!d.running) {
          clearInterval(pollRef.current!)
          pollRef.current = null
          loadAssessment()
        }
      }
    }, 1500)
  }

  async function triggerBackup() {
    setTriggering(true)
    await api('/admin/backup/trigger', { method: 'POST' })
    setTriggering(false)
    startPolling()
    loadStatus()
  }

  async function saveSettings() {
    await api('/admin/backup/settings', {
      method: 'PUT',
      body: JSON.stringify({ backup_nas_path: nasPath, backup_auto_interval: autoInterval }),
    })
    setSettingsSaved(true)
    setTimeout(() => setSettingsSaved(false), 2000)
    loadAssessment()
  }

  function downloadBackup() {
    const a = document.createElement('a')
    a.href = `${getApiUrl()}/api/admin/backup/download`
    a.download = status?.filename ?? 'timelapse-backup.tar.gz'
    a.click()
  }

  async function triggerEdgeBackup(deviceId: string) {
    setEdgeBusy(deviceId)
    try {
      const r = await api(`/admin/backup/trigger-edge/${encodeURIComponent(deviceId)}`, { method: 'POST' })
      if (r.ok) await loadAssessment()
    } finally {
      setEdgeBusy(null)
    }
  }

  async function buildEdgeImage() {
    setBuildImageBusy(true)
    setBuildImageError(null)
    try {
      const r = await api('/admin/edge-provisioning/build-image', { method: 'POST' })
      if (!r.ok) throw new Error(await r.text())
      await loadAssessment()
    } catch (e: unknown) {
      setBuildImageError(e instanceof Error ? e.message : 'Fejl ved bygning af image manifest')
    } finally {
      setBuildImageBusy(false)
    }
  }

  function startDiskBuildPolling() {
    if (diskBuildPollRef.current) return
    diskBuildPollRef.current = setInterval(async () => {
      const r = await api('/admin/edge-provisioning/disk-image-status')
      if (!r.ok) return
      const d = await r.json()
      setDiskBuildStatus(d)
      if (!d.running) {
        clearInterval(diskBuildPollRef.current!)
        diskBuildPollRef.current = null
        if (d.ready) await loadAssessment()
      }
    }, 2000)
  }

  async function buildDiskImage() {
    setDiskBuildStatus({ running: true, progress: ['Starter build...'], error: null, result: null, ready: false, target: diskBuildTarget, mode: diskBuildMode })
    try {
      const r = await api('/admin/edge-provisioning/build-disk-image', {
        method: 'POST',
        body: JSON.stringify({
          target: diskBuildTarget,
          mode: diskBuildMode,
          bootstrap_token: diskBuildToken,
          wifi_ssid: diskBuildWifiSsid,
          wifi_password: diskBuildWifiPassword,
          wifi_country: diskBuildWifiCountry || 'DK',
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        setDiskBuildStatus(s => s ? { ...s, running: false, error: err?.detail ?? 'Fejl' } : s)
        return
      }
      startDiskBuildPolling()
    } catch (e: unknown) {
      setDiskBuildStatus(s => s ? { ...s, running: false, error: e instanceof Error ? e.message : 'Netværksfejl' } : s)
    }
  }

  async function prepareEdgeProvisioning() {
    setProvisioningBusy(true)
    setProvisioningResult(null)
    try {
      let customerId = provisioningForm.customer_id === '__new__' ? null : provisioningForm.customer_id
      let customerName = provisioningForm.customer_name.trim()
      let siteId = provisioningForm.site_id === '__new__' ? null : provisioningForm.site_id
      let siteName = provisioningForm.site_name.trim()
      const cameraId = provisioningForm.camera_id === '__new__' ? null : (provisioningForm.camera_id || null)
      const cameraName = provisioningForm.camera_name.trim() || undefined

      // Auto-opret kunde hvis ny
      if (!customerId && customerName) {
        const cr = await api('/admin/customers', {
          method: 'POST',
          body: JSON.stringify({ name: customerName }),
        })
        if (!cr.ok) throw new Error('Kunne ikke oprette kunde')
        const cd = await cr.json()
        customerId = cd.id
      }

      // Auto-opret site hvis nyt
      if (!siteId && siteName && customerId) {
        const sr = await api('/admin/sites', {
          method: 'POST',
          body: JSON.stringify({ name: siteName, customer_id: customerId }),
        })
        if (!sr.ok) throw new Error('Kunne ikke oprette site')
        const sd = await sr.json()
        siteId = sd.id
      }

      const r = await api('/admin/edge-provisioning/prepare', {
        method: 'POST',
        body: JSON.stringify({
          device_id:     provisioningForm.device_id.trim(),
          customer_id:   customerId || undefined,
          customer_name: customerName || undefined,
          site_id:       siteId || undefined,
          site_name:     siteName || undefined,
          camera_id:     cameraId || undefined,
          camera_name:   cameraName,
          note:          provisioningForm.note.trim() || undefined,
          expires_hours: provisioningForm.expires_hours,
          headend_url:   provisioningForm.headend_url.trim() || undefined,
        }),
      })
      if (!r.ok) throw new Error(await r.text())
      setProvisioningResult(await r.json())
      await loadAssessment()
    } finally {
      setProvisioningBusy(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Database className="w-6 h-6 text-sky-500" />
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-gray-900">Drift & Resilience</h1>
          <p className="text-sm text-gray-400 mt-0.5">Backup, restore, edge image provisioning og compliance readiness</p>
        </div>
        <button onClick={loadAll}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50">
          <RefreshCw className="w-3.5 h-3.5" />
          Opdater
        </button>
      </div>

      {assessment && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5">
          <Metric label="Enheder" value={assessment.summary.devices} />
          <Metric label="CMDB rows" value={assessment.summary.inventory_rows} />
          <Metric label="Pass" value={assessment.summary.counts.pass ?? 0} tone="green" />
          <Metric label="Warnings" value={assessment.summary.counts.warning ?? 0} tone="amber" />
          <Metric label="Fail" value={assessment.summary.counts.fail ?? 0} tone="red" />
          <Metric label="Changes" value={assessment.summary.change_tickets} />
        </div>
      )}

      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === key ? 'border-sky-500 text-sky-700' : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}>
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'headend' && (
        <HeadendDrTab
          status={status}
          assessment={assessment}
          nasPath={nasPath}
          autoInterval={autoInterval}
          settingsSaved={settingsSaved}
          triggering={triggering}
          setNasPath={setNasPath}
          setAutoInterval={setAutoInterval}
          saveSettings={saveSettings}
          triggerBackup={triggerBackup}
          downloadBackup={downloadBackup}
        />
      )}
      {tab === 'edge' && (
        <EdgeRestoreTab
          assessment={assessment}
          busyDevice={edgeBusy}
          triggerEdgeBackup={triggerEdgeBackup}
        />
      )}
      {tab === 'iso' && (
        <IsoTab
          assessment={assessment}
          form={provisioningForm}
          setForm={setProvisioningForm}
          result={provisioningResult}
          busy={provisioningBusy}
          prepareEdge={prepareEdgeProvisioning}
          buildImageBusy={buildImageBusy}
          buildImageError={buildImageError}
          buildImage={buildEdgeImage}
          diskBuildStatus={diskBuildStatus}
          buildDiskImage={buildDiskImage}
          diskBuildTarget={diskBuildTarget}
          setDiskBuildTarget={setDiskBuildTarget}
          diskBuildMode={diskBuildMode}
          setDiskBuildMode={setDiskBuildMode}
          diskBuildToken={diskBuildToken}
          setDiskBuildToken={setDiskBuildToken}
          diskBuildWifiSsid={diskBuildWifiSsid}
          setDiskBuildWifiSsid={setDiskBuildWifiSsid}
          diskBuildWifiPassword={diskBuildWifiPassword}
          setDiskBuildWifiPassword={setDiskBuildWifiPassword}
          diskBuildWifiCountry={diskBuildWifiCountry}
          setDiskBuildWifiCountry={setDiskBuildWifiCountry}
          availableTargets={availableTargets}
        />
      )}
      {tab === 'compliance' && <ComplianceTab assessment={assessment} />}
    </div>
  )
}

function Metric({ label, value, tone = 'gray' }: { label: string; value: string | number; tone?: 'gray' | 'green' | 'amber' | 'red' }) {
  const colors: Record<string, string> = {
    gray: 'text-gray-900',
    green: 'text-emerald-700',
    amber: 'text-amber-700',
    red: 'text-red-700',
  }
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-xl font-semibold mt-1 ${colors[tone]}`}>{value}</div>
    </div>
  )
}

function HeadendDrTab(props: {
  status: BackupStatus | null
  assessment: ResilienceAssessment | null
  nasPath: string
  autoInterval: string
  settingsSaved: boolean
  triggering: boolean
  setNasPath: (v: string) => void
  setAutoInterval: (v: string) => void
  saveSettings: () => void
  triggerBackup: () => void
  downloadBackup: () => void
}) {
  const isRunning = props.status?.running ?? false
  const isReady = props.status?.ready ?? false
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-1">Headend disaster recovery</h2>
        <p className="text-xs text-gray-400 mb-4">Database, config, service state og restore-evidens for Mac Mini headend.</p>
        <div className="flex gap-3 flex-wrap">
          <button onClick={props.triggerBackup} disabled={isRunning || props.triggering}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Server className="w-4 h-4" />}
            {isRunning ? 'Kører...' : 'Start headend backup'}
          </button>
          {isReady && (
            <button onClick={props.downloadBackup}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700">
              <Download className="w-4 h-4" />
              Download ({props.status?.filename})
            </button>
          )}
        </div>

        {props.status && props.status.progress.length > 0 && (
          <div className="mt-4 bg-gray-50 rounded-lg p-3 font-mono text-xs space-y-1 max-h-56 overflow-y-auto">
            {props.status.progress.map((line, i) => (
              <div key={i} className="flex items-start gap-2 text-gray-600">
                <Clock className="w-3.5 h-3.5 mt-0.5 opacity-50" />
                {line}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">Off-host target</h2>
        <label className="text-xs text-gray-400 block mb-1">NAS / backup path</label>
        <input value={props.nasPath} onChange={e => props.setNasPath(e.target.value)}
          placeholder="/Volumes/backup/timelapse"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono" />
        <label className="text-xs text-gray-400 block mt-4 mb-1">Automatisk backup</label>
        <select value={props.autoInterval} onChange={e => props.setAutoInterval(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="manual">Manuel</option>
          <option value="daily">Daglig</option>
          <option value="weekly">Ugentlig</option>
        </select>
        <button onClick={props.saveSettings}
          className="mt-4 flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm rounded-lg">
          {props.settingsSaved && <CheckCircle className="w-4 h-4" />}
          {props.settingsSaved ? 'Gemt' : 'Gem'}
        </button>
        <div className="mt-4 text-xs text-gray-400">
          Warm standby: {props.assessment?.headend_dr.warm_standby_status ?? 'ukendt'}
        </div>
      </section>
    </div>
  )
}

function EdgeRestoreTab({
  assessment,
  busyDevice,
  triggerEdgeBackup,
}: {
  assessment: ResilienceAssessment | null
  busyDevice: string | null
  triggerEdgeBackup: (deviceId: string) => void
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800">Edge backup og restore readiness</h2>
        <p className="text-xs text-gray-400 mt-0.5">Headend kan anmode Edge om restore-backup; Edge kalder hjem og uploader arkivet.</p>
      </div>
      <div className="divide-y divide-gray-100">
        {(assessment?.edge_restore ?? []).length === 0 && (
          <div className="px-5 py-10 text-sm text-gray-500">
            Ingen Edge-enheder med restore-data endnu. Klargør en ny Edge under <span className="font-medium text-gray-700">Edge ISO</span>,
            og vent på første bootstrap/inventory heartbeat før baseline-backup kan anmodes.
          </div>
        )}
        {(assessment?.edge_restore ?? []).map(edge => (
          <div key={edge.device_id} className="px-5 py-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-gray-900 font-mono">{edge.device_id}</div>
                <div className="text-xs text-gray-400 mt-1">
                  {[edge.hardware_model, edge.os_name, edge.app_version].filter(Boolean).join(' / ')}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap justify-end">
                {edge.backup_requested && (
                  <span className="text-xs px-2 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">
                    Backup anmodet
                  </span>
                )}
                {edge.backup_complete && (
                  <span className="text-xs px-2 py-0.5 rounded border bg-emerald-50 text-emerald-700 border-emerald-200">
                    Backup OK
                  </span>
                )}
                <span className={`text-xs px-2 py-0.5 rounded border ${edge.device_exists ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                  {edge.device_exists ? 'Device linked' : 'CMDB only'}
                </span>
                {edge.device_exists && (
                  <button onClick={() => triggerEdgeBackup(edge.device_id)} disabled={busyDevice === edge.device_id || edge.backup_requested}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white text-xs rounded-lg hover:bg-gray-800 disabled:opacity-50">
                    {busyDevice === edge.device_id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <HardDrive className="w-3.5 h-3.5" />}
                    {edge.backup_requested ? 'Afventer Edge' : 'Anmod Edge backup'}
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3 text-xs">
              <Evidence label="Firmware" ok={!!edge.firmware_version} value={edge.firmware_version || '-'} />
              <Evidence label="OS packages" ok={edge.has_os_packages} value={edge.package_manager || '-'} />
              <Evidence label="Venv" ok={edge.has_venv_packages} value={edge.has_venv_packages ? 'reported' : '-'} />
              <Evidence label="Software" ok={edge.has_software_inventory} value={edge.has_software_inventory ? 'reported' : '-'} />
              <Evidence label="Inventory" ok={!!edge.inventory_reported_at} value={fmt(edge.inventory_reported_at)} />
            </div>
            {(edge.backup_requested || edge.backup_complete) && (
              <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 p-3 text-xs text-gray-600">
                {edge.backup_requested && (
                  <div><span className="text-gray-400">Anmodet: </span>{fmt(edge.backup_requested_at ?? null)}</div>
                )}
                {edge.backup_complete && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
                    <div><span className="text-gray-400">Seneste backup: </span>{fmt(edge.backup_complete.at ?? null)}</div>
                    <div><span className="text-gray-400">Fil: </span>{edge.backup_complete.filename || '-'}</div>
                    <div><span className="text-gray-400">Størrelse: </span>{edge.backup_complete.size_kb ?? '-'} KB</div>
                    {edge.backup_complete.path && <div className="md:col-span-3 truncate"><span className="text-gray-400">Sti: </span>{edge.backup_complete.path}</div>}
                    {edge.backup_complete.sha256 && <div className="md:col-span-3 font-mono truncate"><span className="text-gray-400">SHA-256: </span>{edge.backup_complete.sha256}</div>}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function Evidence({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="border border-gray-100 rounded-lg p-3 bg-gray-50">
      <div className="flex items-center gap-1.5 text-gray-500">
        {ok ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> : <AlertCircle className="w-3.5 h-3.5 text-amber-500" />}
        {label}
      </div>
      <div className="text-gray-800 mt-1 truncate">{value}</div>
    </div>
  )
}

type DiskBuildStatus = {
  running: boolean
  progress: string[]
  error: string | null
  result: {
    artifact_id: string; filename: string; sha256: string; signed_by: string
    size_bytes: number; sbom_os_count: number; sbom_venv_count: number
    mode?: string; token_baked_in?: boolean
    flash_instructions?: { linux_mac: string; windows: string; note: string }
  } | null
  ready: boolean; target?: string; mode?: string
} | null

/** Slugify til gyldigt device_id format (kun a-z0-9 og bindestreg) */
function slugify(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')  // fjern accenter
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)
}

function randomSuffix(n = 4): string {
  return Math.random().toString(36).slice(2, 2 + n)
}

function suggestDeviceId(cameraName: string, siteName: string): string {
  const parts = [cameraName, siteName].filter(Boolean).map(slugify).filter(Boolean)
  const base = parts.length ? parts[0] : 'tl'
  return `${base}-${randomSuffix(4)}`
}

/** Device ID felt med auto-forslag og ↺ regenerér knap */
function DeviceIdPicker({
  value,
  onChange,
  cameraName,
  siteName,
}: {
  value: string
  onChange: (v: string) => void
  cameraName: string
  siteName: string
}) {
  const [isAuto, setIsAuto] = useState(true)

  // Generér ved mount
  useEffect(() => {
    if (!value) {
      onChange(suggestDeviceId(cameraName, siteName))
    }
  }, [])

  // Opdatér forslag når kamera/site ændres — kun hvis brugeren ikke har redigeret
  useEffect(() => {
    if (isAuto) {
      onChange(suggestDeviceId(cameraName, siteName))
    }
  }, [cameraName, siteName])

  function regenerate() {
    const id = suggestDeviceId(cameraName, siteName)
    onChange(id)
    setIsAuto(true)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-gray-500">Device ID</label>
        {isAuto && (
          <span className="text-xs text-sky-500 bg-sky-50 border border-sky-200 rounded px-1.5 py-0.5">auto</span>
        )}
      </div>
      <div className="flex gap-1.5">
        <input
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-300"
          value={value}
          placeholder="tl-kamera1-a3f2"
          onChange={e => {
            setIsAuto(false)
            onChange(e.target.value)
          }}
        />
        <button
          type="button"
          title="Generér nyt forslag"
          onClick={regenerate}
          className="px-2.5 py-2 border border-gray-200 rounded-lg text-gray-400 hover:text-sky-600 hover:border-sky-300 hover:bg-sky-50 transition-colors text-sm"
        >
          ↺
        </button>
      </div>
      <p className="mt-1 text-xs text-gray-400">
        Bruges til CMDB-kladde. Det endelige Device ID sættes automatisk fra MAC-adressen ved enrollment.
      </p>
    </div>
  )
}

/** Headend API URL dropdown — henter faktisk base_url fra settings */
function HeadendUrlPicker({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const [knownUrl, setKnownUrl] = useState<string>('')
  const [custom, setCustom]     = useState(false)

  useEffect(() => {
    api('/admin/settings')
      .then(r => r.ok ? r.json() : {})
      .then((s: Record<string, string>) => {
        const url = s['base_url'] ? s['base_url'].replace(/\/$/, '') + '/api' : ''
        setKnownUrl(url)
        // Sæt default til den kendte URL hvis ingen er valgt endnu
        if (!value && url) onChange(url)
      })
      .catch(() => {})
  }, [])

  const selCls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white font-mono focus:outline-none focus:ring-2 focus:ring-sky-300"
  const inpCls = "w-full border border-sky-300 rounded-lg px-3 py-2 text-sm bg-sky-50 font-mono placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-300"

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">Headend API URL</label>
      <select className={selCls} value={custom ? '__custom__' : (value || knownUrl || '')}
        onChange={e => {
          if (e.target.value === '__custom__') {
            setCustom(true)
            onChange('')
          } else {
            setCustom(false)
            onChange(e.target.value)
          }
        }}>
        {knownUrl && <option value={knownUrl}>{knownUrl}</option>}
        <option value="__custom__">Tilpasset URL…</option>
      </select>
      {custom && (
        <input className={`${inpCls} mt-2`}
          placeholder="https://headend.example.com/api"
          value={value}
          onChange={e => onChange(e.target.value)} />
      )}
    </div>
  )
}

function IsoTab({
  assessment,
  form,
  setForm,
  result,
  busy,
  prepareEdge,
  buildImageBusy,
  buildImageError,
  buildImage,
  diskBuildStatus,
  buildDiskImage,
  diskBuildTarget,
  setDiskBuildTarget,
  diskBuildMode,
  setDiskBuildMode,
  diskBuildToken,
  setDiskBuildToken,
  diskBuildWifiSsid,
  setDiskBuildWifiSsid,
  diskBuildWifiPassword,
  setDiskBuildWifiPassword,
  diskBuildWifiCountry,
  setDiskBuildWifiCountry,
  availableTargets,
}: {
  assessment: ResilienceAssessment | null
  form: EdgeProvisioningForm
  setForm: Dispatch<SetStateAction<EdgeProvisioningForm>>
  result: EdgeProvisioningResult | null
  busy: boolean
  prepareEdge: () => void
  buildImageBusy: boolean
  buildImageError: string | null
  buildImage: () => void
  diskBuildStatus: DiskBuildStatus
  buildDiskImage: () => void
  diskBuildTarget: string
  setDiskBuildTarget: (t: string) => void
  diskBuildMode: 'rootfs' | 'flashable'
  setDiskBuildMode: (m: 'rootfs' | 'flashable') => void
  diskBuildToken: string
  setDiskBuildToken: (t: string) => void
  diskBuildWifiSsid: string
  setDiskBuildWifiSsid: (v: string) => void
  diskBuildWifiPassword: string
  setDiskBuildWifiPassword: (v: string) => void
  diskBuildWifiCountry: string
  setDiskBuildWifiCountry: (v: string) => void
  availableTargets: Array<{ id: string; display_name: string; arch: string; flashable: boolean; install_script: boolean }>
}) {
  const blueprint = assessment?.iso_blueprint
  const canPrepare = form.device_id.trim().length >= 3 && !busy
  const edges = assessment?.edge_restore ?? []
  const latestImage = blueprint?.latest_image
  const hasImage = !!latestImage

  // WiFi B: post-process inject state (lokal til IsoTab)
  const [wifiInjectOpen, setWifiInjectOpen] = useState(false)
  const [wifiInjectArtifactId, setWifiInjectArtifactId] = useState('')
  const [wifiInjectSsid, setWifiInjectSsid] = useState('')
  const [wifiInjectPassword, setWifiInjectPassword] = useState('')
  const [wifiInjectCountry, setWifiInjectCountry] = useState('DK')
  const [wifiInjectRunning, setWifiInjectRunning] = useState(false)
  const [wifiInjectResult, setWifiInjectResult] = useState<{artifact_id:string;filename:string;sha256:string;size_bytes:number;wifi_ssid:string} | null>(null)
  const [wifiInjectError, setWifiInjectError] = useState<string | null>(null)
  const wifiInjectPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function startWifiInjectPoll() {
    if (wifiInjectPollRef.current) return
    wifiInjectPollRef.current = setInterval(async () => {
      const r = await api('/admin/edge-provisioning/wifi-inject-status')
      const s = await r.json()
      if (s.progress) setWifiInjectRunning(s.running)
      if (!s.running) {
        clearInterval(wifiInjectPollRef.current!)
        wifiInjectPollRef.current = null
        if (s.error) setWifiInjectError(s.error)
        if (s.result) setWifiInjectResult(s.result)
      }
    }, 2000)
  }

  async function submitWifiInject() {
    if (!wifiInjectArtifactId || !wifiInjectSsid || !wifiInjectPassword) return
    setWifiInjectRunning(true)
    setWifiInjectError(null)
    setWifiInjectResult(null)
    try {
      const r = await api('/admin/edge-provisioning/inject-wifi', {
        method: 'POST',
        body: JSON.stringify({
          artifact_id: wifiInjectArtifactId,
          wifi_ssid: wifiInjectSsid,
          wifi_password: wifiInjectPassword,
          wifi_country: wifiInjectCountry || 'DK',
          wifi_method: 'auto',
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        setWifiInjectError(err?.detail ?? 'Fejl')
        setWifiInjectRunning(false)
        return
      }
      startWifiInjectPoll()
    } catch (e) {
      setWifiInjectError(e instanceof Error ? e.message : 'Netværksfejl')
      setWifiInjectRunning(false)
    }
  }

  const pipelineSteps: { label: string; done: boolean; note: string }[] = [
    {
      label: 'Bootstrap provisioning',
      done: true,
      note: 'API /admin/edge-provisioning/prepare og call-home /api/bootstrap',
    },
    {
      label: 'Aktive bootstrap tokens',
      done: (blueprint?.active_bootstrap_tokens ?? 0) > 0,
      note: `${blueprint?.active_bootstrap_tokens ?? 0} aktive token(s)`,
    },
    {
      label: 'Signed update artifact catalog',
      done: (assessment?.summary.update_artifacts ?? 0) > 0,
      note: `${assessment?.summary.update_artifacts ?? 0} artifact(s) registreret`,
    },
    {
      label: 'Signed Edge image manifest og SBOM',
      done: hasImage,
      note: hasImage
        ? `${latestImage!.artifact_id} · ${latestImage!.signed_by ?? 'system-hash'} · ${fmt(latestImage!.signed_at)}`
        : 'GPG-signeret manifest med SBOM – ikke genereret endnu',
    },
    {
      label: 'Fysisk arm64 disk image (rootfs)',
      done: diskBuildStatus?.ready ?? false,
      note: diskBuildStatus?.ready && diskBuildStatus.result
        ? `${diskBuildStatus.result.filename} · ${(diskBuildStatus.result.size_bytes / 1024 / 1024).toFixed(0)} MB · ${diskBuildStatus.result.sbom_os_count} OS-pakker`
        : diskBuildStatus?.running
          ? 'Bygger via Docker buildx arm64…'
          : 'ARM64 rootfs tarball (Docker buildx) — ikke bygget endnu',
    },
  ]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Provisioning form */}
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-800 mb-1">Klargør ny Edge</h2>
          <p className="text-xs text-gray-400 mb-4">Opret CMDB-kladde og engangs-bootstrap, så en ny Edge kan kalde hjem til Headend.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <DeviceIdPicker
              value={form.device_id}
              onChange={v => setForm(s => ({ ...s, device_id: v }))}
              cameraName={form.camera_name}
              siteName={form.site_name}
            />
            <Field label="Token levetid timer" value={String(form.expires_hours)} onChange={v => setForm(s => ({ ...s, expires_hours: Number(v) || 48 }))} type="number" />
            <LocationPicker form={form} setForm={setForm} />
            <HeadendUrlPicker value={form.headend_url} onChange={v => setForm(s => ({ ...s, headend_url: v }))} />
            <div className="md:col-span-2">
              <Field label="Note" value={form.note} onChange={v => setForm(s => ({ ...s, note: v }))} placeholder="Installationsnote" />
            </div>
          </div>
          <button onClick={prepareEdge} disabled={!canPrepare}
            className="mt-4 flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-50">
            {busy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" />}
            {busy ? 'Klargør...' : 'Klargør Edge'}
          </button>

          {result && (
            <div className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-800">
                <CheckCircle className="w-4 h-4" />
                {result.device_id} er klar til bootstrap indtil {fmt(result.expires_at)}
              </div>
              <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-white border border-emerald-100 p-3 text-xs text-gray-800">{result.bootstrap_yaml}</pre>
              <div className="mt-3 space-y-1 text-xs text-emerald-800">
                {result.next_steps.map(step => <div key={step}>• {step}</div>)}
              </div>
            </div>
          )}
        </section>

        {/* Pipeline status + hardening */}
        <section className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-gray-800 mb-1">ISO pipeline status</h2>
            <p className="text-xs text-gray-400 mb-3">Call-home: <span className="font-mono">{blueprint?.call_home ?? '-'}</span></p>
            <div className="space-y-2 mb-4">
              {pipelineSteps.map(step => (
                <div key={step.label} className="flex items-start gap-2.5 text-xs">
                  {step.done
                    ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                    : <AlertCircle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />}
                  <div>
                    <div className={`font-medium ${step.done ? 'text-gray-800' : 'text-amber-700'}`}>{step.label}</div>
                    <div className="text-gray-400 mt-0.5">{step.note}</div>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={buildImage}
              disabled={buildImageBusy}
              className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50"
            >
              {buildImageBusy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FileCheck className="w-4 h-4" />}
              {buildImageBusy ? 'Bygger...' : hasImage ? 'Generer nyt image manifest' : 'Byg og signér Edge image manifest'}
            </button>

            {buildImageError && (
              <div className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {buildImageError}
              </div>
            )}

            {latestImage && (
              <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-emerald-800">
                  <CheckCircle className="w-3.5 h-3.5" />
                  {latestImage.artifact_id}
                </div>
                <div className="text-emerald-700">Signeret: {fmt(latestImage.signed_at)} · {latestImage.signed_by ?? 'system-hash'}</div>
                <div className="font-mono text-emerald-600 truncate">sha256: {latestImage.sha256}</div>
                {latestImage.sbom_ref && <div className="text-emerald-600">SBOM: {latestImage.sbom_ref}</div>}
              </div>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <Checklist title="Hardening krav" items={blueprint?.hardening ?? []} />
            <Checklist title="Build artifacts" items={blueprint?.required_outputs ?? []} />
          </div>

          {/* Disk image build */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center gap-2 mb-3">
              <Package className="w-4 h-4 text-sky-500" />
              <span className="text-sm font-semibold text-gray-800">Edge disk image</span>
            </div>

            {/* Target + mode selectors */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Hardware target</label>
                <select
                  value={diskBuildTarget}
                  onChange={e => setDiskBuildTarget(e.target.value)}
                  disabled={diskBuildStatus?.running}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white text-gray-800 disabled:opacity-50"
                >
                  {availableTargets.filter(t => !t.install_script).map(t => (
                    <option key={t.id} value={t.id}>
                      {t.display_name} ({t.arch})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Output type</label>
                <select
                  value={diskBuildMode}
                  onChange={e => setDiskBuildMode(e.target.value as 'rootfs' | 'flashable')}
                  disabled={diskBuildStatus?.running}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white text-gray-800 disabled:opacity-50"
                >
                  <option value="rootfs">rootfs.tar.gz — hurtig (~5 min), kræver manuel flash</option>
                  <option value="flashable">Flashbart .img.gz — klar til dd/balenaEtcher (~20 min)</option>
                </select>
              </div>
            </div>

            {diskBuildMode === 'flashable' && (
              <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 p-3">
                <p className="text-xs text-amber-800 font-medium mb-2">Batch bootstrap token (valgfri)</p>
                <p className="text-xs text-amber-700 mb-2">
                  Bages ind i imaget. Lad feltet stå tomt for at bruge placeholder — du kan injicere token efterfølgende.
                </p>
                <input
                  value={diskBuildToken}
                  onChange={e => setDiskBuildToken(e.target.value)}
                  placeholder="btk-batch-xxxxx (valgfri)"
                  disabled={diskBuildStatus?.running}
                  className="w-full text-xs border border-amber-200 rounded-lg px-2.5 py-1.5 bg-white font-mono placeholder-amber-300 disabled:opacity-50"
                />
              </div>
            )}

            {diskBuildMode === 'flashable' && (
              <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 p-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Wifi className="w-3.5 h-3.5 text-blue-600" />
                  <p className="text-xs text-blue-800 font-medium">WiFi konfiguration (valgfri)</p>
                </div>
                <p className="text-xs text-blue-700 mb-3">
                  Bages ind i imaget. Lad SSID stå tomt for ingen WiFi — kan tilføjes via "Tilføj WiFi" efterfølgende.
                </p>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div>
                    <label className="block text-xs text-blue-700 mb-1">SSID (netværksnavn)</label>
                    <input
                      value={diskBuildWifiSsid}
                      onChange={e => setDiskBuildWifiSsid(e.target.value)}
                      placeholder="MitWiFi"
                      disabled={diskBuildStatus?.running}
                      className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white placeholder-blue-300 disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-blue-700 mb-1">Adgangskode</label>
                    <input
                      type="password"
                      value={diskBuildWifiPassword}
                      onChange={e => setDiskBuildWifiPassword(e.target.value)}
                      placeholder="••••••••"
                      disabled={diskBuildStatus?.running}
                      className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white placeholder-blue-300 disabled:opacity-50"
                    />
                  </div>
                </div>
                <div className="w-24">
                  <label className="block text-xs text-blue-700 mb-1">Landekode</label>
                  <input
                    value={diskBuildWifiCountry}
                    onChange={e => setDiskBuildWifiCountry(e.target.value.toUpperCase().slice(0, 2))}
                    placeholder="DK"
                    maxLength={2}
                    disabled={diskBuildStatus?.running}
                    className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white font-mono placeholder-blue-300 disabled:opacity-50 uppercase"
                  />
                </div>
              </div>
            )}

            <p className="text-xs text-gray-400 mb-3">
              {diskBuildMode === 'flashable'
                ? 'Bygger rootfs via Docker buildx + injicerer i base-image via Docker --privileged. Output: .img.gz der flashes direkte på SSD/SD-kort med dd eller balenaEtcher.'
                : 'Bygger rootfs via Docker buildx. Output: .tar.gz tarball der kan injiceres manuelt eller bruges som depot til manuel flash.'
              }
            </p>

            <button
              onClick={buildDiskImage}
              disabled={diskBuildStatus?.running}
              className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {diskBuildStatus?.running
                ? <RefreshCw className="w-4 h-4 animate-spin" />
                : <Package className="w-4 h-4" />}
              {diskBuildStatus?.running
                ? `Bygger ${diskBuildStatus.target ?? ''} (${diskBuildStatus.mode ?? 'rootfs'})…`
                : `Byg ${diskBuildMode === 'flashable' ? 'flashbart image' : 'rootfs'}`}
            </button>

            {/* Progress log */}
            {diskBuildStatus && diskBuildStatus.progress.length > 0 && (
              <BuildLog lines={diskBuildStatus.progress} running={diskBuildStatus.running} />
            )}

            {diskBuildStatus?.error && (
              <div className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {diskBuildStatus.error}
              </div>
            )}

            {diskBuildStatus?.ready && diskBuildStatus.result && (
              <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-xs space-y-1.5">
                <div className="flex items-center gap-1.5 font-medium text-emerald-800">
                  <CheckCircle className="w-3.5 h-3.5" />
                  {diskBuildStatus.result.artifact_id}
                  {diskBuildStatus.result.mode === 'flashable' && (
                    <span className="ml-1.5 px-1.5 py-0.5 bg-sky-100 text-sky-700 rounded text-xs">flashbart</span>
                  )}
                  {diskBuildStatus.result.token_baked_in && (
                    <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">token bagt ind</span>
                  )}
                </div>
                <div className="text-emerald-700">
                  {diskBuildStatus.result.filename} · {(diskBuildStatus.result.size_bytes / 1024 / 1024).toFixed(0)} MB
                </div>
                {(diskBuildStatus.result.sbom_os_count > 0 || diskBuildStatus.result.sbom_venv_count > 0) && (
                  <div className="text-emerald-700">
                    SBOM: {diskBuildStatus.result.sbom_os_count} OS-pakker + {diskBuildStatus.result.sbom_venv_count} Python-pakker
                  </div>
                )}
                <div className="font-mono text-emerald-600 truncate">sha256: {diskBuildStatus.result.sha256}</div>
                <div className="text-emerald-600">Signeret af: {diskBuildStatus.result.signed_by}</div>
                {diskBuildStatus.result.flash_instructions && (
                  <div className="mt-1 p-2 bg-emerald-100 rounded text-emerald-800 font-mono text-xs">
                    <div className="text-emerald-600 font-sans mb-1 font-medium">Flash kommando:</div>
                    <div className="truncate">{diskBuildStatus.result.flash_instructions.linux_mac}</div>
                    <div className="text-emerald-600 font-sans mt-1">Windows: {diskBuildStatus.result.flash_instructions.windows}</div>
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mt-1">
                  <a
                    href={`${getApiUrl()}/api/admin/edge-provisioning/disk-image-download/${diskBuildStatus.result.artifact_id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 text-white rounded-lg hover:bg-emerald-800 text-xs"
                  >
                    <Download className="w-3 h-3" />
                    {diskBuildStatus.result.mode === 'flashable' ? 'Download .img.gz' : 'Download rootfs.tar.gz'}
                  </a>
                  {diskBuildStatus.result.mode === 'flashable' && (
                    <button
                      onClick={() => {
                        setWifiInjectArtifactId(diskBuildStatus!.result!.artifact_id)
                        setWifiInjectOpen(true)
                        setWifiInjectResult(null)
                        setWifiInjectError(null)
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs"
                    >
                      <Wifi className="w-3 h-3" />
                      Tilføj WiFi
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* WiFi B — post-process inject panel */}
            {wifiInjectOpen && (
              <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5 font-medium text-blue-800">
                    <Wifi className="w-3.5 h-3.5" />
                    Tilføj WiFi til eksisterende image
                  </div>
                  <button onClick={() => setWifiInjectOpen(false)} className="text-blue-400 hover:text-blue-700 text-xs">✕</button>
                </div>
                <p className="text-blue-700 mb-3">
                  Producerer et nyt .img.gz med WiFi-config bagt ind — originalen bevares urørt.
                </p>
                <div className="mb-2">
                  <label className="block text-blue-700 mb-1">Artifact ID</label>
                  <input
                    value={wifiInjectArtifactId}
                    onChange={e => setWifiInjectArtifactId(e.target.value)}
                    placeholder="TL-FLASH-IMG-..."
                    disabled={wifiInjectRunning}
                    className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white font-mono placeholder-blue-300 disabled:opacity-50"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div>
                    <label className="block text-blue-700 mb-1">SSID</label>
                    <input
                      value={wifiInjectSsid}
                      onChange={e => setWifiInjectSsid(e.target.value)}
                      placeholder="MitWiFi"
                      disabled={wifiInjectRunning}
                      className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white placeholder-blue-300 disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-blue-700 mb-1">Adgangskode</label>
                    <input
                      type="password"
                      value={wifiInjectPassword}
                      onChange={e => setWifiInjectPassword(e.target.value)}
                      placeholder="••••••••"
                      disabled={wifiInjectRunning}
                      className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white placeholder-blue-300 disabled:opacity-50"
                    />
                  </div>
                </div>
                <div className="w-20 mb-3">
                  <label className="block text-blue-700 mb-1">Landekode</label>
                  <input
                    value={wifiInjectCountry}
                    onChange={e => setWifiInjectCountry(e.target.value.toUpperCase().slice(0, 2))}
                    placeholder="DK"
                    maxLength={2}
                    disabled={wifiInjectRunning}
                    className="w-full text-xs border border-blue-200 rounded-lg px-2.5 py-1.5 bg-white font-mono uppercase placeholder-blue-300 disabled:opacity-50"
                  />
                </div>
                <button
                  onClick={submitWifiInject}
                  disabled={wifiInjectRunning || !wifiInjectSsid || !wifiInjectPassword || !wifiInjectArtifactId}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-700 text-white text-xs rounded-lg hover:bg-blue-800 disabled:opacity-50"
                >
                  {wifiInjectRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
                  {wifiInjectRunning ? 'Injecterer WiFi...' : 'Injectér WiFi'}
                </button>
                {wifiInjectError && (
                  <div className="mt-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                    {wifiInjectError}
                  </div>
                )}
                {wifiInjectResult && (
                  <div className="mt-2 rounded-lg border border-emerald-100 bg-emerald-50 p-3 space-y-1.5">
                    <div className="flex items-center gap-1.5 font-medium text-emerald-800">
                      <CheckCircle className="w-3.5 h-3.5" />
                      WiFi injiceret: {wifiInjectResult.wifi_ssid}
                    </div>
                    <div className="text-emerald-700">{wifiInjectResult.filename}</div>
                    <div className="font-mono text-emerald-600 truncate">sha256: {wifiInjectResult.sha256}</div>
                    <a
                      href={`${getApiUrl()}/api/admin/edge-provisioning/disk-image-download/${wifiInjectResult.artifact_id}`}
                      className="inline-flex items-center gap-1.5 mt-1 px-3 py-1.5 bg-emerald-700 text-white rounded-lg hover:bg-emerald-800 text-xs"
                    >
                      <Download className="w-3 h-3" />
                      Download WiFi .img.gz
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Deployed edges */}
      {edges.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-800">Aktive edges ({edges.length})</h2>
            <p className="text-xs text-gray-400 mt-0.5">Nuværende software-versioner på registrerede edges — bruges til at identificere hvad en ny ISO skal matche.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Device ID</th>
                  <th className="px-4 py-2.5 text-left font-medium">Hardware</th>
                  <th className="px-4 py-2.5 text-left font-medium">OS</th>
                  <th className="px-4 py-2.5 text-left font-medium">App version</th>
                  <th className="px-4 py-2.5 text-left font-medium">Kernel</th>
                  <th className="px-4 py-2.5 text-left font-medium">Inventory</th>
                  <th className="px-4 py-2.5 text-left font-medium">Backup</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {edges.map(edge => (
                  <tr key={edge.device_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-mono text-gray-800">{edge.device_id}</td>
                    <td className="px-4 py-2.5 text-gray-600">{edge.hardware_model ?? '-'}</td>
                    <td className="px-4 py-2.5 text-gray-600">{edge.os_name ?? '-'}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-700">{edge.app_version ?? '-'}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-500 truncate max-w-[160px]">{edge.kernel_version ?? '-'}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1">
                        {edge.has_os_packages && <span className="px-1.5 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded">OS</span>}
                        {edge.has_venv_packages && <span className="px-1.5 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded">venv</span>}
                        {edge.has_software_inventory && <span className="px-1.5 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded">SW</span>}
                        {!edge.has_os_packages && !edge.has_venv_packages && !edge.has_software_inventory && <span className="text-gray-400">-</span>}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {edge.backup_complete
                        ? <span className="flex items-center gap-1 text-emerald-600"><CheckCircle className="w-3 h-3" />{fmt(edge.backup_complete.at ?? null)}</span>
                        : edge.backup_requested
                          ? <span className="flex items-center gap-1 text-amber-600"><Clock className="w-3 h-3" />Anmodet</span>
                          : <span className="text-gray-400">-</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

/** Auto-scrollende log-viewer med pause/play/reset kontrol */
function BuildLog({ lines, running }: { lines: string[]; running: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Auto-scroll til bunden når nye linjer ankommer
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [lines.length, autoScroll])

  // Detektér manuel scroll op → pauser auto-scroll
  function handleScroll() {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32
    if (!atBottom) setAutoScroll(false)
    else setAutoScroll(true)
  }

  function scrollToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    setAutoScroll(true)
  }

  function clearLog() {
    // Vi kan ikke rydde lines udefra — scroll bare til top
    containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    setAutoScroll(false)
  }

  return (
    <div className="mt-3 rounded-lg bg-gray-950 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${running ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-[10px] text-gray-400 font-mono">{running ? 'kører…' : 'færdig'} · {lines.length} linjer</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            title={autoScroll ? 'Pause auto-scroll' : 'Genoptag auto-scroll'}
            onClick={() => autoScroll ? setAutoScroll(false) : scrollToBottom()}
            className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
              autoScroll
                ? 'bg-emerald-900 text-emerald-400 hover:bg-emerald-800'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {autoScroll ? '⏸ pause' : '▶ følg'}
          </button>
          <button
            title="Scroll til bunden"
            onClick={scrollToBottom}
            className="px-2 py-0.5 rounded text-[10px] font-mono bg-gray-800 text-gray-400 hover:bg-gray-700"
          >
            ↓ bund
          </button>
          <button
            title="Scroll til toppen"
            onClick={clearLog}
            className="px-2 py-0.5 rounded text-[10px] font-mono bg-gray-800 text-gray-400 hover:bg-gray-700"
          >
            ↑ top
          </button>
        </div>
      </div>
      {/* Log indhold */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="p-3 max-h-72 overflow-y-auto text-xs font-mono"
      >
        {lines.map((line, i) => (
          <div key={i} className={
            line.startsWith('✅') ? 'text-emerald-400' :
            line.startsWith('❌') ? 'text-red-400' :
            line.startsWith('⚠️') ? 'text-amber-400' :
            line.startsWith('🎉') ? 'text-sky-400' :
            line.startsWith('💉') ? 'text-purple-400' :
            'text-gray-300'
          }>{line}</div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function Field({
  label, value, onChange, placeholder, type = 'text', mono = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  mono?: boolean
}) {
  return (
    <label className="block">
      <span className="text-xs text-gray-400 block mb-1">{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full border border-gray-200 rounded-lg px-3 py-2 text-sm ${mono ? 'font-mono' : ''}`}
      />
    </label>
  )
}

function Checklist({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="font-medium text-gray-700 mb-2">{title}</div>
      <div className="space-y-1.5">
        {items.map(item => (
          <div key={item} className="flex items-start gap-2 text-gray-500">
            <FileCheck className="w-3.5 h-3.5 text-sky-500 mt-0.5 flex-shrink-0" />
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

function ComplianceTab({ assessment }: { assessment: ResilienceAssessment | null }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800">Compliance readiness</h2>
        <p className="text-xs text-gray-400 mt-0.5">SABSA, IEC 62443, ISO 27000, NIS2 og CRA kontroller med evidens.</p>
      </div>
      <div className="divide-y divide-gray-100">
        {(assessment?.controls ?? []).map(control => (
          <div key={control.title} className="px-5 py-4">
            <div className="flex items-start gap-3">
              <StatusIcon status={control.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-gray-900">{control.title}</span>
                  <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusStyle(control.status)}`}>{control.status}</span>
                  {control.domains.map(domain => (
                    <span key={domain} className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-500 border-gray-200">
                      {domain}
                    </span>
                  ))}
                </div>
                <div className="text-xs text-gray-500 mt-1 font-mono">{control.evidence}</div>
                {control.recommendation && (
                  <div className="text-xs text-gray-400 mt-1">{control.recommendation}</div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
