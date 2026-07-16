// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — TimelapseVideoPage.tsx
// ───────────────────────────────────────────────────────────────────────────
// Version  : 1.1.0
// Dato     : 13. april 2026
// ───────────────────────────────────────────────────────────────────────────
// Changelog:
//   1.1.0  13-apr-2026  Brightness filter, dag/nat, timestamp format, ny video knap
//   1.0.0  13-apr-2026  Første version — timelapse video generator
//                       Billedvælger med tidsinterval, blur-filter,
//                       manuel fravalg, FFmpeg rendering på Pi 5,
//                       download MP4
// ═══════════════════════════════════════════════════════════════════════════

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Film, Download, RefreshCw, X,
  Clock, Eye, EyeOff, ChevronDown, ChevronUp,
  AlertTriangle, Video, Settings2, Brain, Loader2, Sparkles
} from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import { VirtualImageGrid } from '../components/VirtualImageGrid'
import { Lightbox } from './DevicePage'
import type { Capture } from '../types'

const apiCall = async (path: string, options?: RequestInit) => {
  const base = getApiUrl()
  const res = await fetch(`${base}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Typer ────────────────────────────────────────────────────────────────────

interface Frame {
  id: number
  filename: string
  device_id: string
  captured_at: string | null
  blur_score: number | null
  quality_passed: boolean | null
  quality_flag: string | null
  filesize_mb: number | null
  ai_result?: string | null
  ai_analyzed_at?: string | null
  ai_tags?: string[] | null
}

interface RenderJob {
  job_id: string
  status: 'queued' | 'rendering' | 'done' | 'error'
  progress: number
  error: string | null
  frame_count: number
  fps: number
  duration_s: number
  filesize_mb?: number
  title: string
}

interface Settings {
  fps: number
  resolution: '1080p' | '4k' | 'original'
  codec: 'h264' | 'h265'
  deflicker: boolean
  fade_frames: number
  timestamp_overlay: boolean
  timestamp_position: 'tl' | 'tr' | 'bl' | 'br'
  ken_burns: 'none' | 'zoom_in' | 'zoom_out'
  crop_ratio: '16:9' | '4:3' | '1:1' | 'original'
  min_blur: number
  min_brightness: number
  max_brightness: number
  day_night: 'all' | 'day' | 'night'
  quality_only: boolean
  timestamp_format: 'pts' | 'datetime'
  stabilization: 'none' | 'light' | 'strong'
  denoise: 'none' | 'light' | 'strong'
  sharpen: 'none' | 'light' | 'strong'
  title: string
}

const DEFAULT_SETTINGS: Settings = {
  fps: 25,
  resolution: '1080p',
  codec: 'h264',
  deflicker: false,
  fade_frames: 0,
  timestamp_overlay: false,
  timestamp_position: 'br',
  ken_burns: 'none',
  crop_ratio: '16:9',
  min_blur: 0,
  min_brightness: 0,
  max_brightness: 255,
  day_night: 'all',
  quality_only: false,
  timestamp_format: 'pts',
  stabilization: 'none',
  denoise: 'none',
  sharpen: 'none',
  title: 'timelapse',
}

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function toLocalISO(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// ── Hjælpefunktioner ─────────────────────────────────────────────────────────

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)} sek`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', {
    timeZone: getTz(),
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

// ── Hoved komponent ──────────────────────────────────────────────────────────

export default function TimelapseVideoPage() {
  const { id: deviceId } = useParams<{ id: string }>()

  // Tidsinterval
  const now = new Date()
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  const [startTime, setStartTime] = useState(toLocalISO(yesterday))
  const [endTime, setEndTime]     = useState(toLocalISO(now))

  // Frames
  const [frames, setFrames]             = useState<Frame[]>([])
  const [excluded, setExcluded]         = useState<Set<number>>(new Set())
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [loading, setLoading]           = useState(false)
  const [loadError, setLoadError]       = useState<string | null>(null)
  const [aiQuery, setAiQuery]           = useState('')
  const [aiSelecting, setAiSelecting]   = useState(false)
  const [aiNote, setAiNote]             = useState('')

  const lightboxCaptures = useMemo<Capture[]>(() => frames.map(frame => ({
    ...frame,
    uploaded: true,
  })), [frames])

  // Indstillinger
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [showSettings, setShowSettings] = useState(true)

  // Rendering
  const [job, setJob]           = useState<RenderJob | null>(null)
  const [rendering, setRendering] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Auto-hent når filtre ændres ──────────────────────────────────────────
  useEffect(() => {
    if (frames.length > 0) loadFrames()
  }, [settings.day_night, settings.min_brightness, settings.max_brightness, settings.min_blur, settings.quality_only])

  // ── Hent frames ────────────────────────────────────────────────────────────

  const loadFrames = useCallback(async () => {
    if (!deviceId) return
    setLoading(true)
    setLoadError(null)
    setFrames([])
    setExcluded(new Set())
    try {
      const start = new Date(startTime).toISOString()
      const end   = new Date(endTime).toISOString()
      const params = new URLSearchParams({
        device_id: deviceId!,
        start, end,
        min_blur: String(settings.min_blur),
        quality_only: String(settings.quality_only),
        min_brightness: String(settings.min_brightness),
        max_brightness: String(settings.max_brightness),
        day_night: settings.day_night,
      })
      const data = await apiCall(`/api/timelapse/frames?${params}`)
      setFrames(data)
      // Auto-ekskluder billeder med lav blur
      if (settings.min_blur === 0) {
        const autoExclude = new Set<number>(
          data.filter((f: Frame) => f.quality_passed === false).map((f: Frame) => f.id)
        )
        setExcluded(autoExclude)
      }
    } catch (e: any) {
      setLoadError(e.message ?? 'Fejl ved hentning af billeder')
    } finally {
      setLoading(false)
    }
  }, [deviceId, startTime, endTime, settings.min_blur, settings.quality_only, settings.day_night, settings.min_brightness, settings.max_brightness])

  // ── Toggle frame ───────────────────────────────────────────────────────────

  function toggleFrame(id: number) {
    setExcluded(prev => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
  }

  function excludeAllFailed() {
    setExcluded(new Set(frames.filter(f => !f.quality_passed).map(f => f.id)))
  }

  function includeAll() {
    setExcluded(new Set())
    setAiNote('')
  }

  async function applyAiSelection() {
    if (!aiQuery.trim() || frames.length === 0) return
    setAiSelecting(true)
    try {
      const data = await apiCall('/api/ai/captures/natural-search', {
        method: 'POST',
        body: JSON.stringify({
          query: aiQuery,
          purpose: 'timelapse',
          device_id: deviceId,
          candidate_ids: frames.map(f => f.id),
          limit: Math.min(frames.length, 500),
        }),
      })
      const selected = new Set<number>((data.selected_ids ?? data.capture_ids ?? []).map((id: any) => Number(id)))
      if (selected.size === 0) {
        setAiNote('AI fandt ingen billeder i det aktuelle udvalg. Prøv at gøre søgningen bredere.')
      } else {
        setExcluded(new Set(frames.filter(f => !selected.has(f.id)).map(f => f.id)))
        setAiNote(data.selection?.explanation || `AI valgte ${selected.size} af ${frames.length} billeder`)
      }
    } catch (e: any) {
      setAiNote(`AI-udvalg fejlede: ${e.message ?? 'ukendt fejl'}`)
    } finally {
      setAiSelecting(false)
    }
  }

  // ── Beregn statistik ───────────────────────────────────────────────────────

  const selectedFrames = frames.filter(f => !excluded.has(f.id))
  const duration_s     = selectedFrames.length / settings.fps
  const failedCount    = frames.filter(f => !f.quality_passed).length

  // ── Start render ───────────────────────────────────────────────────────────

  async function startRender() {
    if (selectedFrames.length < 2) return
    setRendering(true)
    setJob(null)
    try {
      const result = await apiCall('/api/timelapse/create', {
        method: 'POST',
        body: JSON.stringify({
          device_id:          deviceId,
          frame_ids:          selectedFrames.map(f => f.id),
          fps:                settings.fps,
          resolution:         settings.resolution,
          codec:              settings.codec,
          deflicker:          settings.deflicker,
          fade_frames:        settings.fade_frames,
          timestamp_overlay:  settings.timestamp_overlay,
          timestamp_position: settings.timestamp_position,
          timestamp_format:   settings.timestamp_format,
          stabilization:      settings.stabilization,
          denoise:            settings.denoise,
          sharpen:            settings.sharpen,
          ken_burns:          settings.ken_burns,
          crop_ratio:         settings.crop_ratio,
          title:              settings.title || 'timelapse',
        })
      })
      setJob({ ...result, status: 'queued', progress: 0, error: null, title: settings.title })
      // Poll status
      pollRef.current = setInterval(async () => {
        try {
          const status = await apiCall(`/api/timelapse/status/${result.job_id}`)
          setJob(s => ({ ...s, ...status }))
          if (status.status === 'done' || status.status === 'error') {
            clearInterval(pollRef.current!)
            setRendering(false)
          }
        } catch {
          clearInterval(pollRef.current!)
          setRendering(false)
        }
      }, 1000)
    } catch (e: any) {
      setRendering(false)
      alert('Render fejlede: ' + (e.message ?? 'Ukendt fejl'))
    }
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const apiUrl = getApiUrl()

  // ── UI ─────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {lightboxIndex !== null && (
        <Lightbox
          captures={lightboxCaptures}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}

      {/* Header */}
      <div className="border-b border-white/10 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to={`/devices/${pathSegment(deviceId ?? '')}`} className="text-white/40 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <Film className="w-5 h-5 text-sky-400" />
          <h1 className="font-semibold text-sm">Timelapse Video</h1>
          <span className="text-white/30 text-xs font-mono">{deviceId}</span>
        </div>
      </div>

      <div className="max-w-screen-2xl mx-auto px-4 py-6 grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-6">

        {/* ── Venstre panel: Indstillinger ──────────────────────────────── */}
        <div className="space-y-4">

          {/* Tidsinterval */}
          <div className="bg-gray-900 rounded-2xl p-4 border border-white/8 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Clock className="w-4 h-4 text-sky-400" />
              Tidsinterval
            </div>
            <div className="space-y-2">
              <div>
                <label className="text-xs text-white/40 block mb-1">Start</label>
                <input type="datetime-local" value={startTime} onChange={e => setStartTime(e.target.value)}
                  className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500/50" />
              </div>
              <div>
                <label className="text-xs text-white/40 block mb-1">Slut</label>
                <input type="datetime-local" value={endTime} onChange={e => setEndTime(e.target.value)}
                  className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500/50" />
              </div>
            </div>
            <div className="flex gap-2">
              <label className="flex items-center gap-2 text-xs text-white/60 cursor-pointer">
                <input type="checkbox" checked={settings.quality_only}
                  onChange={e => setSettings(s => ({...s, quality_only: e.target.checked}))}
                  className="w-3.5 h-3.5 rounded accent-sky-500" />
                Kun godkendte
              </label>
              <div className="flex-1" />
              <label className="text-xs text-white/40">Min blur</label>
              <input type="number" value={settings.min_blur} min={0} max={1000}
                onChange={e => setSettings(s => ({...s, min_blur: Number(e.target.value)}))}
                className="w-20 bg-gray-800 border border-white/10 rounded-lg px-2 py-1 text-xs text-white text-right" />
            </div>
            <button onClick={loadFrames} disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm rounded-xl py-2.5 transition-colors cursor-pointer font-medium">
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              {loading ? 'Henter…' : 'Hent billeder'}
            </button>
          </div>

          {/* Video indstillinger */}
          <div className="bg-gray-900 rounded-2xl border border-white/8">
            <button onClick={() => setShowSettings(s => !s)}
              className="w-full flex items-center justify-between p-4 cursor-pointer">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Settings2 className="w-4 h-4 text-purple-400" />
                Video indstillinger
              </div>
              {showSettings ? <ChevronUp className="w-4 h-4 text-white/40" /> : <ChevronDown className="w-4 h-4 text-white/40" />}
            </button>
            {showSettings && (
              <div className="px-4 pb-4 space-y-3 border-t border-white/8 pt-3">

                {/* Titel */}
                <div>
                  <label className="text-xs text-white/40 block mb-1">Titel / filnavn</label>
                  <input type="text" value={settings.title}
                    onChange={e => setSettings(s => ({...s, title: e.target.value}))}
                    className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white" />
                </div>

                {/* FPS */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Frames per sekund (FPS)</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {[12, 24, 25, 30, 60].map(f => (
                      <button key={f} onClick={() => setSettings(s => ({...s, fps: f}))}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.fps === f ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Opløsning */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Opløsning</label>
                  <div className="flex gap-1.5">
                    {(['1080p', '4k', 'original'] as const).map(r => (
                      <button key={r} onClick={() => setSettings(s => ({...s, resolution: r}))}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.resolution === r ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                        {r === 'original' ? 'Original' : r.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Codec */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Format</label>
                  <div className="flex gap-1.5">
                    <button onClick={() => setSettings(s => ({...s, codec: 'h264'}))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.codec === 'h264' ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                      H.264 (web)
                    </button>
                    <button onClick={() => setSettings(s => ({...s, codec: 'h265'}))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.codec === 'h265' ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                      H.265 (arkiv)
                    </button>
                  </div>
                </div>

                {/* Beskæring */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Billedformat</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {(['16:9', '4:3', '1:1', 'original'] as const).map(r => (
                      <button key={r} onClick={() => setSettings(s => ({...s, crop_ratio: r}))}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.crop_ratio === r ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                        {r}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Lysstyrke filter */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Lysstyrke filter</label>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-white/30 w-6">Min</span>
                      <input type="range" min={0} max={254} value={settings.min_brightness}
                        onChange={e => setSettings(s => ({...s, min_brightness: Number(e.target.value)}))}
                        className="flex-1 accent-sky-500" />
                      <span className="text-xs text-white/60 w-8 text-right">{settings.min_brightness}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-white/30 w-6">Max</span>
                      <input type="range" min={1} max={255} value={settings.max_brightness}
                        onChange={e => setSettings(s => ({...s, max_brightness: Number(e.target.value)}))}
                        className="flex-1 accent-sky-500" />
                      <span className="text-xs text-white/60 w-8 text-right">{settings.max_brightness}</span>
                    </div>
                  </div>
                </div>

                {/* Dag/nat filter */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Dag / nat filter</label>
                  <div className="flex gap-1.5">
                    {([['all','Alle'],['day','☀️ Kun dag'],['night','🌙 Kun nat']] as const).map(([v,l]) => (
                      <button key={v} onClick={() => setSettings(s => ({...s, day_night: v}))}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.day_night === v ? 'bg-amber-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Fade */}
                <div>
                  <label className="text-xs text-white/40 block mb-1">Fade in/ud (frames)</label>
                  <div className="flex gap-2 items-center">
                    <input type="range" min={0} max={60} step={5} value={settings.fade_frames}
                      onChange={e => setSettings(s => ({...s, fade_frames: Number(e.target.value)}))}
                      className="flex-1 accent-sky-500" />
                    <span className="text-xs text-white/60 w-8 text-right">{settings.fade_frames}</span>
                  </div>
                </div>

                {/* Ken Burns */}
                <div>
                  <label className="text-xs text-white/40 block mb-1.5">Ken Burns effekt</label>
                  <div className="flex gap-1.5">
                    {([['none','Ingen'],['zoom_in','Zoom ind'],['zoom_out','Zoom ud']] as const).map(([v,l]) => (
                      <button key={v} onClick={() => setSettings(s => ({...s, ken_burns: v}))}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings.ken_burns === v ? 'bg-purple-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Fotografisk efterbehandling */}
                <div className="space-y-3 border-t border-white/10 pt-3">
                  <div className="text-xs font-medium text-white/70">Fotografisk efterbehandling</div>
                  {([
                    ['stabilization', 'Stabilisering'],
                    ['denoise', 'Støjreduktion'],
                    ['sharpen', 'Skarphed'],
                  ] as const).map(([key, label]) => (
                    <div key={key}>
                      <label className="text-xs text-white/40 block mb-1.5">{label}</label>
                      <div className="flex gap-1.5">
                        {([['none', 'Ingen'], ['light', 'Let'], ['strong', 'Kraftig']] as const).map(([value, text]) => (
                          <button
                            key={value}
                            onClick={() => setSettings(s => ({...s, [key]: value}))}
                            className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${settings[key] === value ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50 hover:text-white'}`}
                          >
                            {text}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Checkboxes */}
                <div className="space-y-2 pt-1">
                  <label className="flex items-center gap-2 text-xs text-white/70 cursor-pointer">
                    <input type="checkbox" checked={settings.deflicker}
                      onChange={e => setSettings(s => ({...s, deflicker: e.target.checked}))}
                      className="w-3.5 h-3.5 rounded accent-purple-500" />
                    Deflicker (udjævn lys)
                  </label>
                  <label className="flex items-center gap-2 text-xs text-white/70 cursor-pointer">
                    <input type="checkbox" checked={settings.timestamp_overlay}
                      onChange={e => setSettings(s => ({...s, timestamp_overlay: e.target.checked}))}
                      className="w-3.5 h-3.5 rounded accent-purple-500" />
                    Tidsstempel overlay
                  </label>
                  {settings.timestamp_overlay && (
                    <div className="ml-5 space-y-2">
                      <div className="flex gap-1.5">
                        {([['tl','↖'],['tr','↗'],['bl','↙'],['br','↘']] as const).map(([v,l]) => (
                          <button key={v} onClick={() => setSettings(s => ({...s, timestamp_position: v}))}
                            className={`w-8 h-8 rounded-lg text-sm transition-colors cursor-pointer ${settings.timestamp_position === v ? 'bg-sky-600 text-white' : 'bg-gray-800 text-white/50'}`}>
                            {l}
                          </button>
                        ))}
                      </div>
                      <div className="flex gap-1.5">
                        <button onClick={() => setSettings(s => ({...s, timestamp_format: 'pts'}))}
                          className={`flex-1 py-1 rounded-lg text-xs cursor-pointer ${settings.timestamp_format === 'pts' ? 'bg-purple-600 text-white' : 'bg-gray-800 text-white/50'}`}>
                          Sekunder
                        </button>
                        <button onClick={() => setSettings(s => ({...s, timestamp_format: 'datetime'}))}
                          className={`flex-1 py-1 rounded-lg text-xs cursor-pointer ${settings.timestamp_format === 'datetime' ? 'bg-purple-600 text-white' : 'bg-gray-800 text-white/50'}`}>
                          Dato/tid
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Render knap + status */}
          {frames.length > 0 && (
            <div className="bg-gray-900 rounded-2xl p-4 border border-white/8 space-y-3">
              <div className="border border-sky-400/20 bg-sky-950/30 rounded-xl p-3 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-sky-200">
                  <Brain className="w-4 h-4" />
                  AI-udvalg til timelapse
                </div>
                <textarea
                  className="w-full bg-gray-950/80 border border-white/10 rounded-lg px-3 py-2 text-sm text-white resize-none outline-none focus:border-sky-400/60"
                  rows={3}
                  placeholder="f.eks. vælg de bedste skarpe billeder med byggeaktivitet uden regn og fordel dem jævnt"
                  value={aiQuery}
                  onChange={e => setAiQuery(e.target.value)}
                />
                <button
                  onClick={applyAiSelection}
                  disabled={aiSelecting || !aiQuery.trim()}
                  className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white text-sm rounded-lg py-2 transition-colors"
                >
                  {aiSelecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Anvend AI-udvalg
                </button>
                {aiNote && <p className="text-xs text-sky-200/80">{aiNote}</p>}
              </div>

              {/* Sammenfatning */}
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-gray-800/60 rounded-xl py-2.5">
                  <div className="text-lg font-bold text-white">{selectedFrames.length}</div>
                  <div className="text-[10px] text-white/40 uppercase tracking-wider">billeder</div>
                </div>
                <div className="bg-gray-800/60 rounded-xl py-2.5">
                  <div className="text-lg font-bold text-white">{settings.fps}</div>
                  <div className="text-[10px] text-white/40 uppercase tracking-wider">fps</div>
                </div>
                <div className="bg-gray-800/60 rounded-xl py-2.5">
                  <div className="text-lg font-bold text-white">{fmtDuration(duration_s)}</div>
                  <div className="text-[10px] text-white/40 uppercase tracking-wider">varighed</div>
                </div>
              </div>

              {excluded.size > 0 && (
                <p className="text-xs text-amber-400/80 text-center">{excluded.size} billeder ekskluderet</p>
              )}

              {/* Render knap */}
              {!job || job.status === 'error' ? (
                <button onClick={startRender}
                  disabled={rendering || selectedFrames.length < 2}
                  className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl py-3 transition-colors cursor-pointer">
                  {rendering ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Video className="w-4 h-4" />}
                  {rendering ? 'Forbereder…' : 'Render video'}
                </button>
              ) : null}

              {/* Progress */}
              {job && job.status !== 'error' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-white/60">
                      {job.status === 'queued' && 'Klar i kø…'}
                      {job.status === 'rendering' && `Renderer… ${job.progress}%`}
                      {job.status === 'done' && '✅ Færdig!'}
                    </span>
                    {job.status === 'rendering' && (
                      <span className="text-white/40">{job.progress}%</span>
                    )}
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                      style={{width: `${job.progress}%`}} />
                  </div>
                  {job.status === 'done' && (
                    <div className="space-y-2">
                      <a href={`${apiUrl}/api/timelapse/download/${job.job_id}`}
                        className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm rounded-xl py-2.5 transition-colors">
                        <Download className="w-4 h-4" />
                        Download MP4 {job.filesize_mb ? `(${job.filesize_mb} MB)` : ''}
                      </a>
                      <button onClick={() => { setJob(null); setRendering(false) }}
                        className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-white/70 text-sm rounded-xl py-2 transition-colors cursor-pointer">
                        + Lav ny video
                      </button>
                    </div>
                  )}
                </div>
              )}

              {job?.status === 'error' && (
                <div className="space-y-2">
                  <div className="bg-red-950/50 border border-red-800/50 rounded-xl p-3 text-xs text-red-300">
                    <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />
                    {job.error}
                  </div>
                  <button onClick={() => { setJob(null); setRendering(false) }}
                    className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-white/70 text-sm rounded-xl py-2 transition-colors cursor-pointer">
                    + Prøv igen med nye indstillinger
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Højre panel: Filmstrip ─────────────────────────────────────── */}
        <div className="space-y-4">

          {loadError && (
            <div className="bg-red-950/30 border border-red-800/40 rounded-2xl p-4 text-sm text-red-300">
              <AlertTriangle className="w-4 h-4 inline mr-2" />
              {loadError}
            </div>
          )}

          {frames.length === 0 && !loading && !loadError && (
            <div className="bg-gray-900/50 rounded-2xl border border-white/8 p-16 text-center">
              <Film className="w-12 h-12 text-white/10 mx-auto mb-3" />
              <p className="text-white/30 text-sm">Vælg et tidsinterval og klik "Hent billeder"</p>
            </div>
          )}

          {frames.length > 0 && (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm text-white/60">
                  <span className="text-white font-medium">{frames.length}</span> billeder fundet
                  {failedCount > 0 && (
                    <span className="text-red-400/80 ml-2">· {failedCount} fejlede</span>
                  )}
                </span>
                <div className="flex-1" />
                {failedCount > 0 && (
                  <button onClick={excludeAllFailed}
                    className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1 cursor-pointer">
                    <EyeOff className="w-3.5 h-3.5" />
                    Ekskluder fejlede
                  </button>
                )}
                {excluded.size > 0 && (
                  <button onClick={includeAll}
                    className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1 cursor-pointer">
                    <Eye className="w-3.5 h-3.5" />
                    Inkluder alle
                  </button>
                )}
              </div>

              {/* Virtuel grid — renderer KUN synlige frames, så 21.000+ ikke vælter browseren */}
              <VirtualImageGrid
                count={frames.length}
                minColWidth={140}
                gap={6}
                footerHeight={70}
                renderItem={(idx) => {
                  const frame = frames[idx]
                  const isExcluded = excluded.has(frame.id)
                  return (
                    <div
                      className={`h-full w-full ${isExcluded ? 'scale-[0.98]' : ''} transition-transform`}
                      title={`${fmtDate(frame.captured_at)}\nFrame ${idx + 1}`}
                    >
                      <CaptureThumbnailCard
                        capture={{ ...frame, uploaded: true }}
                        compact
                        selected={isExcluded}
                        showFileSize={false}
                        onClick={() => setLightboxIndex(idx)}
                        overlay={isExcluded ? (
                          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-red-950/10">
                            <X className="h-10 w-10 text-red-500 drop-shadow-[0_1px_2px_rgba(255,255,255,0.9)]" strokeWidth={3} />
                          </div>
                        ) : null}
                        footerAction={(
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              toggleFrame(frame.id)
                            }}
                            className={`flex min-h-6 w-full items-center justify-center gap-1 rounded border px-1.5 text-[10px] font-semibold leading-none transition-colors ${
                              isExcluded
                                ? 'border-red-300 bg-red-600 text-white'
                                : 'border-emerald-300 bg-emerald-600 text-white hover:bg-emerald-500'
                            }`}
                            title={isExcluded ? 'Inkluder billedet i videoen' : 'Ekskluder billedet fra videoen'}
                            aria-label={isExcluded ? 'Inkluder billedet i videoen' : 'Ekskluder billedet fra videoen'}
                          >
                            {isExcluded ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            {isExcluded ? 'Fravalgt' : 'Medtaget'}
                          </button>
                        )}
                      />
                    </div>
                  )
                }}
              />

              <p className="text-xs text-white/30 text-center">
                Klik på et billede for fuld størrelse. Brug øje-knappen til at inkludere eller ekskludere det.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
