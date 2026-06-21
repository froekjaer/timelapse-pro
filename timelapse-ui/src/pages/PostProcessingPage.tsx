import { useEffect, useState } from 'react'
import { Brain, Image, Play, RefreshCw, Wrench } from 'lucide-react'
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

export default function PostProcessingPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [limit, setLimit] = useState('1000')
  const [thumbnails, setThumbnails] = useState(true)
  const [ai, setAi] = useState(false)
  const [forceAi, setForceAi] = useState(false)
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

  useEffect(() => {
    api('/api/admin/devices')
      .then((data: any) => setDevices(data.devices ?? data))
      .catch(() => {})
    loadStatus().catch(e => setError(e instanceof Error ? e.message : 'Kunne ikke hente status'))
    loadAiStatus()
  }, [])

  useEffect(() => {
    if (!status?.running) return
    const timer = window.setInterval(() => {
      loadStatus().catch(() => {})
      loadAiStatus()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [status?.running])

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
        <button
          onClick={() => loadStatus().catch(() => {})}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-200 bg-white text-sm text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" />
          Opdater
        </button>
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

          <button
            onClick={start}
            disabled={!!status?.running || (!thumbnails && !ai)}
            className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-slate-800"
          >
            <Play className="w-4 h-4" />
            {status?.running ? 'Kører...' : 'Start post-processing'}
          </button>
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
        </div>
      </div>
    </div>
  )
}
