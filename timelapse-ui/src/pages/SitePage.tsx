import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, MapPin, Building2, Camera, Save, Trash2, Plus, ChevronRight, CheckCircle } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts
  }).then(r => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
}

interface Site {
  id: string
  customer_id: string
  customer_name: string
  name: string
  address?: string
  gps_lat?: number
  gps_lon?: number
  gps_alt?: number
  timezone: string
  config_overrides: Record<string, unknown>
  notes?: string
  devices: Device[]
}

interface Device {
  device_id: string
  camera_name?: string
  camera_index: number
  status: string
  last_seen?: string
}

const TZ = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

export function SitePage() {
  const { siteId } = useParams<{ siteId: string }>()
  const navigate = useNavigate()
  const [site, setSite] = useState<Site | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Editable fields
  const [name, setName] = useState('')
  const [sftpUser, setSftpUser] = useState('')
  const [sftpRemoteBase, setSftpRemoteBase] = useState('')
  const [sftpPassword, setSftpPassword] = useState('')
  const [sftpPort, setSftpPort] = useState('2222')
  const [address, setAddress] = useState('')
  const [gpsLat, setGpsLat] = useState('')
  const [gpsLon, setGpsLon] = useState('')
  const [gpsAlt, setGpsAlt] = useState('')
  const [timezone, setTimezone] = useState('Europe/Copenhagen')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    if (!siteId) return
    api(`/api/admin/sites/${siteId}`)
      .then(d => {
        setSite(d)
        setName(d.name ?? '')
        setAddress(d.address ?? '')
        setGpsLat(d.gps_lat ?? '')
        setGpsLon(d.gps_lon ?? '')
        setGpsAlt(d.gps_alt ?? '')
        setTimezone(d.timezone ?? 'Europe/Copenhagen')
        setNotes(d.notes ?? '')
        const sftp = d.config_overrides?.sftp ?? {}
        setSftpUser(sftp.username ?? '')
        setSftpPassword(sftp.password ?? '')
        setSftpPort(String(sftp.port ?? '2222'))
        setSftpRemoteBase(sftp.remote_base ?? '')
      })
      .catch(() => setError('Kunne ikke hente site'))
      .finally(() => setLoading(false))
  }, [siteId])

  async function save() {
    setSaving(true)
    try {
      await api(`/api/admin/sites/${siteId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name, address,
          gps_lat: gpsLat ? parseFloat(gpsLat) : null,
          gps_lon: gpsLon ? parseFloat(gpsLon) : null,
          gps_alt: gpsAlt ? parseFloat(gpsAlt) : null,
          timezone, notes,
          config_overrides: {
            sftp: {
              username: sftpUser,
              password: sftpPassword,
              port: parseInt(sftpPort),
              remote_base: sftpRemoteBase,
            }
          }
        })
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      setError('Kunne ikke gemme')
    } finally {
      setSaving(false)
    }
  }

  async function deleteSite() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    setDeleting(true)
    try {
      await api(`/api/admin/sites/${siteId}`, { method: 'DELETE' })
      navigate('/')
    } catch (e: any) {
      setError(e.message === '400' ? 'Kan ikke slette — enheder eksisterer på dette site' : 'Sletning fejlede')
      setConfirmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>
  if (error && !site) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-500">{error}</div>
  if (!site) return null

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Building2 className="w-4 h-4" />
          <Link to="/" className="hover:text-gray-600">{site.customer_name}</Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <MapPin className="w-4 h-4" />
          <span className="text-gray-700 font-medium">{site.name}</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Site info */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Site oplysninger</h2>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Site navn</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Adresse</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Vejnavn 1, 1234 By"
              value={address} onChange={e => setAddress(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Tidszone</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={timezone} onChange={e => setTimezone(e.target.value)}>
              <option value="Europe/Copenhagen">Europe/Copenhagen (dansk tid)</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Berlin">Europe/Berlin</option>
              <option value="UTC">UTC</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Noter</label>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2}
              placeholder="Interne noter om dette site..."
              value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
        </div>
      </div>

      {/* SFTP */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">SFTP adgang</h2>
        <p className="text-xs text-gray-400 mb-4">Credentials til edge-nodernes upload på dette site</p>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">SFTP brugernavn</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="sftp_nvj17c"
              value={sftpUser} onChange={e => setSftpUser(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">SFTP password</label>
            <input type="password" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={sftpPassword} onChange={e => setSftpPassword(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Remote base sti</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="/Users/Shared/timelapse/incoming/sftp_nvj17c"
              value={sftpRemoteBase} onChange={e => setSftpRemoteBase(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Port</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="2222"
              value={sftpPort} onChange={e => setSftpPort(e.target.value)} />
          </div>
        </div>
      </div>

      {/* GPS */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">GPS og lokation</h2>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Breddegrad (lat)</label>
            <input type="number" step="0.000001" placeholder="55.676098"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={gpsLat} onChange={e => setGpsLat(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Længdegrad (lon)</label>
            <input type="number" step="0.000001" placeholder="9.535400"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={gpsLon} onChange={e => setGpsLon(e.target.value)} />
          </div>
        </div>
        <div className="mb-3">
          <label className="text-xs text-gray-400 block mb-1">Højde (meter over hav)</label>
          <input type="number" step="1" placeholder="0"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            value={gpsAlt} onChange={e => setGpsAlt(e.target.value)} />
        </div>
        {gpsLat && gpsLon && (
          <a href={`https://www.openstreetmap.org/?mlat=${gpsLat}&mlon=${gpsLon}&zoom=17`}
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-sky-500 hover:text-sky-700">
            🗺️ Vis på OpenStreetMap
          </a>
        )}
      </div>

      {/* Kameraer på dette site */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Kameraer</h2>
          <span className="text-xs text-gray-400">{site.devices.length} enhed{site.devices.length !== 1 ? 'er' : ''}</span>
        </div>
        {site.devices.length === 0 ? (
          <p className="text-sm text-gray-400 italic">Ingen kameraer registreret på dette site</p>
        ) : (
          <div className="space-y-2">
            {site.devices.map(d => {
              const lastSeen = d.last_seen
                ? new Date(d.last_seen + 'Z').toLocaleString('da-DK', { timeZone: TZ(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
                : null
              return (
                <Link key={d.device_id} to={`/devices/${d.device_id}`}
                  className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors group">
                  <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                    <Camera className="w-4 h-4 text-slate-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">
                      {d.camera_name || `Kamera ${d.camera_index + 1}`}
                    </p>
                    <p className="text-xs text-gray-400 font-mono">{d.device_id}</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {lastSeen && <span className="text-gray-400 hidden sm:block">{lastSeen}</span>}
                    <span className={`px-2 py-0.5 rounded-full font-medium ${
                      d.status === 'online' ? 'bg-emerald-50 text-emerald-600' :
                      d.status === 'offline' ? 'bg-red-50 text-red-500' :
                      'bg-gray-100 text-gray-400'
                    }`}>{d.status}</span>
                    <ChevronRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-gray-400" />
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>

      {/* Gem og slet */}
      <div className="flex items-center justify-between">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>

        <button onClick={deleteSite} disabled={deleting}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors ${
            confirmDelete
              ? 'bg-red-500 text-white border-red-500 hover:bg-red-600'
              : 'text-red-400 border-red-200 hover:bg-red-50'
          }`}>
          <Trash2 className="w-4 h-4" />
          {confirmDelete ? 'Bekræft sletning' : 'Slet site'}
        </button>
      </div>
      {confirmDelete && (
        <p className="text-xs text-red-400 mt-2 text-right">
          Klik igen for at bekræfte — dette kan ikke fortrydes!
        </p>
      )}
    </div>
  )
}
