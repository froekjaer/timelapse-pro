import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Building2, MapPin, Save, Trash2, Plus, ChevronRight, CheckCircle, Camera } from 'lucide-react'
import { getApiUrl } from '../api/client'

const AI_MODES = ['off', 'monitor', 'assist', 'autonomous', 'npu_first', 'lab']

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

interface Customer {
  id: string
  name: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  address?: string
  notes?: string
  config_overrides?: Record<string, any>
  sites: Site[]
}

interface Site {
  id: string
  name: string
  address?: string
  gps_lat?: number
  gps_lon?: number
  devices_count: number
}

function triFrom(value: unknown) {
  return value === true ? 'true' : value === false ? 'false' : ''
}

function triTo(value: string) {
  return value === 'true' ? true : value === 'false' ? false : undefined
}

function buildQualityOverride(
  existingConfig: Record<string, any> | undefined,
  fields: {
    edgeAiEnabled: string
    edgeAiMode: string
    preferNpu: string
    runner: string
    modelPath: string
    adaptiveExposure: string
    evStep: string
  }
) {
  const quality = { ...(existingConfig?.quality ?? {}) }
  const edgeAi = { ...(quality.edge_ai ?? {}) }
  const adaptive = { ...(quality.adaptive_exposure ?? {}) }

  for (const key of ['enabled', 'mode', 'prefer_npu', 'runner', 'model_path']) delete edgeAi[key]
  for (const key of ['enabled', 'step_ev']) delete adaptive[key]

  const enabled = triTo(fields.edgeAiEnabled)
  const preferNpu = triTo(fields.preferNpu)
  if (enabled !== undefined) edgeAi.enabled = enabled
  if (fields.edgeAiMode) edgeAi.mode = fields.edgeAiMode
  if (preferNpu !== undefined) edgeAi.prefer_npu = preferNpu
  if (fields.runner.trim()) edgeAi.runner = fields.runner.trim()
  if (fields.modelPath.trim()) edgeAi.model_path = fields.modelPath.trim()

  const adaptiveEnabled = triTo(fields.adaptiveExposure)
  if (adaptiveEnabled !== undefined) adaptive.enabled = adaptiveEnabled
  if (fields.evStep.trim()) adaptive.step_ev = Number(fields.evStep)

  if (Object.keys(edgeAi).length) quality.edge_ai = edgeAi
  else delete quality.edge_ai
  if (Object.keys(adaptive).length) quality.adaptive_exposure = adaptive
  else delete quality.adaptive_exposure
  return quality
}

