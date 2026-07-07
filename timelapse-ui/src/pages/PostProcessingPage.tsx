import { useEffect, useState } from 'react'
import { Brain, Image, Play, RefreshCw, Wrench, Clock, Mail } from 'lucide-react'
import { getApiUrl } from '../api/client'

interface Device {
  device_id: string
  customer_name?: string
  site_name?: string
  camera_name?: string
}

interface JobStatus {
  running: boolean
  started_at: string | null
  finished_at: string | null
  requested_by: string | null
  options: Record<string, unknown>
  total: number
  processed: number
  thumbnails_generated: number
  thumbnails_existing: number
  ai_queued: number
  files_missing: number
  errors: number
  error_samples?: string[]
  last_message: string
  ollama_warning?: string | null
  ai_strategy?: string | null
}

interface AiStatus {
  ollama_running: boolean
  vision_ready: boolean
  models: string[]
  queue_size: number
  open_webui_priority: boolean
  worker_stats: {
    completed: number
    completed_cloud: number
    skipped_no_capture: number
    skipped_no_image: number
    skipped_disabled: number
    skipped_technical_only: number
    skipped_ollama_down: number
    skipped_no_cloud_credentials: number
    skipped_already_done: number
    skipped_queue_full: number
    failed: number
  }
}

interface BatchJob {
  id: string
  gemini_job_name: string
  status: string   // submitted|running|succeeded|failed|cancelled|expired
  total_count: number
  success_count: number
  error_count: number
  requested_by: string | null
  cloud_model: string | null
  created_at: string | null
  submitted_at: string | null
  completed_at: string | null
  error_message: string | null
}

const BATCH_STATUS_LABEL: Record<string, string> = {
  submitted: 'Sendt til Google',
  running:   'Kører hos Google',
  succeeded: 'Færdig',
  failed:    'Fejlet',
  cancelled: 'Annulleret',
  expired:   'Udløbet (48t)',
}
const BATCH_STATUS_COLOR: Record<string, string> = {
  submitted: 'bg-blue-50 text-blue-700 border-blue-200',
  running:   'bg-amber-50 text-amber-700 border-amber-200',
  succeeded: 'bg-green-50 text-green-700 border-green-200',
  failed:    'bg-red-50 text-red-700 border-red-200',
  cancelled: 'bg-gray-50 text-gray-600 border-gray-200',
  expired:   'bg-red-50 text-red-700 border-red-200',
}

async function api(path: string, options?: RequestInit) {
  const response = await fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `${response.status}`)
  }
  return response.json()
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="border border-slate-200 bg-white rounded-lg p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-900 mt-1">{value}</p>
    </div>
  )
}

interface ThumbnailBacklog {
  total: number
  missing: number
  devices: Record<string, number>
  scan_time_seconds: number
  partial: boolean
}

