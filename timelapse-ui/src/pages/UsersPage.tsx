// ───────────────────────────────────────────────────────────────────────────
// UsersPage.tsx v2 — Brugerstyring med password-politik, kunde-link, MFA
// ───────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import {
  Users, Plus, Trash2, Key, Shield, Check, AlertTriangle,
  Eye, EyeOff, Settings, ChevronDown, ChevronRight, X, Pencil, Fingerprint, Trash, Terminal
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
  super_admin: 'MFA kræves som standard',
  admin: 'MFA kræves som standard',
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
  mfa_required?: boolean
  mfa_partial?: boolean
  totp_configured?: boolean
  webauthn_count?: number
  id: number
  username: string
  email?: string
  role: Role
  customer_id?: string
  is_active: boolean
  created_at: string
  last_login?: string
  field_role?: 'none' | 'installer' | 'technician'
}

interface SSHKeyRec {
  id: number
  label: string | null
  public_key: string
  created_at: string | null
  created_by: string | null
  revoked_at: string | null
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

function isMfaRequiredError(message: string | null) {
  return (message ?? '').toLowerCase().includes('mfa kræves')
}

// ── Browser-side SSH-nøgle-generering ─────────────────────────────────────
// Genererer et Ed25519-nøglepar direkte i browseren via Web Crypto API, så
// en operatør aldrig behøver en terminal. Den private nøgle forlader ALDRIG
// browseren undtagen som en lokal fil-download — kun den offentlige nøgle
// sendes til serveren. Output-formatet er ægte OpenSSH-format (samme som
// `ssh-keygen` selv producerer), verificeret byte-for-byte mod `ssh-keygen -y`
// før dette blev bygget ind i UI'en — kan bruges direkte med `ssh -i fil`,
// ingen konvertering nødvendig.
function u32Bytes(n: number): Uint8Array {
  return new Uint8Array([(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff])
}

function concatBytes(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Uint8Array(total)
  let offset = 0
  for (const c of chunks) { out.set(c, offset); offset += c.length }
  return out
}

function sshString(data: Uint8Array | string): Uint8Array {
  const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : data
  return concatBytes([u32Bytes(bytes.length), bytes])
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary)
}

function base64urlToBytes(s: string): Uint8Array {
  let padded = s.replace(/-/g, '+').replace(/_/g, '/')
  while (padded.length % 4) padded += '='
  const binary = atob(padded)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i)
  return out
}

function wrapPem(header: string, base64: string): string {
  const lines = base64.match(/.{1,70}/g) ?? []
  return `-----BEGIN ${header}-----\n${lines.join('\n')}\n-----END ${header}-----\n`
}

