import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Camera, FlaskConical, Power, PowerOff, RefreshCw,
  Lock, ChevronLeft, ZoomIn, ZoomOut, Settings, X, Check
} from 'lucide-react'
import {
  setDebugMode, requestPreview, requestCapture,
  setParam, listPreviews, getPreviewUrl, getPreviewThumbUrl,
  getDeviceRawConfig, getDevice
} from '../api/client'
import type { LabPreview, CameraParam, DebugMode } from '../types'

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

// ── Histogram hook ────────────────────────────────────────────────────────────
function useHistogram(imgRef: React.RefObject<HTMLImageElement>) {
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
      // Extract path key without /main/ prefix
      const key = param.path.replace('/main/', '')
      await setParam(deviceId, key, value)
      setSaved(true)
      setTimeout(() => { setSaved(false); setEditing(false); onChanged() }, 800)
    } catch {
      setError('Fejl')
    } finally {
      setSaving(false)
    }
  }

  const isReadonly = param.readonly || param.type === 'TEXT'
  const hasChoices = param.choices.length > 0

  return (
    <div className={`flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors ${isReadonly ? 'opacity-60' : ''}`}>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-700 truncate">{param.label}</div>
        <div className="text-xs text-gray-400 truncate">{param.path}</div>
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
                {param.choices.map(c => (
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

// ── Main LabPage ──────────────────────────────────────────────────────────────
export default function LabPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const deviceId = id!

  const [deviceName, setDeviceName]   = useState('')
  const [debugMode, setDebugModeState] = useState<DebugMode | null>(null)
  const [labActive, setLabActive]     = useState(false)
  const [previews, setPreviews]       = useState<LabPreview[]>([])
  const [params, setParams]           = useState<CameraParam[]>([])
  const [selectedPreview, setSelectedPreview] = useState<LabPreview | null>(null)
  const userSelectedRef = useRef(false)
  const [loadingPreview, setLoadingPreview]   = useState(false)
  const [loadingCapture, setLoadingCapture]   = useState(false)
  const [loadingParams, setLoadingParams]     = useState(false)
  const [activeGroup, setActiveGroup] = useState<string>('Eksponering')
  const [zoom, setZoom]               = useState(1)
  const [showHistogram, setShowHistogram] = useState(true)
  const [pollInterval, setPollInterval]   = useState<ReturnType<typeof setInterval> | null>(null)
  const [statusMsg, setStatusMsg]     = useState('')
  const imgRef = useRef<HTMLImageElement>(null)
  const { hist, compute, clear } = useHistogram(imgRef)

  // Load device info
  useEffect(() => {
    getDevice(deviceId).then(d => {
      const dev = d.device
      setDeviceName(dev.camera_name || dev.location_name || deviceId)
    }).catch(() => {})
    loadConfig()
  }, [deviceId])

  async function loadConfig() {
    try {
      const cfg = await getDeviceRawConfig(deviceId)
      const dm  = cfg?.debug_mode
      if (dm) {
        setDebugModeState(dm)
        setLabActive(dm.enabled)
      }
    } catch {}
  }

  // Poll for new previews when lab is active
  useEffect(() => {
    if (labActive) {
      const iv = setInterval(() => {
        listPreviews(deviceId).then(p => {
          setPreviews(p)
          // Auto-select kun nyeste hvis bruger ikke har valgt manuelt
          if (p.length > 0 && !userSelectedRef.current && p[0].filename !== selectedPreview?.filename) {
            setSelectedPreview(p[0])
            clear()
          }
        }).catch(() => {})
      }, 3000)
      setPollInterval(iv)
      return () => clearInterval(iv)
    } else {
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [labActive, deviceId])

  async function toggleLab() {
    const next = !labActive
    setLabActive(next)
    setStatusMsg(next ? 'Aktiverer lab mode…' : 'Deaktiverer lab mode…')
    try {
      await setDebugMode(deviceId, next, 2)
      setStatusMsg(next ? 'Lab mode aktiv — kamera tænder…' : 'Lab mode deaktiveret')
      setTimeout(() => setStatusMsg(''), 3000)
      if (next) {
        // Load previews after short delay
        setTimeout(() => listPreviews(deviceId).then(setPreviews).catch(() => {}), 3000)
      }
    } catch {
      setLabActive(!next)
      setStatusMsg('Fejl ved skift af lab mode')
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
      setStatusMsg('Capture anmodet!')
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
      await fetch(`${apiUrl}/api/lab/${deviceId}/get-params`, { method: 'POST' })
      setStatusMsg('Venter på kamera-parametre…')

      // Trin 2: poll config indtil camera_params er klar
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        try {
          const cfg = await getDeviceRawConfig(deviceId)
          const camParams = cfg?.camera_params || []
          if (camParams.length > 0) {
            clearInterval(poll)
            setParams(camParams)
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
    const client = import('../api/client').then(({ getApiUrl }) => {
      fetch(`${getApiUrl()}/api/admin/devices/${deviceId}/config`, {
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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(`/devices/${deviceId}`)}
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
            <button onClick={toggleLab}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all ${
                labActive
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : 'bg-purple-600 hover:bg-purple-700 text-white'
              }`}>
              {labActive ? <><PowerOff className="w-4 h-4" /> Stop lab</> : <><Power className="w-4 h-4" /> Start lab</>}
            </button>
          </div>
        </div>
      </div>

      {/* Lab inactive notice */}
      {!labActive && (
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
              </div>
            </div>

            {/* Image */}
            <div className="bg-gray-900 aspect-video flex items-center justify-center overflow-hidden relative">
              {selectedPreview ? (
                <img
                  ref={imgRef}
                  src={getPreviewUrl(deviceId, selectedPreview.filename)}
                  alt="preview"
                  crossOrigin="anonymous"
                  onLoad={() => {
                  if (showHistogram) {
                    setTimeout(compute, 100)
                  }
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
              <button onClick={takePreview} disabled={loadingPreview}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors">
                {loadingPreview ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                Preview <span className="text-purple-200 text-xs">(ingen lukker)</span>
              </button>
              <button onClick={takeCapture} disabled={loadingCapture}
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
                    <button key={p.filename} onClick={() => { userSelectedRef.current = true; setSelectedPreview(p); clear() }}
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
        </div>
      )}
    </div>
  )
}
