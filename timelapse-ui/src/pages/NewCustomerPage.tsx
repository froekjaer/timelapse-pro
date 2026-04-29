import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Building2, Save } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    headers: { 'Content-Type': 'application/json' }, ...opts
  }).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
}

export default function NewCustomerPage() {
  const navigate = useNavigate()
  const [name, setName]               = useState('')
  const [contactName, setContactName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [address, setAddress]         = useState('')
  const [saving, setSaving]           = useState(false)
  const [error, setError]             = useState<string | null>(null)

  async function create() {
    if (!name.trim()) return
    setSaving(true)
    try {
      const result = await api('/api/admin/customers', {
        method: 'POST',
        body: JSON.stringify({ name, contact_name: contactName, contact_email: contactEmail, contact_phone: contactPhone, address })
      })
      navigate(`/customers/${result.id}`)
    } catch {
      setError('Kunne ikke oprette kunde')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-sky-500" />
          <h1 className="text-xl font-semibold text-gray-900">Ny kunde</h1>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Firmanavn *</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Byggros A/S" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Kontaktperson</label>
              <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Fulde navn" value={contactName} onChange={e => setContactName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Telefon</label>
              <input type="tel" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="70 20 30 40" value={contactPhone} onChange={e => setContactPhone(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Email</label>
            <input type="email" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="kontakt@firma.dk" value={contactEmail} onChange={e => setContactEmail(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Adresse</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Vejnavn 1, 1234 By" value={address} onChange={e => setAddress(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={create} disabled={saving || !name.trim()}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          <Save className="w-4 h-4" />
          {saving ? 'Opretter…' : 'Opret kunde'}
        </button>
      </div>
    </div>
  )
}
