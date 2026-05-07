// ───────────────────────────────────────────────────────────────────
// UsersPage.tsx — Brugerstyring (kun super_admin)
// ───────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import { Users, Plus, Trash2, Key, Shield, ChevronDown, Check, AlertTriangle } from 'lucide-react'
import { getApiUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'

const ROLES = ['super_admin', 'admin', 'operator', 'viewer'] as const
type Role = typeof ROLES[number]

const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'Super Admin',
  admin:       'Admin',
  operator:    'Operatør',
  viewer:      'Seer',
}
const ROLE_COLORS: Record<Role, string> = {
  super_admin: 'bg-red-100 text-red-700',
  admin:       'bg-violet-100 text-violet-700',
  operator:    'bg-sky-100 text-sky-700',
  viewer:      'bg-gray-100 text-gray-600',
}

interface UserRec { id: number; username: string; role: Role; created_at: string; last_login?: string }

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('tl_token') ?? ''}`,
    },
    ...opts,
  }).then(r => { if (!r.ok) throw new Error(r.status.toString()); return r.json() })
}

export default function UsersPage() {
  const { user: me } = useAuth()
  const [users,   setUsers]   = useState<UserRec[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  // Ny bruger form
  const [showNew,  setShowNew]  = useState(false)
  const [newUser,  setNewUser]  = useState('')
  const [newPw,    setNewPw]    = useState('')
  const [newRole,  setNewRole]  = useState<Role>('viewer')
  const [creating, setCreating] = useState(false)

  // Skift password
  const [changePwId, setChangePwId] = useState<number | null>(null)
  const [newPwFor,   setNewPwFor]   = useState('')
  const [changingPw, setChangingPw] = useState(false)

  const load = () => {
    setLoading(true)
    api('/api/admin/users')
      .then(d => setUsers(d.users ?? d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function createUser() {
    if (!newUser || !newPw) return
    setCreating(true)
    try {
      await api('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({ username: newUser, password: newPw, role: newRole }),
      })
      setShowNew(false); setNewUser(''); setNewPw(''); setNewRole('viewer')
      load()
    } catch (e: any) { alert('Fejl: ' + e.message) }
    finally { setCreating(false) }
  }

  async function deleteUser(id: number) {
    if (!confirm('Slet bruger?')) return
    await api(`/api/admin/users/${id}`, { method: 'DELETE' }).catch(e => alert(e.message))
    load()
  }

  async function changePassword(id: number) {
    if (!newPwFor) return
    setChangingPw(true)
    try {
      await api(`/api/admin/users/${id}/password`, {
        method: 'PUT',
        body: JSON.stringify({ password: newPwFor }),
      })
      setChangePwId(null); setNewPwFor('')
    } catch (e: any) { alert('Fejl: ' + e.message) }
    finally { setChangingPw(false) }
  }

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500 flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Brugerstyring</h1>
            <p className="text-sm text-gray-500">Administrer adgang til TimeLapse Pro</p>
          </div>
        </div>
        <button onClick={() => setShowNew(v => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-500 hover:bg-violet-600 text-white text-sm rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
          Ny bruger
        </button>
      </div>

      {/* Ny bruger form */}
      {showNew && (
        <div className="bg-white rounded-xl border border-violet-100 shadow-sm p-5 mb-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Opret ny bruger</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Brugernavn</label>
              <input value={newUser} onChange={e => setNewUser(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
                placeholder="john" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Adgangskode</label>
              <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300"
                placeholder="••••••••" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Rolle</label>
              <select value={newRole} onChange={e => setNewRole(e.target.value as Role)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-300">
                {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <div className="flex items-end">
              <button onClick={createUser} disabled={creating || !newUser || !newPw}
                className="w-full py-2 bg-violet-500 hover:bg-violet-600 disabled:opacity-50 text-white text-sm rounded-lg transition-colors">
                {creating ? 'Opretter…' : 'Opret'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fejl */}
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
        ) : (
          users.map((u, i) => (
            <div key={u.id}
              className={`flex items-center gap-4 px-5 py-4 ${i < users.length - 1 ? 'border-b border-gray-50' : ''}`}>

              {/* Avatar */}
              <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-medium text-gray-600">
                  {u.username.charAt(0).toUpperCase()}
                </span>
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-gray-900">{u.username}</span>
                  {u.username === me?.username && (
                    <span className="text-xs bg-sky-100 text-sky-600 px-2 py-0.5 rounded-full">dig</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role]}`}>
                    {ROLE_LABELS[u.role]}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  Oprettet {new Date(u.created_at).toLocaleDateString('da-DK')}
                  {u.last_login && ' · Sidst set ' + new Date(u.last_login).toLocaleDateString('da-DK')}
                </p>

                {/* Skift password inline */}
                {changePwId === u.id && (
                  <div className="flex items-center gap-2 mt-2">
                    <input type="password" value={newPwFor} onChange={e => setNewPwFor(e.target.value)}
                      placeholder="Ny adgangskode"
                      className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    <button onClick={() => changePassword(u.id)} disabled={changingPw || !newPwFor}
                      className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg disabled:opacity-50">
                      {changingPw ? 'Gemmer…' : 'Gem'}
                    </button>
                    <button onClick={() => { setChangePwId(null); setNewPwFor('') }}
                      className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded-lg">Annuller</button>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button onClick={() => { setChangePwId(changePwId === u.id ? null : u.id); setNewPwFor('') }}
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
          ))
        )}
      </div>

      {/* Rolle-forklaring */}
      <div className="mt-4 bg-gray-50 rounded-xl p-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Roller og adgange</p>
        <div className="grid grid-cols-2 gap-2">
          {ROLES.map(r => (
            <div key={r} className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[r]}`}>{ROLE_LABELS[r]}</span>
              <span className="text-xs text-gray-400">
                {r === 'super_admin' ? 'Fuld adgang inkl. brugerstyring' :
                 r === 'admin'       ? 'Alle sites og konfiguration' :
                 r === 'operator'    ? 'Drift — ingen sletning' :
                                       'Kun visning'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
