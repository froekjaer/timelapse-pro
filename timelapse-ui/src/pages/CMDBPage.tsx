// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — CMDBPage.tsx
// ───────────────────────────────────────────────────────────────────────────
// Version  : 1.0.0
// Dato     : 2026-05-11
// ───────────────────────────────────────────────────────────────────────────
// Changelog:
//   1.0.0  11-maj-2026  Initial CMDB side: inventory + break-glass
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Server, ChevronRight, RefreshCw, AlertTriangle,
  HardDrive, Cpu, Wifi, Package, Key, Eye, Trash2,
  Plus, ArrowLeft, Edit2, Check, X,
  Brain, Loader2
} from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────

interface CMDBEntry {
  device_id: string
  environment: 'lab' | 'staging' | 'production'
  hardware_model: string | null
  soc_model: string | null
  os_name: string | null
  app_version: string | null
  package_manager: string | null
  hostname: string | null
  location_id: string | null
  inventory_reported_at: string | null
  provisioned_at: string | null
  provisioned_by: string | null
  gpg_fingerprint: string | null
  notes: string | null
  status: string
  customer_name: string | null
  site_name: string | null
  ip_address: string | null
  last_seen: string | null
  break_glass_count: number
  update_summary?: UpdateSummary
}

interface CMDBDetail extends CMDBEntry {
  cpu_cores: number | null
  ram_mb: number | null
  mac_address: string | null
  serial_number: string | null
  kernel_version: string | null
  python_version: string | null
  boot_storage_type: string | null
  boot_storage_total_gb: number | null
  boot_storage_used_pct: number | null
  data_partition_path: string | null
  data_partition_total_gb: number | null
  data_partition_used_pct: number | null
  primary_interface: string | null
  wifi_capable: boolean
  wifi_ssid: string | null
  os_packages: Record<string, string>
  venv_packages: Record<string, string>
  software_inventory: Record<string, unknown>
}

interface UpdateSummaryItem {
  id: number
  update_type: string
  status: string
  severity: string | null
  environment: string | null
  component: string | null
  current_version: string | null
  latest_available_version: string | null
  version_gap_label: string | null
  package_count: number | null
}

interface UpdateSummary {
  active_count: number
  security_count: number
  blocked_count: number
  approved_count: number
  latest: UpdateSummaryItem[]
}

interface BreakGlassAccount {
  id: number
  admin_username: string
  ssh_username: string
  has_public_key: boolean
  checkout_count: number
  last_used_at: string | null
  last_used_by: string | null
  rotated_at: string | null
  expires_at: string | null
  created_at: string | null
}

interface SbomDocument {
  bomFormat?: string
  specVersion?: string
  serialNumber?: string
  metadata?: {
    timestamp?: string
    component?: {
      name?: string
      version?: string
      type?: string
    }
  }
  components?: Array<{
    type?: string
    name?: string
    version?: string
    purl?: string
  }>
}

// ── Helpers ───────────────────────────────────────────────────────────────

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include' })
}

function apiPost(path: string, body: unknown) {
  return fetch(`${getApiUrl()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })
}

function apiPut(path: string, body: unknown) {
  return fetch(`${getApiUrl()}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })
}

function apiDelete(path: string) {
  return fetch(`${getApiUrl()}${path}`, { method: 'DELETE', credentials: 'include' })
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('da-DK', { dateStyle: 'short', timeStyle: 'short' })
}

function EnvBadge({ env }: { env: string }) {
  const cls = {
    lab:        'bg-purple-100 text-purple-700 border-purple-200',
    staging:    'bg-amber-100  text-amber-700  border-amber-200',
    production: 'bg-green-100  text-green-700  border-green-200',
  }[env] ?? 'bg-gray-100 text-gray-600 border-gray-200'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${cls}`}>
      {env}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
      status === 'online' ? 'bg-green-500' : 'bg-gray-300'
    }`} />
  )
}

function StorageBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-gray-400 text-xs">—</span>
  const color = pct > 85 ? 'bg-red-500' : pct > 65 ? 'bg-amber-400' : 'bg-sky-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-10 text-right">{pct.toFixed(0)}%</span>
    </div>
  )
}

function statusBadgeClass(status: string) {
  const map: Record<string, string> = {
    pending: 'bg-amber-50 text-amber-700 border-amber-200',
    approved: 'bg-sky-50 text-sky-700 border-sky-200',
    blocked: 'bg-amber-50 text-amber-700 border-amber-200',
    deployed: 'bg-green-50 text-green-700 border-green-200',
    rolled_back: 'bg-purple-50 text-purple-700 border-purple-200',
  }
  return map[status] ?? 'bg-gray-50 text-gray-500 border-gray-200'
}

function compactValue(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return `${value.length} elementer`
  if (typeof value === 'object') return `${Object.keys(value as Record<string, unknown>).length} elementer`
  return String(value)
}

type VersionRisk = 'security' | 'feature' | 'current'

interface VersionRow {
  key: string
  name: string
  installed: string
  available: string
  source: string
  risk: VersionRisk
}

function normalizedPackageName(value: unknown): string {
  return String(value ?? '').trim().toLowerCase().replace(/:(arm64|amd64|all)$/, '')
}

