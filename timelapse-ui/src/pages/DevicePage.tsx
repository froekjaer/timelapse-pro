// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — DevicePage.tsx
// ───────────────────────────────────────────────────────────────────────────
// Version  : 5.4.0
// Dato     : 13. april 2026
// ───────────────────────────────────────────────────────────────────────────
// Changelog:
//   5.4.0  13-apr-2026  Komplet metadata panel: 3 kolonner, alle felter vist
//   5.3.0  13-apr-2026  Scroll fix via metaRef — onWheel ignorerer metadata panel
//   5.2.0  13-apr-2026  Metadata panel: blur score, scroll fix (onWheel stop),
//                       projekt sektion, duplikat panel fjernet
//   5.1.0  12-apr-2026  Sidecar metadata panel, integritet, XMP status
//   5.0.0  12-apr-2026  Sprint A, LAB route fix /lab/:deviceId
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { FlaskConical, Film, Check, ArrowLeft, RefreshCw, Thermometer, HardDrive, Wifi, Clock, Image, Settings, Camera, BarChart2, X, ChevronLeft, ChevronRight, Heart, CalendarDays } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Legend, CartesianGrid, ReferenceLine } from 'recharts'
import { getDevice, getCaptures, getConfig, updateConfig, getImageUrl, getThumbnailUrl, updateDeviceInfo, setParam, pathSegment } from '../api/client'
import { TimelineNavigator } from '../components/TimelineNavigator'
import { StatusBadge } from '../components/StatusBadge'
import type { DeviceDetail, Capture } from '../types'

function authFetch(url: string, opts?: RequestInit) {
  return fetch(url, { credentials: 'include', ...opts })
}



