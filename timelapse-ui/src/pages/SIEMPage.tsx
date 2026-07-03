// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — SIEMPage.tsx
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Shield, AlertTriangle, AlertCircle, Info, RefreshCw,
  Wifi, Terminal, User, Key, Server, Activity, Zap, Brain, Loader2,
  X, Settings, ListFilter, RadioTower, Database, SlidersHorizontal, Eye
} from 'lucide-react'
import { getApiUrl } from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────

interface SecurityEvent {
  id: number
  device_id: string
  event_type: string
  severity: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  username: string | null
  source_ip: string | null
  raw_message: string | null
  source?: string | null
  category?: string | null
  logger?: string | null
  process?: string | null
  normalized?: string | null
  occurred_at: string
  received_at?: string | null
}

interface Summary {
  total: number
  period_hours: number
  by_severity: Record<string, number>
  by_event_type: Record<string, number>
  by_device: Record<string, number>
  latest_critical: SecurityEvent | null
}

interface Threat {
  source_ip: string
  device_id: string
  attempts: number
  first_seen: string
  last_seen: string
  threat_level: 'info' | 'warning' | 'critical'
}

// ── Helpers ───────────────────────────────────────────────────────────────

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include' })
}

function apiPost(path: string, body: unknown) {
  return fetch(`${getApiUrl()}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', { dateStyle: 'short', timeStyle: 'medium' })
}

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1)  return 'lige nu'
  if (min < 60) return `${min} min siden`
  const hr = Math.floor(min / 60)
  if (hr < 24)  return `${hr} t siden`
  return `${Math.floor(hr / 24)} d siden`
}

const EVENT_META: Record<string, { label: string; icon: any; color: string }> = {
  ssh_failure:   { label: 'SSH fejl',       icon: Key,      color: 'text-red-500' },
  ssh_success:   { label: 'SSH login',      icon: Key,      color: 'text-green-500' },
  sudo_use:      { label: 'Sudo',           icon: Terminal, color: 'text-amber-500' },
  sudo_failure:  { label: 'Sudo afvist',    icon: Terminal, color: 'text-red-500' },
  service_crash: { label: 'Service crash',  icon: Server,   color: 'text-red-600' },
  new_user:      { label: 'Ny bruger',      icon: User,     color: 'text-purple-500' },
  passwd_change: { label: 'Password ændret',icon: Key,      color: 'text-amber-600' },
  camera_config_drift: { label: 'Kamera drift', icon: AlertTriangle, color: 'text-amber-500' },
  network_connection_denied: { label: 'Firewall deny', icon: Shield, color: 'text-amber-600' },
  network_auth_failed: { label: 'Netværk auth fejl', icon: Key, color: 'text-red-500' },
  network_link_down: { label: 'Link down', icon: Wifi, color: 'text-amber-500' },
  network_link_up: { label: 'Link up', icon: Wifi, color: 'text-green-500' },
  syslog_event: { label: 'Syslog', icon: RadioTower, color: 'text-sky-500' },
}

const SEVERITY_CONFIG = {
  debug:    { bg: 'bg-gray-100',   text: 'text-gray-600',   border: 'border-gray-200',   label: 'Debug', icon: Info },
  critical: { bg: 'bg-red-100',    text: 'text-red-700',    border: 'border-red-200',    label: 'Kritisk', icon: AlertCircle },
  error:    { bg: 'bg-rose-100',   text: 'text-rose-700',   border: 'border-rose-200',   label: 'Fejl', icon: AlertCircle },
  warning:  { bg: 'bg-amber-100',  text: 'text-amber-700',  border: 'border-amber-200',  label: 'Advarsel', icon: AlertTriangle },
  info:     { bg: 'bg-sky-100',    text: 'text-sky-700',    border: 'border-sky-200',    label: 'Info', icon: Info },
}

type SiemTab = 'overview' | 'events' | 'sources' | 'policy'

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  )
}

function EventTypeIcon({ type }: { type: string }) {
  const meta = EVENT_META[type]
  if (!meta) return <Activity className="w-4 h-4 text-gray-400" />
  const Icon = meta.icon
  return <Icon className={`w-4 h-4 ${meta.color}`} />
}

// ── SIEM Page ─────────────────────────────────────────────────────────────

export function SIEMPage() {
  const [events,   setEvents]   = useState<SecurityEvent[]>([])
  const [summary,  setSummary]  = useState<Summary | null>(null)
  const [threats,  setThreats]  = useState<Threat[]>([])
  const [loading,  setLoading]  = useState(true)
  const [hours,    setHours]    = useState(24)
  const [filterSeverity, setFilterSeverity] = useState('')
  const [filterType,     setFilterType]     = useState('')
  const [filterDevice,   setFilterDevice]   = useState('')
  const [activeTab, setActiveTab] = useState<SiemTab>('events')
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const [autoRefresh,    setAutoRefresh]    = useState(true)
  const [aiQuestion, setAiQuestion] = useState('Hvad er mest mistænkeligt i SIEM de sidste 24 timer?')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiAnswer, setAiAnswer] = useState<any | null>(null)
  const [searchParams] = useSearchParams()

  // Deep-link fra Drift-siden: ?device_id=HEADEND-LOCAL / ?severity=warning
  useEffect(() => {
    const dev = searchParams.get('device_id')
    const sev = searchParams.get('severity')
    if (dev) setFilterDevice(dev)
    if (sev) setFilterSeverity(sev)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ hours: String(hours), limit: '500' })
      if (filterSeverity) params.set('severity',   filterSeverity)
      if (filterType)     params.set('event_type', filterType)
      if (filterDevice)   params.set('device_id',  filterDevice)

      const [evR, sumR, thrR] = await Promise.all([
        api(`/api/siem/events?${params}`),
        api(`/api/siem/summary?hours=${hours}`),
        api(`/api/siem/threats?hours=${hours}`),
      ])
      setEvents(await evR.json())
      setSummary(await sumR.json())
      setThreats(await thrR.json())
    } catch { /* ignore */ }
    setLoading(false)
  }, [hours, filterSeverity, filterType, filterDevice])

  useEffect(() => { load() }, [load])

  // Auto-refresh hvert 30 sek
  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [autoRefresh, load])

  const critCount = summary?.by_severity['critical'] ?? 0
  const errorCount = summary?.by_severity['error'] ?? 0
  const warnCount = summary?.by_severity['warning']  ?? 0
  const eventTypes = summary ? Object.keys(summary.by_event_type).sort() : []

  function resetFilters() {
    setFilterSeverity('')
    setFilterType('')
    setFilterDevice('')
  }

  async function askAi() {
    if (!aiQuestion.trim()) return
    setAiLoading(true)
    try {
      const r = await apiPost('/api/ai/ops/query', { area: 'siem', question: aiQuestion, hours })
      const data = await r.json()
      setAiAnswer(data.analysis)
    } catch {
      setAiAnswer({ answer: 'AI SIEM-analyse fejlede. Tjek Ollama/headend-log og prøv igen.', risk_level: 'unknown', recommendations: [] })
    } finally {
      setAiLoading(false)
    }
  }

  function applyAiFilters() {
    const filters = aiAnswer?.suggested_filters ?? {}
    if (filters.severity) setFilterSeverity(filters.severity)
    if (filters.event_type) setFilterType(filters.event_type)
    if (filters.device_id) setFilterDevice(filters.device_id)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="w-6 h-6 text-red-500" />
            Security Events — Mini SIEM
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Realtidsovervågning af alle noder
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Tidsperiode */}
          <select
            value={hours}
            onChange={e => setHours(Number(e.target.value))}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700"
          >
            <option value={1}>Sidste time</option>
            <option value={6}>Sidste 6 timer</option>
            <option value={24}>Sidste 24 timer</option>
            <option value={168}>Sidste 7 dage</option>
          </select>
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(r => !r)}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              autoRefresh
                ? 'bg-green-50 text-green-700 border-green-200'
                : 'bg-gray-50 text-gray-500 border-gray-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            {autoRefresh ? 'Live' : 'Pause'}
          </button>
          <button onClick={load} className="text-gray-400 hover:text-gray-700">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard
            label="Total events"
            value={summary.total}
            icon={Activity}
            color="text-gray-600"
            bg="bg-gray-50"
          />
          <SummaryCard
            label="Kritiske"
            value={critCount}
            icon={AlertCircle}
            color="text-red-600"
            bg="bg-red-50"
            alert={critCount > 0}
          />
          <SummaryCard
            label="Advarsler"
            value={warnCount}
            icon={AlertTriangle}
            color="text-amber-600"
            bg="bg-amber-50"
          />
          <SummaryCard
            label="Trusler (IPs)"
            value={threats.length}
            icon={Wifi}
            color="text-purple-600"
            bg="bg-purple-50"
            alert={threats.length > 0}
          />
        </div>
      )}

      <div className="bg-white rounded-xl border border-sky-100 p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-sky-600" />
          <h2 className="text-sm font-semibold text-gray-800">AI SIEM-analyse</h2>
          {aiAnswer?.risk_level && (
            <span className="ml-auto text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
              Risk: {aiAnswer.risk_level}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={aiQuestion}
            onChange={e => setAiQuestion(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') askAi() }}
          />
          <button
            onClick={askAi}
            disabled={aiLoading || !aiQuestion.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white text-sm rounded-lg disabled:opacity-40"
          >
            {aiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
            Spørg
          </button>
        </div>
        {aiAnswer && (
          <div className="mt-3 text-sm text-gray-700">
            <p>{aiAnswer.answer}</p>
            {aiAnswer.suggested_filters && Object.values(aiAnswer.suggested_filters).some(Boolean) && (
              <button onClick={applyAiFilters} className="mt-2 text-xs px-3 py-1.5 rounded-lg border border-sky-200 text-sky-700 hover:bg-sky-50">
                Anvend foreslåede filtre
              </button>
            )}
            {(aiAnswer.recommendations ?? []).length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
                {aiAnswer.recommendations.slice(0, 4).map((rec: any, idx: number) => (
                  <div key={idx} className="border border-gray-100 rounded-lg p-3 bg-gray-50">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">{rec.title}</span>
                      <span className="text-xs text-gray-400">{rec.severity}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{rec.proposed_action || rec.rationale}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 border-b border-gray-200 mb-5">
        {([
          ['overview', Activity, 'Overblik'],
          ['events', ListFilter, 'Events'],
          ['sources', RadioTower, 'Kilder'],
          ['policy', Settings, 'Politik'],
        ] as const).map(([tab, Icon, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-sky-500 text-sky-700'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && summary && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-800 mb-3">Hændelsesoverblik</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(summary.by_event_type)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 12)
                .map(([type, count]) => (
                  <button
                    key={type}
                    onClick={() => { setFilterType(type); setActiveTab('events') }}
                    className="text-left border border-gray-100 rounded-lg p-3 hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-2">
                      <EventTypeIcon type={type} />
                      <span className="text-sm font-medium text-gray-900">{EVENT_META[type]?.label ?? type}</span>
                      <span className="ml-auto text-sm font-bold text-gray-900">{count}</span>
                    </div>
                  </button>
                ))}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-800 mb-3">Aktiv risiko</h2>
            <div className="space-y-3 text-sm">
              <RiskLine label="Kritiske events" value={critCount} tone="red" />
              <RiskLine label="Fejl" value={errorCount} tone="rose" />
              <RiskLine label="Advarsler" value={warnCount} tone="amber" />
              <RiskLine label="Brute-force IPs" value={threats.length} tone="purple" />
            </div>
          </div>
        </div>
      )}

      {activeTab === 'events' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event feed */}
        <div className="lg:col-span-2">
          {/* Filtre */}
          <div className="flex gap-2 mb-3 flex-wrap">
            <select
              value={filterSeverity}
              onChange={e => setFilterSeverity(e.target.value)}
              className="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600"
            >
              <option value="">Alle severity</option>
              <option value="critical">Kritisk</option>
              <option value="error">Fejl</option>
              <option value="warning">Advarsel</option>
              <option value="info">Info</option>
              <option value="debug">Debug</option>
            </select>
            <select
              value={filterType}
              onChange={e => setFilterType(e.target.value)}
              className="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600"
            >
              <option value="">Alle typer</option>
              {eventTypes.map(type => (
                <option key={type} value={type}>{EVENT_META[type]?.label ?? type}</option>
              ))}
            </select>
            {summary && Object.keys(summary.by_device).length > 1 && (
              <select
                value={filterDevice}
                onChange={e => setFilterDevice(e.target.value)}
                className="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600"
              >
                <option value="">Alle enheder</option>
                {Object.keys(summary.by_device).map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            )}
            {(filterSeverity || filterType || filterDevice) && (
              <button
                onClick={resetFilters}
                className="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-50"
              >
                Ryd filtre
              </button>
            )}
          </div>

          {/* Events tabel */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {loading ? (
              <div className="py-12 text-center text-gray-400 text-sm">Indlæser…</div>
            ) : events.length === 0 ? (
              <div className="py-12 text-center">
                <Shield className="w-10 h-10 text-gray-200 mx-auto mb-3" />
                <p className="text-gray-400 text-sm">Ingen events i perioden</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {events.map(ev => (
                  <button
                    key={ev.id}
                    onClick={() => setSelectedEvent(ev)}
                    className="w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex-shrink-0">
                        <EventTypeIcon type={ev.event_type} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-gray-900">
                            {EVENT_META[ev.event_type]?.label ?? ev.event_type}
                          </span>
                          <SeverityBadge severity={ev.severity} />
                          <span className="text-xs text-gray-400 font-mono">{ev.device_id}</span>
                          {ev.source && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{ev.source}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
                          {ev.category && <span>Kategori: {ev.category}</span>}
                          {ev.logger && <span className="font-mono">{ev.logger}</span>}
                          {ev.source_ip && (
                            <span className="font-mono">IP: {ev.source_ip}</span>
                          )}
                          {ev.username && (
                            <span>Bruger: {ev.username}</span>
                          )}
                          <span className="ml-auto text-gray-400">{fmtRelative(ev.occurred_at)}</span>
                        </div>
                        {ev.raw_message && (
                          <div className="mt-1 text-xs text-gray-400 font-mono truncate">
                            {ev.raw_message.slice(0, 120)}
                          </div>
                        )}
                      </div>
                      <Eye className="w-4 h-4 text-gray-300 mt-1" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Højre kolonne: statistik + trusler */}
        <div className="space-y-4">

          {/* Event typer */}
          {summary && Object.keys(summary.by_event_type).length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Event-typer</h3>
              <div className="space-y-2">
                {Object.entries(summary.by_event_type)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => {
                    const meta = EVENT_META[type]
                    const Icon = meta?.icon ?? Activity
                    const max = Math.max(...Object.values(summary.by_event_type))
                    return (
                      <div key={type} className="flex items-center gap-2">
                        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${meta?.color ?? 'text-gray-400'}`} />
                        <div className="flex-1">
                          <div className="flex justify-between text-xs mb-0.5">
                            <span className="text-gray-600">{meta?.label ?? type}</span>
                            <span className="font-medium text-gray-900">{count}</span>
                          </div>
                          <div className="h-1 bg-gray-100 rounded-full">
                            <div
                              className="h-full bg-sky-400 rounded-full"
                              style={{ width: `${(count / max) * 100}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
              </div>
            </div>
          )}

          {/* Trusler / Brute force */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Wifi className="w-4 h-4 text-red-500" />
              Brute force — Top IPs
            </h3>
            {threats.length === 0 ? (
              <p className="text-xs text-gray-400">Ingen trusler detekteret i perioden</p>
            ) : (
              <div className="space-y-2">
                {threats.slice(0, 10).map(t => (
                  <div key={`${t.source_ip}-${t.device_id}`}
                    className={`rounded-lg p-2.5 border ${
                      t.threat_level === 'critical'
                        ? 'bg-red-50 border-red-200'
                        : t.threat_level === 'warning'
                        ? 'bg-amber-50 border-amber-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm font-bold text-gray-900">
                        {t.source_ip}
                      </span>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        t.threat_level === 'critical' ? 'bg-red-200 text-red-800' :
                        t.threat_level === 'warning'  ? 'bg-amber-200 text-amber-800' :
                        'bg-gray-200 text-gray-700'
                      }`}>
                        {t.attempts} forsøg
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      <span className="font-mono">{t.device_id}</span>
                      {' · '}
                      {fmtDate(t.first_seen)} → {fmtDate(t.last_seen)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Per enhed */}
          {summary && Object.keys(summary.by_device).length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Per enhed</h3>
              <div className="space-y-1.5">
                {Object.entries(summary.by_device)
                  .sort((a, b) => b[1] - a[1])
                  .map(([device, count]) => (
                    <div key={device} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-gray-600 truncate">{device}</span>
                      <span className="font-medium text-gray-900 ml-2">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
      )}

      {activeTab === 'sources' && summary && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SiemSourceCard
            icon={Server}
            title="Headend"
            status="Aktiv"
            description="Headend collector indsamler applikations- og nginx-loglinjer lokalt og normaliserer dem ind i SIEM."
            items={['source=headend_log/nginx-*', 'device_id=HEADEND-LOCAL', 'Collector kører i FastAPI startup']}
          />
          <SiemSourceCard
            icon={Activity}
            title="Edge journal"
            status="Aktiv"
            description="Edge-agenten forwarder journal-events via det autentificerede TimeLapse API. Lab sender bredt, prod kan begrænses."
            items={['source=edge_journal', 'Default lab: info+', 'Default prod: warning+']}
          />
          <SiemSourceCard
            icon={RadioTower}
            title="Syslog"
            status="Loopback/lab"
            description="Headend kan modtage syslog på 5514 lokalt. I prod bør syslog normalt termineres på Edge/site collector og sendes videre via API."
            items={['127.0.0.1:5514 UDP/TCP', 'RFC3164/RFC5424', 'Switch/firewall events']}
          />
          <SiemSourceCard
            icon={Database}
            title="GitHub og eksterne kilder"
            status="Næste lag"
            description="GitHub Actions, code scanning og artifact-status bør ind som pollende collector med least-privilege GitHub App/token."
            items={['CI/deploy status', 'Signed commit checks', 'SAST/secret scanning']}
          />
        </div>
      )}

      {activeTab === 'policy' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <SlidersHorizontal className="w-5 h-5 text-sky-600" />
              <h2 className="text-sm font-semibold text-gray-900">Aktiv SIEM-politik</h2>
            </div>
            <div className="space-y-3 text-sm text-gray-700">
              <PolicyLine label="Edge lab" value="journal info+, max 200 pr. batch" />
              <PolicyLine label="Edge prod" value="journal warning+ som standard, konfigurerbart pr. site/enhed" />
              <PolicyLine label="Headend API" value="server-side max batch og rate-limit pr. device" />
              <PolicyLine label="Syslog prod" value="via Edge/site collector og signeret API, ikke åbent mod Headend" />
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Settings className="w-5 h-5 text-gray-600" />
              <h2 className="text-sm font-semibold text-gray-900">Konfiguration</h2>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Næste trin er at gøre disse værdier redigerbare pr. kunde, site og edge-enhed med change-ticket og godkendelsesflow.
            </p>
            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3 text-xs text-gray-600 font-mono whitespace-pre-wrap">
{`siem:
  enabled: true
  mode: lab | prod
  min_severity: info | warning | error
  forward_interval_s: 300
  max_events_per_batch: 200
  journal_units:
    - timelapse-edge.service`}
            </div>
          </div>
        </div>
      )}

      {selectedEvent && (
        <EventDetailDrawer
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
          onFilter={(field, value) => {
            if (field === 'device') setFilterDevice(value)
            if (field === 'type') setFilterType(value)
            if (field === 'severity') setFilterSeverity(value)
            setActiveTab('events')
            setSelectedEvent(null)
          }}
        />
      )}
    </div>
  )
}

// ── Summary card ──────────────────────────────────────────────────────────

function SummaryCard({ label, value, icon: Icon, color, bg, alert = false }: {
  label: string; value: number; icon: any
  color: string; bg: string; alert?: boolean
}) {
  return (
    <div className={`rounded-xl border p-4 ${bg} ${alert && value > 0 ? 'border-red-300 ring-1 ring-red-200' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">{label}</span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <div className={`text-2xl font-bold ${alert && value > 0 ? 'text-red-600' : 'text-gray-900'}`}>
        {value}
      </div>
    </div>
  )
}

function RiskLine({ label, value, tone }: { label: string; value: number; tone: 'red' | 'rose' | 'amber' | 'purple' }) {
  const cls = {
    red: 'text-red-700 bg-red-50 border-red-100',
    rose: 'text-rose-700 bg-rose-50 border-rose-100',
    amber: 'text-amber-700 bg-amber-50 border-amber-100',
    purple: 'text-purple-700 bg-purple-50 border-purple-100',
  }[tone]
  return (
    <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${cls}`}>
      <span>{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  )
}

function PolicyLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-gray-100 pb-2 last:border-0">
      <span className="font-medium text-gray-900">{label}</span>
      <span className="text-right text-gray-600">{value}</span>
    </div>
  )
}

function SiemSourceCard({ icon: Icon, title, status, description, items }: {
  icon: any
  title: string
  status: string
  description: string
  items: string[]
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-5 h-5 text-sky-600" />
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        <span className="ml-auto text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{status}</span>
      </div>
      <p className="text-sm text-gray-600 mb-4">{description}</p>
      <div className="space-y-1.5">
        {items.map(item => (
          <div key={item} className="text-xs font-mono text-gray-600 bg-gray-50 rounded px-2 py-1">
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

function parseNormalized(value?: string | null) {
  if (!value) return null
  try { return JSON.parse(value) } catch { return value }
}

function DetailRow({ label, value, mono = false }: { label: string; value: any; mono?: boolean }) {
  if (value == null || value === '') return null
  return (
    <div className="grid grid-cols-3 gap-3 py-2 border-b border-gray-100 last:border-b-0">
      <dt className="text-xs font-medium text-gray-500">{label}</dt>
      <dd className={`col-span-2 text-sm text-gray-900 break-words ${mono ? 'font-mono text-xs' : ''}`}>{String(value)}</dd>
    </div>
  )
}

function EventDetailDrawer({ event, onClose, onFilter }: {
  event: SecurityEvent
  onClose: () => void
  onFilter: (field: 'device' | 'type' | 'severity', value: string) => void
}) {
  const normalized = parseNormalized(event.normalized)
  return (
    <div className="fixed inset-0 z-50">
      <button className="absolute inset-0 bg-gray-900/20" onClick={onClose} aria-label="Luk detaljer" />
      <aside className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl border-l border-gray-200 overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-start gap-3">
          <div className="mt-0.5"><EventTypeIcon type={event.event_type} /></div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900">Event #{event.id}</h2>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-gray-700">{EVENT_META[event.event_type]?.label ?? event.event_type}</span>
              <SeverityBadge severity={event.severity} />
            </div>
          </div>
          <button onClick={onClose} className="ml-auto text-gray-400 hover:text-gray-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Kernefelter</h3>
            <dl className="rounded-lg border border-gray-200 px-3">
              <DetailRow label="Device" value={event.device_id} mono />
              <DetailRow label="Type" value={event.event_type} mono />
              <DetailRow label="Severity" value={event.severity} />
              <DetailRow label="Source" value={event.source} mono />
              <DetailRow label="Category" value={event.category} />
              <DetailRow label="Logger" value={event.logger} mono />
              <DetailRow label="Process" value={event.process} mono />
              <DetailRow label="Source IP" value={event.source_ip} mono />
              <DetailRow label="Username" value={event.username} />
              <DetailRow label="Occurred" value={fmtDate(event.occurred_at)} />
              <DetailRow label="Received" value={fmtDate(event.received_at ?? null)} />
            </dl>
          </section>

          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Handlinger</h3>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => onFilter('device', event.device_id)} className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50">
                Filtrer på device
              </button>
              <button onClick={() => onFilter('type', event.event_type)} className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50">
                Filtrer på type
              </button>
              <button onClick={() => onFilter('severity', event.severity)} className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50">
                Filtrer på severity
              </button>
            </div>
          </section>

          {event.raw_message && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Raw message</h3>
              <pre className="rounded-lg bg-gray-950 text-gray-100 text-xs p-3 overflow-x-auto whitespace-pre-wrap">{event.raw_message}</pre>
            </section>
          )}

          {normalized && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Normalized</h3>
              <pre className="rounded-lg bg-gray-50 border border-gray-200 text-gray-700 text-xs p-3 overflow-x-auto whitespace-pre-wrap">
                {typeof normalized === 'string' ? normalized : JSON.stringify(normalized, null, 2)}
              </pre>
            </section>
          )}
        </div>
      </aside>
    </div>
  )
}