export function CustomerPage() {
  const { customerId } = useParams<{ customerId: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Editable fields
  const [name, setName]               = useState('')
  const [contactName, setContactName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [address, setAddress]         = useState('')
  const [notes, setNotes]             = useState('')
  const [btTotpSecret, setBtTotpSecret] = useState('')
  const [btTotpSid, setBtTotpSid]       = useState('')
  const [edgeAiEnabled, setEdgeAiEnabled] = useState('')
  const [edgeAiMode, setEdgeAiMode]       = useState('')
  const [preferNpu, setPreferNpu]         = useState('')
  const [edgeAiRunner, setEdgeAiRunner]   = useState('')
  const [edgeAiModel, setEdgeAiModel]     = useState('')
  const [adaptiveExposure, setAdaptiveExposure] = useState('')
  const [evStep, setEvStep]               = useState('')

  // Nyt site form
  const [showNewSite, setShowNewSite]     = useState(false)
  const [newSiteName, setNewSiteName]     = useState('')
  const [newSiteAddress, setNewSiteAddress] = useState('')
  const [creatingSite, setCreatingSite]   = useState(false)

  useEffect(() => {
    if (!customerId) return
    api(`/api/admin/customers/${customerId}`)
      .then(d => {
        setCustomer(d)
        setName(d.name ?? '')
        setContactName(d.contact_name ?? '')
        setContactEmail(d.contact_email ?? '')
        setContactPhone(d.contact_phone ?? '')
        setAddress(d.address ?? '')
        setNotes(d.notes ?? '')
        const btTotp = d.config_overrides?.bt_totp ?? {}
        setBtTotpSecret(btTotp.secret ?? '')
        setBtTotpSid(btTotp.sid ?? '')
        const quality = d.config_overrides?.quality ?? {}
        const edgeAi = quality.edge_ai ?? {}
        const adaptive = quality.adaptive_exposure ?? {}
        setEdgeAiEnabled(triFrom(edgeAi.enabled))
        setEdgeAiMode(edgeAi.mode ?? '')
        setPreferNpu(triFrom(edgeAi.prefer_npu))
        setEdgeAiRunner(edgeAi.runner ?? '')
        setEdgeAiModel(edgeAi.model_path ?? '')
        setAdaptiveExposure(triFrom(adaptive.enabled))
        setEvStep(adaptive.step_ev != null ? String(adaptive.step_ev) : '')
      })
      .catch(() => setError('Kunne ikke hente kunde'))
      .finally(() => setLoading(false))
  }, [customerId])

  async function save() {
    setSaving(true)
    try {
      const quality = buildQualityOverride(customer?.config_overrides, {
        edgeAiEnabled,
        edgeAiMode,
        preferNpu,
        runner: edgeAiRunner,
        modelPath: edgeAiModel,
        adaptiveExposure,
        evStep,
      })
      const config_overrides: Record<string, any> = {
        ...(customer?.config_overrides ?? {}),
        bt_totp: btTotpSecret ? { secret: btTotpSecret, sid: btTotpSid || 'kunde' } : {},
      }
      if (Object.keys(quality).length) config_overrides.quality = quality
      else delete config_overrides.quality
      await api(`/api/admin/customers/${customerId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name, contact_name: contactName, contact_email: contactEmail, contact_phone: contactPhone, address, notes,
          config_overrides
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

  async function deleteCustomer() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await api(`/api/admin/customers/${customerId}`, { method: 'DELETE' })
      navigate('/')
    } catch (e: any) {
      setError(e.message === '400' ? 'Kan ikke slette — sites eksisterer under denne kunde' : 'Sletning fejlede')
      setConfirmDelete(false)
    }
  }

  async function createSite() {
    if (!newSiteName.trim()) return
    setCreatingSite(true)
    try {
      await api('/api/admin/sites', {
        method: 'POST',
        body: JSON.stringify({ customer_id: customerId, name: newSiteName.trim(), address: newSiteAddress.trim() })
      })
      // Reload
      const d = await api(`/api/admin/customers/${customerId}`)
      setCustomer(d)
      setNewSiteName('')
      setNewSiteAddress('')
      setShowNewSite(false)
    } catch {
      setError('Kunne ikke oprette site')
    } finally {
      setCreatingSite(false)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>
  if (error && !customer) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-500">{error}</div>
  if (!customer) return null

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Building2 className="w-4 h-4 text-sky-500" />
          <span className="text-gray-700 font-medium">{customer.name}</span>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      {/* Kunde info */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Kundeoplysninger</h2>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Firmanavn</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Kontaktperson</label>
              <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Fulde navn"
                value={contactName} onChange={e => setContactName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Telefon</label>
              <input type="tel" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="70 20 30 40"
                value={contactPhone} onChange={e => setContactPhone(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Email</label>
            <input type="email" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="kontakt@firma.dk"
              value={contactEmail} onChange={e => setContactEmail(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Faktureringsadresse</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Vejnavn 1, 1234 By"
              value={address} onChange={e => setAddress(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Noter</label>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2}
              placeholder="Interne noter om kunden..."
              value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
        </div>
      </div>

      {/* BT PAN TOTP — kunde-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">BT PAN TOTP — kunde-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Gælder alle kameraer hos denne kunde (overstyrer global/fabriksstandard, overstyres af site/kamera-lag).
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Secret (Base32)</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Tom = ingen kunde-override"
              value={btTotpSecret} onChange={e => setBtTotpSecret(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">SID</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="kunde-label"
              value={btTotpSid} onChange={e => setBtTotpSid(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Edge AI — kunde-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Edge QA AI — kunde-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Blank betyder arv fra globalt niveau. Site og kamera kan stadig overstyre.
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Edge AI</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiEnabled} onChange={e => setEdgeAiEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">AI mode</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiMode} onChange={e => setEdgeAiMode(e.target.value)}>
              <option value="">Arv</option>
              {AI_MODES.map(mode => <option key={mode} value={mode}>{mode}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Foretræk NPU</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={preferNpu} onChange={e => setPreferNpu(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Ja</option>
              <option value="false">Nej</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Adaptiv EV</label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={adaptiveExposure} onChange={e => setAdaptiveExposure(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">EV trin</label>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={evStep} onChange={e => setEvStep(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">NPU runner</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiRunner} onChange={e => setEdgeAiRunner(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">NPU modelsti</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiModel} onChange={e => setEdgeAiModel(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Sites */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Sites</h2>
          <button onClick={() => setShowNewSite(s => !s)}
            className="flex items-center gap-1.5 text-xs text-sky-500 hover:text-sky-700">
            <Plus className="w-3.5 h-3.5" />
            Nyt site
          </button>
        </div>

        {/* Nyt site form */}
        {showNewSite && (
          <div className="mb-4 p-4 bg-sky-50 rounded-lg border border-sky-100 space-y-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Site navn</label>
              <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="fx Nørreport Byggeplads"
                value={newSiteName} onChange={e => setNewSiteName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && createSite()} />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Adresse (valgfri)</label>
              <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Vejnavn 1, 1234 By"
                value={newSiteAddress} onChange={e => setNewSiteAddress(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && createSite()} />
            </div>
            <div className="flex gap-2">
              <button onClick={createSite} disabled={creatingSite || !newSiteName.trim()}
                className="px-3 py-1.5 bg-sky-500 text-white text-xs rounded-lg hover:bg-sky-600 disabled:opacity-50">
                {creatingSite ? 'Opretter…' : 'Opret site'}
              </button>
              <button onClick={() => setShowNewSite(false)}
                className="px-3 py-1.5 text-gray-500 text-xs rounded-lg hover:bg-gray-100">
                Annuller
              </button>
            </div>
          </div>
        )}

        {customer.sites.length === 0 && !showNewSite ? (
          <p className="text-sm text-gray-400 italic">Ingen sites oprettet</p>
        ) : (
          <div className="space-y-2">
            {customer.sites.map(s => (
              <Link key={s.id} to={`/sites/${s.id}`}
                className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors group">
                <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{s.name}</p>
                  {s.address && <p className="text-xs text-gray-400">{s.address}</p>}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <Camera className="w-3.5 h-3.5" />
                    {s.devices_count}
                  </span>
                  {s.gps_lat && s.gps_lon && (
                    <a href={`https://www.openstreetmap.org/?mlat=${s.gps_lat}&mlon=${s.gps_lon}&zoom=17`}
                      target="_blank" rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      className="hover:text-sky-500">🗺️</a>
                  )}
                  <ChevronRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-gray-400" />
                </div>
              </Link>
            ))}
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

        <button onClick={deleteCustomer}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors ${
            confirmDelete
              ? 'bg-red-500 text-white border-red-500 hover:bg-red-600'
              : 'text-red-400 border-red-200 hover:bg-red-50'
          }`}>
          <Trash2 className="w-4 h-4" />
          {confirmDelete ? 'Bekræft sletning' : 'Slet kunde'}
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
