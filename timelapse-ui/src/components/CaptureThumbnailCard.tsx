import { useEffect, useState, useRef } from 'react'
import { Image } from 'lucide-react'
import { getThumbnailUrl, requestThumbnailGeneration } from '../api/client'
import { acquireImageSlot, observeInView } from '../lib/imageLoadGate'
import { useTagLabels, tagLabel } from '../hooks/useTagLabels'
import type { Capture } from '../types'

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

export function parseCaptureAI(capture: any, sidecar?: any): Record<string, any> | null {
  if (sidecar?.ai_analysis) return sidecar.ai_analysis
  if (!capture.ai_result) return null
  try { return JSON.parse(capture.ai_result) } catch { return null }
}

export function parseEdgeQA(capture: any, sidecar?: any): Record<string, any> | null {
  if (sidecar?.edge_qa) return sidecar.edge_qa
  if (!capture.ai_result) return null
  try {
    const parsed = JSON.parse(capture.ai_result)
    if (parsed?.edge_ai) return parsed.edge_ai
    if (parsed?.source === 'edge') return parsed
  } catch {
    return null
  }
  return null
}

export function parseCaptureQA(capture: any, sidecar?: any): Record<string, any> | null {
  return parseEdgeQA(capture, sidecar) ?? parseCaptureAI(capture, sidecar)
}

function filenameParts(filename: string) {
  const fn = filename.replace(/\.[^.]+$/, '')
  const parts = fn.split('_')
  const dateIdx = parts.findIndex((p: string) => /^\d{8}$/.test(p))
  const nameParts = dateIdx > 0 ? parts.slice(0, dateIdx) : parts
  return {
    customer: nameParts[0] ?? '',
    site: nameParts.slice(1, -2).join(' '),
    camera: nameParts.slice(-2).join(' '),
  }
}

// 2026-07-07 (Claude, Peters fototekniske gennemgang): "Dansk" navnegivet
// oversættelse af probable_cause → menneskelæsbar label. Delt mellem
// CaptureThumbnailCard og DevicePage, så de to steder ikke kan drifte fra
// hinanden (var tidligere duplikeret lokalt i DevicePage.tsx).
export const causeLabels: Record<string, string> = {
  ok: 'OK', condensation_on_lens: 'Kondens på linse',
  dirty_lens: 'Snavset linse', focus_drift: 'Fokusdrift',
  camera_moved: 'Kamera flyttet', obstruction: 'Afskærmning',
  rain_on_lens: 'Regn på linse', sun_flare: 'Solreflektion',
  night_capture: 'Natkamera', hardware_failure: 'Hardwarefejl',
  focus_or_lens_issue: 'Fokus/linse-problem',
  snow_or_dirt_on_lens: 'Sne/skidt på frontglas',
  condensation_or_soft_lens_obstruction: 'Dug/kondens/blød linse',
  direct_sun_reflection: 'Direkte sol/refleks',
  underexposure_or_camera_blocked: 'Undereksponeret/blokeret',
  overexposure_or_direct_sun: 'Overeksponeret/sol',
  depth_of_field_issue: 'Dybdeskarphed/fokus',
  white_balance_cast: 'Hvidbalance-farvestik',
  qa_analysis_error: 'QA-analysefejl',
  file_integrity_error: 'Filfejl',
  unknown: 'Ukendt',
}

// 2026-07-07 (Claude): skelner mellem en REEL QA-fejl (den deterministiske
// OpenCV-test i edge/capture/quality.py fejlede: flag != 'ok' / passed ===
// false / quality_ok === false) og en BLØD anbefaling fra den autonome
// optimizer (is_anomaly === true, men selve billedet bestod fint). Se
// edge_qa_npu_runner.py linje 93: `is_anomaly = bool(recs)` — is_anomaly
// betyder kun "optimizeren har en anbefaling", ikke "billedet er dårligt".
// Peter fangede at et billede med flag=ok og "excellent"-score alligevel
// fik en advarselstrekant, fordi UI kun kiggede på is_anomaly. Denne
// funktion er den fælles kilde til sandhed for "er dette en REEL fejl".
export function qaHardFailed(ai: Record<string, any> | null): boolean {
  if (!ai) return false
  if (ai.alarm) return true
  if (ai.passed === false) return true
  if (typeof ai.flag === 'string' && ai.flag !== 'ok') return true
  if (ai.quality_ok === false) return true
  if (typeof ai.quality_flag === 'string' && !['ok', 'clear_image'].includes(ai.quality_flag)) return true
  return false
}

