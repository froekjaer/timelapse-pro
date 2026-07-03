import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, CheckCircle, Fingerprint, Key, Plus,
  RefreshCw, RotateCw, Server, ShieldCheck, Trash2, XCircle
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

interface Credential {
  credential_id: string
  entity_type: string
  entity_id: string
  key_type: string
  label: string | null
  status: string
  scopes: string[]
  fingerprint: string | null
  algorithm: string | null
  created_by: string | null
  created_at: string | null
  expires_at: string | null
  last_used_at: string | null
  last_used_from: string | null
  use_count: number
  revoked_by: string | null
  revoke_reason: string | null
  rotated_from_id: string | null
  has_secret: boolean
  metadata: Record<string, any>
  request_signature_required: boolean
  tags: string[]
}

interface DeviceKeyState {
  device_id: string
  status: string | null
  customer_name: string | null
  site_name: string | null
  hostname: string | null
  hardware_model: string | null
  has_api_key: boolean
  has_signing_key: boolean
  has_legacy_token: boolean
}

interface Control {
  status: 'pass' | 'warning' | 'fail' | string
  title: string
  evidence: string
  domains: string[]
  recommendation: string
}

interface KeyManagementData {
  credentials: Credential[]
  devices: DeviceKeyState[]
  summary: Record<string, number>
  controls: Control[]
  cleanup_candidates?: CleanupCandidate[]
  trust_policy?: {
    artifact_verification_required: boolean
    mutual_auth_required: boolean
    trusted_release_signers: unknown[]
    edge_acceptance_rule: string
  }
}

interface CleanupCandidate {
  credential_id: string
  entity_id: string
  key_type: string
  status: string
  last_used_at: string | null
  created_at: string | null
  is_primary: boolean
  group_count: number
  stale: boolean
  action: string
  auto_revoke: boolean
  reason: string
}

type Tab = 'credentials' | 'devices' | 'compliance'

const keyTypes = [
  { value: 'api', label: 'API token' },
  { value: 'ssh', label: 'SSH key' },
  { value: 'signing', label: 'Signing key' },
  { value: 'bootstrap', label: 'Bootstrap' },
]

