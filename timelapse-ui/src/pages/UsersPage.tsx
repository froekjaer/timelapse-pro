// ───────────────────────────────────────────────────────────────────────────
// UsersPage.tsx v2 — Brugerstyring med password-politik, kunde-link, MFA
// ───────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import {
  Users, Plus, Trash2, Key, Shield, Check, AlertTriangle,
  Eye, EyeOff, Settings, ChevronDown, ChevronRight, X, Pencil, Fingerprint, Trash
} from 'lucide-react'
import { startRegistration } from '@simplewebauthn/browser'
import { getApiUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'

const ROLES = ['super_admin', 'admin', 'operator', 'viewer'] as const
type Role = typeof ROLES[number]

const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  operator: 'Operatør',
  viewer: 'Seer',
}
const ROLE_COLORS: Record<Role, string> = {
  super_admin: 'bg-red-100 text-red-700',
  admin: 'bg-violet-100 text-violet-700',
  operator: 'bg-sky-100 text-sky-700',
  viewer: 'bg-gray-100 text-gray-600',
}
const MFA_BY_ROLE: Record<Role, string> = {
  super_admin: 'MFA anbefalet',
  admin: 'MFA anbefalet',
  operator: 'MFA valgfrit',
  viewer: 'Ingen MFA krav',
}

interface Policy {
  min_length: number
  require_uppercase: boolean
  require_number: boolean
  require_special: boolean
}

interface UserRec {
  mfa_enabled?: boolean
  webauthn_count?: number
  id: number
  username: string
  email?: string
  role: Role
  customer_id?: string
  is_active: boolean
  created_at: string
  last_login?: string
}

interface Customer { id: string; name: string }

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',

    },
    ...opts,
  }).then(async r => {
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail ?? r.status.toString())
    }
    return r.json()
  })
}

