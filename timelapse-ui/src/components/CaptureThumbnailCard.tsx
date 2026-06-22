import { useEffect, useState } from 'react'
import { Image } from 'lucide-react'
import { getThumbnailUrl, requestThumbnailGeneration } from '../api/client'
import { useTagLabels, tagLabel } from '../hooks/useTagLabels'
import type { Capture } from '../types'

const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

export function parseCaptureAI(capture: any, sidecar?: any): Record<string, any> | null {
  if (sidecar?.ai_analysis) return sidecar.ai_analysis
  if (!capture.ai_result) return null
  try { return JSON.parse(capture.ai_result) } catch { return null }
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

function qaBadge(ai: Record<string, any> | null) {
  if (!ai) return null
  if (ai.alarm) {
    return <span title={ai.description ?? 'QA alarm'} className="text-xs flex-shrink-0 cursor-help">🚨</span>
  }
  if (ai.is_anomaly) {
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
  const ai = parseCaptureAI(capture)
  const parts = filenameParts(capture.filename)
  const imgSrc = refresh > 0 ? `${thumbUrl}?repair=${refresh}` : thumbUrl
  const tagLabels = useTagLabels()

  useEffect(() => {
    setImgOk(true)
    setRepairState('idle')
    setRefresh(0)
  }, [thumbUrl])

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
      onClick={onClick}
      className={`rounded-xl border overflow-hidden bg-white cursor-pointer hover:ring-2 hover:ring-sky-300 transition-all ${
        selected ? 'ring-2 ring-red-400 border-red-300' : passed ? 'border-gray-200' : 'border-red-200'
      }`}
    >
      <div className="aspect-video bg-slate-100 relative overflow-hidden flex items-center justify-center">
        {imgOk ? (
          <img
            src={imgSrc}
            alt={capture.filename}
            className="w-full h-full object-cover"
            loading="lazy"
            onLoad={() => setRepairState('idle')}
            onError={requestRepair}
          />
        ) : (
          <div className="flex flex-col items-center gap-1 text-slate-300">
            <Image className="w-8 h-8" />
            {repairState === 'queued' && <span className="text-[10px] text-slate-400">Genererer...</span>}
            {repairState === 'failed' && <span className="text-[10px] text-slate-400">Mangler thumbnail</span>}
          </div>
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
            {capture.ai_tags && capture.ai_tags.length > 0 && (
              <div className="flex flex-wrap gap-0.5 mt-1">
                {capture.ai_tags.slice(0, 3).map((t: string) => (
                  <span key={t} className="text-[9px] bg-gray-100 text-gray-500 px-1 py-0.5 rounded-full">#{tagLabel(t, tagLabels)}</span>
                ))}
                {capture.ai_tags.length > 3 && (
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
