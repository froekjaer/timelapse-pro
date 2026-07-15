// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — DriftPage.tsx  (Observability / ITIM)
// Drifts-overblik: health-tiles, tidsserie-grafer og aktive alarmer.
// Data fra /api/itim/* (letvægt ITIM-lag i Postgres).
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, RefreshCw, AlertTriangle, AlertCircle, CheckCircle2,
  HelpCircle, HardDrive, Server, Cpu, Camera, Brain, Boxes, ArrowRight,
  ScrollText,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { getApiUrl } from '../api/client'

// ── Types ───────────────────────────────────────────────────────────────────
interface HealthTile {
  target_key: string
  kind: string
  scope: string
  device_id: string | null
  display_name: string | null
  state: 'ok' | 'warning' | 'critical' | 'unknown'
  summary: string | null
  metrics: Record<string, number | string>
  updated_at: string | null
}
interface AlertRow {
  id: number
  severity: string
  state: string
  value: number | null
  message: string | null
  target_key: string | null
  started_at: string | null
  resolved_at: string | null
}
interface Point { ts: string; value: number | null }
interface CaptureAccessRow {
  id: number; capture_id: number; device_id: string; filename: string
  action: string; username: string; role: string; accessed_at: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include' })
}

const STATE_STYLE: Record<string, { ring: string; dot: string; label: string }> = {
  ok:       { ring: 'border-emerald-200 bg-emerald-50', dot: 'bg-emerald-500', label: 'OK' },
  warning:  { ring: 'border-amber-200 bg-amber-50',     dot: 'bg-amber-500',   label: 'Advarsel' },
  critical: { ring: 'border-red-200 bg-red-50',         dot: 'bg-red-500',     label: 'Kritisk' },
  unknown:  { ring: 'border-slate-200 bg-slate-50',     dot: 'bg-slate-400',   label: 'Ukendt' },
}

const KIND_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  volume: HardDrive, service: Server, host: Cpu, edge: Camera, pipeline: Brain, image_qa: Boxes,
}

const SCOPE_LABEL: Record<string, string> = {
  core: 'Kerne (services & volumen)', host: 'Vært (Mac)', edge: 'Edge-enheder', ai: 'AI & billedkvalitet',
}

function StateIcon({ state }: { state: string }) {
  if (state === 'critical') return <AlertCircle className="w-4 h-4 text-red-500" />
  if (state === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-500" />
  if (state === 'ok') return <CheckCircle2 className="w-4 h-4 text-emerald-500" />
  return <HelpCircle className="w-4 h-4 text-slate-400" />
}

function fmt(v: number | string): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(1)
  return String(v)
}

// Defekt-metrik → repræsentativt søge-tag (til kontekst-bevidst deep-link)
const _DEFECT_TAG: Record<string, string> = {
  unusable_rate: 'unusable_image', blurry_rate: 'blurry',
  overexposed_rate: 'overexposed', underexposed_rate: 'underexposed',
  lens_obstruction_rate: 'dirty_lens',
}

// Deep-link pr. blok-type → "hop hen hvor fejlen er" (kontekst-bevidst)
function sourceLink(t: HealthTile): { to: string; label: string } | null {
  if (t.kind === 'edge' && t.device_id) return { to: `/cmdb/${t.device_id}`, label: 'Vis enhed i CMDB' }
  if (t.kind === 'pipeline')            return { to: '/post-processing', label: 'Åbn Post-processing' }
  if (t.kind === 'image_qa') {
    // find den værste defekt-rate og deep-link Tag søgning på netop det tag
    let worst = '', worstVal = 0
    for (const [m, tag] of Object.entries(_DEFECT_TAG)) {
      const v = t.metrics[m]
      if (typeof v === 'number' && v > worstVal) { worstVal = v; worst = tag }
    }
    return worst
      ? { to: `/tags?tags=${worst}`, label: `Se «${worst}»-billeder` }
      : { to: '/tags', label: 'Åbn Tag søgning' }
  }
  if (t.kind === 'service' || t.kind === 'volume' || t.kind === 'host')
    // infra-hændelser fra headend/nginx/data-fast logges under HEADEND-LOCAL
    return { to: '/siem?device_id=HEADEND-LOCAL', label: 'Se hændelser i SIEM' }
  return null
}