async function generateEd25519KeyPair(): Promise<{ publicKeyOpenSSH: string; privateKeyOpenSSH: string }> {
  const keyPair = await crypto.subtle.generateKey({ name: 'Ed25519' } as EcKeyGenParams, true, ['sign', 'verify']) as CryptoKeyPair
  const jwk = await crypto.subtle.exportKey('jwk', keyPair.privateKey)
  const seed = base64urlToBytes(jwk.d as string)   // 32-byte private seed
  const pub  = base64urlToBytes(jwk.x as string)   // 32-byte public key

  const pubBlob = concatBytes([sshString('ssh-ed25519'), sshString(pub)])
  const publicKeyOpenSSH = `ssh-ed25519 ${bytesToBase64(pubBlob)}`

  const checkint = crypto.getRandomValues(new Uint8Array(4))
  let privSection = concatBytes([
    checkint, checkint,
    sshString('ssh-ed25519'),
    sshString(pub),
    sshString(concatBytes([seed, pub])), // OpenSSH's "expanded" private key: seed + pubkey
    sshString(''), // comment
  ])
  const padLen = (8 - (privSection.length % 8)) % 8
  const padding = new Uint8Array(padLen)
  for (let i = 0; i < padLen; i++) padding[i] = i + 1
  privSection = concatBytes([privSection, padding])

  const full = concatBytes([
    new TextEncoder().encode('openssh-key-v1\0'),
    sshString('none'), sshString('none'), sshString(''), // cipher, kdf, kdfoptions
    u32Bytes(1),
    sshString(pubBlob),
    sshString(privSection),
  ])
  const privateKeyOpenSSH = wrapPem('OPENSSH PRIVATE KEY', bytesToBase64(full))

  return { publicKeyOpenSSH, privateKeyOpenSSH }
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
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
  const [newFieldRole, setNewFieldRole] = useState<'none' | 'installer' | 'technician'>('none')
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
  const [editFieldRole, setEditFieldRole] = useState<'none' | 'installer' | 'technician'>('none')
  const [editErr,    setEditErr]    = useState<string | null>(null)
  const [editSaving,    setEditSaving]    = useState(false)
  const [mfaId,         setMfaId]         = useState<number | null>(null)
  const [mfaQr,         setMfaQr]         = useState('')
  const [mfaSecret,     setMfaSecret]     = useState('')
  const [mfaCode,       setMfaCode]       = useState('')
  const [mfaErr,        setMfaErr]        = useState<string | null>(null)
  const [mfaSaving,     setMfaSaving]     = useState(false)

  // SSH-nøgler (field-role/RBAC teknikeradgang, PR #79)
  const [sshKeysId,      setSshKeysId]      = useState<number | null>(null)
  const [sshKeys,        setSshKeys]        = useState<SSHKeyRec[]>([])
  const [sshKeysErr,     setSshKeysErr]     = useState<string | null>(null)
  const [sshKeysLoading, setSshKeysLoading] = useState(false)
  const [newSshKey,      setNewSshKey]      = useState('')
  const [newSshKeyLabel, setNewSshKeyLabel] = useState('')
  const [sshKeyGeneratedInfo, setSshKeyGeneratedInfo] = useState<string | null>(null)
  const [showManualKeyEntry,  setShowManualKeyEntry]  = useState(false)
  const [mfaDisableOpen, setMfaDisableOpen] = useState(false)
  const [mfaDisablePassword, setMfaDisablePassword] = useState('')
  const [mfaDisableCode, setMfaDisableCode] = useState('')
  const [waId,          setWaId]          = useState<number | null>(null)
  const [waDeviceName,  setWaDeviceName]  = useState('')
  const [waCredentials, setWaCredentials] = useState<any[]>([])
  const [waLoading,     setWaLoading]     = useState(false)
  const [waErr,         setWaErr]         = useState<string | null>(null)

  // Kun ét ekspanderet panel ad gangen pr. bruger — de var uafhængige før,
  // så fx "Rediger" + "SSH-nøgler" åbne samtidig gav et rodet, stablet
  // layout i stedet for den fokuserede visning brugeren forventede.
  function closeExpandedPanels() {
    setChangePwId(null)
    setEditId(null)
    setMfaId(null)
    setSshKeysId(null)
    setWaId(null)
  }

  const load = () => {
    setLoading(true)
    api('/api/admin/users')
      .then(async u => {
        const [c, p] = await Promise.all([
          api('/api/admin/customers').catch(() => []),
          api('/api/admin/password-policy').catch(() => ({ min_length: 8, require_uppercase: false, require_number: false, require_special: false })),
        ])
      setUsers(Array.isArray(u) ? u : (u.users ?? []))
      setCustomers(Array.isArray(c) ? c : (c.customers ?? []))
      setPolicy(p)
      })
      .catch(e => {
        setError(e.message)
        setUsers([])
      })
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
          field_role: newFieldRole,
        }),
      })
      setShowNew(false)
      setNewUser(''); setNewPw(''); setNewEmail(''); setNewRole('viewer'); setNewCust(''); setNewFieldRole('none')
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
    closeExpandedPanels()
    setEditId(u.id)
    setEditRole(u.role)
    setEditEmail(u.email ?? '')
    setEditCust(u.customer_id ?? '')
    setEditActive(u.is_active)
    setEditFieldRole(u.field_role ?? 'none')
    setEditErr(null)
  }

  async function saveEdit(id: number) {
    setEditSaving(true); setEditErr(null)
    try {
      await api(`/api/admin/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ role: editRole, email: editEmail || null, customer_id: editCust || null, is_active: editActive, field_role: editFieldRole })
      })
      setEditId(null)
      load()
    } catch (e: any) { setEditErr(e.message) }
    finally { setEditSaving(false) }
  }

  async function openSshKeys(id: number) {
    const opening = sshKeysId !== id
    closeExpandedPanels()
    if (!opening) return
    setSshKeysId(id)
    setSshKeysErr(null); setNewSshKey(''); setNewSshKeyLabel('')
    setSshKeyGeneratedInfo(null); setShowManualKeyEntry(false)
    try {
      const keys = await api(`/api/admin/users/${id}/ssh-keys`)
      setSshKeys(keys)
    } catch (e: unknown) { setSshKeysErr(e instanceof Error ? e.message : String(e)) }
  }

  async function registerSshKey(id: number, publicKey: string, label: string) {
    await api(`/api/admin/users/${id}/ssh-keys`, {
      method: 'POST',
      body: JSON.stringify({ public_key: publicKey, label: label || null })
    })
    const keys = await api(`/api/admin/users/${id}/ssh-keys`)
    setSshKeys(keys)
  }

  async function addSshKey(id: number) {
    setSshKeysLoading(true); setSshKeysErr(null)
    try {
      await registerSshKey(id, newSshKey, newSshKeyLabel)
      setNewSshKey(''); setNewSshKeyLabel('')
    } catch (e: unknown) { setSshKeysErr(e instanceof Error ? e.message : String(e)) }
    finally { setSshKeysLoading(false) }
  }

  async function generateAndRegisterSshKey(id: number) {
    setSshKeysLoading(true); setSshKeysErr(null); setSshKeyGeneratedInfo(null)
    try {
      const { publicKeyOpenSSH, privateKeyOpenSSH } = await generateEd25519KeyPair()
      const label = newSshKeyLabel.trim() || `Nøgle oprettet ${new Date().toLocaleDateString('da-DK')}`
      const filename = `${label.replace(/[^a-zA-Z0-9._-]+/g, '-')}.key`
      await registerSshKey(id, publicKeyOpenSSH, label)
      downloadTextFile(filename, privateKeyOpenSSH)
      setNewSshKey(''); setNewSshKeyLabel('')
      setSshKeyGeneratedInfo(filename)
    } catch (e: unknown) { setSshKeysErr(e instanceof Error ? e.message : String(e)) }
    finally { setSshKeysLoading(false) }
  }

  async function revokeSshKey(userId: number, keyId: number) {
    setSshKeysErr(null)
    try {
      await api(`/api/admin/users/${userId}/ssh-keys/${keyId}`, { method: 'DELETE' })
      const keys = await api(`/api/admin/users/${userId}/ssh-keys`)
      setSshKeys(keys)
    } catch (e: unknown) { setSshKeysErr(e instanceof Error ? e.message : String(e)) }
  }

  async function startMfaSetup(id: number) {
    setMfaId(id); setMfaQr(''); setMfaSecret(''); setMfaCode(''); setMfaErr(null)
    try {
      const d = await api('/api/auth/setup-mfa', { method: 'POST' })
      setMfaQr(d.qr_code); setMfaSecret(d.secret)
    } catch (e: any) { setMfaErr(e.message) }
  }

  async function confirmMfaSetup() {
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
      await api('/api/auth/disable-mfa', {
        method: 'POST',
        body: JSON.stringify({
          user_id: id,
          current_password: mfaDisablePassword,
          totp_code: mfaDisableCode,
        }),
      })
      setMfaId(null)
      setMfaDisableOpen(false)
      setMfaDisablePassword('')
      setMfaDisableCode('')
      load()
    } catch (e: any) { setMfaErr(e.message) }
    finally { setMfaSaving(false) }
  }

  async function resetMfa(u: UserRec) {
    setMfaSaving(true); setMfaErr(null)
    try {
      await api(`/api/admin/users/${u.id}/mfa/reset`, {
        method: 'POST',
        body: JSON.stringify({
          current_password: mfaDisablePassword,
          totp_code: mfaDisableCode,
        }),
      })
      setMfaId(null)
      setMfaDisableOpen(false)
      setMfaDisablePassword('')
      setMfaDisableCode('')
      load()
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
            <div className="col-span-2 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2">
              <label className="text-xs text-sky-900 font-medium block mb-1">Felt-rolle (on-site adgang)</label>
              <select value={newFieldRole} onChange={e => setNewFieldRole(e.target.value as 'none' | 'installer' | 'technician')}
                className="w-full border border-sky-200 rounded-lg px-2 py-1.5 text-sm bg-white">
                <option value="none">Ingen</option>
                <option value="installer">Idriftsætter</option>
                <option value="technician">Servicetekniker</option>
              </select>
              <p className="text-xs text-sky-700 mt-1">Tillader tekniker-login til lokal Edge-service efter normal TimeLapse Pro-autentificering. Primær rolle og kundeafgrænsning bevares.</p>
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
          <AlertTriangle className="w-4 h-4" />
          <span className="flex-1">{error}</span>
          {isMfaRequiredError(error) && (
            <button onClick={() => { localStorage.removeItem('tl_user'); window.location.href = '/login' }}
              className="px-3 py-1.5 bg-red-600 text-white text-xs rounded-lg">
              Log ind med MFA
            </button>
          )}
        </div>
      )}

      {/* Brugerliste */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">Henter brugere…</div>
        ) : users.length === 0 && !error ? (
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
                  <span className="text-sm font-medium text-gray-900 flex-shrink-0">{u.username}</span>
                  {u.username === me?.username && (
                    <span className="text-xs bg-sky-100 text-sky-600 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">dig</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 whitespace-nowrap ${ROLE_COLORS[u.role]}`}>
                    {ROLE_LABELS[u.role]}
                  </span>
                  {u.customer_id && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">
                      {customers.find(c => c.id === u.customer_id)?.name ?? 'Kunde'}
                    </span>
                  )}
                  {!u.is_active && (
                    <span className="text-xs bg-red-100 text-red-500 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">Deaktiveret</span>
                  )}
                  {u.mfa_required && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">MFA kræves</span>
                  )}
                  {u.mfa_partial && (
                    <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">MFA halv state</span>
                  )}
                  {u.field_role === 'installer' && (
                    <span className="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">Idriftsætter</span>
                  )}
                  {u.field_role === 'technician' && (
                    <span className="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap">Servicetekniker</span>
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
                      <div className="col-span-2 rounded-lg border border-sky-100 bg-sky-50 px-2 py-2">
                        <label className="text-xs text-sky-900 font-medium block mb-1">Felt-rolle (on-site adgang)</label>
                        <select value={editFieldRole} onChange={e => setEditFieldRole(e.target.value as 'none' | 'installer' | 'technician')}
                          className="w-full border border-sky-200 rounded-lg px-2 py-1.5 text-xs bg-white">
                          <option value="none">Ingen</option>
                          <option value="installer">Idriftsætter</option>
                          <option value="technician">Servicetekniker</option>
                        </select>
                        <p className="text-xs text-sky-700 mt-1">Kan gennemføre lokal Edge-service med sin normale konto og gældende rolle.</p>
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
                      {u.mfa_enabled ? 'Administrer MFA' : u.mfa_partial ? 'Nulstil halv MFA-state' : 'MFA (TOTP)'}
                    </p>
                    {mfaErr && <p className="text-xs text-red-600">{mfaErr}</p>}
                    {u.username !== me?.username && (
                      <p className="text-xs text-gray-400">
                        Af sikkerhedsgrunde skal brugeren selv scanne sin nye MFA-kode. Som super_admin kan du nulstille en hel eller halv TOTP-state, så brugeren kan oprette den igen ved næste login.
                      </p>
                    )}
                    {u.username === me?.username && !u.mfa_enabled && !mfaQr && <p className="text-xs text-gray-400">Henter QR-kode…</p>}
                    {u.username === me?.username && !u.mfa_enabled && mfaQr.length > 0 && (
                      <div className="flex flex-col items-center gap-2">
                        <img src={mfaQr} alt="QR kode" className="w-40 h-40 rounded-lg border border-gray-200" />
                        <p className="text-xs text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded">{mfaSecret}</p>
                        <p className="text-xs text-gray-400">Scan QR-koden i din authenticator app</p>
                      </div>
                    )}
                    {(u.mfa_enabled || u.mfa_partial) && mfaDisableOpen && (
                      <div className="grid sm:grid-cols-2 gap-2 rounded-md border border-red-100 bg-red-50 p-3">
                        <input
                          type="password"
                          value={mfaDisablePassword}
                          onChange={e => setMfaDisablePassword(e.target.value)}
                          placeholder="Aktuel adgangskode"
                          autoComplete="current-password"
                          className="border border-gray-200 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-red-300"
                        />
                        <input
                          type="text"
                          inputMode="numeric"
                          maxLength={6}
                          value={mfaDisableCode}
                          onChange={e => setMfaDisableCode(e.target.value.replace(/[^0-9]/g, ''))}
                          placeholder="TOTP-kode"
                          className="border border-gray-200 rounded-md px-3 py-2 text-xs font-mono text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-red-300"
                        />
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      {u.username === me?.username && !u.mfa_enabled && (
                      <input type="text" inputMode="numeric" maxLength={6}
                        value={mfaCode} onChange={e => setMfaCode(e.target.value.replace(/[^0-9]/g, ''))}
                        placeholder="000000" autoFocus
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs font-mono w-28 text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-violet-300" />
                      )}
                      {u.username === me?.username && !u.mfa_enabled ? (
                        <button onClick={() => confirmMfaSetup()} disabled={mfaSaving || mfaCode.length < 6}
                          className="px-3 py-1.5 bg-violet-500 text-white text-xs rounded-lg disabled:opacity-50">
                          {mfaSaving ? 'Aktiverer…' : 'Bekræft og aktiver'}
                        </button>
                      ) : null}
                      {(u.mfa_enabled || u.mfa_partial || u.username !== me?.username) && (
                        <button
                          onClick={() => mfaDisableOpen ? resetMfa(u) : setMfaDisableOpen(true)}
                          disabled={mfaSaving || (mfaDisableOpen && (!mfaDisablePassword || mfaDisableCode.length !== 6))}
                          className="px-3 py-1.5 bg-amber-500 text-white text-xs rounded-lg disabled:opacity-50">
                          {mfaSaving ? 'Nulstiller…' : mfaDisableOpen ? 'Bekræft nulstilling' : 'Nulstil MFA'}
                        </button>
                      )}
                      {u.username === me?.username && u.mfa_enabled && !mfaDisableOpen && (
                        <button
                          onClick={() => mfaDisableOpen ? disableMfa(u.id) : setMfaDisableOpen(true)}
                          disabled={mfaSaving || (mfaDisableOpen && (!mfaDisablePassword || mfaDisableCode.length !== 6))}
                          className="px-3 py-1.5 bg-red-500 text-white text-xs rounded-lg disabled:opacity-50">
                          {mfaSaving ? 'Deaktiverer…' : mfaDisableOpen ? 'Bekræft deaktivering' : 'Deaktiver MFA'}
                        </button>
                      )}
                      <button onClick={() => { setMfaId(null); setMfaDisableOpen(false); setMfaDisablePassword(''); setMfaDisableCode('') }} className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Annuller</button>
                    </div>
                  </div>
                )}

                {sshKeysId === u.id && (
                  <div className="mt-3 space-y-2 border-t border-gray-50 pt-3">
                    <p className="text-xs font-medium text-gray-600 flex items-center gap-1.5">
                      <Terminal className="w-3.5 h-3.5 text-sky-500" />
                      SSH-nøgler til lokal Edge-adgang
                    </p>
                    <p className="text-xs text-gray-400">
                      Erstatter den delte, fælles nøgle — hver nøgle logger ind som "servicetekniker" på enheder, men er sporbar til denne bruger.
                    </p>
                    {sshKeysErr && <p className="text-xs text-red-600">{sshKeysErr}</p>}
                    {sshKeyGeneratedInfo && (
                      <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                        ✓ Nøgle oprettet og registreret. Filen <strong>{sshKeyGeneratedInfo}</strong> er hentet til din computer (typisk i "Filer hentet") — gem den et sikkert sted, den bruges til at logge ind.
                      </p>
                    )}
                    {sshKeys.length > 0 ? (
                      <div className="space-y-1">
                        {sshKeys.map(k => (
                          <div key={k.id} className={`flex items-center gap-2 rounded-lg border px-2 py-1.5 ${k.revoked_at ? 'border-gray-100 bg-gray-50' : 'border-sky-100 bg-sky-50'}`}>
                            <Terminal className={`w-3.5 h-3.5 flex-shrink-0 ${k.revoked_at ? 'text-gray-300' : 'text-sky-500'}`} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs text-gray-700 truncate">{k.label || 'Uden navn'}</p>
                              <p className="text-[10px] text-gray-400 font-mono truncate">{k.public_key}</p>
                            </div>
                            {k.revoked_at ? (
                              <span className="text-[10px] text-gray-400 flex-shrink-0">Tilbagekaldt</span>
                            ) : (
                              <button onClick={() => revokeSshKey(u.id, k.id)}
                                title="Tilbagekald nøgle"
                                className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 flex-shrink-0">
                                <Trash className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400">Ingen SSH-nøgler registreret endnu.</p>
                    )}
                    <div className="flex items-center gap-2 flex-wrap">
                      <input value={newSshKeyLabel} onChange={e => setNewSshKeyLabel(e.target.value)}
                        placeholder="Navn, fx Peters MacBook Pro"
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs w-full sm:w-48 flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                      <button onClick={() => generateAndRegisterSshKey(u.id)} disabled={sshKeysLoading}
                        className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg disabled:opacity-50 flex-shrink-0">
                        {sshKeysLoading ? 'Genererer…' : 'Generér ny nøgle'}
                      </button>
                      <button onClick={() => setSshKeysId(null)} className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg flex-shrink-0">Luk</button>
                    </div>
                    <button onClick={() => setShowManualKeyEntry(v => !v)}
                      className="text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2">
                      {showManualKeyEntry ? 'Skjul' : 'Har du allerede en nøgle, du vil bruge i stedet?'}
                    </button>
                    {showManualKeyEntry && (
                      <div className="flex items-center gap-2 flex-wrap rounded-lg bg-gray-50 border border-gray-100 p-2">
                        <input value={newSshKey} onChange={e => setNewSshKey(e.target.value)}
                          placeholder="ssh-ed25519 AAAA... eller ssh-rsa AAAA..."
                          className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs flex-1 min-w-[12rem] font-mono focus:outline-none focus:ring-2 focus:ring-sky-300" />
                        <label className="px-3 py-1.5 bg-white border border-gray-200 text-gray-600 text-xs rounded-lg flex-shrink-0 cursor-pointer hover:bg-gray-100 transition-colors">
                          Vælg fil…
                          <input type="file" accept=".pub,text/plain" className="hidden"
                            onChange={e => {
                              const file = e.target.files?.[0]
                              if (!file) return
                              const reader = new FileReader()
                              reader.onload = () => setNewSshKey(String(reader.result ?? '').trim())
                              reader.readAsText(file)
                              if (!newSshKeyLabel) setNewSshKeyLabel(file.name.replace(/\.pub$/, ''))
                              e.target.value = ''
                            }} />
                        </label>
                        <button onClick={() => addSshKey(u.id)} disabled={sshKeysLoading || !newSshKey.trim()}
                          className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg disabled:opacity-50 flex-shrink-0">
                          {sshKeysLoading ? 'Tilføjer…' : 'Tilføj'}
                        </button>
                      </div>
                    )}
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
                <button onClick={() => {
                    const opening = waId !== u.id
                    closeExpandedPanels()
                    if (opening) { setWaId(u.id); openWebAuthn(u) }
                  }}
                  title={(u.webauthn_count ?? 0) > 0 ? `${u.webauthn_count} passkey-enhed(er)` : 'Windows Hello / Touch ID'}
                  className={`p-1.5 rounded-lg transition-colors ${(u.webauthn_count ?? 0) > 0 ? 'text-sky-600 hover:bg-sky-50' : 'text-gray-400 hover:text-sky-600 hover:bg-sky-50'}`}>
                  <Fingerprint className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => {
                    const opening = mfaId !== u.id
                    closeExpandedPanels()
                    if (!opening) return
                    setMfaId(u.id)
                    if (!u.mfa_enabled && u.username === me?.username) startMfaSetup(u.id)
                  }}
                  title={u.mfa_enabled ? 'Administrer MFA' : u.mfa_required ? 'MFA kræves' : 'MFA'}
                  className={`p-1.5 rounded-lg transition-colors ${
                    u.mfa_partial ? 'text-orange-600 hover:bg-orange-50' :
                    u.mfa_enabled ? 'text-green-500 hover:bg-green-50' :
                    u.mfa_required ? 'text-amber-600 hover:bg-amber-50' :
                    'text-gray-400 hover:text-violet-600 hover:bg-violet-50'
                  }`}>
                  <Shield className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => startEdit(u)}
                  title="Rediger bruger"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-violet-600 hover:bg-violet-50 transition-colors">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => {
                    const opening = changePwId !== u.id
                    closeExpandedPanels()
                    if (opening) { setChangePwId(u.id); setNewPwFor(''); setChangePwErr(null) }
                  }}
                  title="Skift adgangskode"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-sky-600 hover:bg-sky-50 transition-colors">
                  <Key className="w-3.5 h-3.5" />
                </button>
                {(u.field_role === 'installer' || u.field_role === 'technician') && (
                  <button onClick={() => openSshKeys(u.id)}
                    title="SSH-nøgler til lokal Edge-adgang"
                    className={`p-1.5 rounded-lg transition-colors ${sshKeysId === u.id ? 'text-sky-600 bg-sky-50' : 'text-gray-400 hover:text-sky-600 hover:bg-sky-50'}`}>
                    <Terminal className="w-3.5 h-3.5" />
                  </button>
                )}
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
          MFA-krav kan overstyres i konfigurationshierarkiet under session_policy på globalt, kunde-, site- og kameralag.
        </p>
      </div>
    </div>
  )
}
