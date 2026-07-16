import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, CheckCircle, ClipboardCheck, FileText, RefreshCw,
  ShieldCheck, XCircle
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface ChangeTicket {
  ticket_id: string
  title: string
  summary: string | null
  pending_update_id: number | null
  update_type: string | null
  severity: string | null
  environment: string | null
  scope: string | null
  scope_id: string | null
  status: string
  rollback_plan: string | null
  reboot_required: boolean
  maintenance_window: string | null
  human_readable_md: string | null
  content_sha256: string | null
  signature: string | null
  signed_by: string | null
  signed_at: string | null
  created_by: string | null
  created_at: string | null
  approvals?: {
    decision: string
    decided_by: string
    decided_at: string | null
    signed_payload_sha256: string | null
    signature: string | null
    notes: string | null
  }[]
}

function fmt(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function statusClass(status: string) {
  const map: Record<string, string> = {
    draft: 'bg-gray-50 text-gray-600 border-gray-200',
    ready: 'bg-sky-50 text-sky-700 border-sky-200',
    pending_approval: 'bg-amber-50 text-amber-700 border-amber-200',
    approved: 'bg-green-50 text-green-700 border-green-200',
    rejected: 'bg-red-50 text-red-600 border-red-200',
    deployed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rolled_back: 'bg-purple-50 text-purple-700 border-purple-200',
  }
  return map[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'
}

function shortHash(value: string | null) {
  if (!value) return '-'
  return value.length > 18 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value
}

export function ChangeTicketsPage() {
  const [tickets, setTickets] = useState<ChangeTicket[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<ChangeTicket | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [updateId, setUpdateId] = useState('')

  const load = useCallback(async () => {
    setError(null)
    try {
      const data = await api('/api/change-tickets')
      setTickets(Array.isArray(data) ? data : [])
      if (!selectedId && Array.isArray(data) && data.length) {
        setSelectedId(data[0].ticket_id)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente change tickets')
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!selectedId) {
      setSelected(null)
      return
    }
    let cancelled = false
    api(`/api/change-tickets/${selectedId}`)
      .then(data => { if (!cancelled) setSelected(data) })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Kunne ikke hente ticket') })
    return () => { cancelled = true }
  }, [selectedId])

  async function createFromUpdate() {
    const id = Number(updateId)
    if (!Number.isInteger(id) || id <= 0) {
      setError('Update ID skal være et positivt tal')
      return
    }
    setBusy(true)
    try {
      const ticket = await api(`/api/updates/${id}/change-ticket`, { method: 'POST', body: JSON.stringify({}) })
      setUpdateId('')
      setSelectedId(ticket.ticket_id)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke oprette change ticket')
    } finally {
      setBusy(false)
    }
  }

  async function decide(decision: 'approve' | 'reject') {
    if (!selected) return
    setBusy(true)
    try {
      await api(`/api/change-tickets/${selected.ticket_id}/${decision}`, {
        method: 'POST',
        body: JSON.stringify({ notes: notes.trim() || null }),
      })
      setNotes('')
      await load()
      setSelected(await api(`/api/change-tickets/${selected.ticket_id}`))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke gemme beslutning')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-gray-500" />
            Change tickets
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Signerede opdateringsbeslutninger og kundegodkendelser</p>
        </div>
        <button onClick={() => load()} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50">
          <RefreshCw className="w-3.5 h-3.5" />
          Opdater
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-100 text-red-600 text-sm rounded-lg">
          {error}
        </div>
      )}

      <div className="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <label className="block text-xs font-medium text-gray-500 mb-1">PendingUpdate ID</label>
            <div className="flex gap-2">
              <input value={updateId} onChange={e => setUpdateId(e.target.value)}
                className="min-w-0 flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="fx 12" />
              <button onClick={createFromUpdate} disabled={busy}
                className="px-3 py-2 text-sm rounded-lg bg-gray-900 text-white disabled:opacity-50">
                Opret
              </button>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {loading ? (
              <div className="py-12 text-center text-sm text-gray-400">Henter...</div>
            ) : tickets.length === 0 ? (
              <div className="py-12 text-center">
                <FileText className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                <p className="text-sm text-gray-500">Ingen change tickets</p>
              </div>
            ) : tickets.map(ticket => (
              <button key={ticket.ticket_id} onClick={() => setSelectedId(ticket.ticket_id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-100 last:border-0 hover:bg-gray-50 ${
                  selectedId === ticket.ticket_id ? 'bg-sky-50' : ''
                }`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-gray-800 truncate">{ticket.title}</span>
                  <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(ticket.status)}`}>
                    {ticket.status}
                  </span>
                </div>
                <div className="mt-1 text-xs text-gray-400 font-mono">{ticket.ticket_id}</div>
                <div className="mt-1 text-xs text-gray-400">{fmt(ticket.created_at)} af {ticket.created_by || '-'}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden min-h-[560px]">
          {!selected ? (
            <div className="py-20 text-center text-sm text-gray-400">Vælg et change ticket</div>
          ) : (
            <div>
              <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold text-gray-900">{selected.title}</h2>
                    <span className={`text-xs px-2 py-0.5 rounded border ${statusClass(selected.status)}`}>
                      {selected.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 font-mono">{selected.ticket_id}</p>
                </div>
                <div className="text-right text-xs text-gray-400">
                  <div>SHA-256</div>
                  <div className="font-mono text-gray-600">{shortHash(selected.content_sha256)}</div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-0 border-b border-gray-100 text-sm">
                <div className="px-5 py-3 border-r border-gray-100">
                  <div className="text-xs text-gray-400 mb-1">Update</div>
                  <div className="text-gray-800">{selected.update_type || '-'}</div>
                </div>
                <div className="px-5 py-3 border-r border-gray-100">
                  <div className="text-xs text-gray-400 mb-1">Miljø</div>
                  <div className="text-gray-800">{selected.environment || '-'}</div>
                </div>
                <div className="px-5 py-3">
                  <div className="text-xs text-gray-400 mb-1">Scope</div>
                  <div className="text-gray-800">{selected.scope || '-'}{selected.scope_id ? ` / ${selected.scope_id}` : ''}</div>
                </div>
              </div>

              <div className="p-5 grid grid-cols-[1fr_300px] gap-5">
                <pre className="whitespace-pre-wrap text-sm leading-6 text-gray-700 bg-gray-50 border border-gray-100 rounded-lg p-4 min-h-[360px] overflow-auto">
                  {selected.human_readable_md || selected.summary || 'Ingen tickettekst'}
                </pre>

                <div className="space-y-4">
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-gray-800 mb-3">
                      <ShieldCheck className="w-4 h-4 text-gray-500" />
                      Beslutning
                    </div>
                    <textarea value={notes} onChange={e => setNotes(e.target.value)}
                      className="w-full h-24 border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none"
                      placeholder="Noter til audit" />
                    <div className="flex gap-2 mt-3">
                      <button onClick={() => decide('approve')} disabled={busy || selected.status === 'approved'}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm disabled:opacity-50">
                        <CheckCircle className="w-4 h-4" />
                        Godkend
                      </button>
                      <button onClick={() => decide('reject')} disabled={busy || selected.status === 'rejected'}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-50 text-red-600 border border-red-200 text-sm disabled:opacity-50">
                        <XCircle className="w-4 h-4" />
                        Afvis
                      </button>
                    </div>
                  </div>

                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="text-xs font-medium text-gray-500 mb-2">Approvals</div>
                    {!selected.approvals?.length ? (
                      <p className="text-sm text-gray-400">Ingen beslutninger endnu</p>
                    ) : selected.approvals.map((approval, index) => (
                      <div key={`${approval.decided_at}-${index}`} className="border-t border-gray-100 py-2 first:border-t-0 first:pt-0 last:pb-0">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium text-gray-700">{approval.decision}</span>
                          <span className="text-xs text-gray-400">{fmt(approval.decided_at)}</span>
                        </div>
                        <div className="text-xs text-gray-400">af {approval.decided_by}</div>
                        <div className="text-xs text-gray-500 font-mono mt-1">{shortHash(approval.signed_payload_sha256)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
