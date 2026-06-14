import { type Dispatch, type SetStateAction, useEffect, useRef, useState } from 'react'
import {
  AlertCircle, CheckCircle, Clock, Database, Download, FileCheck,
  HardDrive, RefreshCw, Server, ShieldCheck, Wifi, Wrench, XCircle
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
  customer_name: string
  site_name: string
  camera_name: string
  note: string
  expires_hours: number
  headend_url: string
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
  const [provisioningForm, setProvisioningForm] = useState<EdgeProvisioningForm>({
    device_id: '',
    customer_name: '',
    site_name: '',
    camera_name: 'Kamera 1',
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

  async function prepareEdgeProvisioning() {
    setProvisioningBusy(true)
    setProvisioningResult(null)
    try {
      const r = await api('/admin/edge-provisioning/prepare', {
        method: 'POST',
        body: JSON.stringify({
          ...provisioningForm,
          device_id: provisioningForm.device_id.trim(),
          customer_name: provisioningForm.customer_name.trim() || undefined,
          site_name: provisioningForm.site_name.trim() || undefined,
          camera_name: provisioningForm.camera_name.trim() || undefined,
          note: provisioningForm.note.trim() || undefined,
          headend_url: provisioningForm.headend_url.trim() || undefined,
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

function IsoTab({
  assessment,
  form,
  setForm,
  result,
  busy,
  prepareEdge,
}: {
  assessment: ResilienceAssessment | null
  form: EdgeProvisioningForm
  setForm: Dispatch<SetStateAction<EdgeProvisioningForm>>
  result: EdgeProvisioningResult | null
  busy: boolean
  prepareEdge: () => void
}) {
  const blueprint = assessment?.iso_blueprint
  const canPrepare = form.device_id.trim().length >= 3 && !busy
  const edges = assessment?.edge_restore ?? []

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
      label: 'ISO image build & sign pipeline',
      done: false,
      note: 'GPG-signeret image med hardening-profil – pending',
    },
    {
      label: 'Signed ISO manifest og SBOM',
      done: false,
      note: 'SHA-256 + signeret manifest i artifact catalog – pending',
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
            <Field label="Device ID" value={form.device_id} onChange={v => setForm(s => ({ ...s, device_id: v }))} placeholder="timelapse0102" mono />
            <Field label="Token levetid timer" value={String(form.expires_hours)} onChange={v => setForm(s => ({ ...s, expires_hours: Number(v) || 48 }))} type="number" />
            <Field label="Kunde" value={form.customer_name} onChange={v => setForm(s => ({ ...s, customer_name: v }))} placeholder="Kundenavn" />
            <Field label="Site" value={form.site_name} onChange={v => setForm(s => ({ ...s, site_name: v }))} placeholder="Byggeplads / lokation" />
            <Field label="Kamera" value={form.camera_name} onChange={v => setForm(s => ({ ...s, camera_name: v }))} placeholder="Kamera 1" />
            <Field label="Headend API URL" value={form.headend_url} onChange={v => setForm(s => ({ ...s, headend_url: v }))} placeholder="auto: https://timelapse.froekjaer.dk/api" mono />
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
            <div className="space-y-2">
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
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <Checklist title="Hardening krav" items={blueprint?.hardening ?? []} />
            <Checklist title="Build artifacts" items={blueprint?.required_outputs ?? []} />
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