// ── Component ────────────────────────────────────────────────────────────────
export default function DriftPage() {
  const navigate = useNavigate()
  const [tiles, setTiles] = useState<HealthTile[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [metric, setMetric] = useState<string | null>(null)
  const [series, setSeries] = useState<Point[]>([])
  const [hours, setHours] = useState(24)
  const [accessRows, setAccessRows] = useState<CaptureAccessRow[]>([])
  const [accessLoading, setAccessLoading] = useState(false)
  const [accessFilters, setAccessFilters] = useState({ username: '', device_id: '', filename: '', action: '', hours: '168' })

  const loadHealth = useCallback(async () => {
    try {
      const [h, a] = await Promise.all([
        api('/api/itim/health'),
        api('/api/itim/alerts?state=firing'),
      ])
      if (!h.ok) throw new Error(`health ${h.status}`)
      setTiles(await h.json())
      setAlerts(a.ok ? await a.json() : [])
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente drifts-status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadHealth() }, [loadHealth])
  useEffect(() => {
    const t = window.setInterval(loadHealth, 30000)
    return () => window.clearInterval(t)
  }, [loadHealth])

  const selectedTile = useMemo(() => tiles.find(t => t.target_key === selected) || null, [tiles, selected])
  const numericMetrics = useMemo(
    () => selectedTile ? Object.keys(selectedTile.metrics).filter(k => typeof selectedTile.metrics[k] === 'number') : [],
    [selectedTile],
  )

  const loadSeries = useCallback(async (target: string, m: string, hrs: number) => {
    try {
      const rollup = hrs > 72 ? '1h' : hrs > 12 ? '5m' : 'raw'
      const r = await api(`/api/itim/metrics?target=${encodeURIComponent(target)}&metric=${encodeURIComponent(m)}&hours=${hrs}&rollup=${rollup}`)
      if (!r.ok) throw new Error(String(r.status))
      const data = await r.json()
      setSeries(data.points ?? [])
    } catch { setSeries([]) }
  }, [])

  useEffect(() => {
    if (selected && metric) loadSeries(selected, metric, hours)
  }, [selected, metric, hours, loadSeries])

  function openTarget(t: HealthTile) {
    setSelected(t.target_key)
    const keys = Object.keys(t.metrics).filter(k => typeof t.metrics[k] === 'number')
    setMetric(keys[0] ?? null)
  }

  async function loadCaptureAccess() {
    setAccessLoading(true)
    try {
      const params = new URLSearchParams({ hours: accessFilters.hours, limit: '500' })
      Object.entries(accessFilters).forEach(([key, value]) => {
        if (key !== 'hours' && value.trim()) params.set(key, value.trim())
      })
      const response = await api(`/api/audit/capture-access?${params}`)
      if (!response.ok) throw new Error(`Billedadgang ${response.status}`)
      setAccessRows(await response.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente billedadgang')
    } finally {
      setAccessLoading(false)
    }
  }

  // Gruppér tiles efter scope
  const grouped = useMemo(() => {
    const g: Record<string, HealthTile[]> = {}
    for (const t of tiles) (g[t.scope] ??= []).push(t)
    return g
  }, [tiles])

  const worstState = useMemo(() => {
    if (tiles.some(t => t.state === 'critical')) return 'critical'
    if (tiles.some(t => t.state === 'warning')) return 'warning'
    if (tiles.length && tiles.every(t => t.state === 'ok')) return 'ok'
    return 'unknown'
  }, [tiles])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-6 h-6 text-sky-500" />
          <h1 className="text-xl font-semibold text-slate-900">Drift &amp; Observability</h1>
          <span className={`ml-2 inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border ${STATE_STYLE[worstState].ring}`}>
            <span className={`w-2 h-2 rounded-full ${STATE_STYLE[worstState].dot}`} />
            {STATE_STYLE[worstState].label}
          </span>
        </div>
        <button onClick={loadHealth}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-900 text-white text-sm hover:bg-slate-800">
          <RefreshCw className="w-4 h-4" /> Opdatér
        </button>
      </div>

      {error && <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>}

      <section className="border border-slate-200 bg-white rounded-lg p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2"><ScrollText className="w-4 h-4 text-sky-500" /> Logs &amp; hændelser</h2>
            <p className="text-xs text-slate-500 mt-1">Samlet, server-side redigeret logkonsol med RBAC.</p>
          </div>
          <button onClick={() => navigate('/siem')} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-900 text-white text-xs hover:bg-slate-800">
            Åbn alle <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
          {[
            ['Headend', '/siem?source=timelapse-headend.log'],
            ['nginx fejl', '/siem?source=nginx-timelapse-error.log'],
            ['nginx adgang', '/siem?source=nginx-timelapse-access.log'],
            ['Edge journal', '/siem?source=edge_journal'],
            ['Syslog', '/siem?source=syslog'],
          ].map(([label, to]) => (
            <button key={label} onClick={() => navigate(to)} className="text-left px-3 py-2 rounded-md border border-slate-200 hover:border-sky-300 hover:bg-sky-50 text-xs text-slate-700">
              {label}
            </button>
          ))}
        </div>
      </section>

      <details className="border border-slate-200 bg-white rounded-lg p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">Billedadgang (GDPR)</summary>
        <p className="text-xs text-slate-500 mt-1">Søg i hvem der har set eller hentet et bestemt billede. Thumbnailvisninger deduplikeres i ti minutter.</p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mt-3">
          <input aria-label="Bruger" placeholder="Bruger" value={accessFilters.username} onChange={e => setAccessFilters(v => ({...v, username: e.target.value}))} className="text-xs border border-slate-200 rounded px-2 py-1.5" />
          <input aria-label="Edge device" placeholder="Edge/device" value={accessFilters.device_id} onChange={e => setAccessFilters(v => ({...v, device_id: e.target.value}))} className="text-xs border border-slate-200 rounded px-2 py-1.5" />
          <input aria-label="Filnavn" placeholder="Filnavn" value={accessFilters.filename} onChange={e => setAccessFilters(v => ({...v, filename: e.target.value}))} className="text-xs border border-slate-200 rounded px-2 py-1.5" />
          <select aria-label="Adgangstype" value={accessFilters.action} onChange={e => setAccessFilters(v => ({...v, action: e.target.value}))} className="text-xs border border-slate-200 rounded px-2 py-1.5">
            <option value="">Alle adgangstyper</option>
            <option value="thumbnail_view">Thumbnail</option>
            <option value="download">Fuld visning/download</option>
          </select>
          <div className="flex gap-2">
            <select aria-label="Periode" value={accessFilters.hours} onChange={e => setAccessFilters(v => ({...v, hours: e.target.value}))} className="min-w-0 flex-1 text-xs border border-slate-200 rounded px-2 py-1.5">
              <option value="24">24 timer</option><option value="168">7 dage</option><option value="720">30 dage</option><option value="8760">1 år</option>
            </select>
            <button onClick={loadCaptureAccess} disabled={accessLoading} className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs disabled:opacity-50">Søg</button>
          </div>
        </div>
        <div className="mt-3 max-h-72 overflow-auto rounded border border-slate-100">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-slate-50 text-slate-500"><tr><th className="text-left px-2 py-1.5">Tid</th><th className="text-left px-2 py-1.5">Bruger</th><th className="text-left px-2 py-1.5">Billede</th><th className="text-left px-2 py-1.5">Handling</th></tr></thead>
            <tbody>
              {accessRows.map(row => <tr key={row.id} className="border-t border-slate-100"><td className="px-2 py-1.5 whitespace-nowrap">{new Date(row.accessed_at).toLocaleString('da-DK')}</td><td className="px-2 py-1.5"><div>{row.username}</div><div className="text-[10px] text-slate-400">{row.role}</div></td><td className="px-2 py-1.5"><div className="font-mono break-all">{row.filename}</div><div className="text-[10px] text-slate-400">{row.device_id} · capture #{row.capture_id}</div></td><td className="px-2 py-1.5">{row.action === 'thumbnail_view' ? 'Thumbnail' : 'Fuld visning/download'}</td></tr>)}
              {!accessLoading && accessRows.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-slate-400">Tryk Søg for at hente adgangsloggen</td></tr>}
            </tbody>
          </table>
        </div>
      </details>

      {/* Aktive alarmer */}
      {alerts.length > 0 && (
        <div className="border border-red-200 bg-red-50 rounded-lg p-4">
          <p className="text-sm font-semibold text-red-800 mb-2 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> {alerts.length} aktive alarm{alerts.length === 1 ? '' : 'er'}
          </p>
          <div className="space-y-1">
            {alerts.map(a => (
              <div key={a.id} className="text-xs text-red-800 flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded ${a.severity === 'critical' ? 'bg-red-200' : 'bg-amber-200 text-amber-900'}`}>
                  {a.severity}
                </span>
                <span className="font-mono">{a.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Henter drifts-status…</p>}

      {/* Health-tiles grupperet efter scope */}
      {Object.entries(grouped).map(([scope, list]) => (
        <div key={scope}>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">{SCOPE_LABEL[scope] ?? scope}</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {list.map(t => {
              const Icon = KIND_ICON[t.kind] ?? Server
              const sel = t.target_key === selected
              return (
                <button key={t.target_key} onClick={() => openTarget(t)}
                  className={`text-left border rounded-lg p-3 transition-shadow hover:shadow-sm ${STATE_STYLE[t.state].ring} ${sel ? 'ring-2 ring-sky-400' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Icon className="w-4 h-4 text-slate-500 flex-shrink-0" />
                      <span className="text-sm font-medium text-slate-900 truncate">{t.display_name || t.target_key}</span>
                    </div>
                    <StateIcon state={t.state} />
                  </div>
                  <p className="text-xs text-slate-600 mt-1 truncate">{t.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5">
                    {Object.entries(t.metrics).filter(([k]) => k !== 'engine').slice(0, 4).map(([k, v]) => (
                      <span key={k} className="text-[11px] text-slate-500">
                        <span className="text-slate-400">{k}</span> {fmt(v)}
                      </span>
                    ))}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      ))}

      {/* Detalje-panel for valgt blok */}
      {selectedTile && (
        <div className="border border-slate-200 bg-white rounded-lg p-4 space-y-3">
          {/* Header: navn + tilstand + gå-til-kilde */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <StateIcon state={selectedTile.state} />
              <h2 className="text-sm font-semibold text-slate-900 truncate">{selectedTile.display_name || selectedTile.target_key}</h2>
              <span className="text-xs text-slate-400 font-mono truncate">{selectedTile.target_key}</span>
            </div>
            {sourceLink(selectedTile) && (
              <button onClick={() => navigate(sourceLink(selectedTile)!.to)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-sky-600 text-white text-xs font-medium hover:bg-sky-700 flex-shrink-0">
                {sourceLink(selectedTile)!.label} <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Summary */}
          {selectedTile.summary && (
            <p className={`text-sm ${selectedTile.state === 'critical' ? 'text-red-700' : selectedTile.state === 'warning' ? 'text-amber-700' : 'text-slate-600'}`}>
              {selectedTile.summary}
            </p>
          )}

          {/* Alle metrikker (ikke kun de 4 fra tile'en) */}
          <div className="flex flex-wrap gap-2">
            {Object.entries(selectedTile.metrics).filter(([k]) => k !== 'engine').map(([k, v]) => (
              <span key={k} className="text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1">
                <span className="text-slate-400">{k}</span> <span className="font-medium text-slate-700">{fmt(v)}</span>
              </span>
            ))}
          </div>

          {/* Aktive alarmer for netop denne blok */}
          {alerts.filter(a => a.target_key === selectedTile.target_key).length > 0 && (
            <div className="border border-red-200 bg-red-50 rounded-md p-2 space-y-1">
              {alerts.filter(a => a.target_key === selectedTile.target_key).map(a => (
                <p key={a.id} className="text-xs text-red-800 font-mono break-all">{a.message}</p>
              ))}
            </div>
          )}

          {/* Tidsserie-kontroller */}
          <div className="flex items-center justify-between flex-wrap gap-2 border-t border-slate-100 pt-3">
            <span className="text-xs font-medium text-slate-500">Tidsserie</span>
            <div className="flex items-center gap-2">
              <select value={metric ?? ''} onChange={e => setMetric(e.target.value)}
                className="text-xs border border-slate-200 rounded-md px-2 py-1">
                {numericMetrics.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              {[6, 24, 72, 168].map(h => (
                <button key={h} onClick={() => setHours(h)}
                  className={`text-xs px-2 py-1 rounded-md border ${hours === h ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-200 text-slate-600'}`}>
                  {h < 24 ? `${h}t` : `${h / 24}d`}
                </button>
              ))}
            </div>
          </div>
          <div className="h-64">
            {series.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series.map(p => ({ ...p, t: new Date(p.ts).getTime() }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} scale="time"
                    tickFormatter={(v: number) => new Date(v).toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })}
                    tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={40} />
                  <Tooltip labelFormatter={(v) => new Date(Number(v)).toLocaleString('da-DK')}
                    formatter={(value) => [fmt(value as number), metric ?? '']} />
                  <Line type="monotone" dataKey="value" stroke="#0ea5e9" dot={false} strokeWidth={2} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-400 flex items-center h-full justify-center">Ingen datapunkter i perioden</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
