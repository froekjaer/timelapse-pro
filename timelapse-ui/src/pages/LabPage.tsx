// ═══════════════════════════════════════════════════════════════
// LabPage.tsx
// Version: 5.2.0  |  12. april 2026
// ───────────────────────────────────────────────────────────────
// Changelog:
//   5.2.0  12-apr-2026  useParams fix, histogram stale closure fix
//   5.1.0  11-apr-2026  Histogram, preview polling
//   5.0.0  10-apr-2026  LAB mode komplet
// ═══════════════════════════════════════════════════════════════
// v5.1
import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Camera, FlaskConical, Power, PowerOff, RefreshCw,
  Lock, ChevronLeft, ZoomIn, ZoomOut, Settings, X, Check, Wifi, Crosshair, Wand2, Ban,
  Maximize, Minimize, Info, HelpCircle
} from 'lucide-react'
import {
  setDebugMode, requestPreview, requestCapture,
  setParam, listPreviews, getPreviewUrl, getPreviewThumbUrl,
  getDevice, pathSegment, getApiUrl,
  requestFocusDrive, requestAutofocus, requestFocusSlice, requestEdgeAiFocusTest
} from '../api/client'
import type { LabPreview, CameraParam, DebugMode, CameraProfile } from '../types'
// // import { useWebRTC } from '../hooks/useWebRTC' // F-013B/C: Replaced with Frame Push

function authFetch(url: string, opts?: RequestInit) {
  return fetch(url, { ...opts, credentials: 'include' })
}

function parseDeviceConfig(raw: unknown): Record<string, any> {
  if (!raw) return {}
  if (typeof raw !== 'string') return raw as Record<string, any>
  try { return JSON.parse(raw) } catch { return {} }
}

async function loadAdminDeviceConfig(deviceId: string): Promise<Record<string, any>> {
  const data = await getDevice(deviceId)
  return parseDeviceConfig((data as any)?.device_config ?? (data.device as any)?.device_config)
}

function readLabState(data: any) {
  const cfg = parseDeviceConfig(data?.device_config ?? data?.device?.device_config)
  const debugMode = cfg?.debug_mode ?? data?.debug_mode ?? data?.device?.debug_mode ?? null
  return {
    cfg,
    debugMode,
    debugEnabled: debugMode?.enabled === true,
    cameraReady: cfg?.lab_camera_ready === true || data?.lab_camera_ready === true || data?.device?.lab_camera_ready === true,
  }
}

// ── Kamera-parameter grupper ──────────────────────────────────────────────────
const PARAM_GROUPS: Record<string, string[]> = {
  'Eksponering':    ['/main/capturesettings/autoexposuremode', '/main/capturesettings/shutterspeed',
                    '/main/capturesettings/aperture', '/main/capturesettings/exposurecompensation',
                    '/main/capturesettings/meteringmode'],
  'ISO & Lys':      ['/main/imgsettings/iso', '/main/imgsettings/whitebalance',
                    '/main/capturesettings/picturestyle'],
  'Billedkvalitet': ['/main/imgsettings/imageformat', '/main/imgsettings/colorspace'],
  'Fokus':          ['/main/capturesettings/focusmode', '/main/actions/manualfocusdrive',
                    '/main/actions/autofocusdrive'],
  'Kamera-styring': ['/main/settings/capturetarget', '/main/settings/reviewtime',
                    '/main/actions/syncdatetime'],
  'Status':         ['/main/status/batterylevel', '/main/status/shuttercounter',
                    '/main/status/availableshots', '/main/status/lensname',
                    '/main/status/cameramodel'],
}

// ── Parameter beskrivelser (tooltips) ───────────────────────────────────────────
const PARAM_DESCRIPTIONS: Record<string, string> = {
  // Eksponering
  '/main/capturesettings/autoexposuremode': 'Eksponeringsmode. I Auto/Program styrer kameraet lukker/blænde automatisk. I Manual (M) har du fuld kontrol. Shutter/Aperture priority giver delvis kontrol.',
  '/main/capturesettings/shutterspeed': 'Lukkerhastighed i sekunder eller brøk (f.eks. 1/125). Hurtig = fryser bevægelse, langsom = motion blur. Kræver Manual eller Shutter Priority mode.',
  '/main/capturesettings/aperture': 'Blændeåbning (f-tal). Lav (f/3.5) = lysstærk + lille dybdeskarphed. Høj (f/11) = stor dybdeskarphed. Kræver Manual eller Aperture Priority mode.',
  '/main/capturesettings/exposurecompensation': 'EV kompensation ±. Justerer eksponering op/ned fra kameraets automatiske måling. Fungerer i alle auto/semi-auto modes.',
  '/main/capturesettings/meteringmode': 'Lysmåling. Matrix evaluere hele scenen. Center-weightet fokus på midten. Spot måler lille område omkring fokuspunkt.',
  // ISO & Lys
  '/main/imgsettings/iso': 'ISO følsomhed. Lav (100) = mindre støj men kræver lys. Høj (3200+) til svagt lys men introducerer støj/grain.',
  '/main/imgsettings/whitebalance': 'Hvidbalance. Auto justerer farvetemperatur automatisk. Daylight (5500K) til sol, Tungsten (3200K) til indendørs belysning.',
  '/main/capturesettings/picturestyle': 'Farveprofil. Neutral/Standard til timelapse (bedre post-processing). Landscape/Vivid øger mætning.',
  // Billedkvalitet
  '/main/imgsettings/imageformat': 'Filformat. RAW til fuld kontrol (stor fil). JPEG til komprimering. RAW+JPEG begge dele.',
  '/main/imgsettings/colorspace': 'Farverum. sRGB til skærme/web. Adobe RGB til print.',
  // Fokus
  '/main/capturesettings/focusmode': 'Fokusmode. Manual = du styrer. Autofokus = kameraet finder fokus. Kan være readonly hvis optaget ikke understøttes.',
  '/main/actions/manualfocusdrive': 'Manuel fokusjustering. Flytter fokus trinvis (-5 til +5). Brug til fine-tuning.',
  '/main/actions/autofocusdrive': 'Autofokus trigger. Kameraet søger og låser fokus automatisk.',
  // Kamera-styring
  '/main/settings/capturetarget': 'Hvor billeder gemmes. SD kort eller intern hukommelse.',
  '/main/settings/reviewtime': 'Hvor længe billedet vises på skærmen efter capture. 0-10 sekunder.',
  '/main/actions/syncdatetime': 'Synkroniser kameraets dato/tid med systemet.',
  // Status
  '/main/status/batterylevel': 'Batteriniveau i procent.',
  '/main/status/shuttercounter': 'Antal lukkercyklinger (total levetid).',
  '/main/status/availableshots': 'Estimerede billeder remaining på SD kort.',
  '/main/status/lensname': 'Navn på objektivet.',
  '/main/status/cameramodel': 'Kamera model.',
}

// ── Eksponeringsmode matrix ─────────────────────────────────────────────────────
// Viser hvilke parametre der er editable i hvilke modes
const EXPOSURE_MODE_MATRIX = {
  'Auto': { shutter: false, aperture: false, iso: false, ev: true, note: 'Alt er automatisk' },
  'Program (P)': { shutter: false, aperture: false, iso: false, ev: true, note: 'Kamera vælger lukker/blænde' },
  'Shutter Priority (S)': { shutter: true, aperture: false, iso: false, ev: true, note: 'Du styrer lukker' },
  'Aperture Priority (A)': { shutter: false, aperture: true, iso: false, ev: true, note: 'Du styrer blænde' },
  'Manual (M)': { shutter: true, aperture: true, iso: true, ev: true, note: 'Fuld manuel kontrol' },
}