function fmt(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('da-DK', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function shortHash(value: string | null | undefined) {
  if (!value) return '-'
  return value.length > 20 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value
}

function statusClass(status: string) {
  const map: Record<string, string> = {
    active: 'bg-green-50 text-green-700 border-green-200',
    revoked: 'bg-red-50 text-red-600 border-red-200',
    expired: 'bg-amber-50 text-amber-700 border-amber-200',
    rotated: 'bg-sky-50 text-sky-700 border-sky-200',
    pass: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    fail: 'bg-red-50 text-red-600 border-red-200',
  }
  return map[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-gray-200 bg-white rounded-lg px-4 py-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-xl font-semibold text-gray-900 mt-1">{value}</div>
    </div>
  )
}

export default function KeyManagementPage() {
  const [data, setData] = useState<KeyManagementData | null>(null)
  const [tab, setTab] = useState<Tab>('credentials')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [oneTimeSecret, setOneTimeSecret] = useState<string | null>(null)
  const [operationMessage, setOperationMessage] = useState<string | null>(null)
  const [form, setForm] = useState({
    entity_type: 'edge',
    entity_id: '',
    key_type: 'api',
    label: '',
    expires_days: 365,
    public_key: '',
    generate_keypair: false,
    scopes: '',
  })

  const load = useCallback(async () => {
    setError(null)
    try {
      setData(await api('/api/admin/key-management'))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke hente nøgler')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const suggestedDevices = useMemo(() => data?.devices ?? [], [data])

  async function createCredential(rotatedFromId?: string, formOverride = form) {
    if (!formOverride.entity_id.trim()) {
      setError('Entity ID er påkrævet')
      return
    }
    setBusy(true)
    setError(null)
    setOneTimeSecret(null)
    setOperationMessage(null)
    try {
      const payload = {
        ...formOverride,
        entity_id: formOverride.entity_id.trim(),
        label: formOverride.label.trim() || null,
        public_key: formOverride.public_key.trim() || null,
        scopes: formOverride.scopes.split(',').map(s => s.trim()).filter(Boolean),
        rotated_from_id: rotatedFromId || null,
      }
      const created = await api('/api/admin/key-management/credentials', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setOneTimeSecret(created.secret_once || created.private_key_once || null)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke oprette credential')
    } finally {
      setBusy(false)
    }
  }

  async function revoke(credentialId: string) {
    const reason = prompt('Årsag til revocation') || 'Manuelt revokeret'
    setBusy(true)
    setError(null)
    setOperationMessage(null)
    try {
      await api(`/api/admin/key-management/credentials/${credentialId}/revoke`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      })
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke revokere credential')
    } finally {
      setBusy(false)
    }
  }

  async function migrateLegacyTokens() {
    setBusy(true)
    setError(null)
    try {
      const result = await api('/api/admin/key-management/migrate-legacy-device-tokens', {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setOperationMessage(`Migreret: ${result.migrated}. Allerede registreret: ${result.already_registered}. Sprunget over: ${result.skipped}.`)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke migrere legacy tokens')
    } finally {
      setBusy(false)
    }
  }

  async function setSignaturePolicy(credential: Credential, required: boolean) {
    setBusy(true)
    setError(null)
    setOperationMessage(null)
    try {
      const reason = required
        ? 'HMAC request-signature required for production hardening'
        : 'Manual exception'
      await api(`/api/admin/key-management/credentials/${credential.credential_id}/request-signature`, {
        method: 'POST',
        body: JSON.stringify({ require_request_signature: required, reason }),
      })
      setOperationMessage(`${credential.credential_id}: HMAC ${required ? 'kræves' : 'er slået fra'}.`)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke ændre HMAC policy')
    } finally {
      setBusy(false)
    }
  }

  async function cleanupStaleCredentials(dryRun: boolean) {
    if (!dryRun && !confirm('Revoker sekundære edge credentials nu? Primære credentials bliver ikke automatisk revokeret.')) return
    setBusy(true)
    setError(null)
    setOperationMessage(null)
    try {
      const result = await api('/api/admin/key-management/cleanup-stale-credentials', {
        method: 'POST',
          body: JSON.stringify({
            dry_run: dryRun,
          older_than_days: 14,
            reason: 'Admin cleanup from Key Management UI',
          }),
      })
      if (dryRun) {
        setOperationMessage(`Oprydnings-preview: ${result.candidates.length} fundet, ${result.auto_revoke_candidates} kan revokeres automatisk.`)
      } else {
        setOperationMessage(`Oprydning udført: ${result.revoked_count} credential(s) revokeret.`)
      }
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Kunne ikke køre credential cleanup')
    } finally {
      setBusy(false)
    }
  }

  function rotateFrom(credential: Credential) {
    const nextForm = {
      entity_type: credential.entity_type,
      entity_id: credential.entity_id,
      key_type: credential.key_type,
      label: `${credential.label || credential.key_type} rotation`,
      expires_days: 365,
      public_key: '',
      generate_keypair: credential.key_type === 'ssh' || credential.key_type === 'signing',
      scopes: credential.scopes.join(', '),
    }
    setForm(nextForm)
    createCredential(credential.credential_id, nextForm)
  }

  const summary = data?.summary ?? {}

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Key className="w-5 h-5 text-gray-500" />
            Nøglehåndtering
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">Credential lifecycle for Headend, Edge, API, SSH og signing</p>
        </div>
        <button onClick={load} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-200 text-gray-500 rounded-lg hover:bg-gray-50 disabled:opacity-50">
          <RefreshCw className="w-3.5 h-3.5" />
          Opdater
        </button>
        <button onClick={migrateLegacyTokens} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-amber-200 text-amber-700 rounded-lg hover:bg-amber-50 disabled:opacity-50">
          <ShieldCheck className="w-3.5 h-3.5" />
          Migrer legacy
        </button>
        <button onClick={() => cleanupStaleCredentials(true)} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-sky-200 text-sky-700 rounded-lg hover:bg-sky-50 disabled:opacity-50">
          <RefreshCw className="w-3.5 h-3.5" />
          Preview oprydning
        </button>
        <button onClick={() => cleanupStaleCredentials(false)} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-red-200 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50">
          <Trash2 className="w-3.5 h-3.5" />
          Ryd sekundære
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg border border-red-100 bg-red-50 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {oneTimeSecret && (
        <div className="mb-4 border border-amber-200 bg-amber-50 rounded-lg p-4">
          <div className="text-sm font-medium text-amber-900">Ny hemmelighed vises kun denne ene gang</div>
          <textarea readOnly value={oneTimeSecret}
            className="mt-2 w-full h-24 border border-amber-200 rounded-lg p-3 text-xs font-mono bg-white text-gray-800" />
        </div>
      )}

      {operationMessage && (
        <div className="mb-4 px-4 py-3 rounded-lg border border-sky-100 bg-sky-50 text-sky-700 text-sm flex items-center gap-2">
          <CheckCircle className="w-4 h-4" />
          {operationMessage}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-10 gap-3 mb-5">
        <Metric label="Aktive" value={summary.active ?? 0} />
        <Metric label="Revoked" value={summary.revoked ?? 0} />
        <Metric label="Expired" value={summary.expired ?? 0} />
        <Metric label="Legacy tokens" value={summary.legacy_device_tokens ?? 0} />
        <Metric label="Mangler API" value={summary.missing_edge_api_key ?? 0} />
        <Metric label="Mangler signing" value={summary.missing_signing_key ?? 0} />
        <Metric label="HMAC krævet" value={summary.api_hmac_required ?? 0} />
        <Metric label="HMAC mangler" value={summary.api_hmac_missing ?? 0} />
        <Metric label="Oprydning" value={summary.cleanup_candidates ?? 0} />
        <Metric label="Release signers" value={summary.trusted_release_signers ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        <div className="bg-white border border-gray-200 rounded-lg p-4 h-fit">
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <Plus className="w-4 h-4 text-gray-500" />
            Udsted credential
          </h2>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <select value={form.entity_type} onChange={e => setForm(f => ({ ...f, entity_type: e.target.value }))}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
                <option value="edge">Edge</option>
                <option value="headend">Headend</option>
                <option value="service">Service</option>
                <option value="user">User</option>
              </select>
              <select value={form.key_type} onChange={e => setForm(f => ({ ...f, key_type: e.target.value }))}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
                {keyTypes.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <input value={form.entity_id} onChange={e => setForm(f => ({ ...f, entity_id: e.target.value }))}
              list="key-management-devices"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="CMDB/device/service id" />
            <datalist id="key-management-devices">
              {suggestedDevices.map(d => <option key={d.device_id} value={d.device_id} />)}
              <option value="headend" />
            </datalist>
            <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Label" />
            <input value={form.scopes} onChange={e => setForm(f => ({ ...f, scopes: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Scopes, kommasepareret" />
            <input type="number" min={0} value={form.expires_days}
              onChange={e => setForm(f => ({ ...f, expires_days: Number(e.target.value) }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Udløb i dage" />
            {(form.key_type === 'ssh' || form.key_type === 'signing') && (
              <>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={form.generate_keypair}
                    onChange={e => setForm(f => ({ ...f, generate_keypair: e.target.checked }))} />
                  Generer Ed25519 nøglepar
                </label>
                <textarea value={form.public_key} onChange={e => setForm(f => ({ ...f, public_key: e.target.value }))}
                  disabled={form.generate_keypair}
                  className="w-full h-24 border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono disabled:bg-gray-50"
                  placeholder="Public key" />
              </>
            )}
            <button onClick={() => createCredential()} disabled={busy}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-gray-900 text-white text-sm disabled:opacity-50">
              <ShieldCheck className="w-4 h-4" />
              Udsted
            </button>
          </div>
        </div>

        <div>
          <div className="flex gap-1 mb-4">
            {[
              ['credentials', 'Credentials'],
              ['devices', 'CMDB binding'],
              ['compliance', 'Compliance'],
            ].map(([key, label]) => (
              <button key={key} onClick={() => setTab(key as Tab)}
                className={`px-3 py-1.5 text-xs rounded-lg ${tab === key ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
                {label}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="bg-white border border-gray-200 rounded-lg py-16 text-center text-sm text-gray-400">Henter nøgler...</div>
          ) : tab === 'credentials' ? (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {(data?.credentials ?? []).length === 0 ? (
                <div className="py-16 text-center text-sm text-gray-400">Ingen credentials endnu</div>
              ) : data?.credentials.map(credential => (
                <div key={credential.credential_id} className="px-5 py-4 border-b border-gray-100 last:border-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-sm font-semibold text-gray-900">{credential.credential_id}</span>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded border ${statusClass(credential.status)}`}>{credential.status}</span>
                        <span className="text-[11px] px-1.5 py-0.5 rounded border bg-gray-50 text-gray-600 border-gray-200">{credential.key_type}</span>
                        {credential.key_type === 'api' && (
                          <span className={`text-[11px] px-1.5 py-0.5 rounded border ${credential.request_signature_required ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                            {credential.request_signature_required ? 'HMAC required' : 'HMAC missing'}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        {credential.entity_type}:{credential.entity_id} / {credential.label || '-'}
                      </div>
                      <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                        <div className="bg-gray-50 rounded-lg px-3 py-2">
                          <div className="text-gray-400">Fingerprint</div>
                          <div className="font-mono text-gray-700">{shortHash(credential.fingerprint)}</div>
                        </div>
                        <div className="bg-gray-50 rounded-lg px-3 py-2">
                          <div className="text-gray-400">Udløb</div>
                          <div className="text-gray-700">{fmt(credential.expires_at)}</div>
                        </div>
                        <div className="bg-gray-50 rounded-lg px-3 py-2">
                          <div className="text-gray-400">Brug</div>
                          <div className="text-gray-700">{credential.use_count} / {fmt(credential.last_used_at)}</div>
                          {credential.last_used_from && (
                            <div className="font-mono text-gray-400 mt-0.5">{credential.last_used_from}</div>
                          )}
                        </div>
                      </div>
                      {credential.scopes.length > 0 && (
                        <div className="mt-2 flex gap-1 flex-wrap">
                          {credential.scopes.map(scope => (
                            <span key={scope} className="text-[11px] bg-sky-50 text-sky-700 border border-sky-100 rounded px-1.5 py-0.5">{scope}</span>
                          ))}
                        </div>
                      )}
                    </div>
	                    <div className="flex items-center gap-2 flex-shrink-0">
                      {credential.key_type === 'api' && credential.status === 'active' && !credential.request_signature_required && (
                        <button onClick={() => setSignaturePolicy(credential, true)} disabled={busy}
                          className="p-2 rounded-lg border border-green-200 text-green-700 hover:bg-green-50 disabled:opacity-40"
                          title="Kræv HMAC request-signature">
                          <ShieldCheck className="w-4 h-4" />
                        </button>
                      )}
	                      <button onClick={() => rotateFrom(credential)} disabled={busy || credential.status !== 'active'}
	                        className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40"
	                        title="Roter">
                        <RotateCw className="w-4 h-4" />
                      </button>
                      <button onClick={() => revoke(credential.credential_id)} disabled={busy || credential.status !== 'active'}
                        className="p-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-40"
                        title="Revoker">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : tab === 'devices' ? (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {data?.devices.map(device => (
                <div key={device.device_id} className="px-5 py-4 border-b border-gray-100 last:border-0">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="font-mono text-sm font-semibold text-gray-900">{device.device_id}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        {[device.customer_name, device.site_name, device.hostname, device.hardware_model].filter(Boolean).join(' / ') || 'Ingen ekstra CMDB-kontekst'}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-wrap justify-end">
                      <Badge ok={device.has_api_key} label="API" />
                      <Badge ok={device.has_signing_key} label="Signing" />
                      <Badge ok={!device.has_legacy_token} label="No legacy" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {(data?.cleanup_candidates ?? []).length > 0 && (
                <div className="bg-white border border-amber-200 rounded-lg p-4">
                  <div className="text-sm font-semibold text-amber-900 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Credential cleanup kandidater
                  </div>
                  <div className="mt-3 space-y-2">
                    {(data?.cleanup_candidates ?? []).slice(0, 8).map(candidate => (
                      <div key={candidate.credential_id} className="flex items-start justify-between gap-3 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                        <div className="min-w-0">
                          <div className="font-mono text-xs text-amber-950">{candidate.credential_id}</div>
                          <div className="text-xs text-amber-800 mt-0.5">{candidate.entity_id} / {candidate.key_type} / {candidate.reason}</div>
                        </div>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded border ${candidate.auto_revoke ? 'bg-red-50 text-red-700 border-red-200' : 'bg-white text-amber-700 border-amber-200'}`}>
                          {candidate.auto_revoke ? 'auto revoke' : 'review'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {data?.trust_policy && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-500" />
                    Edge code-signing policy
                  </div>
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Artifact verification</div>
                      <div className="text-gray-800">{data.trust_policy.artifact_verification_required ? 'Required' : 'Not required'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Mutual auth</div>
                      <div className="text-gray-800">{data.trust_policy.mutual_auth_required ? 'Required' : 'Not required'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2">
                      <div className="text-gray-400">Trusted signers</div>
                      <div className="text-gray-800">{data.trust_policy.trusted_release_signers.length}</div>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-3">{data.trust_policy.edge_acceptance_rule}</p>
                </div>
              )}
              {data?.controls.map(control => (
                <div key={control.title} className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                        <Fingerprint className="w-4 h-4 text-gray-500" />
                        {control.title}
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
          )}
        </div>
      </div>
    </div>
  )
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded border ${ok ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
      {ok ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {label}
    </span>
  )
}
