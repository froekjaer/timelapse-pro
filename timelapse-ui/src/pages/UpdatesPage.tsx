// ═══════════════════════════════════════════════════════════════
// UpdatesPage.tsx
// Version: 1.0.0  |  08. maj 2026
// ═══════════════════════════════════════════════════════════════
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, RefreshCw, CheckCircle, XCircle, Clock,
  Package, AlertTriangle, Shield, ChevronDown, ChevronRight
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface Update {
  id:                number
  update_type:       string
  version:           string
  description:       string | null
  severity:          string
  scope:             string
  scope_id:          string | null
  status:            string
  environment:       string | null
  deployed_count:    number
  failed_count:      number
  created_at:        string | null
  approved_at:       string | null
  approved_by:       string | null
}

interface ApproveOptions {
  environment:      'test' | 'production'
  scope:            'global' | 'device'
  scope_id:         string
}

type Filter = 'pending' | 'approved' | 'deployed' | 'rejected' | 'rolled_back' | 'all'

function fmt(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

function severityBadge(s: string) {
  const map: Record<string, string> = {
    critical: 'bg-red-50 text-red-700 border-red-200',
    high:     'bg-orange-50 text-orange-700 border-orange-200',
    medium:   'bg-amber-50 text-amber-700 border-amber-200',
    low:      'bg-gray-50 text-gray-500 border-gray-200',
  }
  return map[s] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

function statusBadge(s: string) {
  const map: Record<string, string> = {
    pending:     'bg-amber-50 text-amber-700 border-amber-200',
    approved:    'bg-sky-50 text-sky-700 border-sky-200',
    deployed:    'bg-green-50 text-green-700 border-green-200',
    rejected:    'bg-red-50 text-red-500 border-red-200',
    rolled_back: 'bg-purple-50 text-purple-700 border-purple-200',
  }
  return map[s] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

const STATUS_LABELS: Record<string, string> = {
  pending:     'Afventer',
  approved:    'Godkendt',
  deployed:    'Deployet',
  rejected:    'Afvist',
  rolled_back: 'Rullet tilbage',
}

const TYPE_LABELS: Record<string, string> = {
  app_security: 'App sikkerhed',
  os_security:  'OS sikkerhed',
  app_updates:  'App opdatering',
  os_updates:   'OS opdatering',
}

function UpdateRow({ u, onApprove, onReject, onPromote, onRollback, busy }: {
  u: Update
  onApprove:  (id: number) => void
  onReject:   (id: number) => void
  onPromote:  (id: number) => void
  onRollback: (id: number) => void
  busy: number | null
}) {
  const [open, setOpen] = useState(false)
  const isBusy = busy === u.id

  return (
    <div className="border-b border-gray-50 last:border-0">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 transition-colors text-left">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-800">
              {TYPE_LABELS[u.update_type] ?? u.update_type}
            </span>
            <span className="text-xs font-mono text-gray-500">v{u.version}</span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${severityBadge(u.severity)}`}>
              {u.severity}
            </span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${statusBadge(u.status)}`}>
              {STATUS_LABELS[u.status] ?? u.status}
            </span>
            {u.environment && (
              <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${u.environment === 'test' ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-gray-50 text-gray-500 border-gray-200'}`}>
                {u.environment === 'test' ? '🧪 test' : '🚀 prod'}
              </span>
            )}
            {u.scope !== 'global' && (
              <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-500 border-gray-200">
                {u.scope}{u.scope_id ? `: ${u.scope_id}` : ''}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">Oprettet {fmt(u.created_at)}</p>
        </div>
        {u.status === 'pending' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => { onApprove(u.id) }}
              disabled={isBusy}
              className="flex items-center gap-1 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
              <CheckCircle className="w-3.5 h-3.5" />
              Godkend
            </button>
            <button onClick={() => onReject(u.id)} disabled={isBusy}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 text-xs rounded-lg border border-red-200 disabled:opacity-50 transition-colors">
              <XCircle className="w-3.5 h-3.5" />
              Afvis
            </button>
          </div>
        )}
        {u.status === 'deployed' && u.environment === 'test' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => onPromote(u.id)} disabled={isBusy}
              className="flex items-center gap-1 px-3 py-1.5 bg-sky-500 hover:bg-sky-600 text-white text-xs rounded-lg disabled:opacity-50">
              🚀 Promovér til prod
            </button>
          </div>
        )}
        {u.status === 'deployed' && (
          <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
            <button onClick={() => onRollback(u.id)} disabled={isBusy}
              className="flex items-center gap-1 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 text-xs rounded-lg border border-amber-200 disabled:opacity-50">
              ↩ Rollback
            </button>
          </div>
        )}
        {u.status === 'approved' && (
          <div className="flex items-center gap-1.5 mr-3 text-xs text-sky-500 flex-shrink-0">
            <Clock className="w-3.5 h-3.5 animate-pulse" />
            Afventer edge
          </div>
        )}
        {open ? <ChevronDown className="w-4 h-4 text-gray-300 flex-shrink-0" />
               : <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-4 pt-1 bg-gray-50 border-t border-gray-100">
          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
            {u.description && (
              <div className="col-span-2 mb-1">
                <span className="text-gray-400">Beskrivelse: </span>
                <span className="text-gray-700">{u.description}</span>
              </div>
            )}
            <div><span className="text-gray-400">Type: </span><span className="text-gray-700 font-mono">{u.update_type}</span></div>
            <div><span className="text-gray-400">Scope: </span><span className="text-gray-700">{u.scope}{u.scope_id ? ` / ${u.scope_id}` : ''}</span></div>
            <div><span className="text-gray-400">Oprettet: </span><span className="text-gray-700">{fmt(u.created_at)}</span></div>
            {u.approved_at && <div><span className="text-gray-400">Behandlet: </span><span className="text-gray-700">{fmt(u.approved_at)} af {u.approved_by}</span></div>}
            <div><span className="text-gray-400">ID: </span><span className="text-gray-500 font-mono">#{u.id}</span></div>
          </div>
        </div>
      )}
    </div>
  )
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'pending',  label: 'Afventer' },
  { key: 'approved', label: 'Godkendt' },
  { key: 'deployed', label: 'Deployet' },
  { key: 'rejected',     label: 'Afvist' },
  { key: 'rolled_back',  label: 'Rullet tilbage' },
  { key: 'all',      label: 'Alle' },
]