// ── Histogram hook ────────────────────────────────────────────────────────────
function useHistogram(imgRef: React.RefObject<HTMLImageElement | null>) {
  const [hist, setHist] = useState<{ r: number[]; g: number[]; b: number[]; lum: number[] } | null>(null)
  const compute = useCallback(() => {
    const img = imgRef.current
    if (!img || !img.complete || !img.naturalWidth) return
    const canvas = document.createElement('canvas')
    const scale  = Math.min(1, 400 / Math.max(img.naturalWidth, img.naturalHeight))
    canvas.width  = Math.round(img.naturalWidth * scale)
    canvas.height = Math.round(img.naturalHeight * scale)
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
    const r = new Array(256).fill(0), g = new Array(256).fill(0)
    const b = new Array(256).fill(0), lum = new Array(256).fill(0)
    for (let i = 0; i < data.length; i += 4) {
      r[data[i]]++; g[data[i+1]]++; b[data[i+2]]++
      lum[Math.round(0.299*data[i] + 0.587*data[i+1] + 0.114*data[i+2])]++
    }
    setHist({ r, g, b, lum })
  }, [imgRef])
  return { hist, compute, clear: () => setHist(null) }
}

// ── Mini histogram display ────────────────────────────────────────────────────
function MiniHistogram({ hist }: { hist: { r: number[]; g: number[]; b: number[]; lum: number[] } }) {
  return (
    <div className="flex gap-4 items-end p-3 bg-black/60 rounded-xl w-full">
      {(['lum', 'r', 'g', 'b'] as const).map(ch => {
        const colors: Record<string, string> = { lum: '#d1d5db', r: '#f87171', g: '#4ade80', b: '#60a5fa' }
        const labels: Record<string, string> = { lum: 'L', r: 'R', g: 'G', b: 'B' }
        const data = hist[ch]
        const max  = Math.max(...data.slice(1, 255)) || 1
        const H = 56
        // Alarm grænse: bucket 60/64 ≈ pixel value 240 (overbelyst varsel)
        return (
          <div key={ch} className="flex flex-col items-center gap-1 flex-1">
            <div className="relative w-full" style={{ height: H + 12 }}>
              {/* Y-akse linje */}
              <div style={{
                position: 'absolute', left: 0, top: 0, width: 1,
                height: H, background: 'rgba(255,255,255,0.4)'
              }} />
              {/* X-akse linje */}
              <div style={{
                position: 'absolute', left: 0, top: H - 1, right: 0,
                height: 1, background: 'rgba(255,255,255,0.4)'
              }} />
              {/* Vandret clip-alarm linje øverst */}
              <div style={{
                position: 'absolute', left: 0, right: 0,
                top: 0, height: 2,
                background: '#fbbf24', opacity: 0.85,
              }} />
              {/* Bars */}
              <div className="absolute inset-0 flex items-end gap-px" style={{ height: H }}>
                {Array.from({ length: 64 }, (_, i) => {
                  const val = data.slice(i*4, i*4+4).reduce((a: number, b: number) => a + b, 0)
                  const h = Math.max(1, Math.round((val / max / 4) * H))
                  return <div key={i} style={{ flex: 1, height: h, background: colors[ch], opacity: 0.85 }} />
                })}
              </div>
              
            </div>
            <span style={{ fontSize: 11, color: colors[ch] }}>{labels[ch]}</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Parameter row ─────────────────────────────────────────────────────────────
function ParamRow({
  param, deviceId, onChanged
}: { param: CameraParam; deviceId: string; onChanged: () => void }) {
  const [editing, setEditing]   = useState(false)
  const [value, setValue]       = useState(param.current)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState('')

  async function save() {
    setSaving(true); setError('')
    try {
      await setParam(deviceId, param.path, value)
      setSaved(true)
      setTimeout(() => { setSaved(false); setEditing(false); }, 800)
      setTimeout(() => { onChanged() }, 1500)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Fejl'
      setError(msg)
      console.error('setParam error:', err)
    } finally {
      setSaving(false)
    }
  }

  const isReadonly = param.readonly || param.type === 'TEXT'
  const usableChoices = param.choices.filter(c => c.label && !/^unknown$/i.test(c.label.trim()))
  const hasChoices = usableChoices.length > 0
  const paramDesc = PARAM_DESCRIPTIONS[param.path]

  // Determine if readonly is due to exposure mode
  const isExposureRelated = param.path.includes('shutter') || param.path.includes('aperture') || param.path.includes('iso')
  const readonlyHint = isReadonly && isExposureRelated
    ? 'Skift til Manual (M) mode for at ændre denne parameter'
    : ''

  return (
    <div className={`flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors ${isReadonly ? 'opacity-60' : ''}`}>
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-gray-700 truncate">{param.label}</span>
            {paramDesc && (
              <span className="text-gray-400 hover:text-sky-600 cursor-help" title={paramDesc}>
                <HelpCircle className="w-3.5 h-3.5" />
              </span>
            )}
            {isReadonly && readonlyHint && (
              <span className="text-amber-600 hover:text-amber-700 cursor-help" title={readonlyHint}>
                <Lock className="w-3 h-3" />
              </span>
            )}
          </div>
          <div className="text-xs text-gray-400 truncate">{param.path}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {!editing ? (
          <>
            <span className={`text-sm px-2 py-0.5 rounded font-mono ${
              isReadonly ? 'text-gray-400 bg-gray-50' : 'text-sky-700 bg-sky-50'
            }`}>{param.current || '–'}</span>
            {!isReadonly && (
              <button onClick={() => { setValue(param.current); setEditing(true) }}
                className="p-1 text-gray-400 hover:text-sky-600 rounded">
                <Settings className="w-3.5 h-3.5" />
              </button>
            )}
          </>
        ) : (
          <div className="flex items-center gap-1.5">
            {hasChoices ? (
              <select value={value} onChange={e => setValue(e.target.value)}
                className="text-sm border border-sky-300 rounded px-2 py-0.5 bg-white focus:outline-none focus:ring-2 focus:ring-sky-400">
                {usableChoices.map(c => (
                  <option key={c.index} value={c.label}>{c.label}</option>
                ))}
              </select>
            ) : (
              <input value={value} onChange={e => setValue(e.target.value)}
                className="text-sm border border-sky-300 rounded px-2 py-0.5 w-28 focus:outline-none focus:ring-2 focus:ring-sky-400"
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
              />
            )}
            <button onClick={save} disabled={saving}
              className={`p-1 rounded ${saving ? 'text-gray-400' : 'text-green-600 hover:text-green-700'}`}>
              {saved ? <Check className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            </button>
            <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
            {error && <span className="text-xs text-red-400">{error}</span>}
          </div>
        )}
      </div>
    </div>
  )
}

function CameraProfilePanel({ profile }: { profile: CameraProfile | null }) {
  if (!profile) {
    return (
      <div className="mx-4 mt-4 rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-400">
        Hent kamera-parametre for at se den aktive kamera-profil.
      </div>
    )
  }

  const featureLabels: Record<string, string> = {
    autofocus: 'Autofokus',
    remote_focus: 'Remote focus',
    liveview: 'Liveview',
    movie: 'Video',
  }
  const settingLabels: Record<string, string> = {
    exposure_time: 'Lukker',
    aperture: 'Blænde',
    iso: 'ISO',
    focus_mode: 'Fokus',
  }
  const genericLabels: Record<string, string> = {
    iso: 'ISO',
    shutter_speed: 'Lukker',
    aperture: 'Blænde',
    whitebalance: 'Hvidbalance',
    colorspace: 'Farverum',
    imageformat: 'Billedformat',
    focusmode: 'Fokusmetode',
  }

  return (
    <div className="mx-4 mt-4 rounded-xl border border-purple-100 bg-purple-50/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-purple-500">Aktiv kamera-profil</div>
          <div className="mt-1 text-base font-semibold text-gray-900">{profile.profile_name}</div>
          <div className="mt-0.5 text-xs text-gray-500">
            {profile.detected_model} · {profile.driver} · {profile.gphoto2_port}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(featureLabels).map(([key, label]) => {
            const enabled = profile.features?.[key] === true
            return (
              <span key={key} className={`rounded-full px-2 py-1 text-xs font-medium ${
                enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-400'
              }`}>
                {label}
              </span>
            )
          })}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-medium text-gray-500">Metadata-stier</div>
          <div className="space-y-1.5">
            {Object.entries(settingLabels).map(([key, label]) => (
              <div key={key} className="grid grid-cols-[5rem,1fr] gap-2 text-xs">
                <span className="text-gray-500">{label}</span>
                <span className="break-all font-mono text-gray-700">
                  {(profile.capture_settings?.[key] ?? []).join(', ') || '–'}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-2 text-xs font-medium text-gray-500">Profil-mapping</div>
          <div className="space-y-1.5 mb-4">
            {Object.entries(profile.config_commands ?? {}).length === 0 ? (
              <div className="text-xs text-gray-400">Ingen profil-specifik mapping defineret</div>
            ) : Object.entries(profile.config_commands ?? {}).map(([key, spec]) => (
              <div key={key} className="grid grid-cols-[7rem,1fr] gap-2 text-xs">
                <span className="text-gray-500">{genericLabels[key] ?? key}</span>
                <span className="break-all font-mono text-gray-700">
                  <span className="mr-1 rounded bg-white px-1.5 py-0.5 text-[10px] font-sans text-purple-700">{profile.profile_name}</span>
                  {spec.skip ? 'ikke understøttet/læses kun' : spec.path || '–'}
                </span>
              </div>
            ))}
          </div>
          <div className="mb-2 text-xs font-medium text-gray-500">Kontrol-actions</div>
          <div className="space-y-1.5">
            {Object.entries(profile.actions ?? {}).length === 0 ? (
              <div className="text-xs text-gray-400">Ingen profil-actions defineret</div>
            ) : Object.entries(profile.actions).map(([key, path]) => (
              <div key={key} className="grid grid-cols-[6rem,1fr] gap-2 text-xs">
                <span className="text-gray-500">{key}</span>
                <span className="break-all font-mono text-gray-700">{path}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main LabPage ──────────────────────────────────────────────────────────────
export default function LabPage() {
  const { deviceId: id } = useParams<{ deviceId: string }>()
  const navigate = useNavigate()
  const deviceId = id!

  const [deviceName, setDeviceName]   = useState('')
  // R17 (2026-07-05): gemmes nu faktisk (var tidligere kun sat, aldrig læst)
  // så vi kan vise "aktiv siden" — se badge ved siden af Start/Stop lab-knappen.
  const [debugModeInfo, setDebugModeState] = useState<DebugMode | null>(null)
  const [labActive, setLabActive]     = useState(false)
  const [labStateChecked, setLabStateChecked] = useState(false)
  const [previews, setPreviews]       = useState<LabPreview[]>([])
  const [params, setParams]           = useState<CameraParam[]>([])
  const [cameraProfile, setCameraProfile] = useState<CameraProfile | null>(null)
  const [selectedPreview, setSelectedPreview] = useState<LabPreview | null>(null)
  const userSelectedRef = useRef(false)
  const selectedPreviewRef = useRef<LabPreview | null>(null)
  const [loadingPreview, setLoadingPreview]   = useState(false)
  const [loadingCapture, setLoadingCapture]   = useState(false)
  const [livePreview, setLivePreview] = useState(false)
  const [loadingParams, setLoadingParams]     = useState(false)
  const [focusBusy, setFocusBusy]             = useState(false)
  const [focusStepValue, setFocusStepValue]   = useState('')
  const [focusSliceCount, setFocusSliceCount] = useState(5)
  const [labResult, setLabResult]             = useState<any>(null)
  const [activeGroup, setActiveGroup] = useState<string>('Eksponering')
  const [wifiData, setWifiData]       = useState<any>(null)
  const [wifiLoading, setWifiLoading] = useState(false)
  const [wifiPasswords, setWifiPasswords] = useState<Record<string, string>>({})
  const [wifiConnecting, setWifiConnecting] = useState('')
  const [zoom, setZoom]               = useState(1)
  const [showHistogram, setShowHistogram] = useState(true)
  const [liveFrameEnabled, setLiveFrameEnabled] = useState(false) // F-013C: Frame Push Live View
  const [liveFrameUrl, setLiveFrameUrl] = useState<string | null>(null) // F-013C: Live frame URL
  const [fullscreen, setFullscreen] = useState(false)
  const [pollInterval, setPollInterval]   = useState<ReturnType<typeof setInterval> | null>(null)
  const [statusMsg, setStatusMsg]     = useState('')
  const [labConnecting, setLabConnecting] = useState(false)
  const [labConnectSecs, setLabConnectSecs] = useState(0)
  const [labReady, setLabReady]           = useState(false)
  const [labConnectingStart, setLabConnectingStart] = useState<number | null>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const liveFrameRef = useRef<HTMLImageElement>(null) // F-013C: Live frame img element
  const videoContainerRef = useRef<HTMLDivElement>(null) // Fullscreen container ref

  // Fullscreen toggle function
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      videoContainerRef.current?.requestFullscreen().catch(err => {
        console.error('Fullscreen error:', err)
      })
    } else {
      document.exitFullscreen().catch(err => {
        console.error('Exit fullscreen error:', err)
      })
    }
  }

  // Listen for fullscreen changes
  useEffect(() => {
    const handleChange = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handleChange)
    return () => document.removeEventListener('fullscreenchange', handleChange)
  }, [])

  const { hist, compute, clear } = useHistogram(imgRef)

  // Hold ref synkroniseret med state for brug i polling closure
  useEffect(() => { selectedPreviewRef.current = selectedPreview }, [selectedPreview])

  // Genberegn histogram når selectedPreview ændres (håndterer cached billeder)
  useEffect(() => {
    if (selectedPreview && showHistogram) {
      // Vent til img er klar i DOM — brug lille delay for cached billeder
      const t = setTimeout(() => {
        if (imgRef.current?.complete) compute()
      }, 150)
      return () => clearTimeout(t)
    }
  }, [selectedPreview?.filename, showHistogram])

  // ── Live Frame MJPEG Stream (F-013C) ─────────────────────────────────────────────
  useEffect(() => {
    if (!liveFrameEnabled) {
      setLiveFrameUrl(null)
      return
    }

    // Set MJPEG stream URL directly (browser handles natively)
    const apiUrl = getApiUrl()
    const streamUrl = `${apiUrl}/api/lab/${pathSegment(deviceId)}/live-stream`
    setLiveFrameUrl(streamUrl)

    // No polling needed - MJPEG stream is continuous
  }, [liveFrameEnabled, deviceId])

  // Load device info
  useEffect(() => {
    getDevice(deviceId).then(d => {
      const dev = d.device
      setDeviceName(dev.camera_name || dev.location_name || deviceId)
    }).catch(() => {})
    loadConfig()
  }, [deviceId])

  // ── Genopret og hold LAB-state synkroniseret efter refresh ────────────────
  useEffect(() => {
    if (!deviceId) return
    let cancelled = false

    async function checkExistingLab() {
      try {
        const data = await getDevice(deviceId)
        if (cancelled) return

        const { debugMode, debugEnabled, cameraReady } = readLabState(data)
        setDebugModeState(debugMode)
        setLabStateChecked(true)

        if (debugEnabled && cameraReady) {
          setLabActive(true)
          setLabConnecting(false)
          setLabConnectSecs(0)
          setLabConnectingStart(null)
          setLabReady(true)
          listPreviews(deviceId).then(setPreviews).catch(() => {})
        } else if (debugEnabled && !cameraReady) {
          setLabActive(false)
          setLabConnecting(true)
          setLabReady(false)
          // Start tracking connection time if not already tracking
          setLabConnectingStart(prev => prev || Date.now())
        } else {
          setLabActive(false)
          setLabConnecting(false)
          setLabConnectSecs(0)
          setLabConnectingStart(null)
          setLabReady(false)
        }
      } catch {
        if (!cancelled) setLabStateChecked(true)
      }
    }

    checkExistingLab()
    const iv = window.setInterval(checkExistingLab, 3000)
    return () => { cancelled = true; window.clearInterval(iv) }
  }, [deviceId])

  async function loadConfig() {
    try {
      const cfg = await loadAdminDeviceConfig(deviceId)
      const dm = cfg?.debug_mode
      if (dm) {
        setDebugModeState(dm)
      }
      if (cfg?.camera_profile) {
        setCameraProfile(cfg.camera_profile)
      }
    } catch { /* bevidst ignoreret — config-poll fejler stille, prøver igen næste interval */ }
  }

  // Poll for new previews when lab is active
  useEffect(() => {
    if (labActive) {
      const iv = setInterval(() => {
        listPreviews(deviceId).then(p => {
          setPreviews(p)
          // Auto-select kun nyeste hvis bruger ikke har valgt manuelt
          if (p.length > 0 && !userSelectedRef.current && p[0].filename !== selectedPreviewRef.current?.filename) {
            setSelectedPreview(p[0])
          }
        }).catch(() => {})
      }, 3000)
      setPollInterval(iv)
      return () => clearInterval(iv)
    } else {
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [labActive, deviceId])

  useEffect(() => {
    if (!livePreview || !labActive || labConnecting) return
    let cancelled = false
    let busy = false
    let lastFilename = selectedPreviewRef.current?.filename ?? ''

    async function requestFrame() {
      if (busy || cancelled) return
      busy = true
      try {
        await requestPreview(deviceId)
        for (let attempt = 0; attempt < 8 && !cancelled; attempt++) {
          await new Promise(resolve => window.setTimeout(resolve, 750))
          const p = await listPreviews(deviceId)
          setPreviews(p)
          if (p.length > 0 && p[0].filename !== lastFilename) {
            lastFilename = p[0].filename
            userSelectedRef.current = false
            setSelectedPreview(p[0])
            break
          }
        }
      } catch {
        if (!cancelled) setStatusMsg('Preview loop mistede forbindelsen kort')
      } finally {
        busy = false
      }
    }

    setStatusMsg('Preview loop kører')
    requestFrame()
    const iv = window.setInterval(requestFrame, 4000)
    return () => {
      cancelled = true
      window.clearInterval(iv)
      setStatusMsg('')
    }
  }, [livePreview, labActive, labConnecting, deviceId])

  async function toggleLab() {
    const next = !labActive
    if (next) {
      setLabConnecting(true)
      setLabConnectingStart(Date.now())
      setLabReady(false)
      const warmupS     = 30   // relay 10s + connect + commands
      const configPullS = 60   // edge waker hvert 60s

      // Beregn sekunder til næste 60s wake (synkroniseret)
      const nowS        = Math.floor(Date.now() / 1000)
      const secsToPull  = configPullS - (nowS % configPullS)
      const totalWait   = secsToPull + warmupS
      setLabConnectSecs(totalWait)

      // Nedtælling — viser realistisk ventetid
      let remaining = totalWait
      const countdown = setInterval(() => {
        remaining -= 1
        setLabConnectSecs(Math.max(0, remaining))
      }, 1000)

      try {
        // Sæt debug mode — edge vil opdage det ved næste config pull (~60s)
        await setDebugMode(deviceId, true, 5)

        // Poll headend for faktisk LAB CAMERA READY signal
        // Edge sender /lab/{id}/camera-ready når kameraet er forbundet
        // Det er det præcise signal vi venter på
        const check = setInterval(async () => {
          try {
            const apiUrl = getApiUrl()
            const r = await authFetch(`${apiUrl}/api/admin/devices/${pathSegment(deviceId)}`)
            const data = await r.json()
            const { cameraReady } = readLabState(data)
            if (cameraReady) {
              clearInterval(check)
              clearInterval(countdown)
              setLabActive(true)
              setLabConnecting(false)
              setLabConnectSecs(0)
              setLabConnectingStart(null)
              listPreviews(deviceId).then(setPreviews).catch(() => {})
              setLabReady(true)
            }
          } catch { /* ignore */ }
        }, 3000)

      } catch {
        setLabActive(false)
        setLabConnecting(false)
        setLabConnectSecs(0)
        setLabConnectingStart(null)
        clearInterval(countdown)
        setStatusMsg('Fejl ved aktivering af lab mode')
      }
    } else {
      setLabActive(false)
      setLivePreview(false)
      setLiveFrameEnabled(false)  // Stop MJPEG når lab stoppes
      setLabConnecting(false)
      setLabConnectSecs(0)
      setLabConnectingStart(null)
      setLabReady(false)
      // Nulstil camera-ready signal på headend
      try {
        const apiUrl = (await import('../api/client')).getApiUrl()
        await authFetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/camera-ready`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ready: false})
        }).catch(() => {})
      } catch { /* ignore */ }
      try {
        await setDebugMode(deviceId, false)
        setStatusMsg('Lab mode deaktiveret')
        setTimeout(() => setStatusMsg(''), 2000)
      } catch {
        setLabActive(true)
        setStatusMsg('Fejl ved deaktivering')
      }
    }
  }

  async function forceStopLab() {
    // Force stop LAB mode when stuck in connecting state
    setLabConnecting(false)
    setLabActive(false)
    setLivePreview(false)
    setLiveFrameEnabled(false)  // Stop MJPEG
    setLabConnectSecs(0)
    setLabConnectingStart(null)
    setLabReady(false)
    setStatusMsg('LAB mode nulstillet')

    // Send stop command to edge
    try {
      await setDebugMode(deviceId, false)
      // Clear camera-ready signal
      const apiUrl = (await import('../api/client')).getApiUrl()
      await authFetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/camera-ready`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ready: false})
      }).catch(() => {})
      setTimeout(() => setStatusMsg(''), 3000)
    } catch {
      setStatusMsg('Fejl ved nulstilling')
    }
  }

  async function takePreview() {
    setLoadingPreview(true)
    setStatusMsg('Anmoder om preview…')
    try {
      await requestPreview(deviceId)
      setStatusMsg('Preview anmodet — venter på billede…')
      // Poll for new preview
      userSelectedRef.current = false
      const prevFilename = selectedPreview?.filename ?? ''
      let attempts = 0
      const check = setInterval(async () => {
        attempts++
        try {
          const p = await listPreviews(deviceId)
          setPreviews(p)
          if (p.length > 0 && p[0].filename !== prevFilename) {
            setSelectedPreview(p[0])
            clear()
            clearInterval(check)
            setStatusMsg('Preview modtaget! ✓')
            setTimeout(() => setStatusMsg(''), 2000)
            return
          }
        } catch { /* ignore */ }
        if (attempts > 20) {
          clearInterval(check)
          setStatusMsg('Ingen respons — er lab mode aktiv?')
        }
      }, 1500)
    } catch {
      setStatusMsg('Fejl ved preview')
    } finally {
      setLoadingPreview(false)
    }
  }

  async function takeCapture() {
    setLoadingCapture(true)
    setStatusMsg('Anmoder om fuld capture (tæller lukker)…')
    try {
      await requestCapture(deviceId)
      const result = await waitForLabResult(['capture'])
      setStatusMsg(result?.ok ? 'Fuld capture modtaget' : 'Fuld capture fejlede')
      setTimeout(() => setStatusMsg(''), 3000)
    } catch {
      setStatusMsg('Fejl ved capture')
    } finally {
      setLoadingCapture(false)
    }
  }

  async function loadParams() {
    setLoadingParams(true)
    setStatusMsg('Anmoder om kamera-parametre…')
    try {
      // Trin 1: anmod om get_params kommando
      const apiUrl = (await import('../api/client')).getApiUrl()
      await authFetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/get-params`, { method: 'POST' })
      setStatusMsg('Venter på kamera-parametre…')

      // Trin 2: poll config indtil camera_params er klar
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        try {
          const cfg = await loadAdminDeviceConfig(deviceId)
          const camParams = cfg?.camera_params || []
          if (camParams.length > 0) {
            clearInterval(poll)
            setParams(camParams)
            setCameraProfile(cfg?.camera_profile ?? null)
            setStatusMsg(`✓ ${camParams.length} parametre hentet`)
            setTimeout(() => setStatusMsg(''), 3000)
            setLoadingParams(false)
          }
        } catch { /* ignore */ }
        if (attempts > 20) {
          clearInterval(poll)
          setStatusMsg('Timeout — er lab mode aktiv og kamera tilsluttet?')
          setLoadingParams(false)
        }
      }, 1500)
    } catch {
      setStatusMsg('Fejl ved hentning af parametre')
      setLoadingParams(false)
    }
  }

  async function waitForLabResult(expected: string[]) {
    for (let attempt = 0; attempt < 30; attempt++) {
      await new Promise(resolve => window.setTimeout(resolve, 1500))
      const cfg = await loadAdminDeviceConfig(deviceId)
      if (cfg?.lab_result && expected.includes(cfg.lab_result.type)) {
        setLabResult(cfg.lab_result)
        if (cfg.lab_result.preview_filename) {
          const p = await listPreviews(deviceId).catch(() => [])
          setPreviews(p)
          const match = p.find((x: LabPreview) => x.filename === cfg.lab_result.preview_filename) ?? p[0]
          if (match) setSelectedPreview(match)
        } else {
          listPreviews(deviceId).then(setPreviews).catch(() => {})
        }
        return cfg.lab_result
      }
    }
    throw new Error('Timeout')
  }

  async function driveFocus(value: string) {
    if (!value) return
    setFocusBusy(true)
    setStatusMsg(`Flytter fokus: ${value}`)
    try {
      await requestFocusDrive(deviceId, value)
      await waitForLabResult(['focus_drive'])
      setStatusMsg('Fokus flyttet og målt')
      setTimeout(() => setStatusMsg(''), 3000)
    } catch {
      setStatusMsg('Fokuskommando timeout/fejl')
    } finally {
      setFocusBusy(false)
    }
  }

  async function runAutofocusTest() {
    setFocusBusy(true)
    setStatusMsg('Kører autofocus og kvalitetstest…')
    try {
      await requestAutofocus(deviceId)
      await waitForLabResult(['autofocus'])
      setStatusMsg('Autofocus test færdig')
      setTimeout(() => setStatusMsg(''), 3000)
    } catch {
      setStatusMsg('Autofocus test timeout/fejl')
    } finally {
      setFocusBusy(false)
    }
  }

  async function runFocusSliceTest(edgeAi = false) {
    if (!focusStepValue) {
      setStatusMsg('Vælg en focus step-værdi først')
      return
    }
    setFocusBusy(true)
    setStatusMsg(edgeAi ? 'Kører Edge AI fokus-test…' : 'Kører focus slice-test…')
    try {
      if (edgeAi) await requestEdgeAiFocusTest(deviceId, { step_value: focusStepValue, count: focusSliceCount })
      else await requestFocusSlice(deviceId, { step_value: focusStepValue, count: focusSliceCount, run_autofocus_first: true })
      await waitForLabResult(edgeAi ? ['edge_ai_focus_test'] : ['focus_slice'])
      setStatusMsg('Focus slice analyse færdig')
      setTimeout(() => setStatusMsg(''), 3000)
    } catch {
      setStatusMsg('Focus slice timeout/fejl')
    } finally {
      setFocusBusy(false)
    }
  }

  async function wifiScan() {
    setWifiLoading(true)
    setStatusMsg('Scanner WiFi netværk…')
    try {
      const apiUrl = (await import('../api/client')).getApiUrl()
      await authFetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/wifi/scan`, { method: 'POST' })
      // Poll for result
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const cfg = await loadAdminDeviceConfig(deviceId)
        const wd  = cfg?.wifi_data
        if (wd?.type === 'scan') {
          setWifiData(wd)
          setWifiLoading(false)
          setStatusMsg(`${wd.networks?.length ?? 0} netværk fundet`)
          setTimeout(() => setStatusMsg(''), 3000)
          clearInterval(poll)
        }
        if (attempts > 15) { clearInterval(poll); setWifiLoading(false); setStatusMsg('Timeout') }
      }, 1500)
    } catch { setWifiLoading(false) }
  }

  async function wifiConnect(ssid: string, password: string) {
    setWifiConnecting(ssid)
    setStatusMsg(`Tilslutter til ${ssid}…`)
    try {
      const apiUrl = (await import('../api/client')).getApiUrl()
      const res = await authFetch(`${apiUrl}/api/lab/${pathSegment(deviceId)}/wifi/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ssid, password })
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail ?? 'WiFi connect blev afvist')
      }
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const cfg = await loadAdminDeviceConfig(deviceId)
        const wd  = cfg?.wifi_data
        if (wd?.type === 'connect') {
          setWifiData((prev: any) => ({ ...prev, current: wd.current }))
          setWifiConnecting('')
          setStatusMsg(wd.result?.success ? `✓ Tilsluttet ${ssid}` : `Fejl ved tilslutning til ${ssid}`)
          setTimeout(() => setStatusMsg(''), 4000)
          clearInterval(poll)
        }
        if (attempts > 20) { clearInterval(poll); setWifiConnecting('') }
      }, 1500)
    } catch (err) {
      setWifiConnecting('')
      setStatusMsg(err instanceof Error ? err.message : 'WiFi connect fejlede')
      setTimeout(() => setStatusMsg(''), 5000)
    }
  }

  function lockParams() {
    // Build initial_commands from current known params
    const LOCKABLE = ['capturetarget', 'iso', 'colorspace', 'meteringmode',
                      'whitebalance', 'exposurecompensation', 'picturestyle', 'imageformat']
    const commands = params
      .filter(p => !p.readonly && LOCKABLE.some(k => p.path.includes(k)))
      .map(p => {
        const key = p.path.split('/').pop()!
        return `${key}=${p.current}`
      })
    if (commands.length === 0) { setStatusMsg('Ingen parametre at låse'); return }
    // Update config via API
    import('../api/client').then(({ getApiUrl }) => {
      authFetch(`${getApiUrl()}/api/admin/devices/${pathSegment(deviceId)}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera: { initial_commands: commands } })
      }).then(() => setStatusMsg(`✓ ${commands.length} parametre låst som initial_commands`))
        .catch(() => setStatusMsg('Fejl ved låsning'))
    })
  }

  // Group params
  const groupedParams = Object.entries(PARAM_GROUPS).reduce((acc, [group, paths]) => {
    const matched = params.filter(p => paths.includes(p.path))
    const rest = params.filter(p =>
      !Object.values(PARAM_GROUPS).flat().includes(p.path) && group === 'Status'
    )
    acc[group] = group === 'Status' ? [...matched, ...rest] : matched
    return acc
  }, {} as Record<string, CameraParam[]>)

  // All ungrouped params shown under active group if "Alle" selected
  const displayParams = activeGroup === 'Alle'
    ? params
    : (groupedParams[activeGroup] || [])
  const manualFocusParam = params.find(p => p.path === cameraProfile?.actions?.manual_focus || p.path.endsWith('/manualfocusdrive'))
  const manualFocusChoices = (manualFocusParam?.choices ?? []).filter(c => c.label && !/^unknown$/i.test(c.label.trim()))
  const manualFocusIsRange = manualFocusParam?.type?.toUpperCase?.() === 'RANGE'
  const canRemoteFocus = cameraProfile?.features?.remote_focus === true && (manualFocusChoices.length > 0 || manualFocusIsRange)
  useEffect(() => {
    if (focusStepValue) return
    if (manualFocusChoices.length > 0) {
      const defaultChoice = manualFocusChoices.find(c => /near|far/i.test(c.label)) ?? manualFocusChoices[0]
      setFocusStepValue(defaultChoice.label)
      return
    }
    if (manualFocusIsRange) {
      setFocusStepValue(String(cameraProfile?.focus_controls?.manual_focus_default_step ?? manualFocusParam?.step ?? '500'))
    }
  }, [focusStepValue, manualFocusIsRange, manualFocusParam?.step, manualFocusChoices.map(c => c.label).join('|'), cameraProfile?.focus_controls?.manual_focus_default_step])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(`/devices/${pathSegment(deviceId)}`)}
              className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <FlaskConical className="w-5 h-5 text-purple-500" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Kamera-laboratorium</h1>
              <p className="text-sm text-gray-400">{deviceName} · {deviceId}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {statusMsg && (
              <span className="text-sm text-sky-600 bg-sky-50 px-3 py-1 rounded-full">{statusMsg}</span>
            )}
            <div className="flex items-center gap-3">
              {labReady && labActive && (
                <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-xl animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                  Lab klar!
                </span>
              )}
              {labActive && debugModeInfo?.enabled_at && (
                <span className="text-xs text-amber-600 bg-amber-50 px-2.5 py-1 rounded-lg" title="R17: lab mode slukkes automatisk efter et konfigureret antal timer hvis den ikke stoppes manuelt">
                  Aktiv siden {new Date(debugModeInfo.enabled_at).toLocaleString('da-DK', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
                </span>
              )}
              {/* Force stop button when stuck in connecting state */}
              {labConnecting && (
                <button
                  onClick={forceStopLab}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl font-medium text-sm bg-red-100 hover:bg-red-200 text-red-700 transition-colors"
                  title="Nulstil LAB mode nu"
                >
                  <Ban className="w-4 h-4" />
                  Force stop
                </button>
              )}
              <button onClick={toggleLab} disabled={labConnecting && !labConnectingStart}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all ${
                  labConnecting
                    ? 'bg-amber-400 text-white cursor-wait'
                    : labActive
                      ? 'bg-red-500 hover:bg-red-600 text-white'
                      : 'bg-purple-600 hover:bg-purple-700 text-white'
                }`}>
                {labConnecting ? (
                  <><RefreshCw className="w-4 h-4 animate-spin" />
                  {labConnectSecs > 60
                    ? `Venter ~${Math.floor(labConnectSecs/60)}m ${labConnectSecs%60}s`
                    : labConnectSecs > 0
                      ? `Venter ~${labConnectSecs}s`
                      : 'Venter på enhed…'
                  }</>
                ) : labActive ? (
                  <><PowerOff className="w-4 h-4" /> Stop lab</>
                ) : (
                  <><Power className="w-4 h-4" /> Start lab</>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Lab inactive notice */}
      {!labActive && (!labStateChecked || labConnecting) && (
        <div className="max-w-2xl mx-auto mt-12 text-center">
          <RefreshCw className="w-12 h-12 text-purple-300 mx-auto mb-4 animate-spin" />
          <h2 className="text-xl font-semibold text-gray-700 mb-2">{labConnecting ? 'Venter på kamera' : 'Kontrollerer lab-status'}</h2>
          <p className="text-gray-400">
            {labConnecting
              ? 'LAB mode venter på kamera. Brug "Force stop" knappen til at nulstille hvis det hænger.'
              : 'Henter aktuel status fra headend.'}
          </p>
          {labConnecting && labConnectingStart && (
            <p className="text-xs text-gray-400 mt-2">
              Ventetid: {Math.floor((Date.now() - labConnectingStart) / 60000)} minutter
            </p>
          )}
          {labConnecting && (
            <button
              onClick={forceStopLab}
              className="mt-6 flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm bg-red-100 hover:bg-red-200 text-red-700 transition-colors mx-auto"
            >
              <Ban className="w-4 h-4" />
              Force stop LAB mode
            </button>
          )}
        </div>
      )}

      {!labActive && labStateChecked && !labConnecting && (
        <div className="max-w-2xl mx-auto mt-12 text-center">
          <FlaskConical className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-700 mb-2">Lab mode er ikke aktiv</h2>
          <p className="text-gray-400 mb-6">Start lab mode for at tænde kameraet permanent og justere parametre i realtid.</p>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700 text-left max-w-md mx-auto">
            <strong>Bemærk:</strong> Lab mode holder relay tændt og kameraet aktiv. Husk at stoppe lab mode når du er færdig for at spare strøm og lukkerlevetid.
          </div>
        </div>
      )}

      {/* Lab active content */}
      {labActive && (
        <div className="max-w-7xl mx-auto p-6 grid grid-cols-1 xl:grid-cols-2 gap-6">

          {/* Preview panel */}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                <Camera className="w-4 h-4 text-purple-500" /> Live Preview
              </h2>
              <div className="flex items-center gap-2">
                <button onClick={() => setShowHistogram(h => !h)}
                  className={`text-xs px-2 py-1 rounded-lg ${showHistogram ? 'bg-sky-100 text-sky-700' : 'bg-gray-100 text-gray-500'}`}>
                  Histogram
                </button>
                <button onClick={() => { setZoom(z => Math.max(1, z - 0.5)) }}
                  className="p-1 text-gray-400 hover:text-gray-700 rounded"><ZoomOut className="w-4 h-4" /></button>
                <span className="text-xs text-gray-400 w-10 text-center">{Math.round(zoom*100)}%</span>
                <button onClick={() => { setZoom(z => Math.min(4, z + 0.5)) }}
                  className="p-1 text-gray-400 hover:text-gray-700 rounded"><ZoomIn className="w-4 h-4" /></button>
                <button onClick={toggleFullscreen} title="Fuldskærm"
                  className="p-1 text-gray-400 hover:text-gray-700 rounded ml-1">
                  {fullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Image */}
            <div
              ref={videoContainerRef}
              onClick={toggleFullscreen}
              className="bg-gray-900 aspect-video flex items-center justify-center overflow-hidden relative cursor-pointer"
              title="Klik for fuldskærm"
            >
              {liveFrameEnabled && liveFrameUrl ? (
                <img
                  ref={liveFrameRef}
                  src={liveFrameUrl}
                  alt="Live Frame"
                  className="w-full h-full object-contain"
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: 'center center',
                    transition: 'transform 0.15s',
                  }}
                />
              ) : selectedPreview ? (
                <img
                  key={selectedPreview.filename}
                  ref={imgRef}
                  src={getPreviewUrl(deviceId, selectedPreview.filename)}
                  alt="preview"
                  crossOrigin="anonymous"
                  onLoad={() => {
                    if (showHistogram) setTimeout(compute, 100)
                  }}
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: 'center center',
                    transition: 'transform 0.15s',
                    maxWidth: '100%', maxHeight: '100%',
                    width: 'auto', height: 'auto',
                  }}
                />
              ) : (
                <div className="text-gray-600 text-sm flex flex-col items-center gap-2">
                  <Camera className="w-8 h-8 opacity-30" />
                  <span>Tag et preview for at se billedet</span>
                </div>
              )}
            </div>

            {/* Histogram */}
            {showHistogram && hist && (
              <div className="px-4 py-3 bg-gray-900 border-t border-gray-800">
                <MiniHistogram hist={hist} />
              </div>
            )}

            {/* Preview actions */}
            <div className="p-4 flex gap-3">
              <button onClick={() => setLiveFrameEnabled(v => !v)} disabled={labConnecting}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors ${
                  liveFrameEnabled ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-sky-600 hover:bg-sky-700'
                }`}>
                {liveFrameEnabled ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                {liveFrameEnabled ? 'MJPEG Live' : 'MJPEG Live'}
              </button>
              <button onClick={() => setLivePreview(v => !v)} disabled={labConnecting || liveFrameEnabled}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors ${
                  livePreview ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-sky-600 hover:bg-sky-700'
                }`}>
                {livePreview ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                {livePreview ? 'Stop preview loop' : 'Preview loop'}
              </button>
              <button onClick={takePreview} disabled={loadingPreview || liveFrameEnabled}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors">
                {loadingPreview ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                Preview <span className="text-purple-200 text-xs">(ingen lukker)</span>
              </button>
              <button onClick={takeCapture} disabled={loadingCapture || liveFrameEnabled}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors">
                {loadingCapture ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                Fuld capture <span className="text-gray-400 text-xs">(tæller lukker)</span>
              </button>
            </div>

            {/* Preview filmstrip */}
            {previews.length > 0 && (
              <div className="px-4 pb-4">
                <div className="flex gap-1.5 overflow-x-auto">
                  {previews.map(p => (
                    <button key={p.filename} onClick={() => { userSelectedRef.current = true; setSelectedPreview(p) }}
                      className={`flex-shrink-0 w-16 h-12 rounded-lg overflow-hidden border-2 transition-all ${
                        selectedPreview?.filename === p.filename ? 'border-purple-400' : 'border-transparent opacity-60 hover:opacity-100'
                      }`}>
                      <img src={getPreviewThumbUrl(deviceId, p.filename)} alt="" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-1">{previews.length} previews — ingen lukker-forbrug</p>
              </div>
            )}
          </div>

          {/* Parameter panel */}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                <Settings className="w-4 h-4 text-purple-500" /> Kamera-parametre
              </h2>
              <div className="flex gap-2">
                <button onClick={loadParams} disabled={loadingParams}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg font-medium">
                  {loadingParams ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Hent parametre
                </button>
                {params.length > 0 && (
                  <button onClick={lockParams}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 rounded-lg font-medium">
                    <Lock className="w-3 h-3" /> Lås parametre
                  </button>
                )}
              </div>
            </div>

            <CameraProfilePanel profile={cameraProfile} />

            {/* Eksponeringsmode matrix - hjælpetabel for readonly parametre */}
            <div className="mx-4 mt-4 rounded-xl border border-amber-100 bg-amber-50/60 p-4">
              <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2 mb-3">
                <HelpCircle className="w-4 h-4 text-amber-600" /> Eksponeringsmode og parametre
              </h3>
              <p className="text-xs text-gray-600 mb-3">
                <strong>Skift eksponeringsmode:</strong> Klik på tandhjulet ud for <span className="text-amber-700">Eksponeringsmode</span> under "Eksponering" gruppen og vælg en mode. Manual (M) giver fuld kontrol over alle parametre.
              </p>
              <p className="text-xs text-gray-600 mb-3">
                Når en parameter er låst (🔒), betyder det at den styres automatisk i den aktuelle mode.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-amber-200">
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Mode</th>
                      <th className="text-center py-2 px-2 font-semibold text-gray-700">Lukker</th>
                      <th className="text-center py-2 px-2 font-semibold text-gray-700">Blænde</th>
                      <th className="text-center py-2 px-2 font-semibold text-gray-700">ISO</th>
                      <th className="text-center py-2 px-2 font-semibold text-gray-700">EV ±</th>
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(EXPOSURE_MODE_MATRIX).map(([mode, data]) => (
                      <tr key={mode} className="border-b border-amber-100 hover:bg-amber-100/40">
                        <td className="py-2 px-3 font-medium">{mode}</td>
                        <td className="text-center py-2 px-2">{data.shutter ? '✅' : '🔒'}</td>
                        <td className="text-center py-2 px-2">{data.aperture ? '✅' : '🔒'}</td>
                        <td className="text-center py-2 px-2">{data.iso ? '✅' : '🔒'}</td>
                        <td className="text-center py-2 px-2">{data.ev ? '✅' : '🔒'}</td>
                        <td className="py-2 px-3 text-gray-600">{data.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>


            <div className="mx-4 mt-4 rounded-xl border border-sky-100 bg-sky-50/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                    <Crosshair className="w-4 h-4 text-sky-600" /> Nikon/fokus LAB
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Remote focus og focus slice bruger kameraets egne profilvalg. Resultatet scores lokalt på Edge.
                  </p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                  canRemoteFocus ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-400'
                }`}>
                  {canRemoteFocus ? 'Remote focus klar' : 'Hent parametre / ikke understøttet'}
                </span>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-[1fr,auto,auto]">
                {manualFocusIsRange ? (
                  <input type="number"
                    value={focusStepValue}
                    min={Number(manualFocusParam?.bottom ?? cameraProfile?.focus_controls?.manual_focus_min ?? -32767)}
                    max={Number(manualFocusParam?.top ?? cameraProfile?.focus_controls?.manual_focus_max ?? 32767)}
                    step={Number(manualFocusParam?.step ?? 1)}
                    onChange={e => setFocusStepValue(e.target.value)}
                    disabled={!canRemoteFocus || focusBusy}
                    className="border border-sky-200 rounded-lg px-3 py-2 text-sm bg-white disabled:opacity-50"
                    title={`Manual focus range ${manualFocusParam?.bottom ?? '-32767'}..${manualFocusParam?.top ?? '32767'}`} />
                ) : (
                  <select value={focusStepValue} onChange={e => setFocusStepValue(e.target.value)}
                    disabled={!canRemoteFocus || focusBusy}
                    className="border border-sky-200 rounded-lg px-3 py-2 text-sm bg-white disabled:opacity-50">
                    <option value="">Vælg focus step fra kamera-profil…</option>
                    {manualFocusChoices.map(c => <option key={c.index} value={c.label}>{c.label}</option>)}
                  </select>
                )}
                <input type="number" min={1} max={12} value={focusSliceCount}
                  onChange={e => setFocusSliceCount(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))}
                  className="border border-sky-200 rounded-lg px-3 py-2 text-sm w-24 bg-white"
                  title="Antal slices" />
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => driveFocus(focusStepValue)} disabled={!canRemoteFocus || focusBusy}
                    className="px-3 py-2 rounded-lg bg-sky-600 text-white text-xs font-medium disabled:opacity-50">
                    {focusBusy ? 'Arbejder…' : 'Step focus'}
                  </button>
                  <button onClick={runAutofocusTest} disabled={focusBusy || cameraProfile?.features?.autofocus !== true}
                    className="px-3 py-2 rounded-lg bg-purple-600 text-white text-xs font-medium disabled:opacity-50">
                    Autofocus test
                  </button>
                  <button onClick={() => runFocusSliceTest(false)} disabled={!canRemoteFocus || focusBusy}
                    className="px-3 py-2 rounded-lg bg-gray-800 text-white text-xs font-medium disabled:opacity-50">
                    Focus slice
                  </button>
                  <button onClick={() => runFocusSliceTest(true)} disabled={!canRemoteFocus || focusBusy}
                    className="inline-flex items-center gap-1 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-medium disabled:opacity-50">
                    <Wand2 className="w-3 h-3" /> Edge test
                  </button>
                </div>
              </div>
              {labResult && (
                <div className="mt-3 rounded-lg border border-white bg-white/80 p-3 text-xs text-gray-700">
                  <div className="font-medium text-gray-800">
                    Seneste resultat: {labResult.type} · {labResult.ok ? 'OK' : 'Fejl'}
                  </div>
                  {labResult.quality && (
                    <div className="mt-1">
                      Blur {labResult.quality.blur_score?.toFixed?.(1) ?? '–'} · Lys {labResult.quality.brightness_mean?.toFixed?.(1) ?? '–'} · {labResult.quality.flag}
                    </div>
                  )}
                  {labResult.recommendation?.best_preview_filename && (
                    <div className="mt-1">
                      Bedste slice: {labResult.recommendation.best_preview_filename} · blur {labResult.recommendation.best_blur_score?.toFixed?.(1) ?? '–'}
                    </div>
                  )}
                  {labResult.error && <div className="mt-1 text-red-600">{labResult.error}</div>}
                </div>
              )}
            </div>

            {params.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-gray-400 text-sm flex-col gap-2 p-8">
                <Settings className="w-8 h-8 opacity-20" />
                <p>Klik "Hent parametre" for at se kamera-indstillinger</p>
                <p className="text-xs text-gray-300">Kameraet skal være tilsluttet og lab mode aktiv</p>
              </div>
            ) : (
              <>
                {/* Group tabs */}
                <div className="flex gap-1 px-4 pt-3 pb-2 overflow-x-auto flex-shrink-0">
                  {[...Object.keys(PARAM_GROUPS), 'Alle'].map(group => (
                    <button key={group} onClick={() => setActiveGroup(group)}
                      className={`flex-shrink-0 text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
                        activeGroup === group
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}>
                      {group}
                      {groupedParams[group] && (
                        <span className={`ml-1 ${activeGroup === group ? 'text-purple-200' : 'text-gray-400'}`}>
                          {groupedParams[group].length}
                        </span>
                      )}
                    </button>
                  ))}
                </div>

                {/* Param list */}
                <div className="flex-1 overflow-y-auto px-2 pb-4">
                  {displayParams.length === 0 ? (
                    <p className="text-center text-sm text-gray-400 py-8">
                      Ingen parametre i denne gruppe
                    </p>
                  ) : (
                    displayParams.map(p => (
                      <ParamRow key={p.path} param={p} deviceId={deviceId} onChanged={loadParams} />
                    ))
                  )}
                </div>
              </>
            )}
          </div>

          {/* WiFi Panel */}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden xl:col-span-2">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h2 className="font-semibold text-gray-800 flex items-center gap-2">
              <Wifi className="w-4 h-4 text-purple-500" /> WiFi Konfiguration
            </h2>
            <div className="flex items-center gap-3">
              {wifiData?.current?.connected && (
                <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full flex items-center gap-1">
                  <Wifi className="w-3 h-3" /> {wifiData.current.ssid} · {wifiData.current.signal ?? 0}%
                </span>
              )}
              <button onClick={wifiScan} disabled={wifiLoading}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg font-medium">
                {wifiLoading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Wifi className="w-3 h-3" />}
                Scan netværk
              </button>
            </div>
          </div>
          {!wifiData ? (
            <div className="flex items-center justify-center text-gray-400 text-sm flex-col gap-2 p-8">
              <Wifi className="w-8 h-8 opacity-20" />
              <p>Klik "Scan netværk" for at se tilgængelige WiFi netværk</p>
            </div>
          ) : (
            <div className="overflow-y-auto max-h-64 p-4 space-y-2">
              {(wifiData.networks ?? []).map((net: any) => (
                <div key={net.ssid} className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                  net.in_use ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200 hover:border-purple-200'
                }`}>
                  <Wifi className={`w-4 h-4 flex-shrink-0 ${net.in_use ? 'text-emerald-500' : 'text-gray-400'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-800 truncate">{net.ssid}</span>
                      {net.in_use && <span className="text-xs text-emerald-600 bg-emerald-100 px-1.5 py-0.5 rounded">Aktiv</span>}
                      {net.saved && !net.in_use && <span className="text-xs text-sky-600 bg-sky-50 px-1.5 py-0.5 rounded">Gemt</span>}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">{net.bars} {net.signal}% · {net.security || 'Åbent'} · Kanal {net.channel}</div>
                  </div>
                  {!net.in_use && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {net.security && !net.saved && (
                        <input type="password" placeholder="Password" value={wifiPasswords[net.ssid] ?? ''}
                          onChange={e => setWifiPasswords(p => ({...p, [net.ssid]: e.target.value}))}
                          className="text-xs border border-gray-200 rounded px-2 py-1 w-24 focus:outline-none focus:border-purple-300"
                          onKeyDown={e => e.key === 'Enter' && wifiConnect(net.ssid, wifiPasswords[net.ssid] ?? '')} />
                      )}
                      <button onClick={() => wifiConnect(net.ssid, net.saved ? '' : (wifiPasswords[net.ssid] ?? ''))}
                        disabled={wifiConnecting === net.ssid}
                        className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-1">
                        {wifiConnecting === net.ssid
                          ? <RefreshCw className="w-3 h-3 animate-spin" />
                          : 'Tilslut'}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          </div>

        </div>
      )}
    </div>
  )
}