// ── Password styrke ────────────────────────────────────────────────────────
function PwStrength({ pw, policy }: { pw: string; policy: Policy | null }) {
  if (!policy || !pw) return null
  const checks = [
    { ok: pw.length >= policy.min_length,        label: `Mindst ${policy.min_length} tegn` },
    { ok: !policy.require_uppercase || /[A-Z]/.test(pw), label: 'Stort bogstav', hide: !policy.require_uppercase },
    { ok: !policy.require_number    || /[0-9]/.test(pw), label: 'Tal',           hide: !policy.require_number },
    { ok: !policy.require_special   || /[!@#$%^&*]/.test(pw), label: 'Specialtegn', hide: !policy.require_special },
  ].filter(c => !c.hide)

  const score = checks.filter(c => c.ok).length
  const pct   = Math.round((score / checks.length) * 100)
  const color = pct < 50 ? 'bg-red-400' : pct < 100 ? 'bg-amber-400' : 'bg-emerald-500'

  return (
    <div className="mt-1.5 space-y-1.5">
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {checks.map(c => (
          <span key={c.label} className={`text-xs flex items-center gap-1 ${c.ok ? 'text-emerald-600' : 'text-gray-400'}`}>
            {c.ok ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
            {c.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Policy editor ──────────────────────────────────────────────────────────
function PolicyEditor({ policy, onSaved }: { policy: Policy; onSaved: (p: Policy) => void }) {
  const [open,   setOpen]   = useState(false)
  const [local,  setLocal]  = useState(policy)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const updated = await api('/api/admin/password-policy', {
        method: 'PUT',
        body: JSON.stringify(local),
      })
      onSaved(updated)
      setOpen(false)
    } catch (e: any) { alert(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="mb-4">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-700 transition-colors">
        <Settings className="w-3.5 h-3.5" />
        Password-krav
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="mt-2 bg-gray-50 rounded-xl p-4 border border-gray-100 space-y-3">
          <p className="text-xs font-medium text-gray-600">Password-politik (gælder alle brugere)</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Minimum længde</label>
              <input type="number" min={6} max={32} value={local.min_length}
                onChange={e => setLocal(l => ({ ...l, min_length: +e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm" />
            </div>
            <div className="space-y-2 pt-5">
              {[
                { key: 'require_uppercase', label: 'Stort bogstav' },
                { key: 'require_number',    label: 'Tal' },
                { key: 'require_special',   label: 'Specialtegn (!@#…)' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox"
                    checked={(local as any)[key]}
                    onChange={e => setLocal(l => ({ ...l, [key]: e.target.checked }))}
                    className="rounded" />
                  <span className="text-xs text-gray-600">{label}</span>
                </label>
              ))}
            </div>
          </div>
          <button onClick={save} disabled={saving}
            className="px-4 py-1.5 bg-violet-500 text-white text-xs rounded-lg disabled:opacity-50">
            {saving ? 'Gemmer…' : 'Gem politik'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Hoved-komponent ────────────────────────────────────────────────────────
export default function UsersPage() {
  const { user: me } = useAuth()
  const [users,     setUsers]     = useState<UserRec[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [policy,    setPolicy]    = useState<Policy | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)

  // Ny bruger form
  const [showNew,   setShowNew]   = useState(false)
  const [newUser,   setNewUser]   = useState('')
  const [newEmail,  setNewEmail]  = useState('')
  const [newPw,     setNewPw]     = useState('')
  const [showPw,    setShowPw]    = useState(false)
  const [newRole,   setNewRole]   = useState<Role>('viewer')
  const [newCust,   setNewCust]   = useState('')
  const [creating,  setCreating]  = useState(false)
  const [createErr, setCreateErr] = useState<string | null>(null)

  // Skift password
  const [changePwId, setChangePwId] = useState<number | null>(null)
  const [newPwFor,   setNewPwFor]   = useState('')
  const [changePwErr,setChangePwErr]= useState<string | null>(null)
  const [editId,     setEditId]     = useState<number | null>(null)
  const [editRole,   setEditRole]   = useState<Role>('viewer')
  const [editEmail,  setEditEmail]  = useState('')
  const [editCust,   setEditCust]   = useState('')
  const [editActive, setEditActive] = useState(true)
  const [editErr,    setEditErr]    = useState<string | null>(null)
  const [editSaving,    setEditSaving]    = useState(false)
  const [mfaId,         setMfaId]         = useState<number | null>(null)
  const [mfaQr,         setMfaQr]         = useState('')
  const [mfaSecret,     setMfaSecret]     = useState('')
  const [mfaCode,       setMfaCode]       = useState('')
  const [mfaErr,        setMfaErr]        = useState<string | null>(null)
  const [mfaSaving,     setMfaSaving]     = useState(false)
  const [waId,          setWaId]          = useState<number | null>(null)
  const [waDeviceName,  setWaDeviceName]  = useState('')
  const [waCredentials, setWaCredentials] = useState<any[]>([])
  const [waLoading,     setWaLoading]     = useState(false)
  const [waErr,         setWaErr]         = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api('/api/admin/users'),
      api('/api/admin/customers').catch(() => []),
      api('/api/admin/password-policy').catch(() => ({ min_length: 8, require_uppercase: false, require_number: false, require_special: false })),
    ]).then(([u, c, p]) => {
      setUsers(Array.isArray(u) ? u : (u.users ?? []))
      setCustomers(Array.isArray(c) ? c : (c.customers ?? []))
      setPolicy(p)
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function createUser() {
    if (!newUser || !newPw) return
    setCreating(true)
    setCreateErr(null)
    try {
      await api('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          username:    newUser,
          password:    newPw,
          role:        newRole,
          email:       newEmail || `${newUser}@timelapse.local`,
          customer_id: newCust || null,
        }),
      })
      setShowNew(false)
      setNewUser(''); setNewPw(''); setNewEmail(''); setNewRole('viewer'); setNewCust('')
      load()
    } catch (e: any) { setCreateErr(e.message) }
    finally { setCreating(false) }
  }

  async function deleteUser(id: number) {
    if (!confirm('Slet bruger?')) return
    await api(`/api/admin/users/${id}`, { method: 'DELETE' }).catch(e => alert(e.message))
    load()
  }

  function startEdit(u: UserRec) {
    setEditId(u.id)
    setEditRole(u.role)
    setEditEmail(u.email ?? '')
    setEditCust(u.customer_id ?? '')
    setEditActive(u.is_active)
    setEditErr(null)
  }

  async function saveEdit(id: number) {
    setEditSaving(true); setEditErr(null)
    try {
      await api(`/api/admin/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ role: editRole, email: editEmail || null, customer_id: editCust || null, is_active: editActive })
      })
      setEditId(null)
      load()
    } catch (e: any) { setEditErr(e.message) }
    finally { setEditSaving(false) }
  }

  async function startMfaSetup(id: number) {
    setMfaId(id); setMfaQr(''); setMfaSecret(''); setMfaCode(''); setMfaErr(null)
    try {
      const d = await api('/api/auth/setup-mfa', { method: 'POST' })
      setMfaQr(d.qr_code); setMfaSecret(d.secret)
    } catch (e: any) { setMfaErr(e.message) }
  }

  async function confirmMfaSetup(id: number) {
    setMfaSaving(true); setMfaErr(null)
    try {
      await api('/api/auth/confirm-mfa', { method: 'POST', body: JSON.stringify({ code: mfaCode }) })
      setMfaId(null); load()
    } catch (e: any) { setMfaErr(e.message) }
    finally { setMfaSaving(false) }
  }

  async function disableMfa(id: number) {
    setMfaSaving(true); setMfaErr(null)
    try {
      await api('/api/auth/disable-mfa', { method: 'POST', body: JSON.stringify({ user_id: id }) })
      setMfaId(null); load()
    } catch (e: any) { setMfaErr(e.message) }
    finally { setMfaSaving(false) }
  }

  async function openWebAuthn(u: UserRec) {
    setWaId(u.id); setWaErr(null); setWaDeviceName(''); setWaLoading(true)
    try {
      if (u.username === me?.username) {
        const creds = await api(`/api/auth/webauthn/credentials`)
        setWaCredentials(creds)
      } else {
        setWaCredentials([])
      }
    } catch { setWaCredentials([]) }
    finally { setWaLoading(false) }
  }

  async function registerWebAuthn() {
    setWaErr(null); setWaLoading(true)
    try {
      const opts = await api('/api/auth/webauthn/register-begin', { method: 'POST', body: JSON.stringify({}) })
      const result = await startRegistration({ optionsJSON: opts })
      await api('/api/auth/webauthn/register-complete', {
        method: 'POST',
        body: JSON.stringify({ ...result, deviceName: waDeviceName || 'Denne enhed' })
      })
      const creds = await api('/api/auth/webauthn/credentials')
      setWaCredentials(creds)
      setWaDeviceName('')
    } catch (e: any) {
      setWaErr(e.message ?? 'Registrering fejlede')
    } finally { setWaLoading(false) }
  }

  async function deleteWebAuthnCred(credId: number) {
    try {
      await api(`/api/auth/webauthn/credentials/${credId}`, { method: 'DELETE' })
      setWaCredentials(prev => prev.filter(c => c.id !== credId))
    } catch (e: any) { setWaErr(e.message) }
  }

  async function changePassword(id: number) {
    if (!newPwFor) return
    setChangePwErr(null)
    try {
      await api(`/api/admin/users/${id}/password`, {
        method: 'PUT',
        body: JSON.stringify({ password: newPwFor }),
      })
      setChangePwId(null); setNewPwFor('')
    } catch (e: any) { setChangePwErr(e.message) }
  }

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500 flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Brugerstyring</h1>
            <p className="text-sm text-gray-500">Administrer adgang til TimeLapse Pro</p>
          </div>
        </div>
        <button onClick={() => { setShowNew(v => !v); setCreateErr(null) }}
          className="flex items-center gap-2 px-4 py-2 bg-violet-500 hover:bg-violet-600 text-white text-sm rounded-lg">
          <Plus className="w-4 h-4" />Ny bruger
        </button>
      </div>

      {/* Password politik */}
      {policy && me?.role === 'super_admin' && (
        <PolicyEditor policy={policy} onSaved={setPolicy} />
      )}

      {/* Ny bruger form */}
      {showNew && (
        <div className="bg-white rounded-xl border border-violet-100 shadow-sm p-5 mb-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Opret ny bruger</h3>

          {createErr && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-100 text-red-700 text-sm px-3 py-2.5 rounded-lg mb-3">
              <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{createErr}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Brugernavn *</label>
              <input value={newUser} onChange={e => setNewUser(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
                placeholder="john" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Email</label>
              <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
                placeholder={`${newUser || 'john'}@timelapse.local`} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Adgangskode *</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
                  placeholder="••••••••" />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
              {policy && <PwStrength pw={newPw} policy={policy} />}
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Rolle *</label>
              <select value={newRole} onChange={e => setNewRole(e.target.value as Role)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300">
                {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
              <p className="text-xs text-amber-600 mt-1">
                🔐 {MFA_BY_ROLE[newRole]}
              </p>
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Tilknyt kunde (valgfrit)</label>
              <select value={newCust} onChange={e => setNewCust(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300">
                <option value="">Alle kunder (global adgang)</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <p className="text-xs text-gray-400 mt-1">
                Begrænser brugeren til kun at se og administrere den valgte kundes data.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 mt-4">
            <button onClick={() => { setShowNew(false); setCreateErr(null) }}
              className="px-4 py-2 bg-gray-100 text-gray-600 text-sm rounded-lg">Annuller</button>
            <button onClick={createUser} disabled={creating || !newUser || !newPw}
              className="px-4 py-2 bg-violet-500 hover:bg-violet-600 disabled:opacity-50 text-white text-sm rounded-lg">
              {creating ? 'Opretter…' : 'Opret bruger'}
            </button>
          </div>
        </div>
      )}

      {/* Generel fejl */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Brugerliste */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">Henter brugere…</div>
        ) : users.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">Ingen brugere fundet</div>
        ) : users.map((u, i) => (
          <div key={u.id}
            className={`px-5 py-4 ${i < users.length - 1 ? 'border-b border-gray-50' : ''}`}>
            <div className="flex items-start gap-4">
              <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-medium text-gray-600">
                  {u.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-gray-900">{u.username}</span>
                  {u.username === me?.username && (
                    <span className="text-xs bg-sky-100 text-sky-600 px-2 py-0.5 rounded-full">dig</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role]}`}>
                    {ROLE_LABELS[u.role]}
                  </span>
                  {u.customer_id && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                      {customers.find(c => c.id === u.customer_id)?.name ?? 'Kunde'}
                    </span>
                  )}
                  {!u.is_active && (
                    <span className="text-xs bg-red-100 text-red-500 px-2 py-0.5 rounded-full">Deaktiveret</span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  {u.email && <span className="mr-2">{u.email}</span>}
                  Oprettet {new Date(u.created_at).toLocaleDateString('da-DK')}
                  {u.last_login && ' · Sidst set ' + new Date(u.last_login).toLocaleDateString('da-DK')}
                </p>

                {/* Skift password inline */}
                {changePwId === u.id && (
                  <div className="mt-2 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <input type="password" value={newPwFor}
                        onChange={e => setNewPwFor(e.target.value)}
                        placeholder="Ny adgangskode"
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-300 flex-1 max-w-xs" />
                      <button onClick={() => changePassword(u.id)} disabled={!newPwFor}
                        className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg disabled:opacity-50">Gem</button>
                      <button onClick={() => { setChangePwId(null); setNewPwFor(''); setChangePwErr(null) }}
                        className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Annuller</button>
                    </div>
                    {changePwErr && (
                      <p className="text-xs text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> {changePwErr}
                      </p>
                    )}
                    {policy && newPwFor && <PwStrength pw={newPwFor} policy={policy} />}
                  </div>
                )}

                {editId === u.id && (
                  <div className="mt-3 space-y-2 border-t border-gray-50 pt-3">
                    {editErr && (
                      <p className="text-xs text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> {editErr}
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-gray-400 mb-1 block">Rolle</label>
                        <select value={editRole} onChange={e => setEditRole(e.target.value as Role)}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-300">
                          {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400 mb-1 block">Email</label>
                        <input value={editEmail} onChange={e => setEditEmail(e.target.value)}
                          placeholder="email@timelapse.local"
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-300" />
                      </div>
                      <div>
                        <label className="text-xs text-gray-400 mb-1 block">Kunde</label>
                        <select value={editCust} onChange={e => setEditCust(e.target.value)}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-300">
                          <option value="">Global adgang</option>
                          {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      </div>
                      <div className="flex items-end pb-0.5">
                        <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-600">
                          <input type="checkbox" checked={editActive} onChange={e => setEditActive(e.target.checked)}
                            className="rounded border-gray-300" />
                          Aktiv konto
                        </label>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <button onClick={() => saveEdit(u.id)} disabled={editSaving}
                        className="px-3 py-1.5 bg-violet-500 text-white text-xs rounded-lg disabled:opacity-50">
                        {editSaving ? 'Gemmer…' : 'Gem ændringer'}
                      </button>
                      <button onClick={() => setEditId(null)}
                        className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Annuller</button>
                    </div>
                  </div>
                )}
              </div>


                {mfaId === u.id && (
                  <div className="mt-3 space-y-2 border-t border-gray-50 pt-3">
                    <p className="text-xs font-medium text-gray-600 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-violet-500" />
                      {u.mfa_enabled ? 'Deaktiver MFA' : 'Aktiver MFA (TOTP)'}
                    </p>
                    {mfaErr && <p className="text-xs text-red-600">{mfaErr}</p>}
                    {!u.mfa_enabled && !mfaQr && <p className="text-xs text-gray-400">Henter QR-kode…</p>}
                    {!u.mfa_enabled && mfaQr.length > 0 && (
                      <div className="flex flex-col items-center gap-2">
                        <img src={mfaQr} alt="QR kode" className="w-40 h-40 rounded-lg border border-gray-200" />
                        <p className="text-xs text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded">{mfaSecret}</p>
                        <p className="text-xs text-gray-400">Scan QR-koden i din authenticator app</p>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      {!u.mfa_enabled && (
                      <input type="text" inputMode="numeric" maxLength={6}
                        value={mfaCode} onChange={e => setMfaCode(e.target.value.replace(/[^0-9]/g, ''))}
                        placeholder="000000" autoFocus
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs font-mono w-28 text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-violet-300" />
                      )}
                      {!u.mfa_enabled ? (
                        <button onClick={() => confirmMfaSetup(u.id)} disabled={mfaSaving || mfaCode.length < 6}
                          className="px-3 py-1.5 bg-violet-500 text-white text-xs rounded-lg disabled:opacity-50">
                          {mfaSaving ? 'Aktiverer…' : 'Bekræft og aktiver'}
                        </button>
                      ) : null}
                      {u.mfa_enabled && (
                        <button onClick={() => disableMfa(u.id)} disabled={mfaSaving}
                          className="px-3 py-1.5 bg-red-500 text-white text-xs rounded-lg disabled:opacity-50">
                          {mfaSaving ? 'Deaktiverer…' : 'Deaktiver MFA'}
                        </button>
                      )}
                      <button onClick={() => setMfaId(null)} className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Annuller</button>
                    </div>
                  </div>
                )}

                {waId === u.id && (
                  <div className="mt-3 space-y-2 border-t border-gray-50 pt-3">
                    <p className="text-xs font-medium text-gray-600 flex items-center gap-1.5">
                      <Fingerprint className="w-3.5 h-3.5 text-sky-500" />
                      Windows Hello / Touch ID
                    </p>
                    {u.username !== me?.username ? (
                      <p className="text-xs text-gray-400">
                        Passkeys skal oprettes af brugeren selv på den enhed, der skal bruges til login. Bed brugeren logge ind med password og åbne brugerstyring for sin egen konto.
                      </p>
                    ) : (
                      <>
                        {waErr && <p className="text-xs text-red-600">{waErr}</p>}
                        {waLoading ? (
                          <p className="text-xs text-gray-400">Henter registrerede enheder…</p>
                        ) : waCredentials.length > 0 ? (
                          <div className="space-y-1">
                            {waCredentials.map(c => (
                              <div key={c.id} className="flex items-center justify-between gap-2 bg-gray-50 border border-gray-100 rounded-lg px-2 py-1.5">
                                <div className="min-w-0">
                                  <p className="text-xs font-medium text-gray-700 truncate">{c.device_name || 'Ukendt enhed'}</p>
                                  <p className="text-[10px] text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleString('da-DK') : 'Ingen dato'}</p>
                                </div>
                                <button onClick={() => deleteWebAuthnCred(c.id)}
                                  className="p-1 text-gray-400 hover:text-red-600 rounded">
                                  <Trash className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400">Ingen Windows Hello / Touch ID enheder registreret endnu.</p>
                        )}
                        <div className="flex items-center gap-2">
                          <input value={waDeviceName} onChange={e => setWaDeviceName(e.target.value)}
                            placeholder="Navn, fx Peters Mac Touch ID"
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs flex-1 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                          <button onClick={registerWebAuthn} disabled={waLoading}
                            className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg disabled:opacity-50">
                            {waLoading ? 'Starter…' : 'Registrer denne enhed'}
                          </button>
                          <button onClick={() => setWaId(null)} className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Luk</button>
                        </div>
                      </>
                    )}
                  </div>
                )}

              {/* Actions */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button onClick={() => { setWaId(waId === u.id ? null : u.id); if (waId !== u.id) openWebAuthn(u) }}
                  title={(u.webauthn_count ?? 0) > 0 ? `${u.webauthn_count} passkey-enhed(er)` : 'Windows Hello / Touch ID'}
                  className={`p-1.5 rounded-lg transition-colors ${(u.webauthn_count ?? 0) > 0 ? 'text-sky-600 hover:bg-sky-50' : 'text-gray-400 hover:text-sky-600 hover:bg-sky-50'}`}>
                  <Fingerprint className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => { setMfaId(mfaId === u.id ? null : u.id); if (mfaId !== u.id && !u.mfa_enabled) startMfaSetup(u.id) }}
                  title={u.mfa_enabled ? 'Administrer MFA' : 'Aktiver MFA'}
                  className={`p-1.5 rounded-lg transition-colors ${u.mfa_enabled ? 'text-green-500 hover:bg-green-50' : 'text-gray-400 hover:text-violet-600 hover:bg-violet-50'}`}>
                  <Shield className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => startEdit(u)}
                  title="Rediger bruger"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-violet-600 hover:bg-violet-50 transition-colors">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => { setChangePwId(changePwId === u.id ? null : u.id); setNewPwFor(''); setChangePwErr(null) }}
                  title="Skift adgangskode"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-sky-600 hover:bg-sky-50 transition-colors">
                  <Key className="w-3.5 h-3.5" />
                </button>
                {u.username !== me?.username && (
                  <button onClick={() => deleteUser(u.id)}
                    title="Slet bruger"
                    className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Rolle-forklaring */}
      <div className="mt-4 bg-gray-50 rounded-xl p-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Roller, adgange og MFA-krav</p>
        <div className="grid grid-cols-1 gap-2">
          {ROLES.map(r => (
            <div key={r} className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${ROLE_COLORS[r]}`}>
                {ROLE_LABELS[r]}
              </span>
              <span className="text-xs text-gray-400 flex-1">
                {r === 'super_admin' ? 'Fuld adgang inkl. brugerstyring og nøgler' :
                 r === 'admin'       ? 'Alle sites og konfiguration' :
                 r === 'operator'    ? 'Drift — ingen sletning' :
                                       'Kun visning'}
              </span>
              <span className="text-xs text-amber-600 flex-shrink-0">🔐 {MFA_BY_ROLE[r]}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3">
          MFA-krav kan desuden sættes pr. kunde under Kunder → Sikkerhed.
        </p>
      </div>
    </div>
  )
}