export default function PostProcessingPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [limit, setLimit] = useState('')
  const [thumbnails, setThumbnails] = useState(true)
  const [ai, setAi] = useState(false)
  const [forceAi, setForceAi] = useState(false)
  const [batchMode, setBatchMode] = useState(false)
  const [notifyOnComplete, setNotifyOnComplete] = useState(true)
  const [startingBatch, setStartingBatch] = useState(false)
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([])
  const [backlog, setBacklog] = useState<ThumbnailBacklog | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadStatus() {
    const data = await api('/api/admin/post-processing/status')
    setStatus(data)
  }

  async function loadAiStatus() {
    try {
      const data = await api('/api/ai/status')
      setAiStatus(data)
    } catch { /* AI router kan være utilgængelig — ikke kritisk */ }
  }

  async function loadBatchJobs() {
    try {
      const data = await api('/api/admin/ai-batch/jobs')
      setBatchJobs(data)
    } catch { /* ikke kritisk */ }
  }

  async function loadBacklog() {
    try {
      const data = await api('/api/admin/thumbnail-backlog')
      setBacklog(data)
    } catch { /* ikke kritisk */ }
  }

  useEffect(() => {
    api('/api/admin/devices')
      .then((data: unknown) => {
        if (Array.isArray(data)) {
          setDevices(data)
          return
        }
        if (data && typeof data === 'object' && 'devices' in data) {
          const payload = data as { devices?: unknown }
          if (Array.isArray(payload.devices)) {
            setDevices(payload.devices)
          }
        }
      })
      .catch(() => {})
    loadStatus().catch(e => setError(e instanceof Error ? e.message : 'Kunne ikke hente status'))
    loadAiStatus()
    loadBatchJobs()
    loadBacklog()
  }, [])

  useEffect(() => {
    if (!status?.running) return
    const timer = window.setInterval(() => {
      loadStatus().catch(() => {})
      loadAiStatus()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [status?.running])

  useEffect(() => {
    const hasActive = batchJobs.some(j => j.status === 'submitted' || j.status === 'running')
    if (!hasActive) return
    const timer = window.setInterval(() => { loadBatchJobs() }, 30000)
    return () => window.clearInterval(timer)
  }, [batchJobs])

  async function start() {
    setError(null)
    try {
      const data = await api('/api/admin/post-processing/start', {
        method: 'POST',
        body: JSON.stringify({
          device_id: deviceId || null,
          limit: limit ? Number(limit) : null,
          thumbnails,
          ai,
          force_ai: forceAi,
        }),
      })
      setStatus(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kunne ikke starte post-processing')
    }
  }

  async function startBatch() {
    setError(null)
    setStartingBatch(true)
    try {
      await api('/api/admin/ai-batch/start', {
        method: 'POST',
        body: JSON.stringify({
          device_id: deviceId || null,
          limit: limit ? Number(limit) : null,
          force_ai: forceAi,
          notify_on_complete: notifyOnComplete,
        }),
      })
      await loadBatchJobs()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kunne ikke starte batch-job')
    } finally {
      setStartingBatch(false)
    }
  }

  const progress = status?.total ? Math.round((status.processed / status.total) * 100) : 0

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Wrench className="w-5 h-5 text-sky-600" />
            Post-processing
          </h1>
          <p className="text-sm text-slate-500 mt-1">Kontrolleret efterbehandling af eksisterende billeder, thumbnails og AI-tags.</p>
        </div>
        <div className="flex items-center gap-2">
          {backlog && backlog.missing > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200">
              <Image className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-medium text-amber-900">{backlog.missing} manglende thumbnails</span>
            </div>
          )}
          <button
            onClick={() => { loadStatus(); loadBacklog(); }}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-200 bg-white text-sm text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Opdater
          </button>
        </div>
      </div>

      {error && <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>}

      {status?.ollama_warning && (
        <div className="border border-amber-300 bg-amber-50 text-amber-800 rounded-lg px-4 py-3 text-sm font-medium">
          {status.ollama_warning}
        </div>
      )}
      {/* Bemærk: advarslen ovenfor er strategi-bevidst (beregnet server-side) —
          viser IKKE en falsk Ollama-advarsel hvis I bruger cloud_only (Gemini). */}

      <div className="grid lg:grid-cols-[360px_1fr] gap-5">
        <div className="border border-slate-200 bg-white rounded-lg p-4 space-y-4">
          <div>
            <label className="text-xs font-medium text-slate-600">Enhed</label>
            <select value={deviceId} onChange={e => setDeviceId(e.target.value)}
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white">
              <option value="">Alle synlige enheder</option>
              {devices.map(device => (
                <option key={device.device_id} value={device.device_id}>
                  {device.customer_name ? `${device.customer_name} / ` : ''}{device.site_name ? `${device.site_name} / ` : ''}{device.camera_name || device.device_id}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-600">Maks billeder</label>
              <button type="button" onClick={() => setLimit('')}
                className="text-xs text-sky-600 hover:text-sky-800">
                Alle billeder
              </button>
            </div>
            <input type="number" min="1" value={limit} onChange={e => setLimit(e.target.value)}
              placeholder="Tom = alle billeder (ingen øvre grænse)"
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm font-mono" />
          </div>

          <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 cursor-pointer">
            <input type="checkbox" checked={thumbnails} onChange={e => setThumbnails(e.target.checked)} className="mt-1" />
            <span>
              <span className="text-sm font-medium text-slate-900 flex items-center gap-2"><Image className="w-4 h-4" /> Manglende thumbnails</span>
              <span className="block text-xs text-slate-500 mt-1">Genererer kun når `.thumbs` mangler.</span>
            </span>
          </label>

          <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 cursor-pointer">
            <input type="checkbox" checked={ai} onChange={e => setAi(e.target.checked)} className="mt-1" />
            <span>
              <span className="text-sm font-medium text-slate-900 flex items-center gap-2"><Brain className="w-4 h-4" /> AI-tags</span>
              <span className="block text-xs text-slate-500 mt-1">Køer billeder til AI-analyse.</span>
            </span>
          </label>

          {ai && (
            <label className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 cursor-pointer">
              <input type="checkbox" checked={forceAi} onChange={e => setForceAi(e.target.checked)} className="mt-1" />
              <span>
                <span className="text-sm font-medium text-amber-900">Force reanalyse</span>
                <span className="block text-xs text-amber-700 mt-1">Nulstiller eksisterende AI-resultater før køning.</span>
              </span>
            </label>
          )}

          {ai && (
            <label className="flex items-start gap-3 rounded-lg border border-purple-200 bg-purple-50 p-3 cursor-pointer">
              <input type="checkbox" checked={batchMode} onChange={e => setBatchMode(e.target.checked)} className="mt-1" />
              <span>
                <span className="text-sm font-medium text-purple-900 flex items-center gap-2">
                  <Clock className="w-4 h-4" /> Batch-mode (Gemini)
                </span>
                <span className="block text-xs text-purple-700 mt-1">
                  ~50% billigere end normal pris. Asynkront — resultater kan tage fra få minutter til op til 24 timer.
                  Kører ikke i den almindelige kø ovenfor, men som et separat job.
                </span>
              </span>
            </label>
          )}

          {ai && batchMode && (
            <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 cursor-pointer">
              <input type="checkbox" checked={notifyOnComplete} onChange={e => setNotifyOnComplete(e.target.checked)} className="mt-1" />
              <span>
                <span className="text-sm font-medium text-slate-900 flex items-center gap-2"><Mail className="w-4 h-4" /> Email når færdig</span>
                <span className="block text-xs text-slate-500 mt-1">Bruger jeres eksisterende SIEM email-opsætning (Indstillinger → Notifikationer).</span>
              </span>
            </label>
          )}

          {batchMode && ai ? (
            <>
              {thumbnails && (
                <p className="text-xs text-amber-600 -mt-1">
                  ⚠ Batch-knappen behandler kun AI-tags. Thumbnails skal køres separat (slå batch-mode fra og tryk "Start post-processing").
                </p>
              )}
              <button
                onClick={startBatch}
                disabled={startingBatch}
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-purple-600 text-white text-sm font-medium disabled:bg-purple-300 disabled:cursor-not-allowed hover:bg-purple-700"
              >
                <Clock className="w-4 h-4" />
                {startingBatch ? 'Opretter batch-job…' : 'Start batch-job (Gemini)'}
              </button>
            </>
          ) : (
            <button
              onClick={start}
              disabled={!!status?.running || (!thumbnails && !ai)}
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-slate-800"
            >
              <Play className="w-4 h-4" />
              {status?.running ? 'Kører...' : 'Start post-processing'}
            </button>
          )}
        </div>

        <div className="space-y-4">
          <div className="border border-slate-200 bg-white rounded-lg p-4">
            <div className="flex justify-between text-sm">
              <span className="font-medium text-slate-900">{status?.last_message ?? 'Ingen status'}</span>
              <span className="text-slate-500">{progress}%</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full mt-3 overflow-hidden">
              <div className="h-full bg-sky-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-xs text-slate-500 mt-2">
              {status?.processed ?? 0} / {status?.total ?? 0} billeder
              {status?.requested_by ? ` · startet af ${status.requested_by}` : ''}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Stat label="Thumbnails genereret" value={status?.thumbnails_generated ?? 0} />
            <Stat label="Thumbnails fandtes" value={status?.thumbnails_existing ?? 0} />
            <Stat label="AI køet" value={status?.ai_queued ?? 0} />
            <Stat label="Manglende filer" value={status?.files_missing ?? 0} />
            <Stat label="Fejl" value={status?.errors ?? 0} />
            <Stat label="Status" value={status?.running ? 'Kører' : 'Idle'} />
          </div>

          {(status?.error_samples?.length ?? 0) > 0 && (
            <div className="border border-amber-200 bg-amber-50 rounded-lg p-3">
              <p className="text-xs font-semibold text-amber-900 mb-2">Seneste fejleksempler</p>
              <div className="space-y-1 max-h-40 overflow-auto">
                {status?.error_samples?.map((sample, idx) => (
                  <p key={`${idx}-${sample}`} className="text-xs text-amber-800 font-mono break-all">{sample}</p>
                ))}
              </div>
            </div>
          )}

          {ai && aiStatus && (
            <div className="border border-slate-200 bg-white rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-slate-900">AI-worker — faktisk fremskridt</h2>
                <span className="text-xs text-slate-500">
                  Strategi: {status?.ai_strategy ?? '–'} ·
                  {status?.ai_strategy !== 'cloud_only' && (
                    <> Ollama: {aiStatus.ollama_running ? '✓ kører' : '✗ ikke fundet'} · </>
                  )}
                  Kø: {aiStatus.queue_size}
                </span>
              </div>
              {aiStatus.open_webui_priority && (
                <p className="text-xs text-amber-700 mb-2">⚠ Open WebUI-prioritet er aktiv — analyse er pauset.</p>
              )}
              <div className="grid sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <Stat label="Analyseret (lokal)" value={aiStatus.worker_stats.completed - aiStatus.worker_stats.completed_cloud} />
                <Stat label="Analyseret (cloud)" value={aiStatus.worker_stats.completed_cloud} />
                <Stat label="Allerede gjort" value={aiStatus.worker_stats.skipped_already_done} />
                <Stat label="Ollama nede" value={aiStatus.worker_stats.skipped_ollama_down} />
                <Stat label="Ingen Gemini-nøgle" value={aiStatus.worker_stats.skipped_no_cloud_credentials} />
                <Stat label="Kø fuld" value={aiStatus.worker_stats.skipped_queue_full} />
                <Stat label="AI slået fra" value={aiStatus.worker_stats.skipped_disabled} />
                <Stat label="Billede ikke fundet" value={aiStatus.worker_stats.skipped_no_image} />
                <Stat label="Fejlet" value={aiStatus.worker_stats.failed} />
              </div>
              <p className="text-xs text-slate-400 mt-2">
                "AI køet" ovenfor viser hvor mange billeder jobbet har sat i kø — "Analyseret" her viser hvor mange der reelt er færdigbehandlet (lokalt eller via cloud).
              </p>
            </div>
          )}

          {batchJobs.length > 0 && (
            <div className="border border-slate-200 bg-white rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-purple-600" /> Gemini batch-jobs
                </h2>
                <button onClick={() => loadBatchJobs()} className="text-xs text-sky-600 hover:text-sky-800">
                  Opdater
                </button>
              </div>
              <div className="space-y-2">
                {batchJobs.map(job => (
                  <div key={job.id} className="flex items-center justify-between border border-slate-100 rounded-lg px-3 py-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${BATCH_STATUS_COLOR[job.status] ?? 'bg-gray-50 text-gray-600 border-gray-200'}`}>
                          {BATCH_STATUS_LABEL[job.status] ?? job.status}
                        </span>
                        <span className="text-xs text-slate-400 font-mono">{job.gemini_job_name}</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        {job.total_count} billeder · {job.cloud_model ?? '–'}
                        {job.requested_by ? ` · anmodet af ${job.requested_by}` : ''}
                        {job.error_message ? ` · ${job.error_message}` : ''}
                      </p>
                      {job.status === 'running' && job.total_count > 0 && (
                        <div className="mt-2 w-48 max-w-full">
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-sky-500 transition-all"
                              style={{ width: `${Math.min(100, Math.round(((job.success_count + job.error_count) / job.total_count) * 100))}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                    {job.status === 'running' && job.total_count > 0 && (
                      <div className="text-xs text-right text-slate-500">
                        <div>{job.success_count + job.error_count} / {job.total_count}</div>
                        <div className="text-slate-400">{Math.min(100, Math.round(((job.success_count + job.error_count) / job.total_count) * 100))}%</div>
                        {job.error_count > 0 && <div className="text-red-500">{job.error_count} fejl</div>}
                      </div>
                    )}
                    {(job.status === 'succeeded' || job.status === 'failed') && (
                      <div className="text-xs text-right text-slate-500">
                        <div>{job.success_count} ok</div>
                        {job.error_count > 0 && <div className="text-red-500">{job.error_count} fejl</div>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