const getTz = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function formatUptime(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}t ${m}m` : `${m}m`
}

// v5.1
// ── Lightbox ──────────────────────────────────────────────────────────────────
export function Lightbox({ captures, index, onClose }: { captures: Capture[]; index: number; onClose: () => void }) {
  const [cur, setCur]         = useState(index)
  const [zoom, setZoom]       = useState(1)
  const [pan, setPan]         = useState({ x: 0, y: 0 })
  const [dragging, setDragging]   = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [showHistogram, setShowHistogram] = useState(false)
  const [histogram, setHistogram]         = useState<{r:number[],g:number[],b:number[],lum:number[]} | null>(null)
  const [showMetadata, setShowMetadata]   = useState(false)
  const [sidecar, setSidecar]             = useState<any>(null)
  const [exif, setExif]               = useState<Record<string,string> | null>(null)
  const [overexposed, setOverexposed]     = useState(0)
  const [underexposed, setUnderexposed]   = useState(0)
  const imgRef = useRef<HTMLImageElement>(null)
  const metaRef = useRef<HTMLDivElement>(null)

  // Kompakt metadata række
  const MR = ({ l, v }: { l: string; v: React.ReactNode }) => (
    <div className="flex gap-1.5 min-w-0">
      <span className="text-white/35 shrink-0" style={{width:'90px'}}>{l}</span>
      <span className="text-white/75 min-w-0 truncate">{v ?? '—'}</span>
    </div>
  )
  const c = captures[cur]

  // Hent sidecar JSON når billede skifter
  useEffect(() => {
    let cancelled = false
    setSidecar(null)
    const sidecarName = c.filename.replace(/\.[^.]+$/, '.json')
    const apiUrl = (window as any).__TIMELAPSE_API__ || localStorage.getItem('timelapse_api_url') || ''
    const sidecarUrl = `${apiUrl}/api/sidecar/${encodeURIComponent(c.device_id)}/${encodeURIComponent(sidecarName)}`
    const loadSidecar = (attempt = 0) => {
      authFetch(`${sidecarUrl}?t=${Date.now()}`, { cache: 'no-store' })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (cancelled) return
          setSidecar(d)
          if (d && !d.ai_analysis && attempt < 4) {
            window.setTimeout(() => loadSidecar(attempt + 1), 10000)
          }
        })
        .catch(() => {})
    }
    loadSidecar()
    authFetch(`${apiUrl}/api/exif/${encodeURIComponent(c.device_id)}/${encodeURIComponent(c.filename)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setExif(d?.exif ?? null) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [cur, c.device_id, c.filename])

  // Compute histogram from image pixels via canvas
  function computeHistogram() {
    const img = imgRef.current
    if (!img || !img.complete) return
    try {
      const canvas  = document.createElement('canvas')
      const scale   = Math.min(1, 400 / Math.max(img.naturalWidth, img.naturalHeight))
      canvas.width  = Math.round(img.naturalWidth * scale)
      canvas.height = Math.round(img.naturalHeight * scale)
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      const r   = new Array(256).fill(0)
      const g   = new Array(256).fill(0)
      const b   = new Array(256).fill(0)
      const lum = new Array(256).fill(0)
      let over = 0, under = 0
      for (let i = 0; i < data.length; i += 4) {
        const rv = data[i], gv = data[i+1], bv = data[i+2]
        r[rv]++; g[gv]++; b[bv]++
        const l = Math.round(0.299 * rv + 0.587 * gv + 0.114 * bv)
        lum[l]++
        if (rv > 250 && gv > 250 && bv > 250) over++
        if (rv < 5  && gv < 5  && bv < 5)  under++
      }
      const total = canvas.width * canvas.height
      setOverexposed(Math.round(100 * over / total * 10) / 10)
      setUnderexposed(Math.round(100 * under / total * 10) / 10)
      setHistogram({ r, g, b, lum })
    } catch {
      setHistogram(null)
    }
  }

  useEffect(() => {
    setHistogram(null)
    setOverexposed(0)
    setUnderexposed(0)
    setExif(null)
  }, [cur])

  const prev = useCallback(() => { setCur(i => Math.max(0, i - 1)); setZoom(1); setPan({ x: 0, y: 0 }) }, [])
  const next = useCallback(() => { setCur(i => Math.min(captures.length - 1, i + 1)); setZoom(1); setPan({ x: 0, y: 0 }) }, [captures.length])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === '+' || e.key === '=') setZoom(z => Math.min(z + 0.5, 5))
      if (e.key === '-') setZoom(z => { const nz = Math.max(z - 0.5, 1); if (nz === 1) setPan({ x: 0, y: 0 }); return nz })
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose, prev, next])

  function onWheel(e: React.WheelEvent) {
    e.stopPropagation()
    // Ignorer wheel events fra metadata panelet
    if (metaRef.current && metaRef.current.contains(e.target as Node)) return
    const delta = e.deltaY > 0 ? -0.3 : 0.3
    setZoom(z => { const nz = Math.max(1, Math.min(z + delta, 5)); if (nz === 1) setPan({ x: 0, y: 0 }); return nz })
  }

  function onMouseDown(e: React.MouseEvent) {
    if (zoom <= 1) return
    setDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragging) return
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
  }
  function onMouseUp() { setDragging(false) }

  const time = c.captured_at
    ? new Date(c.captured_at).toLocaleString('da-DK', { timeZone: getTz(), day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '–'

  // Parse kunde/site/kamera fra filnavn: Kunde_Site_Kamera_YYYYMMDD_HHMMSS.jpg
  const nameParts = c.filename?.replace('.jpg','').split('_') ?? []
  const kunde    = nameParts[0] ?? '–'
  const site     = nameParts[1] ?? '–'
  const kamera   = nameParts[2] ?? '–'

  return (
    <div className="fixed inset-0 z-50 bg-black/95 flex flex-col" onClick={zoom === 1 ? onClose : undefined}>
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 text-white flex-shrink-0" onClick={e => e.stopPropagation()}>
        <div className="text-sm flex items-center gap-3 flex-wrap">
          <span className="font-medium">{time}</span>
          <span className="text-white/50 text-xs">{cur + 1} / {captures.length}</span>
          {c.filesize_mb && <span className="text-white/40 text-xs">{c.filesize_mb} MB</span>}
          {c.blur_score != null && <span className="text-white/40 text-xs">blur {Math.round(c.blur_score)}</span>}
          {!c.quality_passed && <span className="text-red-400 text-xs font-medium">Kvalitet FEJL</span>}
        </div>
        <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-white/10 rounded-lg px-2 py-1">
            <button onClick={() => setZoom(z => { const nz = Math.max(z - 0.5, 1); if (nz === 1) setPan({ x: 0, y: 0 }); return nz })}
              className="text-white/70 hover:text-white w-6 h-6 flex items-center justify-center text-lg font-light">−</button>
            <span className="text-white/70 text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom(z => Math.min(z + 0.5, 5))}
              className="text-white/70 hover:text-white w-6 h-6 flex items-center justify-center text-lg font-light">+</button>
          </div>
          {zoom > 1 && (
            <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}
              className="text-white/50 hover:text-white text-xs px-2 py-1 bg-white/10 rounded-lg">Reset</button>
          )}
          <button onClick={() => {
              const next = !showHistogram
              setShowHistogram(next)
              if (next) {
                const tryCompute = (n: number) => {
                  const img = imgRef.current
                  if (img && img.complete && img.naturalWidth > 0) {
                    computeHistogram()
                  } else if (n > 0) {
                    setTimeout(() => tryCompute(n - 1), 200)
                  }
                }
                tryCompute(10)
              }
            }}
            className={`text-xs px-2 py-1 rounded-lg transition-colors ${showHistogram ? 'bg-sky-500/40 text-sky-200' : 'bg-white/10 text-white/50 hover:text-white'}`}>
            Histogram
          </button>
          <button onClick={() => setShowMetadata(m => !m)}
            className={`text-xs px-2 py-1 rounded-lg transition-colors ${showMetadata ? 'bg-emerald-500/40 text-emerald-200' : 'bg-white/10 text-white/50 hover:text-white'}`}>
            {sidecar ? '🔒 Metadata' : 'Metadata'}
          </button>
          <a href={getImageUrl(c.device_id, c.filename)} download={c.filename} onClick={e => e.stopPropagation()}
            className="text-white/50 hover:text-white text-xs px-2 py-1 bg-white/10 rounded-lg">Download</a>
          <button onClick={onClose} className="p-1 hover:text-white/70 ml-1"><X className="w-5 h-5" /></button>
        </div>
      </div>

      {/* Image area */}
      <div className="flex-1 relative overflow-hidden flex items-center justify-center"
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        style={{ cursor: zoom > 1 ? (dragging ? 'grabbing' : 'grab') : 'default' }}
        onClick={e => e.stopPropagation()}
      >
        <img
          ref={imgRef}
          src={getImageUrl(c.device_id, c.filename)}
          alt={c.filename}
          draggable={false}
          onLoad={() => { if (showHistogram) computeHistogram() }}
          style={{
            transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
            transformOrigin: 'center center',
            transition: dragging ? 'none' : 'transform 0.15s ease',
            maxWidth: '100%',
            maxHeight: '100%',
            width: 'auto',
            height: 'auto',
            display: 'block',
            userSelect: 'none',
          }}
        />
        {cur > 0 && (
          <button onClick={e => { e.stopPropagation(); prev() }}
            className="absolute left-2 top-1/2 -translate-y-1/2 p-2 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors">
            <ChevronLeft className="w-6 h-6" />
          </button>
        )}
        {cur < captures.length - 1 && (
          <button onClick={e => { e.stopPropagation(); next() }}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors">
            <ChevronRight className="w-6 h-6" />
          </button>
        )}
      </div>

      {/* Histogram panel */}
      {showHistogram && histogram && (
        <div className="flex-shrink-0 bg-black/80 px-4 py-3 flex gap-4 items-end" onClick={e => e.stopPropagation()}>
          {(['lum','r','g','b'] as const).map(ch => {
            const colors: Record<string, string> = { lum: '#d1d5db', r: '#f87171', g: '#4ade80', b: '#60a5fa' }
            const labels: Record<string, string> = { lum: 'L', r: 'R', g: 'G', b: 'B' }
            const data = histogram[ch]
            const max  = Math.max(...data.slice(1, 255)) || 1
            const H = 48
            return (
              <div key={ch} className="flex flex-col items-center gap-1">
                <div className="relative" style={{ width: 130, height: H + 12 }}>
                  <div style={{ position: 'absolute', left: 0, top: 0, width: 1, height: H, background: 'rgba(255,255,255,0.35)' }} />
                  <div style={{ position: 'absolute', left: 0, top: H - 1, right: 0, height: 1, background: 'rgba(255,255,255,0.35)' }} />
                  {/* Vandret clip-alarm linje */}
                  <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 2, background: '#fbbf24', opacity: 0.8 }} />
                  <div className="absolute inset-0 flex items-end gap-px" style={{ height: H }}>
                    {Array.from({ length: 64 }, (_, i) => {
                      const val = data.slice(i*4, i*4+4).reduce((a, b) => a + b, 0)
                      const h = Math.max(1, Math.round((val / max / 4) * H))
                      return <div key={i} style={{ flex: 1, height: h, background: colors[ch], opacity: 0.85 }} />
                    })}
                  </div>
                </div>
                <span style={{ fontSize: 10, color: colors[ch] }}>{labels[ch]}</span>
              </div>
            )
          })}
          <div className="ml-4 flex flex-col justify-end gap-1 text-xs pb-5">
            <div className={`flex items-center gap-1.5 ${overexposed > 1 ? 'text-amber-400' : 'text-white/40'}`}>
              <span className="w-2 h-2 rounded-full bg-current inline-block"></span>
              Overbelyst: {overexposed}%
            </div>
            <div className={`flex items-center gap-1.5 ${underexposed > 5 ? 'text-slate-400' : 'text-white/40'}`}>
              <span className="w-2 h-2 rounded-full bg-current inline-block"></span>
              For mørk: {underexposed}%
            </div>
            {c.blur_score != null && (
              <div className={`flex items-center gap-1.5 ${c.blur_score < 80 ? 'text-red-400' : 'text-white/40'}`}>
                <span className="w-2 h-2 rounded-full bg-current inline-block"></span>
                Blur: {Math.round(c.blur_score)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Metadata + integritetspanel */}
      {showMetadata && (
        <div ref={metaRef} className="flex-shrink-0 bg-black/90 border-t border-white/10 px-4 py-3 overflow-y-auto" style={{maxHeight: '60vh', overscrollBehavior: 'contain'}} onClick={e => e.stopPropagation()} onWheel={e => e.stopPropagation()} onMouseDown={e => e.stopPropagation()}>
          {!sidecar ? (
            <p className="text-white/40 text-xs italic">Ingen sidecar — billede optaget før v2.2.0 eller ikke uploadet endnu.</p>
          ) : (
            <div className="grid grid-cols-3 gap-x-6 gap-y-0 text-xs">

              {/* Kolonne 1: Integritet + Kvalitet */}
              <div className="space-y-0.5">
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-1.5">🔒 Integritet</p>
                <MR l="SHA-256" v={<span className="font-mono text-[9px] break-all">{sidecar.integrity?.sha256_original}</span>} />
                <MR l="Optaget UTC" v={sidecar.integrity?.captured_at_utc?.replace('T',' ').slice(0,19)} />
                <MR l="Lokal tid" v={sidecar.integrity?.captured_at_local?.replace('T',' ').slice(0,19)} />
                <MR l="Tidszone" v={sidecar.integrity?.timezone} />
                <MR l="Original uberørt" v={<span className={sidecar.integrity?.original_unmodified ? 'text-emerald-400' : 'text-red-400'}>{sidecar.integrity?.original_unmodified ? '✅ Ja' : '⚠️ Nej'}</span>} />
                <MR l="XMP skrevet" v={<span className={sidecar.integrity?.xmp_written ? 'text-emerald-400' : 'text-white/40'}>{sidecar.integrity?.xmp_written ? '✅ Ja' : 'Nej'}</span>} />
                {sidecar.added_metadata?.fields_added?.length > 0 && (
                  <MR l="Tilføjede felter" v={<span className="text-amber-300/80">{sidecar.added_metadata.fields_added.join(', ')}</span>} />
                )}
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mt-2 mb-1.5">📊 Kvalitet</p>
                <MR l="Blur score" v={c.blur_score != null ? `${Math.round(c.blur_score)} ${c.blur_score > 100 ? '✅' : '⚠️ lav'}` : '—'} />
                <MR l="Lysstyrke" v={c.brightness != null ? `${Math.round(c.brightness)}/255` : '—'} />
                <MR l="Kvalitetsflag" v={<span className={c.quality_passed ? 'text-emerald-400' : 'text-red-400'}>{c.quality_flag ?? '—'}</span>} />
                <MR l="Størrelse" v={c.filesize_mb != null ? `${c.filesize_mb.toFixed(1)} MB` : '—'} />

                {/* QA ANALYSE */}
                {(() => {
                  const ai = parseAI(c, sidecar)
                  const causeLabels: Record<string, string> = {
                    ok: 'OK', condensation_on_lens: 'Kondens på linse',
                    dirty_lens: 'Snavset linse', focus_drift: 'Fokusdrift',
                    camera_moved: 'Kamera flyttet', obstruction: 'Afskærmning',
                    rain_on_lens: 'Regn på linse', sun_flare: 'Solreflektion',
                    night_capture: 'Natkamera', hardware_failure: 'Hardwarefejl',
                    unknown: 'Ukendt',
                  }
                  const actionLabels: Record<string, string> = {
                    none: '—', inspect_camera_housing: 'Tjek kamerahus',
                    clean_lens: 'Rengør linse', check_focus: 'Tjek fokus',
                    reposition_camera: 'Juster kamera',
                    wait_for_conditions: 'Afvent vejr', replace_camera: 'Udskift kamera',
                  }
                  return (
                    <div className="mt-2">
                      <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-1.5">🔬 QA</p>
                      {!ai ? (
                        <p className="text-white/30 text-xs italic">Ikke analyseret endnu</p>
                      ) : ai.scene_dk ? (
                        <>
                          <MR l="Scene" v={<span className="text-white/60 text-[10px] leading-tight">{ai.scene_dk}</span>} />
                          <MR l="Kvalitet" v={<span className={ai.quality_ok === false ? 'text-amber-400' : 'text-emerald-400'}>{ai.quality_flag ?? '—'}</span>} />
                          <MR l="Ændring" v={ai.change_detected ? (ai.change_summary ?? 'Ja') : 'Nej'} />
                          <MR l="Model" v={<span className="text-white/40 text-[10px]">{ai.model}{ai.used_thumbnail ? ' · thumbnail' : ''}</span>} />
                          {((ai.tags?.length ?? 0) > 0 || (ai.new_tags?.length ?? 0) > 0 || (c.ai_tags?.length ?? 0) > 0) && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {[...(ai.tags ?? []), ...(ai.new_tags ?? []), ...(c.ai_tags ?? [])].filter((tag, idx, arr) => arr.indexOf(tag) === idx).slice(0, 24).map((tag: string) => (
                                <span key={tag} className="text-[10px] bg-white/10 text-white/60 px-1.5 py-0.5 rounded cursor-pointer hover:bg-white/20" title={`Søg på #${tag}`}>
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          )}
                          {(c.ai_analyzed_at || ai.analyzed_at) && (
                            <MR l="Analyseret" v={
                              <span className="text-white/30 text-[10px]">
                                {new Date(c.ai_analyzed_at ?? ai.analyzed_at).toLocaleString('da-DK', {timeZone: getTz(), day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'})}
                              </span>
                            } />
                          )}
                        </>
                      ) : (
                        <>
                          <MR l="Status" v={
                            <span className={`font-medium ${ai.alarm ? 'text-red-400' : ai.is_anomaly ? 'text-amber-400' : 'text-emerald-400'}`}>
                              {ai.alarm ? '🚨 ' : ai.is_anomaly ? '⚠️ ' : '✓ '}
                              {causeLabels[ai.probable_cause] ?? ai.probable_cause}
                            </span>
                          } />
                          <MR l="Konfidence" v={`${Math.round((ai.confidence ?? 0) * 100)}%`} />
                          <MR l="Beskrivelse" v={<span className="text-white/60 text-[10px] leading-tight">{ai.description}</span>} />
                          {ai.action && ai.action !== 'none' && (
                            <MR l="Handling" v={<span className="text-amber-300">{actionLabels[ai.action] ?? ai.action}</span>} />
                          )}
                          <MR l="Model" v={<span className="text-white/40 text-[10px]">{ai.model}{ai.used_thumbnail ? ' · thumbnail' : ''}</span>} />
                          {c.ai_tags && c.ai_tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {c.ai_tags.map((tag: string) => (
                                <span key={tag} className="text-[10px] bg-white/10 text-white/60 px-1.5 py-0.5 rounded cursor-pointer hover:bg-white/20" title={`Søg på #${tag}`}>
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          )}
                          {c.ai_analyzed_at && (
                            <MR l="Analyseret" v={
                              <span className="text-white/30 text-[10px]">
                                {new Date(c.ai_analyzed_at).toLocaleString('da-DK', {timeZone: getTz(), day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'})}
                              </span>
                            } />
                          )}
                        </>
                      )}
                    </div>
                  )
                })()}

              </div>

              {/* Kolonne 2: Kamera EXIF */}
              <div className="space-y-0.5">
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-1.5">📷 Kamera EXIF</p>
                <MR l="Model" v={sidecar.camera?.model} />
                <MR l="ISO" v={sidecar.camera?.iso} />
                <MR l="Lukker" v={sidecar.camera?.shutter_speed} />
                <MR l="Blænde" v={sidecar.camera?.aperture} />
                <MR l="Fokustilstand" v={sidecar.camera?.focus_mode} />
                <MR l="USB port" v={sidecar.camera?.gphoto2_port} />
                <MR l="Relay GPIO" v={sidecar.camera?.relay_gpio_pin} />
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mt-2 mb-1.5">🏗️ Projekt</p>
                <MR l="Kunde" v={sidecar.project?.customer || '—'} />
                <MR l="Site" v={sidecar.project?.site || '—'} />
                <MR l="Kamera" v={sidecar.project?.camera_name || '—'} />
                <MR l="Device ID" v={<span className="font-mono text-[10px]">{sidecar.project?.device_id}</span>} />
                <MR l="Kamera index" v={sidecar.project?.camera_index ?? '—'} />
                <MR l="TLP version" v={sidecar.timelapse_pro?.version} />
              </div>

              {/* Kolonne 3: Lokation + Orientering */}
              <div className="space-y-0.5">
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-1.5">📍 Lokation</p>
                <MR l="GPS" v={sidecar.location?.gps_lat != null ? `${sidecar.location.gps_lat.toFixed(6)}°, ${sidecar.location.gps_lon?.toFixed(6)}°` : '—'} />
                <MR l="Højde" v={sidecar.location?.gps_alt_m != null ? `${sidecar.location.gps_alt_m} m` : '—'} />
                <MR l="GPS kilde" v={sidecar.location?.gps_source || '—'} />
                <MR l="Adresse" v={sidecar.location?.address || '—'} />
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mt-2 mb-1.5">🧭 Orientering</p>
                <MR l="Azimut" v={sidecar.location?.azimuth_deg != null ? `${sidecar.location.azimuth_deg}°` : '—'} />
                <MR l="Tilt" v={sidecar.location?.tilt_deg != null ? `${sidecar.location.tilt_deg}°` : '—'} />
                <MR l="Montagehøjde" v={sidecar.location?.mount_height_m != null ? `${sidecar.location.mount_height_m} m` : '—'} />
                <MR l="Horis. FOV" v={sidecar.location?.fov_horizontal_deg != null ? `${sidecar.location.fov_horizontal_deg}°` : '—'} />
                <MR l="Vert. FOV" v={sidecar.location?.fov_vertical_deg != null ? `${sidecar.location.fov_vertical_deg}°` : '—'} />
                <MR l="Perspektiv" v={sidecar.location?.perspective || '—'} />
              </div>

              {/* Raw EXIF */}
              {exif && Object.keys(exif).length > 0 && (
              <div className="col-span-3 mt-3 border-t border-white/10 pt-3">
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-semibold mb-2">📷 Raw EXIF fra JPG ({Object.keys(exif).length} felter)</p>
                <div className="grid grid-cols-2 gap-x-8 gap-y-0.5 text-xs">
                  {Object.entries(exif)
                    .filter(([k]) => !['MakerNote','UserComment','PrintImageMatching','FlashPixVersion','ExifVersion','ComponentsConfiguration','SceneType','FileSource','GPSInfo'].includes(k))
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([k, v]) => (
                    <div key={k} className="flex gap-2 min-w-0">
                      <span className="text-white/35 shrink-0 text-[10px]" style={{width:'160px'}}>{k}</span>
                      <span className="text-white/75 min-w-0 truncate text-[10px]" title={v}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              )}

            </div>
          )}
        </div>
      )}
      {/* Filmstrip


      {/* Filmstrip */}
      <div className="flex-shrink-0 flex gap-1 overflow-x-auto px-4 py-2 justify-center bg-black/50" onClick={e => e.stopPropagation()}>
        {captures.map((cap, i) => {
          const nearby = Math.abs(i - cur) <= 8
          return (
            <button key={cap.id} onClick={() => { setCur(i); setZoom(1); setPan({ x: 0, y: 0 }) }}
              className={`flex-shrink-0 w-14 h-10 rounded overflow-hidden border-2 transition-all ${
                i === cur ? 'border-sky-400 opacity-100' : 'border-transparent opacity-40 hover:opacity-70'
              } ${!cap.quality_passed ? 'ring-1 ring-red-500' : ''}`}
            >
              {nearby
                ? <img src={getThumbnailUrl(cap.device_id, cap.filename)} alt="" className="w-full h-full object-cover" />
                : <div className="w-full h-full bg-white/5" />
              }
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Capture thumbnail ─────────────────────────────────────────────────────────

function parseAI(capture: any, sidecar?: any): Record<string, any> | null {
  if (sidecar?.ai_analysis) return sidecar.ai_analysis
  if (!capture.ai_result) return null
  try { return JSON.parse(capture.ai_result) } catch { return null }
}

export function CaptureCard({ capture, onClick }: { capture: Capture; onClick: () => void }) {
  const time = capture.captured_at
    ? new Date(capture.captured_at).toLocaleString('da-DK', { timeZone: getTz(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '–'
  const passed = capture.quality_passed !== false
  const thumbUrl = getThumbnailUrl(capture.device_id, capture.filename)
  const [imgOk, setImgOk] = useState(true)

  return (
    <div
      onClick={onClick}
      className={`rounded-xl border overflow-hidden bg-white cursor-pointer hover:ring-2 hover:ring-sky-300 transition-all ${passed ? 'border-gray-200' : 'border-red-200'}`}
    >
      <div className="aspect-video bg-slate-100 relative overflow-hidden flex items-center justify-center">
        {imgOk ? (
          <img src={thumbUrl} alt={capture.filename} className="w-full h-full object-cover" loading="lazy" onError={() => setImgOk(false)} />
        ) : (
          <Image className="w-8 h-8 text-slate-300" />
        )}
        <span className="absolute bottom-1.5 right-1.5 text-xs bg-black/50 text-white px-1 py-0.5 rounded">
          {capture.filesize_mb ? `${capture.filesize_mb} MB` : '–'}
        </span>
        {!passed && <span className="absolute top-1.5 left-1.5 text-xs bg-red-500 text-white px-1.5 py-0.5 rounded">Fejlet</span>}
      </div>
      <div className="px-2 py-1.5">
        <div className="flex items-center justify-between gap-1">
          <p className="text-xs font-medium text-gray-700">{time}</p>
          {capture.blur_score != null && (
            <p className={`text-xs font-medium flex-shrink-0 ${capture.blur_score < 80 ? 'text-amber-500' : 'text-gray-400'}`}>
              ⬡ {Math.round(capture.blur_score)}
            </p>
          )}
          {/* QA-BADGE */}
          {(() => {
            const ai = parseAI(capture)
            if (!ai) return null
            if (ai.alarm)      return <span title={ai.description} className="text-xs flex-shrink-0 cursor-help">🚨</span>
            if (ai.is_anomaly) return <span title={ai.description} className="text-xs flex-shrink-0 cursor-help">⚠️</span>
            if (ai.probable_cause === 'ok') return <span title="QA: OK" className="text-[9px] flex-shrink-0 text-emerald-400 font-bold cursor-help">QA✓</span>
            return null
          })()}
        </div>
        {(() => {
          const fn = capture.filename.replace('.jpg', '').replace('.JPG', '')
          const parts = fn.split('_')
          const dateIdx = parts.findIndex((p: string) => /^\d{8}$/.test(p))
          const nameParts = dateIdx > 0 ? parts.slice(0, dateIdx) : parts
          const customer = nameParts[0] ?? ''
          const camera   = nameParts.slice(-2).join(' ')
          const site     = nameParts.slice(1, -2).join(' ')
          return (
            <div className="border-t border-gray-100 pt-1 mt-1">
              <p className="text-xs font-bold text-gray-900 leading-tight truncate">{customer}</p>
              <p className="text-xs text-gray-800 leading-tight mt-0.5 truncate">{site}</p>
              <p className="text-xs text-gray-700 leading-tight mt-0.5 truncate">{camera}</p>
            </div>
          )
        })()}
        {capture.ai_tags && (capture.ai_tags as string[]).length > 0 && (
          <div className="flex flex-wrap gap-0.5 mt-1">
            {(capture.ai_tags as string[]).slice(0, 3).map((t: string) => (
              <span key={t} className="text-[9px] bg-gray-100 text-gray-500 px-1 py-0.5 rounded-full">#{t}</span>
            ))}
            {(capture.ai_tags as string[]).length > 3 && (
              <span className="text-[9px] text-gray-400">+{(capture.ai_tags as string[]).length - 3}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Statistics ────────────────────────────────────────────────────────────────

// ── Camera param row (bruges i ConfigTab) ────────────────────────────────────
function CameraParamRow({ param, deviceId }: {
  param: any; deviceId: string
}) {
  const [editing, setEditing]         = useState(false)
  const [value, setValue]             = useState(param.current)
  const [displayValue, setDisplayValue] = useState(param.current)
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)

  async function save() {
    setSaving(true)
    try {
      const key = param.path.replace('/main/', '')
      await setParam(deviceId, key, value)
      // Opdater camera_params i headend så refresh ikke nulstiller værdien
      const apiUrl = (await import('../api/client')).getApiUrl()
      const encodedDeviceId = pathSegment(deviceId)
      const cfg = await (await authFetch(`${apiUrl}/api/admin/devices/${encodedDeviceId}`)).json()
      const updatedParams = (cfg?.device?.device_config ? 
        JSON.parse(typeof cfg.device.device_config === 'string' ? cfg.device.device_config : JSON.stringify(cfg.device.device_config)) : {}
      )
      if (updatedParams.camera_params) {
        updatedParams.camera_params = updatedParams.camera_params.map((cp: any) =>
          cp.path.endsWith(key) ? { ...cp, current: value } : cp
        )
        await authFetch(`${apiUrl}/api/admin/devices/${encodedDeviceId}/config`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ camera_params: updatedParams.camera_params })
        })
      }
      setSaved(true)
      setDisplayValue(value)
      setTimeout(() => { setSaved(false); setEditing(false) }, 800)
    } catch (err) { 
      console.error('save error:', err)
    }
    setSaving(false)
  }

  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-50">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-700 truncate">{param.label}</div>
        <div className="text-xs text-gray-400 truncate">{param.path}</div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {!editing ? (
          <>
            <span className="text-sm px-2 py-0.5 rounded font-mono text-sky-700 bg-sky-50">{displayValue || '–'}</span>
            <button onClick={() => { setValue(displayValue); setEditing(true) }}
              className="p-1 text-gray-400 hover:text-sky-600 rounded">
              <Settings className="w-3.5 h-3.5" />
            </button>
          </>
        ) : (
          <div className="flex items-center gap-1.5">
            {param.choices?.length > 0 ? (
              <select value={value} onChange={e => setValue(e.target.value)}
                className="text-sm border border-sky-300 rounded px-2 py-0.5 bg-white focus:outline-none">
                {param.choices.map((c: any) => (
                  <option key={c.index} value={c.label}>{c.label}</option>
                ))}
              </select>
            ) : (
              <input value={value} onChange={e => setValue(e.target.value)}
                className="text-sm border border-sky-300 rounded px-2 py-0.5 w-28 focus:outline-none"
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
              />
            )}
            <button onClick={save} disabled={saving}
              className="p-1 text-green-600 hover:text-green-700 rounded">
              <Check className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setEditing(false)} className="p-1 text-gray-400 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function ConfigTab({ deviceId }: { deviceId: string }) {
  const [cfg, setCfg]       = useState<any>(null)
  const [info, setInfo]     = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg]       = useState<string | null>(null)

  useEffect(() => {
    getConfig(deviceId).then(d => { setCfg(d); setInfo(d?.device ?? {}) })
  }, [deviceId])

  async function saveConfig() {
    setSaving(true); setMsg(null)
    try {
      await updateConfig(deviceId, cfg)
      setMsg('Konfiguration gemt ✓')
    } catch { setMsg('Fejl ved gemning') }
    setSaving(false)
  }

  async function saveInfo() {
    setSaving(true); setMsg(null)
    try {
      await updateDeviceInfo(deviceId, info)
      setMsg('Enhedsinfo gemt ✓')
    } catch { setMsg('Fejl ved gemning') }
    setSaving(false)
  }

  if (!cfg) return <div className="text-center py-12 text-gray-400">Indlæser konfiguration…</div>

  const schedule = cfg.schedule ?? {}
  const camera   = cfg.camera   ?? {}
  const sftp     = cfg.sftp     ?? {}

  return (
    <div className="space-y-5 max-w-2xl">
      {msg && (
        <div className={`px-4 py-2 rounded-lg text-sm font-medium ${msg.includes('✓') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      {/* Enhedsidentitet */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Enhedsidentitet</h3>
        <div className="space-y-3">
          {[
            { label: 'Kundenavn', key: 'customer_name' },
            { label: 'Sitenavn', key: 'site_name' },
            { label: 'Kameranavn', key: 'camera_name' },
          ].map(({ label, key }) => (
            <div key={key}>
              <label className="text-xs text-gray-400 block mb-1">{label}</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={info?.[key] ?? ''} onChange={e => setInfo({ ...info, [key]: e.target.value })} />
            </div>
          ))}
          <button onClick={saveInfo} disabled={saving}
            className="mt-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            Gem enhedsinfo
          </button>
        </div>
      </div>

      {/* Kamera-parametre */}
      {cfg?.camera_params && cfg.camera_params.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700">Kamera-parametre</h3>
            <span className="text-xs text-gray-400">{cfg.camera_params.length} parametre · fra seneste lab-session</span>
          </div>
          <div className="space-y-1">
            {cfg.camera_params
              .filter((p: any) => !p.readonly && p.current)
              .map((p: any) => (
              <CameraParamRow key={p.path} param={p} deviceId={deviceId} />
            ))}
          </div>
          <p className="text-xs text-gray-300 mt-3">Readonly-parametre vises ikke. Gå til Kamera-lab for fuld liste.</p>
        </div>
      )}

      {/* GPS / Lokation */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">GPS og Lokation</h3>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Breddegrad (lat)</label>
              <input type="number" step="0.000001" placeholder="55.676098"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                value={cfg?.location?.gps_lat ?? ''}
                onChange={e => setCfg({ ...cfg, location: { ...(cfg.location ?? {}), gps_lat: e.target.value ? parseFloat(e.target.value) : null } })} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Længdegrad (lon)</label>
              <input type="number" step="0.000001" placeholder="12.568337"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                value={cfg?.location?.gps_lon ?? ''}
                onChange={e => setCfg({ ...cfg, location: { ...(cfg.location ?? {}), gps_lon: e.target.value ? parseFloat(e.target.value) : null } })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Højde (meter over hav)</label>
              <input type="number" step="1" placeholder="0"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                value={cfg?.location?.gps_alt ?? ''}
                onChange={e => setCfg({ ...cfg, location: { ...(cfg.location ?? {}), gps_alt: e.target.value ? parseFloat(e.target.value) : null } })} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">GPS kilde</label>
              <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={cfg?.location?.gps_source ?? 'manual'}
                onChange={e => setCfg({ ...cfg, location: { ...(cfg.location ?? {}), gps_source: e.target.value } })}>
                <option value="manual">Manuelt indsat</option>
                <option value="gpsd">gpsd (Orange Pi GPS modul)</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Adresse (valgfri)</label>
            <input type="text" placeholder="Nordre Villavej 17c, 7100 Vejle"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={cfg?.location?.address ?? ''}
              onChange={e => setCfg({ ...cfg, location: { ...(cfg.location ?? {}), address: e.target.value } })} />
          </div>
          {cfg?.location?.gps_lat && cfg?.location?.gps_lon && (
            <a href={`https://www.openstreetmap.org/?mlat=${cfg.location.gps_lat}&mlon=${cfg.location.gps_lon}&zoom=17`}
              target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-sky-500 hover:text-sky-700">
              🗺️ Vis på kort (OpenStreetMap)
            </a>
          )}
        </div>
      </div>

      {/* Schedule */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Optagelsesplan</h3>

        {/* Mode selector */}
        <div className="flex gap-2 mb-4">
          {(['interval', 'fixed'] as const).map(m => (
            <button key={m} onClick={() => setCfg({ ...cfg, schedule: { ...schedule, capture_mode: m } })}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                (schedule.capture_mode ?? 'interval') === m
                  ? 'bg-sky-500 text-white border-sky-500'
                  : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300'
              }`}>
              {m === 'interval' ? 'Interval' : 'Faste tidspunkter'}
            </button>
          ))}
        </div>

        {(schedule.capture_mode ?? 'interval') === 'interval' ? (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Interval (minutter)</label>
              <input type="number" min={1} max={720} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={schedule.interval_minutes ?? 10}
                onChange={e => setCfg({ ...cfg, schedule: { ...schedule, interval_minutes: parseInt(e.target.value) } })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Aktiv fra</label>
                <input type="time" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  value={schedule.active_hours?.[0] ?? '06:00'}
                  onChange={e => setCfg({ ...cfg, schedule: { ...schedule, active_hours: [e.target.value, schedule.active_hours?.[1] ?? '21:00'] } })} />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Aktiv til</label>
                <input type="time" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  value={schedule.active_hours?.[1] ?? '21:00'}
                  onChange={e => setCfg({ ...cfg, schedule: { ...schedule, active_hours: [schedule.active_hours?.[0] ?? '06:00', e.target.value] } })} />
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="text-xs text-gray-400 block">Tidspunkter for optagelse</label>
            <div className="space-y-2">
              {(schedule.capture_times ?? ['08:00']).map((t: string, i: number) => (
                <div key={i} className="flex gap-2 items-center">
                  <input type="time" className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                    value={t}
                    onChange={e => {
                      const times = [...(schedule.capture_times ?? [])]
                      times[i] = e.target.value
                      times.sort()
                      setCfg({ ...cfg, schedule: { ...schedule, capture_times: times } })
                    }} />
                  <button onClick={() => {
                    const times = (schedule.capture_times ?? []).filter((_: string, j: number) => j !== i)
                    setCfg({ ...cfg, schedule: { ...schedule, capture_times: times } })
                  }} className="text-red-400 hover:text-red-600 px-2 py-1 text-lg leading-none">×</button>
                </div>
              ))}
            </div>
            <button onClick={() => {
              const times = [...(schedule.capture_times ?? []), '12:00']
              times.sort()
              setCfg({ ...cfg, schedule: { ...schedule, capture_times: times } })
            }} className="text-sky-500 hover:text-sky-700 text-sm flex items-center gap-1">
              + Tilføj tidspunkt
            </button>
            <p className="text-xs text-gray-400 mt-1">Tidspunkterne koordineres automatisk på tværs af kameraer på samme site.</p>
          </div>
        )}
      </div>

      {/* Kamera */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Kamera</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Opvarmningstid (sekunder)</label>
            <input type="number" min={1} max={60} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={camera.relay_on_seconds_before ?? 10}
              onChange={e => setCfg({ ...cfg, camera: { ...camera, relay_on_seconds_before: parseInt(e.target.value) } })} />
          </div>
          <div className="flex items-center gap-3">
            <input type="checkbox" id="delete_after"
              checked={camera.delete_after_download ?? true}
              onChange={e => setCfg({ ...cfg, camera: { ...camera, delete_after_download: e.target.checked } })} />
            <label htmlFor="delete_after" className="text-sm text-gray-700">Slet billede fra kamera efter download</label>
          </div>
        </div>
      </div>

      <button onClick={saveConfig} disabled={saving}
        className="w-full py-2.5 bg-sky-500 text-white text-sm font-medium rounded-lg hover:bg-sky-600 disabled:opacity-50">
        {saving ? 'Gemmer…' : 'Gem konfiguration'}
      </button>
    </div>
  )
}

function ProgressBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="h-1.5 bg-gray-100 rounded-full mt-1.5 overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  )
}

function DriftBadge({ param, expected, actual }: { param: string; expected: string; actual: string }) {
  const labels: Record<string, string> = {
    focus_mode: 'Fokus', image_format: 'Format', iso: 'ISO',
    white_balance: 'Hvidbalance', color_space: 'Farverum',
    exposure_comp: 'Eksponering', ae_mode: 'AE-tilstand',
    picture_style: 'Billedstil', metering_mode: 'Måling',
  }
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0 text-xs">
      <span className="text-gray-500">{labels[param] ?? param}</span>
      <div className="flex items-center gap-2">
        <span className="text-gray-300 line-through">{expected}</span>
        <span className="text-red-600 font-medium">{actual}</span>
      </div>
    </div>
  )
}

function StatsTab({ captures, diagnostics, deviceId }: { captures: Capture[]; diagnostics: any; deviceId: string }) {
  const [diagHistory, setDiagHistory] = useState<any[]>([])
  useEffect(() => {
    const apiUrl = (window as any).__TIMELAPSE_API__ || localStorage.getItem('timelapse_api_url') || ''
    authFetch(`${apiUrl}/api/admin/devices/${pathSegment(deviceId)}/diagnostics/history?days=7&limit=500`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setDiagHistory(d))
      .catch(() => {})
  }, [deviceId])
  const sorted = [...captures].sort((a, b) =>
    new Date(a.captured_at ?? 0).getTime() - new Date(b.captured_at ?? 0).getTime()
  )

  const qualityData = sorted
    .filter(c => c.captured_at)
    .map(c => ({
      time: new Date(c.captured_at!).toLocaleTimeString('da-DK', { timeZone: getTz(), hour: '2-digit', minute: '2-digit' }),
      blur:       c.blur_score != null ? Math.round(c.blur_score) : null,
      brightness: c.brightness != null ? Math.round(c.brightness) : null,
      size:       c.filesize_mb ?? null,
      passed:     c.quality_passed,
    }))

  const passRate   = captures.length > 0 ? Math.round(100 * captures.filter(c => c.quality_passed).length / captures.length) : 0
  const uploadRate = captures.length > 0 ? Math.round(100 * captures.filter(c => c.uploaded).length / captures.length) : 0
  const avgBlur    = captures.filter(c => c.blur_score != null).length > 0
    ? Math.round(captures.reduce((s, c) => s + (c.blur_score ?? 0), 0) / captures.filter(c => c.blur_score != null).length) : 0

  // Parse camera diagnostics from diagnostics object
  const camDrift: any[] = (() => {
    try { return diagnostics?.cam_drift_json ? JSON.parse(diagnostics.cam_drift_json) : [] }
    catch { return [] }
  })()
  const camConfig: any = (() => {
    try { return diagnostics?.cam_config_json ? JSON.parse(diagnostics.cam_config_json) : null }
    catch { return null }
  })()

  const shutterPct   = diagnostics?.cam_shutter_pct
  const shutterAlarm = diagnostics?.cam_shutter_alarm
  const ssdUsedPct   = diagnostics?.ssd_used_pct
  const ntpOffset    = diagnostics?.ntp_offset_s

  return (
    <div className="space-y-5">

      {/* Capture statistik */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-xs text-gray-400 mb-1">Captures</p>
          <p className="text-2xl font-semibold text-gray-800">{captures.length}</p>
        </div>
        <div className={`bg-white rounded-xl border p-4 text-center ${passRate >= 95 ? 'border-emerald-200' : 'border-amber-200'}`}>
          <p className="text-xs text-gray-400 mb-1">Kvalitet OK</p>
          <p className={`text-2xl font-semibold ${passRate >= 95 ? 'text-emerald-600' : 'text-amber-600'}`}>{passRate}%</p>
        </div>
        <div className={`bg-white rounded-xl border p-4 text-center ${uploadRate >= 95 ? 'border-emerald-200' : 'border-amber-200'}`}>
          <p className="text-xs text-gray-400 mb-1">Uploadet</p>
          <p className={`text-2xl font-semibold ${uploadRate >= 95 ? 'text-emerald-600' : 'text-amber-600'}`}>{uploadRate}%</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-xs text-gray-400 mb-1">Gns. blur</p>
          <p className="text-2xl font-semibold text-gray-800">{avgBlur}</p>
        </div>
      </div>

      {/* Hardware diagnostik */}
      {diagnostics && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-1.5">
            <Heart className="w-4 h-4 text-red-400" />Heartbeat — Orange Pi
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {/* CPU */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">CPU temperatur</p>
              <p className={`font-semibold mt-0.5 ${(diagnostics.cpu_temp_c ?? 0) > 75 ? 'text-red-600' : (diagnostics.cpu_temp_c ?? 0) > 65 ? 'text-amber-600' : 'text-gray-700'}`}>
                {diagnostics.cpu_temp_c != null ? `${diagnostics.cpu_temp_c.toFixed(1)}°C` : '–'}
              </p>
              {diagnostics.cpu_temp_c != null && <ProgressBar pct={diagnostics.cpu_temp_c / 85 * 100} color={(diagnostics.cpu_temp_c > 75) ? 'bg-red-400' : (diagnostics.cpu_temp_c > 65) ? 'bg-amber-400' : 'bg-emerald-400'} />}
              <p className="text-xs text-gray-300 mt-1">Alarm ved &gt;75°C</p>
            </div>
            {/* CPU load */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">CPU load</p>
              <p className={`font-semibold mt-0.5 ${(diagnostics.cpu_load_pct ?? 0) > 80 ? 'text-amber-600' : 'text-gray-700'}`}>
                {diagnostics.cpu_load_pct != null ? `${diagnostics.cpu_load_pct.toFixed(1)}%` : '–'}
              </p>
              {diagnostics.cpu_load_pct != null && <ProgressBar pct={diagnostics.cpu_load_pct} color={(diagnostics.cpu_load_pct > 80) ? 'bg-amber-400' : 'bg-emerald-400'} />}
            </div>
            {/* SSD */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">SSD lager</p>
              <p className={`font-semibold mt-0.5 ${(ssdUsedPct ?? 0) > 85 ? 'text-red-600' : (ssdUsedPct ?? 0) > 70 ? 'text-amber-600' : 'text-gray-700'}`}>
                {ssdUsedPct != null ? `${ssdUsedPct.toFixed(1)}% brugt` : diagnostics.disk_used_gb != null ? `${diagnostics.disk_used_gb.toFixed(1)} GB` : '–'}
              </p>
              {ssdUsedPct != null && <ProgressBar pct={ssdUsedPct} color={(ssdUsedPct > 85) ? 'bg-red-400' : (ssdUsedPct > 70) ? 'bg-amber-400' : 'bg-emerald-400'} />}
              <div className="flex justify-between mt-1">
                {ssdUsedPct != null && <p className="text-xs text-gray-400 font-medium">{ssdUsedPct.toFixed(0)}% brugt</p>}
                {diagnostics.ssd_free_gb != null && <p className="text-xs text-gray-300">{diagnostics.ssd_free_gb.toFixed(1)} GB ledig</p>}
              </div>
            </div>
            {/* NTP */}
            <div className={`rounded-lg p-3 ${ntpOffset != null && Math.abs(ntpOffset) > 2 ? 'bg-red-50' : 'bg-gray-50'}`}>
              <p className="text-xs text-gray-400">NTP offset</p>
              <p className={`font-semibold mt-0.5 ${ntpOffset != null && Math.abs(ntpOffset) > 2 ? 'text-red-600' : ntpOffset != null && Math.abs(ntpOffset) > 0.5 ? 'text-amber-600' : 'text-gray-700'}`}>
                {ntpOffset != null ? `${ntpOffset > 0 ? '+' : ''}${ntpOffset.toFixed(3)}s` : '–'}
              </p>
              <p className="text-xs text-gray-300 mt-1">Alarm ved &gt;2s</p>
            </div>
            {/* Netværk */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">Netværk</p>
              <p className="font-semibold mt-0.5 text-gray-700">{diagnostics.connectivity ?? '–'}</p>
              {diagnostics.connectivity === 'wifi' && (diagnostics as any).wifi_ssid && (
                <p className="text-xs text-sky-500 mt-0.5 truncate" title="WiFi SSID">📶 {(diagnostics as any).wifi_ssid}</p>
              )}
              <p className="text-xs text-gray-300 mt-1">{diagnostics.upload_queue != null ? `${diagnostics.upload_queue} i kø` : ''}</p>
            </div>
            {/* Oppetid */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">Oppetid</p>
              <p className="font-semibold mt-0.5 text-gray-700">{diagnostics.uptime_s != null ? formatUptime(diagnostics.uptime_s) : '–'}</p>
              {diagnostics.service_restarts != null && diagnostics.service_restarts > 0 && (
                <p className="text-xs text-amber-500 mt-1">{diagnostics.service_restarts} genstarter</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400">Total captures</p>
              <p className="font-semibold text-gray-700">{diagnostics.capture_total ?? '–'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400">Kvalitet OK</p>
              <p className="font-semibold text-emerald-600">{diagnostics.capture_passed ?? '–'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400">Uploadet</p>
              <p className="font-semibold text-sky-600">{diagnostics.capture_uploaded ?? '–'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Kamera diagnostik */}
      {diagnostics && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Kamera — Canon EOS 1300D</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {/* Batteri */}
            <div className={`rounded-lg p-3 ${(diagnostics.cam_battery_pct ?? 100) < 20 ? 'bg-red-50' : 'bg-gray-50'}`}>
              <p className="text-xs text-gray-400">Batteri</p>
              <p className={`font-semibold mt-0.5 ${(diagnostics.cam_battery_pct ?? 100) < 20 ? 'text-red-600' : 'text-gray-700'}`}>
                {diagnostics.cam_battery_pct != null ? `${diagnostics.cam_battery_pct}%` : '–'}
              </p>
              {diagnostics.cam_battery_pct != null && <ProgressBar pct={diagnostics.cam_battery_pct} color={(diagnostics.cam_battery_pct < 20) ? 'bg-red-400' : (diagnostics.cam_battery_pct < 50) ? 'bg-amber-400' : 'bg-emerald-400'} />}
            </div>
            {/* Shutter */}
            <div className={`rounded-lg p-3 ${shutterAlarm ? 'bg-red-50' : (shutterPct ?? 0) > 60 ? 'bg-amber-50' : 'bg-gray-50'}`}>
              <p className="text-xs text-gray-400">Lukker-tæller</p>
              <p className={`font-semibold mt-0.5 ${shutterAlarm ? 'text-red-600' : (shutterPct ?? 0) > 60 ? 'text-amber-600' : 'text-gray-700'}`}>
                {diagnostics.cam_shutter_cnt != null ? diagnostics.cam_shutter_cnt.toLocaleString('da-DK') : '–'}
              </p>
              {shutterPct != null && <ProgressBar pct={shutterPct} color={shutterAlarm ? 'bg-red-400' : (shutterPct > 60) ? 'bg-amber-400' : 'bg-emerald-400'} />}
              {shutterPct != null && <p className="text-xs text-gray-300 mt-1">{shutterPct.toFixed(1)}% af levetid</p>}
            </div>
            {/* Ledige billeder */}
            <div className={`rounded-lg p-3 ${(diagnostics.cam_available_shots ?? 999) < 50 ? 'bg-amber-50' : 'bg-gray-50'}`}>
              <p className="text-xs text-gray-400">Ledige billeder</p>
              <p className={`font-semibold mt-0.5 ${(diagnostics.cam_available_shots ?? 999) < 50 ? 'text-amber-600' : 'text-gray-700'}`}>
                {diagnostics.cam_available_shots ?? '–'}
              </p>
              <p className="text-xs text-gray-300 mt-1">Alarm ved &lt;50</p>
            </div>
            {/* Linse */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400">Linse</p>
              <p className="font-semibold mt-0.5 text-gray-700 text-xs leading-tight">{diagnostics.cam_lens_name ?? '–'}</p>
            </div>
          </div>

          {/* Config drift */}
          {camDrift.length > 0 ? (
            <div className="border border-red-200 rounded-lg p-3 bg-red-50">
              <p className="text-xs font-semibold text-red-700 mb-2">Kamera-konfiguration afviger fra forventet ({camDrift.length})</p>
              {camDrift.map((d: any) => <DriftBadge key={d.param} {...d} />)}
            </div>
          ) : camConfig ? (
            <div className="border border-emerald-200 rounded-lg p-3 bg-emerald-50">
              <p className="text-xs font-semibold text-emerald-700">Kamera-konfiguration OK — ingen afvigelser</p>
            </div>
          ) : null}
        </div>
      )}

      {/* Diagnostics historik */}
      {diagHistory.length > 1 && (
        <>
          {/* CPU temp historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">CPU temperatur — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;75°C</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="°" />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}°C`, 'CPU temp']} />
                <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'Alarm 75°', fontSize: 10, fill: '#ef4444', position: 'insideTopLeft' }} />
                <Area type="monotone" dataKey="cpu_temp_c" name="CPU temp" stroke="#f97316" fill="#fed7aa" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* SSD forbrug historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">SSD forbrug — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;85%</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="%" domain={[0, 100]} />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}%`, 'SSD brugt']} />
                <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'Alarm 85%', fontSize: 10, fill: '#ef4444', position: 'insideTopLeft' }} />
                <Area type="monotone" dataKey="ssd_used_pct" name="SSD %" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Kamera shutter historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">Kamera shutter-tæller — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;60% af levetid</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: any) => [Number(v).toLocaleString('da-DK'), 'Shutter']} />
                <Area type="monotone" dataKey="cam_shutter_cnt" name="Shutter" stroke="#8b5cf6" fill="#ede9fe" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* NTP offset historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">NTP offset — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;±2s</span>
            </div>
            <ResponsiveContainer width="100%" height={130}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="s" />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(3)}s`, 'NTP offset']} />
                <ReferenceLine y={2}   stroke="#ef4444" strokeDasharray="4 2" />
                <ReferenceLine y={-2}  stroke="#ef4444" strokeDasharray="4 2" />
                <Area type="monotone" dataKey="ntp_offset_s" name="NTP" stroke="#10b981" fill="#d1fae5" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* Diagnostics historik */}
      {diagHistory.length > 1 && (
        <>
          {/* CPU temp historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">CPU temperatur — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;75°C</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="°" />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}°C`, 'CPU temp']} />
                <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'Alarm 75°', fontSize: 10, fill: '#ef4444', position: 'insideTopLeft' }} />
                <Area type="monotone" dataKey="cpu_temp_c" name="CPU temp" stroke="#f97316" fill="#fed7aa" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* SSD forbrug historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">SSD forbrug — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;85%</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="%" domain={[0, 100]} />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}%`, 'SSD brugt']} />
                <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'Alarm 85%', fontSize: 10, fill: '#ef4444', position: 'insideTopLeft' }} />
                <Area type="monotone" dataKey="ssd_used_pct" name="SSD %" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Kamera shutter historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">Kamera shutter-tæller — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;60% af levetid</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: any) => [Number(v).toLocaleString('da-DK'), 'Shutter']} />
                <Area type="monotone" dataKey="cam_shutter_cnt" name="Shutter" stroke="#8b5cf6" fill="#ede9fe" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* NTP offset historik */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">NTP offset — seneste 7 dage</h3>
              <span className="text-xs text-gray-400">alarm &gt;±2s</span>
            </div>
            <ResponsiveContainer width="100%" height={130}>
              <AreaChart data={diagHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} tickLine={false}
                  tickFormatter={v => new Date(v).toLocaleDateString('da-DK', { day: '2-digit', month: '2-digit' })}
                  interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="s" />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(3)}s`, 'NTP offset']} />
                <ReferenceLine y={2}   stroke="#ef4444" strokeDasharray="4 2" />
                <ReferenceLine y={-2}  stroke="#ef4444" strokeDasharray="4 2" />
                <Area type="monotone" dataKey="ntp_offset_s" name="NTP" stroke="#10b981" fill="#d1fae5" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* Kvalitetsgrafer */}
      {qualityData.length > 1 && (
        <>
          {/* Blur graf */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">Billedskarphed (blur-score)</h3>
              <span className="text-xs text-gray-400">højere = skarpere</span>
            </div>
            <p className="text-xs text-gray-300 mb-3">Alarm ved &lt; 80 — fokus-drift, snavs på glas eller kondensation</p>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={qualityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(val: any) => [Math.round(val), 'Blur']} />
                <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: 'Alarm 80', fontSize: 10, fill: '#f59e0b', position: 'insideTopLeft' }} />
                <Area type="monotone" dataKey="blur" name="Skarphed" stroke="#0ea5e9" fill="#e0f2fe" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Lysstyrke graf */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-700">Lysstyrke og eksponering</h3>
              <div className="text-xs flex gap-3">
                <span className="text-red-400">{qualityData.filter(d => d.brightness != null && d.brightness > 230).length} overbelyste</span>
                <span className="text-slate-400">{qualityData.filter(d => d.brightness != null && d.brightness < 25).length} for mørke</span>
              </div>
            </div>
            <p className="text-xs text-gray-300 mb-3">Normal: 25–230 · Skala 0–255</p>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={qualityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 255]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(val: any) => [Math.round(val), 'Lysstyrke']} />
                <ReferenceLine y={230} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'Overbelyst 230', fontSize: 10, fill: '#ef4444', position: 'insideTopLeft' }} />
                <ReferenceLine y={25}  stroke="#94a3b8" strokeDasharray="4 2" label={{ value: 'For mørk 25',   fontSize: 10, fill: '#94a3b8', position: 'insideBottomLeft' }} />
                <Area type="monotone" dataKey="brightness" name="Lysstyrke" stroke="#f59e0b" fill="#fef3c7" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Filstørrelse */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Filstørrelse (MB) — indikator for billedindhold</h3>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={qualityData} barSize={6}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="size" name="MB" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}
// ── Main page ──────────────────────────────────────────────────────────────────
type Tab = 'captures' | 'timeline' | 'stats' | 'config'

export function DevicePage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail]   = useState<DeviceDetail | null>(null)
  const [captures, setCaptures] = useState<Capture[]>([])
  const [loading, setLoading]   = useState(true)
  const [tab, setTab]           = useState<Tab>('captures')
  const [lightbox, setLightbox] = useState<number | null>(null)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [d, c] = await Promise.all([getDevice(id), getCaptures(id, 200)])
      setDetail(d)
      setCaptures(c)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  if (loading) return <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-400">Indlæser…</div>
  if (!detail) return <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-400">Enhed ikke fundet</div>

  const { device, diagnostics } = detail
  const routeDeviceId = pathSegment(device.device_id)

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'captures',  label: `Billeder (${captures.length})`, icon: Camera },
    { key: 'timeline',  label: 'Tidslinje', icon: CalendarDays },
    { key: 'stats',     label: 'Statistik', icon: BarChart2 },
    { key: 'config',    label: 'Konfiguration', icon: Settings },
  ]

  return (
    <>
      {lightbox !== null && (
        <Lightbox captures={captures} index={lightbox} onClose={() => setLightbox(null)} />
      )}

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <Link to="/" className="text-gray-400 hover:text-gray-600"><ArrowLeft className="w-5 h-5" /></Link>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-gray-900">{device.camera_name || device.location_name || device.device_id}</h1>
            {(device.customer_name || device.site_name) && (
              <span className="text-sm text-gray-400">{[device.customer_name, device.site_name].filter(Boolean).join(' — ')}</span>
            )}
              <StatusBadge status={device.status} />
            </div>
            <p className="text-xs text-gray-400 font-mono mt-0.5">{device.device_id}</p>
          </div>
          <button onClick={load} disabled={loading} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {diagnostics?.cpu_temp_c != null && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <Thermometer className="w-5 h-5 text-orange-400 flex-shrink-0" />
              <div><p className="text-xs text-gray-400">CPU temp</p><p className="text-lg font-semibold text-gray-800">{diagnostics.cpu_temp_c.toFixed(1)}°C</p></div>
            </div>
          )}
          {diagnostics?.disk_used_gb != null && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <HardDrive className="w-5 h-5 text-blue-400 flex-shrink-0" />
              <div><p className="text-xs text-gray-400">Disk brugt</p><p className="text-lg font-semibold text-gray-800">{diagnostics.disk_used_gb.toFixed(1)} GB</p></div>
            </div>
          )}
          {diagnostics?.connectivity && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <Wifi className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              <div><p className="text-xs text-gray-400">Netværk</p><p className="text-lg font-semibold text-gray-800">{diagnostics.connectivity}</p></div>
            </div>
          )}
          {diagnostics?.uptime_s != null && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <Clock className="w-5 h-5 text-purple-400 flex-shrink-0" />
              <div><p className="text-xs text-gray-400">Oppetid</p><p className="text-lg font-semibold text-gray-800">{formatUptime(diagnostics.uptime_s)}</p></div>
            </div>
          )}
        </div>

        <div className="flex gap-1 mb-6 border-b border-gray-200">
          <button onClick={() => navigate(`/devices/${routeDeviceId}/timelapse`)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-sky-600 hover:text-sky-700 border-b-2 border-transparent hover:border-sky-400 -mb-px transition-colors mr-2">
            <Film className="w-4 h-4" />Timelapse Video
          </button>
          <button onClick={() => navigate(`/devices/${routeDeviceId}/lab`)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-purple-600 hover:text-purple-700 border-b-2 border-transparent hover:border-purple-400 -mb-px transition-colors mr-2">
            <FlaskConical className="w-4 h-4" />Lab
          </button>
          {tabs.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setTab(key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === key ? 'border-sky-500 text-sky-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />{label}
            </button>
          ))}
        </div>

        {tab === 'captures' && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {captures.map((c, i) => (
              <CaptureCard key={c.id} capture={c} onClick={() => setLightbox(i)} />
            ))}
            {captures.length === 0 && (
              <div className="col-span-full py-12 text-center text-gray-400 text-sm">Ingen captures endnu</div>
            )}
          </div>
        )}

        {tab === 'timeline' && id && <TimelineNavigator deviceId={id} captures={captures} onSelect={i => { setLightbox(i) }} />}
        {tab === 'stats' && id && <StatsTab captures={captures} diagnostics={diagnostics} deviceId={id} />}
        {tab === 'config' && id && <ConfigTab deviceId={id} />}
      </div>
    </>
  )
}
