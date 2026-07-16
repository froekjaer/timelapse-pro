import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, CheckCircle, ClipboardCheck, FileCheck,
  ExternalLink, Globe2, RefreshCw, Search, ShieldCheck
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  }).then(async r => {
    const data = await r.json().catch(() => null)
    if (!r.ok) {
      const detail = data?.detail
      const message = typeof detail === 'string'
        ? detail
        : detail?.message
          ? [detail.message, detail.next_action].filter(Boolean).join(' ')
          : `HTTP ${r.status}`
      throw new Error(message)
    }
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
  evidence_links?: Array<{ url: string; label: string }>
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
  artifact_required?: boolean
  artifact_missing?: boolean
  actionable?: boolean
  block_reason?: string | null
  action_message?: string | null
  next_action?: string | null
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

interface GrcDashboard {
  generated_at: string
  model: string
  summary: {
    devices: number
    security_updates_missing: number
    functional_updates_missing: number
    blocked_updates: number
    approved_updates: number
    deployed_updates: number
    rolled_back_updates: number
    fleet_risk_score: number
    highest_device_risk: number
  }
  risk_model: {
    not_cvss_only: boolean
    components: string[]
  }
  devices: Array<{
    device_id: string
    hostname: string | null
    environment: string | null
    customer_name: string | null
    site_name: string | null
    status: string | null
    last_seen: string | null
    risk_score: number
    risk_level: string
    missing_security_updates: number
    missing_functional_updates: number
    blocked_updates: number
    approved_updates: number
    top_risks: Array<{
      update_id: number
      update_type: string
      status: string
      severity: string | null
      current_version: string | null
      latest_available_version: string | null
      package_count: number | null
      component: string | null
      risk: { score: number; level: string; factors: string[] }
    }>
  }>
}

interface StandardReport {
  standard: string
  audit_type?: string
  catalog_complete?: boolean
  claim_limit?: string
  generated_at: string
  scope: string
  emphasis: string
  summary: {
    controls: Record<string, number>
    control_count: number
    gap_count: number
    fleet_risk_score: number
    high_risk_devices: number
    approval_queue: number
  }
  controls: Control[]
  gaps: Array<{
    title: string
    status: string
    evidence: string
    recommendation: string
    source: string
    evidence_links?: Array<{ url: string; label: string }>
  }>
  high_risk_devices: GrcDashboard['devices']
  evidence_sources: string[]
  recommended_next_steps: string[]
}

interface RegulatoryInstrument {
  id: string
  title: string
  short_name: string
  jurisdiction: string
  kind: string
  category: string
  status: string
  applicability: string
  effective_from: string | null
  next_deadline: string | null
  source_url: string
  relevance: string
}

interface AuditCatalog {
  id: string
  title: string
  catalog_status: string
  license: string
  full_audit_available: boolean
  reason: string
}

type Tab = 'grc' | 'regulatory' | 'approvals' | 'controls' | 'evidence'
type MetricKey = 'pass' | 'warning' | 'fail' | 'approval_queue' | 'change_tickets' | 'sast_findings' | 'fleet_risk' | 'highest_device_risk' | 'security_missing' | 'blocked' | 'approved'

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

function Metric({ label, value, active, onClick }: { label: string; value: number; active?: boolean; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className={`text-left bg-white border rounded-lg px-4 py-3 ${onClick ? 'hover:bg-gray-50 cursor-pointer' : 'cursor-default'} ${active ? 'border-gray-900 ring-1 ring-gray-900' : 'border-gray-200'}`}>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-xl font-semibold text-gray-900 mt-1">{value}</div>
    </button>
  )
}

export function CompliancePage() {
  const [data, setData] = useState<Cockpit | null>(null)
  const [grc, setGrc] = useState<GrcDashboard | null>(null)
  const [tab, setTab] = useState<Tab>('grc')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedMetric, setSelectedMetric] = useState<MetricKey | null>(null)
  const [standardReport, setStandardReport] = useState<StandardReport | null>(null)
  const [reportLoading, setReportLoading] = useState<string | null>(null)
  const [instruments, setInstruments] = useState<RegulatoryInstrument[]>([])
  const [auditCatalogs, setAuditCatalogs] = useState<AuditCatalog[]>([])
  const [regulatorySearch, setRegulatorySearch] = useState('')

  const load = useCallback(async () => {
    setError(null)
    try {
      const [cockpit, grcData, regulatoryData, catalogData] = await Promise.all([
        api('/api/compliance/cockpit'),
        api('/api/grc/dashboard'),
        api('/api/compliance/intelligence/instruments'),
        api('/api/compliance/intelligence/audit-catalogs'),
      ])
      setData(cockpit)
      setGrc(grcData)
      setInstruments(regulatoryData.instruments ?? [])
      setAuditCatalogs(catalogData.catalogs ?? [])
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

  async function loadStandardReport(standard: string) {
    setReportLoading(standard)
    setError(null)
    try {
      setStandardReport(await api(`/api/compliance/reports/${standard}`))
      setTab('evidence')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke generere rapport')
    } finally {
      setReportLoading(null)
    }
  }

  const counts = data?.summary.controls ?? {}
  const filteredControls = selectedMetric === 'pass' || selectedMetric === 'warning' || selectedMetric === 'fail'
    ? (data?.controls ?? []).filter(control => control.status === selectedMetric)
    : []
  const filteredDevices = selectedMetric === 'fleet_risk' || selectedMetric === 'highest_device_risk'
    ? (grc?.devices ?? []).filter(device => device.risk_score > 0)
    : selectedMetric === 'security_missing'
      ? (grc?.devices ?? []).filter(device => device.missing_security_updates > 0)
      : selectedMetric === 'blocked'
        ? (grc?.devices ?? []).filter(device => device.blocked_updates > 0)
        : selectedMetric === 'approved'
          ? (grc?.devices ?? []).filter(device => device.approved_updates > 0)
          : []
  const visibleInstruments = regulatorySearch.trim()
    ? instruments.filter(item => Object.values(item).join(' ').toLocaleLowerCase().includes(regulatorySearch.trim().toLocaleLowerCase()))
    : instruments

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
        <Metric label="Pass" value={counts.pass ?? 0} active={selectedMetric === 'pass'} onClick={() => setSelectedMetric(selectedMetric === 'pass' ? null : 'pass')} />
        <Metric label="Warnings" value={counts.warning ?? 0} active={selectedMetric === 'warning'} onClick={() => setSelectedMetric(selectedMetric === 'warning' ? null : 'warning')} />
        <Metric label="Fail" value={counts.fail ?? 0} active={selectedMetric === 'fail'} onClick={() => setSelectedMetric(selectedMetric === 'fail' ? null : 'fail')} />
        <Metric label="Approval kø" value={data?.summary.approval_queue ?? 0} active={selectedMetric === 'approval_queue'} onClick={() => { setSelectedMetric(selectedMetric === 'approval_queue' ? null : 'approval_queue'); setTab('approvals') }} />
        <Metric label="Change tickets" value={data?.summary.change_tickets ?? 0} active={selectedMetric === 'change_tickets'} onClick={() => setSelectedMetric(selectedMetric === 'change_tickets' ? null : 'change_tickets')} />
        <Metric label="SAST findings" value={data?.summary.sast_findings ?? 0} active={selectedMetric === 'sast_findings'} onClick={() => setSelectedMetric(selectedMetric === 'sast_findings' ? null : 'sast_findings')} />
      </div>

      {selectedMetric && (filteredControls.length > 0 || filteredDevices.length > 0 || selectedMetric === 'change_tickets' || selectedMetric === 'sast_findings') && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-5">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-sm font-semibold text-gray-900">Detaljer</h2>
            <button onClick={() => setSelectedMetric(null)} className="text-xs text-gray-400 hover:text-gray-600">Luk</button>
          </div>
          {filteredControls.length > 0 && (
            <div className="space-y-2">
              {filteredControls.map(control => (
                <div key={`${control.source}-${control.title}`} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-gray-900">{control.title}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(control.status)}`}>{control.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-600">{control.evidence}</p>
                  {control.evidence_links && control.evidence_links.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {control.evidence_links.map((link, idx) => (
                        <a
                          key={idx}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-sky-600 hover:text-sky-800 hover:underline"
                        >
                          {link.label}
                        </a>
                      ))}
                    </div>
                  )}
                  <p className="mt-1 text-[11px] text-gray-400">{control.recommendation}</p>
                </div>
              ))}
            </div>
          )}
          {filteredDevices.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {filteredDevices.map(device => (
                <div key={device.device_id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-gray-900">{device.device_id}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(device.risk_level)}`}>Risk {device.risk_score}</span>
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">{[device.hostname, device.customer_name, device.site_name].filter(Boolean).join(' / ') || 'Ingen CMDB-kontekst'}</p>
                  <p className="mt-2 text-[11px] text-gray-600">{device.missing_security_updates} security · {device.blocked_updates} blokeret · {device.approved_updates} godkendt</p>
                </div>
              ))}
            </div>
          )}
          {selectedMetric === 'change_tickets' && <p className="text-sm text-gray-500">Change ticket detaljer ligger i Change Tickets-menuen. Her vises tælleren som governance-signal.</p>}
          {selectedMetric === 'sast_findings' && <p className="text-sm text-gray-500">SAST findings indgår som AI Ops/control backlog. Næste trin er at konvertere validerede fund til change tickets.</p>}
        </div>
      )}

      <div className="bg-sky-50 border border-sky-100 rounded-lg px-4 py-3 mb-5">
        <div className="text-sm font-medium text-sky-900">Compliance paraply</div>
        <p className="text-xs text-sky-700 mt-1 leading-5">
          Almindelige brugere skal kun tage stilling til relevante godkendelser. Evidens, standardmapping og dybe tekniske detaljer samles her for admin, audit og kundeaccept.
        </p>
      </div>

      <div className="flex gap-1 mb-4">
        {[
          ['grc', 'GRC risk'],
          ['regulatory', 'Regler og standarder'],
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
      ) : tab === 'grc' ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Metric label="Fleet risk" value={grc?.summary.fleet_risk_score ?? 0} active={selectedMetric === 'fleet_risk'} onClick={() => setSelectedMetric(selectedMetric === 'fleet_risk' ? null : 'fleet_risk')} />
            <Metric label="Højeste device risk" value={grc?.summary.highest_device_risk ?? 0} active={selectedMetric === 'highest_device_risk'} onClick={() => setSelectedMetric(selectedMetric === 'highest_device_risk' ? null : 'highest_device_risk')} />
            <Metric label="Security mangler" value={grc?.summary.security_updates_missing ?? 0} active={selectedMetric === 'security_missing'} onClick={() => setSelectedMetric(selectedMetric === 'security_missing' ? null : 'security_missing')} />
            <Metric label="Blokeret" value={grc?.summary.blocked_updates ?? 0} active={selectedMetric === 'blocked'} onClick={() => setSelectedMetric(selectedMetric === 'blocked' ? null : 'blocked')} />
            <Metric label="Godkendt" value={grc?.summary.approved_updates ?? 0} active={selectedMetric === 'approved'} onClick={() => setSelectedMetric(selectedMetric === 'approved' ? null : 'approved')} />
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">Standardrapporter</div>
                <p className="text-xs text-gray-500 mt-1">Generér fokuseret evidensrapport pr. standard.</p>
              </div>
              <div className="flex gap-1 flex-wrap justify-end">
                {['SABSA', 'IEC62443', 'ISO27000', 'NIS2', 'CRA'].map(standard => (
                  <button key={standard} onClick={() => loadStandardReport(standard)} disabled={reportLoading === standard}
                    className="px-2 py-1 rounded border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50">
                    {reportLoading === standard ? 'Genererer...' : standard}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="text-sm font-semibold text-gray-900">Kvantitativ risk-model</div>
            <p className="text-xs text-gray-500 mt-1">
              Risk beregnes ikke kun fra CVE/CVSS. Modellen bruger teknisk severity, update-kategori, CMDB business impact, miljø, headend/edge-rolle, kunde/site og deployment-processtatus.
            </p>
            <div className="mt-3 flex flex-wrap gap-1">
              {grc?.risk_model.components.map(component => (
                <span key={component} className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">{component}</span>
              ))}
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {(grc?.devices ?? []).map(device => (
              <div key={device.device_id} className="p-4 border-b border-gray-100 last:border-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-semibold text-gray-900">{device.device_id}</span>
                      <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(device.risk_level)}`}>Risk {device.risk_score}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">{device.environment || 'ukendt miljø'}</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {[device.hostname, device.customer_name, device.site_name].filter(Boolean).join(' / ') || 'Ingen CMDB-kontekst'}
                    </p>
                  </div>
                  <div className="text-right text-[11px] text-gray-500">
                    {device.missing_security_updates} security · {device.missing_functional_updates} øvrige
                    <br />
                    {device.blocked_updates} blokeret · {device.approved_updates} godkendt
                  </div>
                </div>
                {device.top_risks.length > 0 && (
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                    {device.top_risks.map(item => (
                      <div key={item.update_id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-gray-800">{item.component || item.update_type}</span>
                          <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(item.risk.level)}`}>{item.risk.score}</span>
                        </div>
                        <div className="mt-1 text-[11px] font-mono text-gray-500 truncate">
                          {(item.current_version || '-') + ' -> ' + (item.latest_available_version || '-')}
                        </div>
                        <div className="mt-1 text-[11px] text-gray-400 line-clamp-2">{item.risk.factors.join(', ')}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : tab === 'regulatory' ? (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2"><Globe2 className="w-4 h-4 text-gray-500" />Regulatory intelligence</h2>
                <p className="text-xs text-gray-500 mt-1">Versioneret register over gældende, indfaset, kommende og markedsrelevant regulering.</p>
              </div>
              <label className="relative block md:w-80">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-gray-400" />
                <input value={regulatorySearch} onChange={event => setRegulatorySearch(event.target.value)} placeholder="Søg fx AI, energi, NERC eller privacy"
                  className="w-full h-9 pl-8 pr-3 rounded border border-gray-200 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-gray-400" />
              </label>
            </div>
            <div className="mt-3 rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Opdateringspolitik: autoritativ allowlist → hash og diff → administratorreview → aktiv auditbaseline. Eksternt indhold bliver aldrig automatisk til et krav.
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {visibleInstruments.map(item => (
              <div key={item.id} className="p-4 border-b border-gray-100 last:border-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-gray-900">{item.short_name}</span>
                      <span className="text-xs text-gray-500">{item.title}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">{item.jurisdiction}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">{item.kind}</span>
                      <span className={`text-[11px] px-1.5 py-0.5 rounded border ${item.status.includes('pending') || item.status.includes('future') || item.status.includes('agreement') ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-green-50 text-green-700 border-green-200'}`}>{item.status.replaceAll('_', ' ')}</span>
                    </div>
                    <p className="mt-2 text-xs text-gray-600">{item.relevance}</p>
                    <p className="mt-2 text-[11px] text-gray-400">Applicability: {item.applicability.replaceAll('_', ' ')}{item.effective_from ? ` · fra ${item.effective_from}` : ''}{item.next_deadline ? ` · næste deadline ${item.next_deadline}` : ''}</p>
                  </div>
                  <a href={item.source_url} target="_blank" rel="noopener noreferrer" title="Åbn autoritativ kilde" className="p-2 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            ))}
            {visibleInstruments.length === 0 && <div className="py-12 text-center text-sm text-gray-400">Ingen matchende regler eller standarder</div>}
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-900">Fuld audit - katalogberedskab</h2>
            <p className="text-xs text-gray-500 mt-1">En audit kan først kaldes fuld, når alle relevante clauses, requirements og enhancements er versionsbundet og verificeret.</p>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2">
              {auditCatalogs.map(catalog => (
                <div key={catalog.id} className="rounded border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-gray-900">{catalog.title}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded border ${catalog.full_audit_available ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>{catalog.full_audit_available ? 'fuldt katalog' : catalog.catalog_status.replaceAll('_', ' ')}</span>
                  </div>
                  <p className="mt-2 text-[11px] text-gray-600">{catalog.reason}</p>
                  <p className="mt-2 text-[11px] text-gray-400">Licens/kilde: {catalog.license.replaceAll('_', ' ')}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : tab === 'approvals' ? (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          {data?.approvals.length === 0 ? (
            <div className="py-16 text-center">
              <CheckCircle className="w-8 h-8 text-green-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">Ingen opdateringer afventer din godkendelse</p>
            </div>
          ) : data?.approvals.map(item => {
            const canAccept = item.actionable !== false && busy !== item.id
            return (
            <div key={item.id} className="p-5 border-b border-gray-100 last:border-0">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900">{item.update_type}</span>
                    <span className="text-xs font-mono text-gray-500">{item.version || '-'}</span>
                    <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(item.risk.level)}`}>Risk {item.risk.score}</span>
                    {item.artifact && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-green-50 text-green-700 border-green-200">signed artifact</span>}
                    {item.artifact_missing && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">mangler artifact</span>}
                    {item.actionable === false && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">ikke klar</span>}
                    {item.change_ticket && <span className="text-[11px] px-1.5 py-0.5 rounded border bg-sky-50 text-sky-700 border-sky-200">{item.change_ticket.ticket_id}</span>}
                  </div>
                  <p className="text-sm text-gray-600 mt-2">{item.description || 'Ingen beskrivelse'}</p>
                  {item.actionable === false && (
                    <div className="mt-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
                      <p className="text-xs text-amber-800">{item.action_message || 'Opdateringen er ikke klar til godkendelse.'}</p>
                      {item.next_action && <p className="text-[11px] text-amber-700 mt-1">{item.next_action}</p>}
                    </div>
                  )}
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
                <button onClick={() => accept(item.id)} disabled={!canAccept}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm disabled:opacity-50 ${
                    item.actionable === false
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  }`}>
                  <ClipboardCheck className="w-4 h-4" />
                  {item.actionable === false ? 'Afventer artifact' : 'Acceptér'}
                </button>
              </div>
            </div>
            )
          })}
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
                  {control.evidence_links && control.evidence_links.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {control.evidence_links.map((link, idx) => (
                        <a
                          key={idx}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-sky-600 hover:text-sky-800 hover:underline flex items-center gap-1"
                        >
                          📄 {link.label}
                        </a>
                      ))}
                    </div>
                  )}
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
          {standardReport && (
            <div className="mb-6 rounded-lg border border-sky-100 bg-sky-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-sky-950">{standardReport.standard} rapport</h2>
                  <p className="mt-1 text-xs text-sky-700">{standardReport.emphasis}</p>
                  <p className="mt-1 text-[11px] text-sky-600">{standardReport.scope}</p>
                  {standardReport.catalog_complete === false && (
                    <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-800">
                      Delvis mapping: {standardReport.claim_limit || 'Rapporten er ikke en fuld standardaudit.'}
                    </p>
                  )}
                </div>
                <span className="text-[11px] text-sky-600">{fmt(standardReport.generated_at)}</span>
              </div>
              <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-2">
                <Metric label="Controls" value={standardReport.summary.control_count} />
                <Metric label="Gaps" value={standardReport.summary.gap_count} />
                <Metric label="Fleet risk" value={standardReport.summary.fleet_risk_score} />
                <Metric label="High-risk devices" value={standardReport.summary.high_risk_devices} />
                <Metric label="Approval kø" value={standardReport.summary.approval_queue} />
              </div>
              {standardReport.gaps.length > 0 && (
                <div className="mt-4 space-y-2">
                  {standardReport.gaps.map((gap, idx) => (
                    <div key={`${gap.title}-${idx}`} className="rounded-lg border border-sky-100 bg-white p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-gray-900">{gap.title}</span>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(gap.status)}`}>{gap.status}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-600">{gap.evidence}</p>
                      {gap.evidence_links && gap.evidence_links.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {gap.evidence_links.map((link, idx) => (
                            <a
                              key={idx}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] text-sky-600 hover:text-sky-800 hover:underline"
                            >
                              {link.label}
                            </a>
                          ))}
                        </div>
                      )}
                      <p className="mt-1 text-[11px] text-gray-400">{gap.recommendation}</p>
                    </div>
                  ))}
                </div>
              )}
              {standardReport.recommended_next_steps.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-medium text-sky-900">Anbefalede næste skridt</div>
                  <ul className="mt-2 space-y-1">
                    {standardReport.recommended_next_steps.map((step, idx) => (
                      <li key={idx} className="text-xs text-sky-800">- {step}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
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
