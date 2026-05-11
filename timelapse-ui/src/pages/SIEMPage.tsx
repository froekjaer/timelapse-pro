// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — SIEMPage.tsx
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback } from 'react'
import {
  Shield, AlertTriangle, AlertCircle, Info, RefreshCw,
  Wifi, Terminal, User, Key, Server, Activity, Zap
} from 'lucide-react'
import { getApiUrl } from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────

interface SecurityEvent {
  id: number
  device_id: string
  event_type: string
  severity: 'info' | 'warning' | 'critical'
  username: string | null
  source_ip: string | null
  raw_message: string | null
  occurred_at: string
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
}

const SEVERITY_CONFIG = {
  critical: { bg: 'bg-red-100',    text: 'text-red-700',    border: 'border-red-200',    label: 'Kritisk', icon: AlertCircle },
  warning:  { bg: 'bg-amber-100',  text: 'text-amber-700',  border: 'border-amber-200',  label: 'Advarsel', icon: AlertTriangle },
  info:     { bg: 'bg-sky-100',    text: 'text-sky-700',    border: 'border-sky-200',    label: 'Info', icon: Info },
}

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
  const [autoRefresh,    setAutoRefresh]    = useState(true)

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
  const warnCount = summary?.by_severity['warning']  ?? 0

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
              <option value="warning">Advarsel</option>
              <option value="info">Info</option>
            </select>
            <select
              value={filterType}
              onChange={e => setFilterType(e.target.value)}
              className="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600"
            >
              <option value="">Alle typer</option>
              {Object.entries(EVENT_META).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
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
                  <div key={ev.id} className="px-4 py-2.5 hover:bg-gray-50 transition-colors">
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
                        </div>
                        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
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
                    </div>
                  </div>
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