function qaBadge(ai: Record<string, any> | null) {
  if (!ai) return null
  if (ai.alarm) {
    return <span title={ai.description ?? 'QA alarm'} className="text-xs flex-shrink-0 cursor-help">🚨</span>
  }
  if (qaHardFailed(ai)) {
    return <span title={ai.description ?? 'QA afvigelse'} className="text-xs flex-shrink-0 cursor-help">⚠️</span>
  }
  if (ai.probable_cause === 'ok' || ai.scene_dk || ai.quality_flag) {
    return (
      <span
        title={ai.scene_dk ? `AI: ${ai.scene_dk}` : 'QA: OK'}
        className="text-[9px] flex-shrink-0 text-emerald-600 font-bold cursor-help"
      >
        QA✓
      </span>
    )
  }
  return null
}

// Blød optimizer-anbefaling (is_anomaly=true, men IKKE en reel QA-fejl) —
// vises som en almindelig tag-chip i stedet for en advarselstrekant, som
// Peter bad om. Kun for edge-kilden, hvor probable_cause findes.
function qaSoftTag(ai: Record<string, any> | null) {
  if (!ai || qaHardFailed(ai) || !ai.is_anomaly) return null
  const cause = ai.probable_cause
  if (!cause || cause === 'ok') return null
  return (
    <span
      title={ai.recommended_action ?? ai.description ?? 'Optimizer-anbefaling (ikke en QA-fejl)'}
      className="text-[9px] bg-sky-50 text-sky-600 px-1 py-0.5 rounded-full flex-shrink-0 cursor-help"
    >
      💡 {causeLabels[cause] ?? cause}
    </span>
  )
}

