import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, CheckCircle, ClipboardCheck, FileCheck,
  RefreshCw, ShieldCheck
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  }).then(async r => {
    const data = await r.json().catch(() => null)
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`)
    return data
  })
}

interface Control {
  source: string
  status: string
  title: string
  evidence: string
  recommendation: string
  domains: string[]
}

interface Approval {
  id: number
  update_type: string
  version: string | null
  description: string | null
  severity: string | null
  status: string
  environment: string | null
  scope: string | null
  scope_id: string | null
  created_at: string | null
  risk: { score: number; level: string; factors: string[] }
  targets: Array<{ device_id: string; customer_name: string | null; site_name: string | null; camera_name: string | null }>
  change_ticket: { ticket_id: string; status: string } | null
  artifact: { artifact_id: string; signed_by: string | null } | null
}

interface Cockpit {
  generated_at: string
  mode: string
  summary: {
    controls: Record<string, number>
    approval_queue: number
    devices: number
    change_tickets: number
    sast_findings: number
  }
  standards: string[]
  controls: Control[]
  approvals: Approval[]
  evidence_sources: string[]
}

type Tab = 'approvals' | 'controls' | 'evidence'

function statusClass(status: string) {
  const map: Record<string, string> = {
    pass: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    fail: 'bg-red-50 text-red-600 border-red-200',
    critical: 'bg-red-600 text-white border-red-600',
    high: 'bg-red-50 text-red-700 border-red-200',
    medium: 'bg-amber-50 text-amber-700 border-amber-200',
    low: 'bg-gray-50 text-gray-600 border-gray-200',
  }
  return map[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'
}

function fmt(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-xl font-semibold text-gray-900 mt-1">{value}</div>
    </div>
  )
}

export function CompliancePage() {
  const [data, setData] = useState<Cockpit | null>(null)
  const [tab, setTab] = useState<Tab>('approvals')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setData(await api('/api/compliance/cockpit'))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente compliance cockpit')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function accept(updateId: number) {
    setBusy(updateId)
    setError(null)
    try {
      await api(`/api/compliance/updates/${updateId}/accept`, {
        method: 'POST',
        body: JSON.stringify({
          summary: 'Godkendt fra Compliance Cockpit simple acceptance',
          maintenance_window: 'Efter gældende update policy',
          reboot_required: false,
        }),
      })
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke godkende opdatering')
    } finally {
      setBusy(null)
    }
  }

  const counts = data?.summary.controls ?? {}

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-gray-500" />
            Compliance Cockpit
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Near-realtime posture, evidens og enkel update-accept</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-200 rounded-lg text-gray-500 hover:bg-gray-50 disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Opdater
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5">
        <Metric label="Pass" value={counts.pass ?? 0} />
        <Metric label="Warnings" value={counts.warning ?? 0} />
        <Metric label="Fail" value={counts.fail ?? 0} />
        <Metric label="Approval kø" value={data?.summary.approval_queue ?? 0} />
        <Metric label="Change tickets" value={data?.summary.change_tickets ?? 0} />
        <Metric label="SAST findings" value={data?.summary.sast_findings ?? 0} />
      </div>

      <div className="bg-sky-50 border border-sky-100 rounded-lg px-4 py-3 mb-5">
        <div className="text-sm font-medium text-sky-900">Compliance paraply</div>
        <p className="text-xs text-sky-700 mt-1 leading-5">
          Almindelige brugere skal kun tage stilling til relevante godkendelser. Evidens, standardmapping og dybe tekniske detaljer samles her for admin, audit og kundeaccept.
        </p>
      </div>

      <div className="flex gap-1 mb-4">
        {[
          ['approvals', 'Godkendelser'],
          ['controls', 'Controls'],
          ['evidence', 'Evidens'],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key as Tab)}
            className={`px-3 py-1.5 text-xs rounded-lg ${tab === key ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
            {label}
          </button>
        ))}
      </div>

      {loading && !data ? (
        <div className="bg-white border border-gray-200 rounded-lg py-16 text-center text-sm text-gray-400">Henter compliance data...</div>
      ) : tab === 'approvals' ? (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          {data?.approvals.length === 0 ? (
            <div className="py-16 text-center">
              <CheckCircle className="w-8 h-8 text-green-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">Ingen opdateringer afventer din godkendelse</p>
            </div>
          ) : data?.approvals.map(item => (
            <div key={item.id} className="p-5 border-b border-gray-100 last:border-0">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900">{item.update_type}</span>
                    <span className="text-xs font-mono text-gray-500">{item.version || '-'}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(item.risk.level)}`}>Risk {item.risk.score}</span>
                    {item.artifact && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-green-50 text-green-700 border-green-200">signed artifact</span>}
                    {item.change_ticket && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">{item.change_ticket.ticket_id}</span>}
                  </div>
                  <p className="text-sm text-gray-600 mt-2">{item.description || 'Ingen beskrivelse'}</p>
                  <p className="text-xs text-gray-400 mt-2">
                    Scope: {item.scope || '-'} {item.scope_id || ''} / Oprettet {fmt(item.created_at)}
                  </p>
                  <div className="mt-3 flex gap-1 flex-wrap">
                    {item.targets.map(target => (
                      <span key={target.device_id} className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">
                        {target.customer_name || 'kunde?'} / {target.site_name || 'site?'} / {target.camera_name || target.device_id}
                      </span>
                    ))}
                  </div>
                </div>
                <button onClick={() => accept(item.id)} disabled={busy === item.id}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm disabled:opacity-50">
                  <ClipboardCheck className="w-4 h-4" />
                  Acceptér
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'controls' ? (
        <div className="space-y-3">
          {data?.controls.map(control => (
            <div key={`${control.source}-${control.title}`} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <FileCheck className="w-4 h-4 text-gray-500" />
                    <h2 className="text-sm font-semibold text-gray-900">{control.title}</h2>
                    <span className="text-[11px] text-gray-400">{control.source}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">{control.evidence}</p>
                  <p className="text-xs text-gray-400 mt-2">{control.recommendation}</p>
                  <div className="mt-3 flex gap-1 flex-wrap">
                    {control.domains.map(domain => (
                      <span key={domain} className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">{domain}</span>
                    ))}
                  </div>
                </div>
                <span className={`text-xs px-2 py-1 rounded border ${statusClass(control.status)}`}>{control.status}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Evidenskilder</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {data?.evidence_sources.map(source => (
              <div key={source} className="flex items-center gap-2 text-sm text-gray-700 bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
                <FileCheck className="w-4 h-4 text-gray-300" />
                {source}
              </div>
            ))}
          </div>
          <div className="mt-5">
            <div className="text-xs text-gray-400 mb-2">Standarder</div>
            <div className="flex gap-1 flex-wrap">
              {data?.standards.map(s => (
                <span key={s} className="text-xs px-2 py-1 rounded border bg-gray-50 text-gray-700 border-gray-200">{s}</span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
