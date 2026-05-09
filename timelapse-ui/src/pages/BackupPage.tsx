import { useState, useEffect, useRef } from 'react'
import { Download, HardDrive, Server, RefreshCw, CheckCircle, AlertCircle, Clock, Wifi, Database } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...opts })
}

interface BackupStatus {
  running: boolean
  progress: string[]
  ready: boolean
  error: string | null
  filename: string | null
}

interface BackupSettings {
  backup_nas_path: string | null
  backup_auto_interval: string | null
  backup_include_images: string | null
}

export function BackupPage() {
  const [status, setStatus]       = useState<BackupStatus | null>(null)
  const [settings, setSettings]   = useState<BackupSettings>({ backup_nas_path: null, backup_auto_interval: 'manual', backup_include_images: 'false' })
  const [nasPath, setNasPath]     = useState('')
  const [autoInterval, setAutoInterval] = useState('manual')
  const [settingsSaved, setSettingsSaved] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadSettings()
    loadStatus()
  }, [])

  async function loadSettings() {
    const r = await api('/admin/backup/settings')
    if (r.ok) {
      const d = await r.json()
      setSettings(d)
      setNasPath(d.backup_nas_path ?? '')
      setAutoInterval(d.backup_auto_interval ?? 'manual')
    }
  }

  async function loadStatus() {
    const r = await api('/admin/backup/status')
    if (r.ok) setStatus(await r.json())
  }

  function startPolling() {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      const r = await api('/admin/backup/status')
      if (r.ok) {
        const d = await r.json()
        setStatus(d)
        if (!d.running) {
          clearInterval(pollRef.current!)
          pollRef.current = null
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
      body: JSON.stringify({ backup_nas_path: nasPath, backup_auto_interval: autoInterval })
    })
    setSettingsSaved(true)
    setTimeout(() => setSettingsSaved(false), 2000)
  }

  async function downloadBackup() {
    const url = `${getApiUrl()}/api/admin/backup/download`
    const a = document.createElement('a')
    a.href = url
    a.download = status?.filename ?? 'timelapse-backup.tar.gz'
    a.click()
  }

  const isRunning = status?.running ?? false
  const isReady   = status?.ready ?? false
  const hasError  = !!status?.error

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Database className="w-6 h-6 text-sky-500" />
        <h1 className="text-2xl font-semibold text-gray-900">Backup</h1>
      </div>

      {/* Backup trigger */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Headend backup</h2>
        <p className="text-xs text-gray-400 mb-4">
          Gemmer database, konfiguration og systeminfo fra Mac Mini.
        </p>
        <div className="flex gap-3 flex-wrap">
          <button onClick={triggerBackup} disabled={isRunning || triggering}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed">
            {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Server className="w-4 h-4" />}
            {isRunning ? 'Kører…' : 'Start backup'}
          </button>
          {isReady && (
            <button onClick={downloadBackup}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600">
              <Download className="w-4 h-4" />
              Download til PC ({status?.filename})
            </button>
          )}
        </div>

        {/* Progress log */}
        {status && status.progress.length > 0 && (
          <div className="mt-4 bg-gray-50 rounded-lg p-3 font-mono text-xs space-y-1 max-h-48 overflow-y-auto">
            {status.progress.map((line, i) => (
              <div key={i} className={`flex items-start gap-2 ${
                line.startsWith('✅') ? 'text-emerald-600' :
                line.startsWith('❌') ? 'text-red-500' : 'text-gray-600'
              }`}>
                <span className="flex-shrink-0">
                  {line.startsWith('✅') ? <CheckCircle className="w-3.5 h-3.5 mt-0.5" /> :
                   line.startsWith('❌') ? <AlertCircle className="w-3.5 h-3.5 mt-0.5" /> :
                   <Clock className="w-3.5 h-3.5 mt-0.5 opacity-40" />}
                </span>
                {line}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edge backup */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Edge node backup</h2>
        <p className="text-xs text-gray-400 mb-4">
          Anmoder Orange Pi om at lave lokal backup af database og konfiguration.
          Backup downloades herefter via SSH eller gemmes på NAS.
        </p>
        <EdgeBackupList />
      </div>

      {/* NAS indstillinger */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          <HardDrive className="w-4 h-4 inline mr-1.5 text-gray-400" />
          NAS / netværksdrev
        </h2>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">NAS sti (monteret drev)</label>
            <input type="text"
              placeholder="/mnt/nas/timelapse-backups  eller  \\\\NAS\backups\timelapse"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={nasPath}
              onChange={e => setNasPath(e.target.value)} />
            <p className="text-xs text-gray-300 mt-1">
              Stien skal være monteret på Pi 5. Tom = gem kun lokalt i /tmp.
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Automatisk backup</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={autoInterval}
              onChange={e => setAutoInterval(e.target.value)}>
              <option value="manual">Manuel — kun ved klik</option>
              <option value="daily">Daglig (kl. 03:30)</option>
              <option value="weekly">Ugentlig (søndag kl. 03:30)</option>
            </select>
          </div>
          <button onClick={saveSettings}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600">
            {settingsSaved ? <CheckCircle className="w-4 h-4" /> : null}
            {settingsSaved ? 'Gemt!' : 'Gem indstillinger'}
          </button>
        </div>
      </div>

      {/* Hvad gemmes */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-600 mb-3">Hvad gemmes i backup</h2>
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
          {[
            ['PostgreSQL database', 'Alle enheder, captures, diagnostics'],
            ['SQL dump', 'Gendannelig tekstversion af DB'],
            ['Device configs', 'JSON konfiguration per enhed'],
            ['Systemd services', 'timelapse-headend + deploy'],
            ['Sudoers regler', 'Kørselsprivilegier'],
            ['Nginx config', 'Web server konfiguration'],
            ['Poller script', 'headend_poller.sh'],
            ['Systeminfo', 'OS, Python, Git version'],
          ].map(([title, desc]) => (
            <div key={title} className="flex items-start gap-2 py-1.5 border-b border-gray-100 last:border-0">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-gray-600">{title}</div>
                <div className="text-gray-400">{desc}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3 border-t border-gray-200 pt-3">
          ⚠️ Passwords og SSH private nøgler gemmes aldrig i backup.
          Billeder (.jpg) gemmes ikke — de er allerede på NAS via SFTP.
        </p>
      </div>
    </div>
  )
}

function EdgeBackupList() {
  const [devices, setDevices] = useState<any[]>([])
  const [triggering, setTriggering] = useState<string | null>(null)
  const [done, setDone] = useState<string[]>([])

  useEffect(() => {
    fetch(`${getApiUrl()}/api/admin/devices`)
      .then(r => r.json())
      .then(d => setDevices(d.devices ?? d))
      .catch(() => {})
  }, [])

  const [edgeStatus, setEdgeStatus] = useState<Record<string, any>>({})

  async function trigger(deviceId: string) {
    setTriggering(deviceId)
    await fetch(`${getApiUrl()}/api/admin/backup/trigger-edge/${deviceId}`, { method: 'POST' })
    setTriggering(null)
    setDone(p => [...p, deviceId])
    // Poll edge status
    let polls = 0
    const poll = setInterval(async () => {
      polls++
      const r = await fetch(`${getApiUrl()}/api/admin/backup/edge-status/${deviceId}`)
      if (r.ok) {
        const s = await r.json()
        setEdgeStatus(prev => ({ ...prev, [deviceId]: s }))
        if (s.complete || polls > 40) clearInterval(poll)
      }
    }, 3000)
  }

  if (!devices.length) return <p className="text-xs text-gray-400">Ingen enheder fundet.</p>

  return (
    <div className="space-y-3">
      {devices.map((d: any) => {
        const es = edgeStatus[d.device_id]
        const isComplete = !!es?.complete
        return (
          <div key={d.device_id} className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-700">{d.camera_name || d.location_name || d.device_id}</div>
                <div className="text-xs text-gray-400 font-mono">{d.device_id}</div>
              </div>
              <button onClick={() => trigger(d.device_id)}
                disabled={triggering === d.device_id}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
                {triggering === d.device_id ? (
                  <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sender…</>
                ) : done.includes(d.device_id) && !isComplete ? (
                  <><Clock className="w-3.5 h-3.5" /> Venter på edge…</>
                ) : (
                  <><Wifi className="w-3.5 h-3.5" /> Anmod backup</>
                )}
              </button>
            </div>
            {isComplete && es.complete && (
              <div className="mt-2 flex items-start gap-2 text-xs text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">
                <CheckCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium">Backup komplet</div>
                  <div className="text-emerald-500 font-mono">{es.complete.filename} ({es.complete.size_kb} KB)</div>
                  <div className="text-emerald-400 mt-0.5">
                    Hent: <span className="font-mono">scp orangepi@192.168.86.134:{es.complete.path} .</span>
                  </div>
                </div>
              </div>
            )}
            {done.includes(d.device_id) && !isComplete && (
              <div className="mt-2 text-xs text-gray-400 flex items-center gap-1.5">
                <RefreshCw className="w-3 h-3 animate-spin" />
                Backup kører på edge (op til 2 minutter)…
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