export function UpdatesPage() {
  const [updates, setUpdates]       = useState<Update[]>([])
  const [loading, setLoading]       = useState(true)
  const [filter, setFilter]         = useState<Filter>('pending')
  const [busy, setBusy]             = useState<number | null>(null)
  const [lastRefresh, setLast]      = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [approveId, setApproveId]   = useState<number | null>(null)
  const [approveOpts, setApproveOpts] = useState<ApproveOptions>({
    environment: 'production', scope: 'device', scope_id: ''
  })

  const load = useCallback(async (spin = false) => {
    if (spin) setRefreshing(true)
    setError(null)
    try {
      const params = filter === 'all' ? '' : `?status=${filter}`
      const data = await api(`/api/updates/pending${params}`)
      setUpdates(Array.isArray(data) ? data : [])
      setLast(new Date())
    } catch (e: any) {
      setError(`Kunne ikke hente opdateringer (${e.message})`)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  async function approve(id: number) {
    if (approveOpts.scope === 'device' && !approveOpts.scope_id.trim()) {
      setError('Device ID er påkrævet ved specifik enhed')
      return
    }
    setBusy(id)
    const payload = {
      environment: approveOpts.environment,
      scope: approveOpts.scope,
      scope_id: approveOpts.scope === 'device' ? approveOpts.scope_id.trim() : null,
    }
    try {
      await api(`/api/updates/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) })
      setApproveId(null)
      load()
    }
    catch (e: any) { setError(e.message) }
    finally { setBusy(null) }
  }

  async function reject(id: number) {
    setBusy(id)
    try { await api(`/api/updates/${id}/reject`, { method: 'POST' }); load() }
    catch (e: any) { setError(e.message) }
    finally { setBusy(null) }
  }

  async function promote(id: number) {
    setBusy(id)
    try { await api(`/api/updates/${id}/promote`, { method: 'POST' }); load() }
    catch (e: any) { setError(e.message) }
    finally { setBusy(null) }
  }

  async function forceRollback(id: number) {
    if (!confirm('Er du sikker på at du vil rulle denne opdatering tilbage?')) return
    setBusy(id)
    try { await api(`/api/updates/${id}/force-rollback`, { method: 'POST' }); load() }
    catch (e: any) { setError(e.message) }
    finally { setBusy(null) }
  }

  const pending = updates.filter(u => u.status === 'pending').length

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Package className="w-5 h-5 text-gray-400" />
            Opdateringer
            {pending > 0 && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                {pending} afventer
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Godkend eller afvis software-opdateringer til edge-enheder</p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-300 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastRefresh.toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button onClick={() => load(true)} disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Opdatér
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      <div className="flex gap-1 mb-4">
        {FILTERS.map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              filter === f.key ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}>
            {f.label}
          </button>
        ))}
      </div>


      {approveId !== null && (
        <div className="bg-white rounded-xl border border-green-200 p-4 mb-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">⚙️ Godkend opdatering</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Miljø</label>
              <select value={approveOpts.environment}
                onChange={e => setApproveOpts(o => ({...o, environment: e.target.value as any}))}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                <option value="test">🧪 Test (deploy til testmiljø først)</option>
                <option value="production">🚀 Produktion</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Scope</label>
              <select value={approveOpts.scope}
                onChange={e => setApproveOpts(o => ({...o, scope: e.target.value as any}))}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                <option value="global">Alle enheder</option>
                <option value="device">Specifik enhed</option>
              </select>
            </div>
            {approveOpts.scope === 'device' && (
              <div className="col-span-2">
                <label className="text-xs text-gray-500 block mb-1">Device ID</label>
                <input value={approveOpts.scope_id}
                  onChange={e => setApproveOpts(o => ({...o, scope_id: e.target.value}))}
                  placeholder="fx TL-C87FF9587CA0"
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono" />
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={() => approve(approveId)}
              className="px-4 py-1.5 bg-green-500 text-white text-xs rounded-lg hover:bg-green-600">
              ✓ Bekræft godkendelse
            </button>
            <button onClick={() => setApproveId(null)}
              className="px-4 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">
              Annuller
            </button>
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="py-12 text-center">
            <Package className="w-6 h-6 text-gray-200 mx-auto mb-2 animate-pulse" />
            <p className="text-sm text-gray-400">Henter opdateringer…</p>
          </div>
        ) : updates.length === 0 ? (
          <div className="py-12 text-center">
            <Shield className="w-8 h-8 text-gray-200 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-500">Ingen opdateringer</p>
            <p className="text-xs text-gray-300 mt-1">
              {filter === 'pending' ? 'Alle opdateringer er behandlet' : `Ingen opdateringer med status "${filter}"`}
            </p>
          </div>
        ) : (
          updates.map(u => (
            <UpdateRow key={u.id} u={u} onApprove={id => { setApproveId(id); setApproveOpts({environment:'production',scope:'device',scope_id:u.scope_id||''}) }} onReject={reject} onPromote={id => promote(id)} onRollback={id => forceRollback(id)} busy={busy} />
          ))
        )}
      </div>
    </div>
  )
}