function versionRows(detail: CMDBDetail, sbom: SbomDocument | null): VersionRow[] {
  const rows = new Map<string, VersionRow>()
  const addInstalled = (name: string, version: unknown, source: string) => {
    const key = normalizedPackageName(name)
    if (!key || key.startsWith('_')) return
    const current = rows.get(key)
    rows.set(key, {
      key,
      name: current?.name || name,
      installed: String(version ?? current?.installed ?? '—'),
      available: current?.available || String(version ?? '—'),
      source: current?.source || source,
      risk: current?.risk || 'current',
    })
  }
  Object.entries(detail.os_packages ?? {}).forEach(([name, version]) => addInstalled(name, version, 'OS'))
  Object.entries(detail.venv_packages ?? {}).forEach(([name, version]) => addInstalled(name, version, 'Python'))
  Object.entries(detail.software_inventory ?? {}).forEach(([name, version]) => {
    if (!['available_software_updates', '_os_updates_available'].includes(name) && ['string', 'number'].includes(typeof version)) {
      addInstalled(name, version, 'Applikation')
    }
  })
  ;(sbom?.components ?? []).forEach(component => {
    if (component.name) addInstalled(component.name, component.version, component.type || 'SBOM')
  })

  const updates = Array.isArray(detail.software_inventory?.available_software_updates)
    ? detail.software_inventory.available_software_updates as Array<Record<string, unknown>>
    : []
  updates.forEach(update => {
    const name = String(update.name ?? 'ukendt')
    const key = normalizedPackageName(name)
    const current = rows.get(key)
    const kind = String(update.kind ?? update.update_type ?? '').toLowerCase()
    const risk: VersionRisk = kind.includes('security') ? 'security' : 'feature'
    rows.set(key, {
      key,
      name: current?.name || name,
      installed: String(update.installed_version ?? current?.installed ?? '—'),
      available: String(update.available_version ?? current?.available ?? '—'),
      source: String(update.manager ?? current?.source ?? 'Update'),
      risk,
    })
  })

  ;(detail.update_summary?.latest ?? []).forEach(update => {
    if (!update.component) return
    const key = normalizedPackageName(update.component)
    if (rows.has(key) && rows.get(key)?.risk !== 'current') return
    const risk: VersionRisk = update.update_type.includes('security') ? 'security' : 'feature'
    const current = rows.get(key)
    rows.set(key, {
      key,
      name: current?.name || update.component,
      installed: update.current_version || current?.installed || '—',
      available: update.latest_available_version || current?.available || '—',
      source: update.update_type,
      risk,
    })
  })

  const priority: Record<VersionRisk, number> = { security: 0, feature: 1, current: 2 }
  return [...rows.values()].sort((a, b) => priority[a.risk] - priority[b.risk] || a.name.localeCompare(b.name))
}