export function CaptureThumbnailCard({
  capture,
  onClick,
  selected = false,
  overlay,
  compact = false,
}: {
  capture: Capture
  onClick: () => void
  selected?: boolean
  overlay?: React.ReactNode
  compact?: boolean
}) {
  const time = capture.captured_at
    ? new Date(capture.captured_at).toLocaleString('da-DK', { timeZone: getTz(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '-'
  const passed = capture.quality_passed !== false
  const thumbUrl = getThumbnailUrl(capture.device_id, capture.filename)
  const [imgOk, setImgOk] = useState(true)
  const [repairState, setRepairState] = useState<'idle' | 'queued' | 'failed'>('idle')
  const [refresh, setRefresh] = useState(0)
  const retryCount = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const releaseRef = useRef<null | (() => void)>(null)
  const [inView, setInView] = useState(false)
  const [loadSrc, setLoadSrc] = useState<string | null>(null)
  const ai = parseCaptureQA(capture)
  const parts = filenameParts(capture.filename)
  const imgSrc = refresh > 0 ? `${thumbUrl}?repair=${refresh}` : thumbUrl
  const tagLabels = useTagLabels()

  useEffect(() => {
    setImgOk(true)
    setRepairState('idle')
    setRefresh(0)
    retryCount.current = 0
    setLoadSrc(null)
    if (releaseRef.current) { releaseRef.current(); releaseRef.current = null }
  }, [thumbUrl])

  // Lazy-load via ÉN DELT IntersectionObserver (ikke én pr. kort) — så et grid med
  // mange tusinde kort (Timelapse Video) ikke vælter browseren.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    return observeInView(el, () => setInView(true))
  }, [])

  // Når kortet er i syne (og billedet ikke er fejlet): tag en samtidigheds-slot
  // FØR vi sætter src. Det er det der begrænser belastningen på backenden til
  // maks N samtidige thumbnail-requests og forhindrer 503-stormen.
  useEffect(() => {
    if (!inView || !imgOk) return
    let cancelled = false
    acquireImageSlot().then((release) => {
      if (cancelled) { release(); return }
      releaseRef.current = release
      setLoadSrc(imgSrc)
    })
    return () => {
      cancelled = true
      if (releaseRef.current) { releaseRef.current(); releaseRef.current = null }
    }
  }, [inView, imgSrc, imgOk])

  // Ved billed-fejl: et tæt galleri overbelaster backenden → nginx 503. Thumbnailen
  // FINDES; serveren er bare presset. Prøv derfor den SAMME thumbnail igen med spredt
  // (jittered) backoff i stedet for straks at fyre en tung /generate — det er præcis
  // det der ellers forstærker stormen og holder serveren nede. Først efter flere
  // forgæves forsøg antager vi at den måske faktisk mangler, og beder om generering.
  const MAX_RETRY = 4
  const onImgError = () => {
    if (retryCount.current < MAX_RETRY) {
      retryCount.current += 1
      const delay = 700 * retryCount.current + Math.random() * 800
      window.setTimeout(() => setRefresh(r => r + 1), delay)
      return
    }
    requestRepair()
  }

  const requestRepair = async () => {
    if (repairState !== 'idle') {
      setImgOk(false)
      return
    }
    setRepairState('queued')
    setImgOk(false)
    try {
      const response = await requestThumbnailGeneration(capture.device_id, capture.filename)
      if (response?.status === 'ready') {
        setImgOk(true)
        setRefresh(r => r + 1)
        return
      }
      for (const delay of [1500, 3000, 6000]) {
        window.setTimeout(() => {
          setImgOk(true)
          setRefresh(r => r + 1)
        }, delay)
      }
      window.setTimeout(() => {
        setRepairState(current => current === 'queued' ? 'failed' : current)
      }, 8000)
    } catch {
      setRepairState('failed')
    }
  }

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      className={`rounded-xl border overflow-hidden bg-white cursor-pointer hover:ring-2 hover:ring-sky-300 transition-all ${
        selected ? 'ring-2 ring-red-400 border-red-300' : passed ? 'border-gray-200' : 'border-red-200'
      }`}
    >
      <div className="aspect-video bg-slate-100 relative overflow-hidden flex items-center justify-center">
        {!imgOk ? (
          <div className="flex flex-col items-center gap-1 text-slate-300">
            <Image className="w-8 h-8" />
            {repairState === 'queued' && <span className="text-[10px] text-slate-400">Genererer...</span>}
            {repairState === 'failed' && <span className="text-[10px] text-slate-400">Mangler thumbnail</span>}
          </div>
        ) : loadSrc ? (
          <img
            src={loadSrc}
            alt={capture.filename}
            className="w-full h-full object-cover"
            onLoad={() => { setRepairState('idle'); retryCount.current = 0; releaseRef.current?.(); releaseRef.current = null }}
            onError={() => { releaseRef.current?.(); releaseRef.current = null; onImgError() }}
          />
        ) : (
          // Statisk placeholder (INGEN animate-pulse): ved 21.000 kort ville tusindvis
          // af samtidige CSS-animationer vælte browseren.
          <div className="w-full h-full bg-slate-100" />
        )}
        <span className="absolute bottom-1.5 right-1.5 text-xs bg-black/50 text-white px-1 py-0.5 rounded">
          {capture.filesize_mb ? `${capture.filesize_mb} MB` : '-'}
        </span>
        {!passed && <span className="absolute top-1.5 left-1.5 text-xs bg-red-500 text-white px-1.5 py-0.5 rounded">Fejlet</span>}
        {overlay}
      </div>
      <div className="px-2 py-1.5">
        <div className="flex items-center justify-between gap-1">
          <p className="text-xs font-medium text-gray-700">{time}</p>
          {capture.blur_score != null && (
            <p className={`text-xs font-medium flex-shrink-0 ${capture.blur_score < 80 ? 'text-amber-500' : 'text-gray-400'}`}>
              ⬡ {Math.round(capture.blur_score)}
            </p>
          )}
          {qaBadge(ai)}
        </div>

        {!compact && (
          <>
            <div className="border-t border-gray-100 pt-1 mt-1">
              <p className="text-xs font-bold text-gray-900 leading-tight truncate">{parts.customer}</p>
              <p className="text-xs text-gray-800 leading-tight mt-0.5 truncate">{parts.site}</p>
              <p className="text-xs text-gray-700 leading-tight mt-0.5 truncate">{parts.camera}</p>
            </div>
            {(qaSoftTag(ai) || (capture.ai_tags && capture.ai_tags.length > 0)) && (
              <div className="flex flex-wrap gap-0.5 mt-1">
                {qaSoftTag(ai)}
                {capture.ai_tags?.slice(0, 3).map((t: string) => (
                  <span key={t} className="text-[9px] bg-gray-100 text-gray-500 px-1 py-0.5 rounded-full">#{tagLabel(t, tagLabels)}</span>
                ))}
                {capture.ai_tags && capture.ai_tags.length > 3 && (
                  <span className="text-[9px] text-gray-400">+{capture.ai_tags.length - 3}</span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
