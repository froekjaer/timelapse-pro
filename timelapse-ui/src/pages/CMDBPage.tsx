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
  Server, Shield, ChevronRight, RefreshCw, AlertTriangle,
  HardDrive, Cpu, Wifi, Package, Key, Eye, Trash2,
  Plus, CheckCircle, Clock, ArrowLeft, Edit2, Check, X,
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
  venv_packages: Record<string, string>
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

  // Break-glass state
  const [bgModal, setBgModal] = useState(false)
  const [bgAdminUser, setBgAdminUser] = useState('')
  const [bgExpiresDays, setBgExpiresDays] = useState(0)
  const [bgCreating, setBgCreating] = useState(false)
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
    await apiPost(`/api/cmdb/${pathSegment(deviceId)}/break-glass`, {
      admin_username: bgAdminUser,
      expires_days: bgExpiresDays,
    })
    setBgCreating(false)
    setBgModal(false)
    setBgAdminUser('')
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
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Package className="w-4 h-4 text-sky-500" /> OS / Software
          </h2>
          <div className="space-y-0.5">
            <Row label="OS" value={detail.os_name} />
            <Row label="Kernel" value={detail.kernel_version} mono />
            <Row label="Python" value={detail.python_version} />
            <Row label="App-version" value={detail.app_version} mono />
            <Row label="Sidst set" value={fmtDate(detail.last_seen)} />
            <Row label="Inv. rapporteret" value={fmtDate(detail.inventory_reported_at)} />
          </div>
          {Object.keys(detail.venv_packages ?? {}).length > 0 && (
            <details className="mt-3">
              <summary className="text-xs text-sky-600 cursor-pointer hover:text-sky-700">
                {Object.keys(detail.venv_packages).length} venv-pakker
              </summary>
              <div className="mt-2 max-h-48 overflow-y-auto">
                {Object.entries(detail.venv_packages).sort().map(([name, ver]) => (
                  <div key={name} className="flex justify-between text-xs py-0.5 border-b border-gray-50">
                    <span className="text-gray-700">{name}</span>
                    <span className="text-gray-400 font-mono">{ver}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
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
            onClick={() => setBgModal(true)}
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