function VersionInventory({ detail, sbom }: { detail: CMDBDetail; sbom: SbomDocument | null }) {
  const rows = versionRows(detail, sbom)
  const security = rows.filter(row => row.risk === 'security').length
  const feature = rows.filter(row => row.risk === 'feature').length
  return (
    <div className="mt-4 rounded-lg border border-gray-200 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
        <span className="text-xs font-semibold text-gray-700">Komponentversioner</span>
        {security > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-semibold">{security} sikkerhed</span>}
        {feature > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-semibold">{feature} feature</span>}
        {security === 0 && feature === 0 && <span className="text-[10px] text-emerald-700">Ingen kendte versionsgab</span>}
        <span className="ml-auto text-[10px] text-gray-400">{rows.length} komponenter</span>
      </div>
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-white text-[10px] uppercase text-gray-400 border-b border-gray-100">
            <tr>
              <th className="text-left px-3 py-1.5">Komponent</th>
              <th className="text-left px-3 py-1.5">Installeret</th>
              <th className="text-left px-3 py-1.5">Tilgængelig</th>
              <th className="text-right px-3 py-1.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const rowClass = row.risk === 'security' ? 'bg-red-50' : row.risk === 'feature' ? 'bg-orange-50' : ''
              const badgeClass = row.risk === 'security'
                ? 'bg-red-100 text-red-700'
                : row.risk === 'feature' ? 'bg-orange-100 text-orange-700' : 'bg-emerald-50 text-emerald-700'
              return (
                <tr key={row.key} className={`border-b border-gray-100 last:border-0 ${rowClass}`}>
                  <td className="px-3 py-1.5 min-w-40">
                    <div className="font-medium text-gray-800">{row.name}</div>
                    <div className="text-[10px] text-gray-400">{row.source}</div>
                  </td>
                  <td className="px-3 py-1.5 font-mono text-gray-600 break-all">{row.installed}</td>
                  <td className={`px-3 py-1.5 font-mono font-medium break-all ${row.risk === 'security' ? 'text-red-700' : row.risk === 'feature' ? 'text-orange-700' : 'text-gray-500'}`}>{row.available}</td>
                  <td className="px-3 py-1.5 text-right">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${badgeClass}`}>
                      {row.risk === 'security' ? 'Sikkerhed' : row.risk === 'feature' ? 'Feature' : 'Aktuel'}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── CMDB List (oversigt) ──────────────────────────────────────────────────

export function CMDBPage() {
  const [entries, setEntries] = useState<CMDBEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [aiQuestion, setAiQuestion] = useState('Hvilke enheder har størst drifts- eller compliance-risiko lige nu?')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiAnswer, setAiAnswer] = useState<any | null>(null)
  const navigate = useNavigate()

  async function load() {
    setLoading(true)
    try {
      const r = await api('/api/cmdb/')
      setEntries(await r.json())
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function askAi() {
    if (!aiQuestion.trim()) return
    setAiLoading(true)
    try {
      const r = await apiPost('/api/ai/ops/query', { area: 'cmdb', question: aiQuestion })
      const data = await r.json()
      setAiAnswer(data.analysis)
    } catch {
      setAiAnswer({ answer: 'AI-analyse fejlede. Tjek Ollama/headend-log og prøv igen.', risk_level: 'unknown', recommendations: [] })
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Server className="w-6 h-6 text-sky-600" />
            CMDB — Enhedsinventar
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Hardwareinventar og nødadgang for alle edge-enheder
          </p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Opdater
        </button>
      </div>

      {/* Stats bar */}
      {!loading && entries.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {(['lab', 'staging', 'production'] as const).map(env => {
            const count = entries.filter(e => e.environment === env).length
            return (
              <div key={env} className="bg-white rounded-xl border border-gray-200 px-4 py-3 flex items-center gap-3">
                <EnvBadge env={env} />
                <span className="text-2xl font-bold text-gray-900">{count}</span>
                <span className="text-sm text-gray-500">enhed{count !== 1 ? 'er' : ''}</span>
              </div>
            )
          })}
        </div>
      )}

      <div className="bg-white rounded-xl border border-sky-100 p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-sky-600" />
          <h2 className="text-sm font-semibold text-gray-800">AI CMDB-analyse</h2>
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
          <div className="mt-3 text-sm text-gray-700 space-y-2">
            <p>{aiAnswer.answer}</p>
            {(aiAnswer.recommendations ?? []).length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
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

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-gray-400 text-sm">Indlæser…</div>
        ) : entries.length === 0 ? (
          <div className="py-16 text-center">
            <Server className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">Ingen CMDB-poster endnu.</p>
            <p className="text-gray-400 text-xs mt-1">
              Edge-enheder rapporterer automatisk inventar ved startup.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">Enhed</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Hardware</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Miljø</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">OS / App</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Opdateringer</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Sidst set</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Break-glass</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr
                  key={e.device_id}
                  className="border-b border-gray-50 hover:bg-sky-50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/cmdb/${pathSegment(e.device_id)}`)}
                >
                  <td className="px-4 py-3">
                    <div className="font-mono font-medium text-gray-900 flex items-center">
                      <StatusDot status={e.status} />
                      {e.device_id}
                    </div>
                    {(e.customer_name || e.site_name) && (
                      <div className="text-xs text-gray-400 mt-0.5">
                        {[e.customer_name, e.site_name].filter(Boolean).join(' › ')}
                      </div>
                    )}
                    {e.hostname && (
                      <div className="text-xs text-gray-400">{e.hostname}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-gray-900">{e.hardware_model ?? '—'}</div>
                    <div className="text-xs text-gray-400">{e.soc_model ?? ''}</div>
                  </td>
                  <td className="px-4 py-3">
                    <EnvBadge env={e.environment} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-gray-700 text-xs">{e.os_name ?? '—'}</div>
                    <div className="text-gray-400 text-xs font-mono">{e.app_version ?? ''}</div>
                  </td>
                  <td className="px-4 py-3">
                    {(e.update_summary?.active_count ?? 0) > 0 ? (
                      <div className="space-y-1">
                        <div className="flex gap-1 flex-wrap">
                          {(e.update_summary?.security_count ?? 0) > 0 ? (
                            <span className="text-[11px] px-1.5 py-0.5 rounded border bg-red-50 text-red-700 border-red-200 font-semibold flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
                              {e.update_summary?.security_count} security
                            </span>
                          ) : null}
                          {(e.update_summary?.blocked_count ?? 0) > 0 && (
                            <span className="text-[11px] px-1.5 py-0.5 rounded border bg-orange-50 text-orange-700 border-orange-200">
                              {e.update_summary?.blocked_count} blocked
                            </span>
                          )}
                          {((e.update_summary?.active_count ?? 0) - (e.update_summary?.security_count ?? 0) - (e.update_summary?.blocked_count ?? 0)) > 0 && (
                            <span className="text-[11px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
                              {(e.update_summary?.active_count ?? 0) - (e.update_summary?.security_count ?? 0) - (e.update_summary?.blocked_count ?? 0)} øvrige
                            </span>
                          )}
                        </div>
                        {e.update_summary?.latest?.[0] && (
                          <div className="text-[11px] text-gray-400 truncate max-w-48">
                            {e.update_summary.latest[0].component || e.update_summary.latest[0].update_type}
                            {e.update_summary.latest[0].version_gap_label && `: ${e.update_summary.latest[0].version_gap_label}`}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                        Up to date
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {fmtDate(e.last_seen)}
                    {e.inventory_reported_at && (
                      <div className="text-gray-400">
                        Inv: {fmtDate(e.inventory_reported_at)}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                      e.break_glass_count > 0
                        ? 'bg-orange-100 text-orange-700'
                        : 'bg-gray-100 text-gray-500'
                    }`}>
                      <Key className="w-3 h-3" />
                      {e.break_glass_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    <ChevronRight className="w-4 h-4" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── CMDB Detail ───────────────────────────────────────────────────────────

export function CMDBDetailPage() {
  const { deviceId } = useParams<{ deviceId: string }>()
  const [detail, setDetail] = useState<CMDBDetail | null>(null)
  const [accounts, setAccounts] = useState<BreakGlassAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [editField, setEditField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [sbom, setSbom] = useState<SbomDocument | null>(null)
  const [sbomLoading, setSbomLoading] = useState(false)

  // Break-glass state
  const [bgModal, setBgModal] = useState(false)
  const [bgAdminUser, setBgAdminUser] = useState('')
  const [bgExpiresDays, setBgExpiresDays] = useState(0)
  const [bgCreating, setBgCreating] = useState(false)
  const [bgError, setBgError] = useState('')
  const [checkoutModal, setCheckoutModal] = useState<number | null>(null)
  const [checkoutReason, setCheckoutReason] = useState('')
  const [checkoutResult, setCheckoutResult] = useState<null | { password: string; ssh_username: string }>(null)
  const [checkingOut, setCheckingOut] = useState(false)

  async function load() {
    if (!deviceId) return
    setLoading(true)
    try {
      const [detailR, bgR] = await Promise.all([
        api(`/api/cmdb/${pathSegment(deviceId)}`),
        api(`/api/cmdb/${pathSegment(deviceId)}/break-glass`),
      ])
      setDetail(await detailR.json())
      setAccounts(await bgR.json())
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [deviceId])

  async function saveField(field: string, value: string) {
    if (!deviceId) return
    setSaving(true)
    await apiPut(`/api/cmdb/${pathSegment(deviceId)}`, { [field]: value })
    setSaving(false)
    setEditField(null)
    load()
  }

  async function createBreakGlass() {
    if (!deviceId || !bgAdminUser) return
    setBgCreating(true)
    setBgError('')
    try {
      const r = await apiPost(`/api/cmdb/${pathSegment(deviceId)}/break-glass`, {
        admin_username: bgAdminUser,
        expires_days: bgExpiresDays,
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setBgError(err.detail ?? `Fejl ${r.status}`)
        setBgCreating(false)
        return
      }
    } catch {
      setBgError('Netværksfejl — kunne ikke oprette konto')
      setBgCreating(false)
      return
    }
    setBgCreating(false)
    setBgModal(false)
    setBgAdminUser('')
    setBgError('')
    load()
  }

  async function doCheckout(accountId: number) {
    if (!deviceId) return
    setCheckingOut(true)
    const r = await apiPost(`/api/cmdb/${pathSegment(deviceId)}/break-glass/checkout`, {
      admin_username: accounts.find(a => a.id === accountId)?.admin_username,
      reason: checkoutReason || 'Ikke angivet',
    })
    const data = await r.json()
    setCheckoutResult({ password: data.password, ssh_username: data.ssh_username })
    setCheckingOut(false)
    load()
  }

  async function deleteAccount(accountId: number) {
    if (!deviceId || !confirm('Slet break-glass konto?')) return
    await apiDelete(`/api/cmdb/${pathSegment(deviceId)}/break-glass/${accountId}`)
    load()
  }

  async function loadSbom() {
    if (!deviceId) return
    setSbomLoading(true)
    try {
      const r = await api(`/api/cmdb/${pathSegment(deviceId)}/sbom`)
      setSbom(await r.json())
    } finally {
      setSbomLoading(false)
    }
  }

  function downloadSbom() {
    if (!sbom || !deviceId) return
    const blob = new Blob([JSON.stringify(sbom, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${deviceId}-sbom.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return (
    <div className="max-w-4xl mx-auto px-4 py-16 text-center text-gray-400">Indlæser…</div>
  )

  if (!detail) return (
    <div className="max-w-4xl mx-auto px-4 py-16 text-center text-gray-500">
      Ingen CMDB-post fundet for {deviceId}
    </div>
  )

  function EditableField({ label, field, value }: { label: string; field: string; value: string | null }) {
    const isEditing = editField === field
    return (
      <div className="flex items-start gap-2 py-1.5">
        <span className="text-xs text-gray-400 w-36 flex-shrink-0 mt-0.5">{label}</span>
        {isEditing ? (
          <div className="flex items-center gap-1 flex-1">
            <input
              className="flex-1 text-sm border border-sky-300 rounded px-2 py-0.5 outline-none"
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              autoFocus
            />
            <button onClick={() => saveField(field, editValue)} disabled={saving}
              className="text-green-600 hover:text-green-700">
              <Check className="w-4 h-4" />
            </button>
            <button onClick={() => setEditField(null)} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 flex-1 group">
            <span className={`text-sm ${value ? 'text-gray-900' : 'text-gray-400'}`}>
              {value ?? '—'}
            </span>
            <button
              onClick={() => { setEditField(field); setEditValue(value ?? '') }}
              className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-sky-500 transition-opacity"
            >
              <Edit2 className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    )
  }

  const envOptions: Array<'lab' | 'staging' | 'production'> = ['lab', 'staging', 'production']

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/cmdb" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-gray-900 font-mono">{detail.device_id}</h1>
          <p className="text-sm text-gray-500">
            {[detail.customer_name, detail.site_name].filter(Boolean).join(' › ') || 'Ikke tildelt'}
          </p>
        </div>
        <div className="ml-4">
          <EnvBadge env={detail.environment} />
        </div>
        <div className="ml-2">
          <StatusDot status={detail.status} />
          <span className="text-sm text-gray-500">{detail.status}</span>
        </div>
        <button onClick={load} className="ml-auto text-gray-400 hover:text-gray-600">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Hardware */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-sky-500" /> Hardware
          </h2>
          <div className="space-y-0.5">
            <Row label="Model" value={detail.hardware_model} />
            <Row label="SoC" value={detail.soc_model} />
            <Row label="CPU-kerner" value={detail.cpu_cores?.toString()} />
            <Row label="RAM" value={detail.ram_mb ? `${detail.ram_mb} MB` : null} />
            <Row label="MAC-adresse" value={detail.mac_address} mono />
            <Row label="Serienummer" value={detail.serial_number} mono />
            <Row label="Hostname" value={detail.hostname} />
            <Row label="IP-adresse" value={detail.ip_address} mono />
          </div>
        </div>

        {/* OS / Software */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Package className="w-4 h-4 text-sky-500" /> OS / Software
            </h2>
            <button onClick={loadSbom} disabled={sbomLoading}
              className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50">
              {sbomLoading ? 'Henter…' : 'Vis SBOM'}
            </button>
          </div>
          <div className="space-y-0.5">
            <Row label="OS" value={detail.os_name} />
            <Row label="Kernel" value={detail.kernel_version} mono />
            <Row label="Python" value={detail.python_version} />
            <Row label="App-version" value={detail.app_version} mono />
            <Row label="Package manager" value={detail.package_manager} />
            <Row label="Sidst set" value={fmtDate(detail.last_seen)} />
            <Row label="Inv. rapporteret" value={fmtDate(detail.inventory_reported_at)} />
          </div>
          <VersionInventory detail={detail} sbom={sbom} />
          <details className="mt-3">
            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">Teknisk rådata og SBOM-evidens</summary>
            <div className="mt-2 border-l-2 border-gray-100 pl-3">
          {Object.keys(detail.software_inventory ?? {}).length > 0 && (() => {
            // Skjul nøgler der allerede vises i dedikerede sektioner
            const skipKeys = new Set(['available_software_updates', '_os_updates_available'])
            const invEntries = Object.entries(detail.software_inventory)
              .filter(([k]) => !skipKeys.has(k))
              .sort(([a], [b]) => a.localeCompare(b))
            if (invEntries.length === 0) return null
            return (
              <details className="mt-3">
                <summary className="text-xs text-sky-600 cursor-pointer hover:text-sky-700">
                  Softwareinventar ({invEntries.length} nøgler)
                </summary>
                <div className="mt-2 max-h-56 overflow-y-auto rounded border border-gray-100">
                  {invEntries.map(([name, value]) => (
                    <div key={name} className="flex justify-between gap-3 text-xs py-1 px-2 border-b border-gray-50 last:border-0">
                      <span className="text-gray-600 font-medium shrink-0">{name}</span>
                      <span className="text-gray-400 font-mono text-right break-all">{compactValue(value)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )
          })()}
          {Array.isArray(detail.software_inventory?.available_software_updates) && (() => {
            const updates = detail.software_inventory.available_software_updates as Array<Record<string, unknown>>
            const securityUpdates = updates.filter(u => String(u.kind ?? '') === 'security')
            const otherUpdates = updates.filter(u => String(u.kind ?? '') !== 'security')
            return (
              <details className="mt-3" open>
                <summary className="text-xs cursor-pointer hover:opacity-80 flex items-center gap-2">
                  {securityUpdates.length > 0 && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-semibold">
                      ⚠ {securityUpdates.length} sikkerhed
                    </span>
                  )}
                  {otherUpdates.length > 0 && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                      ↑ {otherUpdates.length} øvrige
                    </span>
                  )}
                  <span className="text-gray-400">tilgængelige opdateringer</span>
                </summary>
                <div className="mt-2 max-h-56 overflow-y-auto rounded border border-gray-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-gray-400 uppercase tracking-wide text-[10px]">
                        <th className="text-left px-2 py-1">Pakke</th>
                        <th className="text-right px-2 py-1">Installeret</th>
                        <th className="text-center px-1 py-1"></th>
                        <th className="text-left px-2 py-1">Tilgængelig</th>
                        <th className="text-right px-2 py-1">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {updates.map((item, idx) => {
                        const isSecurity = String(item.kind ?? '') === 'security'
                        return (
                          <tr key={`${String(item.name)}-${idx}`} className={`border-t border-gray-50 ${isSecurity ? 'bg-red-50/40' : ''}`}>
                            <td className="px-2 py-1 font-medium text-gray-700">{String(item.name ?? 'ukendt')}</td>
                            <td className="px-2 py-1 font-mono text-gray-400 text-right">{String(item.installed_version ?? '?')}</td>
                            <td className="px-1 py-1 text-gray-300 text-center">→</td>
                            <td className="px-2 py-1 font-mono font-semibold text-green-700">{String(item.available_version ?? '?')}</td>
                            <td className="px-2 py-1 text-right">
                              {isSecurity
                                ? <span className="px-1 py-0.5 rounded bg-red-100 text-red-600 text-[10px]">security</span>
                                : <span className="px-1 py-0.5 rounded bg-gray-100 text-gray-400 text-[10px]">{String(item.kind ?? item.manager ?? '')}</span>
                              }
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            )
          })()}
          {(detail.update_summary?.latest?.length ?? 0) > 0 && (
            <details className="mt-3" open>
              <summary className="text-xs text-amber-600 cursor-pointer hover:text-amber-700">
                Installeret vs. senest tilgængelig
              </summary>
              <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-gray-100">
                {detail.update_summary?.latest.map(item => (
                  <div key={item.id} className="grid grid-cols-12 gap-2 text-xs px-3 py-2 border-b border-gray-50 last:border-0">
                    <div className="col-span-3 min-w-0">
                      <div className="font-medium text-gray-800 truncate">{item.component || item.update_type}</div>
                      <div className="text-[11px] text-gray-400">#{item.id} · {item.environment || '-'}</div>
                    </div>
                    <div className="col-span-3 font-mono text-gray-500 truncate">{item.current_version || '—'}</div>
                    <div className="col-span-4 font-mono text-gray-800 truncate">{item.latest_available_version || '—'}</div>
                    <div className="col-span-2 text-right">
                      <span className={`px-1.5 py-0.5 rounded border text-[11px] ${statusBadgeClass(item.status)}`}>{item.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
          {sbom && (() => {
            // Byg opslag: pakkenavn → tilgængelig version (alle managere)
            const availUpdates = Array.isArray(detail.software_inventory?.available_software_updates)
              ? (detail.software_inventory.available_software_updates as Array<Record<string, unknown>>)
              : []
            const allUpdateMap: Record<string, { avail: string; kind: string }> = {}
            availUpdates.forEach(u => {
              allUpdateMap[String(u.name ?? '').toLowerCase()] = {
                avail: String(u.available_version ?? ''),
                kind: String(u.kind ?? ''),
              }
            })
            const components = sbom.components || []
            const updatableInSbom = components.filter(c => allUpdateMap[(c.name ?? '').toLowerCase()]).length
            return (
              <details className="mt-3" open>
                <summary className="text-xs cursor-pointer hover:opacity-80 flex items-center gap-2">
                  <span className="text-sky-600">SBOM · {components.length} komponenter</span>
                  {updatableInSbom > 0 && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-semibold">
                      {updatableInSbom} har nyere version
                    </span>
                  )}
                  <span className="ml-auto text-gray-400 text-[10px]">{sbom.serialNumber?.slice(0, 20) || `${sbom.bomFormat || 'SBOM'} ${sbom.specVersion || ''}`}</span>
                </summary>
                <div className="mt-2 rounded-lg border border-gray-100 overflow-hidden">
                  <div className="flex items-center justify-end gap-3 px-3 py-1.5 bg-gray-50 text-[10px] text-gray-400 border-b border-gray-100">
                    <button onClick={downloadSbom} className="text-sky-600 hover:text-sky-700">Download JSON</button>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-50 text-gray-400 uppercase tracking-wide text-[10px]">
                          <th className="text-left px-2 py-1">Komponent</th>
                          <th className="text-right px-2 py-1">Version</th>
                          <th className="text-left px-2 py-1">Tilgængelig</th>
                          <th className="text-right px-2 py-1">Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {components.slice(0, 200).map((component, idx) => {
                          const upd = allUpdateMap[(component.name ?? '').toLowerCase()]
                          const isSecurity = upd?.kind === 'security'
                          return (
                            <tr key={`${component.name}-${idx}`} className={`border-t border-gray-50 ${isSecurity ? 'bg-red-50/30' : upd ? 'bg-amber-50/30' : ''}`}>
                              <td className={`px-2 py-0.5 truncate max-w-[120px] ${upd ? 'font-medium text-gray-800' : 'text-gray-600'}`}>{component.name || 'ukendt'}</td>
                              <td className={`px-2 py-0.5 font-mono text-right ${upd ? 'text-amber-700' : 'text-gray-400'}`}>{component.version || '—'}</td>
                              <td className="px-2 py-0.5 font-mono">
                                {upd
                                  ? <span className={`font-semibold ${isSecurity ? 'text-red-600' : 'text-green-600'}`}>
                                      {upd.avail}
                                      {isSecurity && <span className="ml-1 text-[10px] bg-red-100 text-red-600 px-1 rounded">sec</span>}
                                    </span>
                                  : <span className="text-gray-300 text-[10px]">✓</span>
                                }
                              </td>
                              <td className="px-2 py-0.5 text-right text-gray-400 text-[10px]">{component.type || 'lib'}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  {components.length > 200 && (
                    <div className="px-3 py-2 text-[11px] text-gray-400 border-t border-gray-50">
                      Viser de første 200 komponenter. Download JSON for fuld SBOM.
                    </div>
                  )}
                </div>
              </details>
            )
          })()}
          {Object.keys(detail.venv_packages ?? {}).length > 0 && (() => {
            // Pip-opdateringer fra inventory
            const availUpdates = Array.isArray(detail.software_inventory?.available_software_updates)
              ? (detail.software_inventory.available_software_updates as Array<Record<string, unknown>>)
              : []
            const pipUpdateMap: Record<string, { avail: string; kind: string }> = {}
            availUpdates
              .filter(u => String(u.manager ?? '').toLowerCase() === 'pip' || String(u.manager ?? '').toLowerCase() === 'python')
              .forEach(u => {
                pipUpdateMap[String(u.name ?? '').toLowerCase()] = {
                  avail: String(u.available_version ?? ''),
                  kind: String(u.kind ?? ''),
                }
              })
            const venvEntries = Object.entries(detail.venv_packages).sort()
            const updatableCount = venvEntries.filter(([name]) => pipUpdateMap[name.toLowerCase()]).length
            return (
              <details className="mt-3">
                <summary className="text-xs cursor-pointer hover:opacity-80 flex items-center gap-2">
                  <span className="text-sky-600">{venvEntries.length} venv-pakker</span>
                  {updatableCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-semibold">
                      {updatableCount} kan opdateres
                    </span>
                  )}
                </summary>
                <div className="mt-2 max-h-56 overflow-y-auto rounded border border-gray-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-gray-400 uppercase tracking-wide text-[10px]">
                        <th className="text-left px-2 py-1">Pakke</th>
                        <th className="text-right px-2 py-1">Installeret</th>
                        <th className="text-left px-2 py-1">Tilgængelig</th>
                      </tr>
                    </thead>
                    <tbody>
                      {venvEntries.map(([name, ver]) => {
                        const upd = pipUpdateMap[name.toLowerCase()]
                        return (
                          <tr key={name} className={`border-t border-gray-50 ${upd ? 'bg-amber-50/30' : ''}`}>
                            <td className={`px-2 py-0.5 ${upd ? 'font-medium text-gray-800' : 'text-gray-600'}`}>{name}</td>
                            <td className={`px-2 py-0.5 font-mono text-right ${upd ? 'text-amber-700' : 'text-gray-400'}`}>{ver}</td>
                            <td className="px-2 py-0.5 font-mono">
                              {upd
                                ? <span className="font-semibold text-green-600">{upd.avail}</span>
                                : <span className="text-gray-300 text-[10px]">✓</span>
                              }
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            )
          })()}
          {Object.keys(detail.os_packages ?? {}).length > 0 && (() => {
            // Byg opslag: pakkenavn → tilgængelig version (fra apt-inventory)
            const availUpdates = Array.isArray(detail.software_inventory?.available_software_updates)
              ? (detail.software_inventory.available_software_updates as Array<Record<string, unknown>>)
              : []
            const updateMap: Record<string, { avail: string; kind: string }> = {}
            availUpdates.forEach(u => {
              updateMap[String(u.name ?? '')] = {
                avail: String(u.available_version ?? ''),
                kind: String(u.kind ?? ''),
              }
            })
            const pkgEntries = Object.entries(detail.os_packages).sort()
            const updatableCount = pkgEntries.filter(([name]) => updateMap[name]).length
            return (
              <details className="mt-3">
                <summary className="text-xs cursor-pointer hover:opacity-80 flex items-center gap-2">
                  <span className="text-sky-600">{pkgEntries.length} OS-/systempakker</span>
                  {updatableCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-semibold">
                      {updatableCount} kan opdateres
                    </span>
                  )}
                </summary>
                <div className="mt-2 max-h-64 overflow-y-auto rounded border border-gray-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 text-gray-400 uppercase tracking-wide text-[10px]">
                        <th className="text-left px-2 py-1">Pakke</th>
                        <th className="text-right px-2 py-1">Installeret</th>
                        <th className="text-left px-2 py-1">Tilgængelig</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pkgEntries.map(([name, ver]) => {
                        const upd = updateMap[name]
                        const isSecurity = upd?.kind === 'security'
                        return (
                          <tr key={name} className={`border-t border-gray-50 ${isSecurity ? 'bg-red-50/30' : upd ? 'bg-amber-50/30' : ''}`}>
                            <td className={`px-2 py-0.5 ${upd ? 'font-medium text-gray-800' : 'text-gray-600'}`}>{name}</td>
                            <td className={`px-2 py-0.5 font-mono text-right ${upd ? 'text-amber-700' : 'text-gray-400'}`}>{ver}</td>
                            <td className="px-2 py-0.5 font-mono">
                              {upd
                                ? <span className={`font-semibold ${isSecurity ? 'text-red-600' : 'text-green-600'}`}>
                                    {upd.avail}
                                    {isSecurity && <span className="ml-1 text-[10px] bg-red-100 text-red-600 px-1 rounded">security</span>}
                                  </span>
                                : <span className="text-gray-300">✓ up to date</span>
                              }
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            )
          })()}
            </div>
          </details>
        </div>

        {/* Storage */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-sky-500" /> Storage
          </h2>
          <div className="space-y-2">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500">
                  Boot ({detail.boot_storage_type ?? '?'}) — {detail.boot_storage_total_gb?.toFixed(0)} GB
                </span>
              </div>
              <StorageBar pct={detail.boot_storage_used_pct} />
            </div>
            {detail.data_partition_path && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500">
                    Data ({detail.data_partition_path}) — {detail.data_partition_total_gb?.toFixed(0)} GB
                  </span>
                </div>
                <StorageBar pct={detail.data_partition_used_pct} />
              </div>
            )}
          </div>

          {/* Network */}
          <h2 className="text-sm font-semibold text-gray-700 mt-4 mb-2 flex items-center gap-2">
            <Wifi className="w-4 h-4 text-sky-500" /> Netværk
          </h2>
          <Row label="Primær iface" value={detail.primary_interface} />
          <Row label="WiFi" value={detail.wifi_capable ? (detail.wifi_ssid ?? 'Tilgængelig') : 'Nej'} />
        </div>

        {/* Admin / CMDB */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Server className="w-4 h-4 text-sky-500" /> CMDB-admin
          </h2>

          {/* Environment picker */}
          <div className="flex items-start gap-2 py-1.5">
            <span className="text-xs text-gray-400 w-36 flex-shrink-0 mt-0.5">Miljø</span>
            <div className="flex gap-1.5">
              {envOptions.map(env => (
                <button
                  key={env}
                  onClick={() => saveField('environment', env)}
                  className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                    detail.environment === env
                      ? 'bg-sky-600 text-white border-sky-600'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'
                  }`}
                >
                  {env}
                </button>
              ))}
            </div>
          </div>

          <EditableField label="Location ID" field="location_id" value={detail.location_id} />
          <EditableField label="GPG fingerprint" field="gpg_fingerprint" value={detail.gpg_fingerprint} />
          <EditableField label="Provisioneret af" field="provisioned_by" value={detail.provisioned_by} />
          <Row label="Provisioneret" value={fmtDate(detail.provisioned_at)} />

          {/* Notes */}
          <div className="mt-3">
            <span className="text-xs text-gray-400 block mb-1">Noter</span>
            {editField === 'notes' ? (
              <div>
                <textarea
                  className="w-full text-sm border border-sky-300 rounded px-2 py-1 outline-none resize-none"
                  rows={3}
                  value={editValue}
                  onChange={e => setEditValue(e.target.value)}
                  autoFocus
                />
                <div className="flex gap-2 mt-1">
                  <button onClick={() => saveField('notes', editValue)} disabled={saving}
                    className="text-xs text-green-600 hover:text-green-700">Gem</button>
                  <button onClick={() => setEditField(null)}
                    className="text-xs text-gray-400 hover:text-gray-600">Annuller</button>
                </div>
              </div>
            ) : (
              <div
                onClick={() => { setEditField('notes'); setEditValue(detail.notes ?? '') }}
                className="text-sm text-gray-600 cursor-pointer hover:bg-gray-50 rounded p-1.5 border border-dashed border-gray-200 min-h-10"
              >
                {detail.notes || <span className="text-gray-300 italic">Klik for at tilføje noter…</span>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Break-the-glass */}
      <div className="mt-6 bg-white rounded-xl border border-orange-200 overflow-hidden">
        <div className="px-5 py-4 bg-orange-50 border-b border-orange-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-orange-800 flex items-center gap-2">
              <Key className="w-4 h-4" />
              Break-the-glass nødadgang
            </h2>
            <p className="text-xs text-orange-600 mt-0.5">
              Passwords krypteres med Fernet AES-128 og roteres automatisk ved checkout.
            </p>
          </div>
          <button
            onClick={() => { setBgModal(true); setBgError('') }}
            className="flex items-center gap-1.5 text-xs bg-orange-600 text-white px-3 py-1.5 rounded-lg hover:bg-orange-700 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Opret konto
          </button>
        </div>

        {accounts.length === 0 ? (
          <div className="px-5 py-8 text-center text-gray-400 text-sm">
            Ingen break-glass konti oprettet endnu.
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {accounts.map(acc => (
              <div key={acc.id} className="px-5 py-3 flex items-center gap-4">
                <div className="flex-1">
                  <div className="font-medium text-sm text-gray-900">{acc.admin_username}</div>
                  <div className="text-xs text-gray-400">
                    SSH: <code className="font-mono">{acc.ssh_username}@{detail.ip_address ?? '<ip>'}</code>
                    {acc.has_public_key && (
                      <span className="ml-2 text-green-600">✓ Public key</span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-gray-400 text-right">
                  <div>Checkouts: {acc.checkout_count}</div>
                  {acc.last_used_at && <div>Sidst: {fmtDate(acc.last_used_at)}</div>}
                  {acc.expires_at && (
                    <div className={new Date(acc.expires_at) < new Date() ? 'text-red-500' : ''}>
                      Udløber: {fmtDate(acc.expires_at)}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { setCheckoutModal(acc.id); setCheckoutReason(''); setCheckoutResult(null) }}
                    className="flex items-center gap-1 text-xs bg-orange-100 text-orange-700 px-2.5 py-1 rounded hover:bg-orange-200 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Checkout
                  </button>
                  <button
                    onClick={() => deleteAccount(acc.id)}
                    className="text-gray-300 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create break-glass modal */}
      {bgModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-200 p-6 w-96 shadow-xl">
            <h3 className="font-semibold text-gray-900 mb-4">Opret break-glass konto</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Admin-brugernavn</label>
                <input
                  className="w-full border border-gray-200 rounded px-3 py-2 text-sm outline-none focus:border-sky-400"
                  value={bgAdminUser}
                  onChange={e => setBgAdminUser(e.target.value)}
                  placeholder="peter"
                  autoFocus
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Udlø (dage, 0 = ingen)</label>
                <input
                  type="number"
                  className="w-full border border-gray-200 rounded px-3 py-2 text-sm outline-none focus:border-sky-400"
                  value={bgExpiresDays}
                  onChange={e => setBgExpiresDays(Number(e.target.value))}
                  min={0}
                />
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-700">
                Password genereres automatisk. Brug /checkout for at se det — passwordet roteres ved hvert checkout.
              </div>
              {bgError && (
                <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
                  ⚠️ {bgError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-5">
              <button
                onClick={createBreakGlass}
                disabled={!bgAdminUser || bgCreating}
                className="flex-1 bg-orange-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50 transition-colors"
              >
                {bgCreating ? 'Opretter…' : 'Opret'}
              </button>
              <button
                onClick={() => setBgModal(false)}
                className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm hover:bg-gray-200 transition-colors"
              >
                Annuller
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Checkout modal */}
      {checkoutModal !== null && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-200 p-6 w-[480px] shadow-xl">
            <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              Break-glass checkout
            </h3>
            {!checkoutResult ? (
              <>
                <p className="text-sm text-gray-500 mb-4">
                  Passwordet vises <strong>kun én gang</strong> og roteres herefter automatisk.
                </p>
                <div className="mb-3">
                  <label className="text-xs text-gray-500 block mb-1">Årsag til adgang</label>
                  <input
                    className="w-full border border-gray-200 rounded px-3 py-2 text-sm outline-none focus:border-sky-400"
                    value={checkoutReason}
                    onChange={e => setCheckoutReason(e.target.value)}
                    placeholder="f.eks. 'SSH forbindelse mistet, enhed hænger'"
                    autoFocus
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => doCheckout(checkoutModal)}
                    disabled={checkingOut}
                    className="flex-1 bg-orange-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50 transition-colors"
                  >
                    {checkingOut ? 'Henter…' : 'Vis password'}
                  </button>
                  <button
                    onClick={() => setCheckoutModal(null)}
                    className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm hover:bg-gray-200"
                  >
                    Annuller
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 my-4">
                  <p className="text-xs text-orange-600 mb-2 font-medium">SSH-kommando:</p>
                  <code className="block text-sm font-mono text-orange-900 select-all">
                    ssh {checkoutResult.ssh_username}@{detail.ip_address ?? '<ip>'}
                  </code>
                  <p className="text-xs text-orange-600 mt-3 mb-1 font-medium">Password (kopier nu):</p>
                  <code className="block text-lg font-mono font-bold text-orange-900 tracking-widest select-all">
                    {checkoutResult.password}
                  </code>
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-700 mb-4">
                  ⚠️ Password er roteret i databasen. Denne session er den eneste chance for at se det.
                </div>
                <button
                  onClick={() => { setCheckoutModal(null); setCheckoutResult(null) }}
                  className="w-full bg-gray-800 text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-900"
                >
                  Jeg har kopieret passwordet — luk
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Lille hjælpekomponent ─────────────────────────────────────────────────

function Row({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <span className="text-xs text-gray-400 w-36 flex-shrink-0">{label}</span>
      <span className={`text-sm ${value ? 'text-gray-900' : 'text-gray-400'} ${mono ? 'font-mono' : ''}`}>
        {value ?? '—'}
      </span>
    </div>
  )
}
