import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Building2, MapPin, Save, Trash2, Plus, ChevronRight, CheckCircle, Camera } from 'lucide-react'
import { getApiUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'

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

interface CustomerRiskInput {
  id: number
  monthly_service_price: number
  currency: string
  effective_from: string
  effective_to: string | null
  source: string
  note: string | null
  validated_by: string
  validated_at: string
}

interface CustomerRiskProfile {
  id: number; version: number; status: string
  product_value_dkk: number | null; daily_downtime_cost_dkk: number | null
  recreation_cost_dkk: number | null; contractual_penalty_dkk: number | null
  business_dependency: number; availability_impact: number; integrity_impact: number; confidentiality_impact: number
  recovery_objective_hours: number | null; max_tolerable_downtime_hours: number | null
  personal_data_level: string; assumptions: string | null; submitted_by: string; submitted_at: string
  validated_by: string | null; validation_note: string | null
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
    vendorBinary: string
    adaptiveExposure: string
    evStep: string
    driftFocusEnabled: string
    driftFocusZ: string
    driftExposureEnabled: string
    driftExposureZ: string
    driftWbEnabled: string
    driftWbZ: string
  }
) {
  const quality = { ...(existingConfig?.quality ?? {}) }
  const edgeAi = { ...(quality.edge_ai ?? {}) }
  const adaptive = { ...(quality.adaptive_exposure ?? {}) }
  const drift = { ...(quality.drift_detection ?? {}) }
  const driftFocus = { ...(drift.focus ?? {}) }
  const driftExposure = { ...(drift.exposure ?? {}) }
  const driftWb = { ...(drift.white_balance ?? {}) }

  for (const key of ['enabled', 'mode', 'prefer_npu', 'runner', 'model_path', 'vendor_binary']) delete edgeAi[key]
  for (const key of ['enabled', 'step_ev']) delete adaptive[key]
  for (const obj of [driftFocus, driftExposure, driftWb]) {
    delete obj.enabled
    delete obj.z_threshold
  }

  const enabled = triTo(fields.edgeAiEnabled)
  const preferNpu = triTo(fields.preferNpu)
  if (enabled !== undefined) edgeAi.enabled = enabled
  if (fields.edgeAiMode) edgeAi.mode = fields.edgeAiMode
  if (preferNpu !== undefined) edgeAi.prefer_npu = preferNpu
  if (fields.runner.trim()) edgeAi.runner = fields.runner.trim()
  if (fields.modelPath.trim()) edgeAi.model_path = fields.modelPath.trim()
  if (fields.vendorBinary.trim()) edgeAi.vendor_binary = fields.vendorBinary.trim()

  const adaptiveEnabled = triTo(fields.adaptiveExposure)
  if (adaptiveEnabled !== undefined) adaptive.enabled = adaptiveEnabled
  if (fields.evStep.trim()) adaptive.step_ev = Number(fields.evStep)

  const driftFocusEnabled = triTo(fields.driftFocusEnabled)
  if (driftFocusEnabled !== undefined) driftFocus.enabled = driftFocusEnabled
  if (fields.driftFocusZ.trim()) driftFocus.z_threshold = Number(fields.driftFocusZ)

  const driftExposureEnabled = triTo(fields.driftExposureEnabled)
  if (driftExposureEnabled !== undefined) driftExposure.enabled = driftExposureEnabled
  if (fields.driftExposureZ.trim()) driftExposure.z_threshold = Number(fields.driftExposureZ)

  const driftWbEnabled = triTo(fields.driftWbEnabled)
  if (driftWbEnabled !== undefined) driftWb.enabled = driftWbEnabled
  if (fields.driftWbZ.trim()) driftWb.z_threshold = Number(fields.driftWbZ)

  if (Object.keys(edgeAi).length) quality.edge_ai = edgeAi
  else delete quality.edge_ai
  if (Object.keys(adaptive).length) quality.adaptive_exposure = adaptive
  else delete quality.adaptive_exposure
  if (Object.keys(driftFocus).length) drift.focus = driftFocus
  else delete drift.focus
  if (Object.keys(driftExposure).length) drift.exposure = driftExposure
  else delete drift.exposure
  if (Object.keys(driftWb).length) drift.white_balance = driftWb
  else delete drift.white_balance
  if (Object.keys(drift).length) quality.drift_detection = drift
  else delete quality.drift_detection
  return quality
}

export function CustomerPage() {
  const { customerId } = useParams<{ customerId: string }>()
  const { user } = useAuth()
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
  const [edgeAiVendorBinary, setEdgeAiVendorBinary] = useState('')
  const [adaptiveExposure, setAdaptiveExposure] = useState('')
  const [evStep, setEvStep]               = useState('')
  const [driftFocusEnabled, setDriftFocusEnabled]       = useState('')
  const [driftFocusZ, setDriftFocusZ]                   = useState('')
  const [driftExposureEnabled, setDriftExposureEnabled] = useState('')
  const [driftExposureZ, setDriftExposureZ]             = useState('')
  const [driftWbEnabled, setDriftWbEnabled]             = useState('')
  const [driftWbZ, setDriftWbZ]                         = useState('')
  const [riskInputs, setRiskInputs] = useState<{ current: CustomerRiskInput | null; history: CustomerRiskInput[] } | null>(null)
  const [monthlyPrice, setMonthlyPrice] = useState('')
  const [priceEffectiveFrom, setPriceEffectiveFrom] = useState(new Date().toISOString().slice(0, 10))
  const [priceSource, setPriceSource] = useState('customer_contract')
  const [priceNote, setPriceNote] = useState('')
  const [priceSaving, setPriceSaving] = useState(false)
  const [priceError, setPriceError] = useState('')
  const [riskProfileData, setRiskProfileData] = useState<{ validated: CustomerRiskProfile | null; pending: CustomerRiskProfile | null; history: CustomerRiskProfile[] } | null>(null)
  const [riskForm, setRiskForm] = useState({
    product_value_dkk: '', daily_downtime_cost_dkk: '', recreation_cost_dkk: '', contractual_penalty_dkk: '',
    business_dependency: '3', availability_impact: '3', integrity_impact: '3', confidentiality_impact: '3',
    recovery_objective_hours: '', max_tolerable_downtime_hours: '', personal_data_level: 'none', assumptions: '',
  })
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [decisionNote, setDecisionNote] = useState('')

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
        setEdgeAiVendorBinary(edgeAi.vendor_binary ?? '')
        setAdaptiveExposure(triFrom(adaptive.enabled))
        setEvStep(adaptive.step_ev != null ? String(adaptive.step_ev) : '')
        const drift = quality.drift_detection ?? {}
        const driftFocus = drift.focus ?? {}
        const driftExposure = drift.exposure ?? {}
        const driftWb = drift.white_balance ?? {}
        setDriftFocusEnabled(triFrom(driftFocus.enabled))
        setDriftFocusZ(driftFocus.z_threshold != null ? String(driftFocus.z_threshold) : '')
        setDriftExposureEnabled(triFrom(driftExposure.enabled))
        setDriftExposureZ(driftExposure.z_threshold != null ? String(driftExposure.z_threshold) : '')
        setDriftWbEnabled(triFrom(driftWb.enabled))
        setDriftWbZ(driftWb.z_threshold != null ? String(driftWb.z_threshold) : '')
      })
      .catch(() => setError('Kunne ikke hente kunde'))
      .finally(() => setLoading(false))
  }, [customerId])

  async function loadRiskInputs() {
    if (!customerId || user?.role !== 'super_admin') return
    try { setRiskInputs(await api(`/api/customer-risk/${customerId}`)) }
    catch { setRiskInputs(null) }
  }

  useEffect(() => { loadRiskInputs() }, [customerId, user?.role])

  async function loadRiskProfile() {
    if (!customerId || !['admin', 'super_admin'].includes(user?.role || '')) return
    try { setRiskProfileData(await api(`/api/customer-risk/profile/${customerId}`)) }
    catch { setRiskProfileData(null) }
  }

  useEffect(() => { loadRiskProfile() }, [customerId, user?.role])

  async function saveMonthlyPrice() {
    if (!customerId) return
    setPriceSaving(true); setPriceError('')
    try {
      await api(`/api/customer-risk/${customerId}`, {
        method: 'POST',
        body: JSON.stringify({
          monthly_service_price: Number(monthlyPrice), currency: 'DKK',
          effective_from: priceEffectiveFrom, source: priceSource, note: priceNote,
        }),
      })
      setMonthlyPrice(''); setPriceNote('')
      await loadRiskInputs()
    } catch (err) {
      setPriceError(`Kunne ikke gemme prisversion (${String(err)})`)
    } finally { setPriceSaving(false) }
  }

  async function submitRiskProfile() {
    if (!customerId) return
    setProfileSaving(true); setProfileError('')
    try {
      await api(`/api/customer-risk/profile/${customerId}`, { method: 'POST', body: JSON.stringify(riskForm) })
      await loadRiskProfile()
    } catch (err) { setProfileError(`Kunne ikke indsende risikoprofil (${String(err)})`) }
    finally { setProfileSaving(false) }
  }

  async function decideRiskProfile(decision: 'validated' | 'rejected') {
    if (!customerId || !riskProfileData?.pending) return
    setProfileSaving(true); setProfileError('')
    try {
      await api(`/api/customer-risk/profile/${customerId}/${riskProfileData.pending.id}/decision`, {
        method: 'POST', body: JSON.stringify({ decision, note: decisionNote }),
      })
      setDecisionNote(''); await loadRiskProfile()
    } catch (err) { setProfileError(`Kunne ikke behandle risikoprofil (${String(err)})`) }
    finally { setProfileSaving(false) }
  }

  async function save() {
    setSaving(true)
    try {
      const quality = buildQualityOverride(customer?.config_overrides, {
        edgeAiEnabled,
        edgeAiMode,
        preferNpu,
        runner: edgeAiRunner,
        modelPath: edgeAiModel,
        vendorBinary: edgeAiVendorBinary,
        adaptiveExposure,
        evStep,
        driftFocusEnabled,
        driftFocusZ,
        driftExposureEnabled,
        driftExposureZ,
        driftWbEnabled,
        driftWbZ,
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
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Firmanavn</label>
              <span className="text-xs text-gray-300 cursor-help" title="Navnet på kunden. Bruges til identifikation, rapportering og fakturering.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="text-xs text-gray-400">Kontaktperson</label>
                <span className="text-xs text-gray-300 cursor-help" title="Primær kontaktperson hos kunden. Bruges til kommunikation og support.">ⓘ</span>
              </div>
              <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Fulde navn"
                value={contactName} onChange={e => setContactName(e.target.value)} />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="text-xs text-gray-400">Telefon</label>
                <span className="text-xs text-gray-300 cursor-help" title="Telefonnummer til kontaktperson. Bruges til akutte henvendelser.">ⓘ</span>
              </div>
              <input type="tel" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                placeholder="70 20 30 40"
                value={contactPhone} onChange={e => setContactPhone(e.target.value)} />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Email</label>
              <span className="text-xs text-gray-300 cursor-help" title="Emailadresse til kontaktperson. Bruges til kommunikation og notifikationer.">ⓘ</span>
            </div>
            <input type="email" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="kontakt@firma.dk"
              value={contactEmail} onChange={e => setContactEmail(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Faktureringsadresse</label>
              <span className="text-xs text-gray-300 cursor-help" title="Fysisk adresse til fakturering og korrespondance.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Vejnavn 1, 1234 By"
              value={address} onChange={e => setAddress(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Noter</label>
              <span className="text-xs text-gray-300 cursor-help" title="Interne noter om kunden. Kun synligt for admin-brugere.">ⓘ</span>
            </div>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2}
              placeholder="Interne noter om kunden..."
              value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
        </div>
      </div>

      {user?.role === 'super_admin' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700">Kommercielt risikoinput</h2>
          <p className="text-xs text-gray-400 mt-1 mb-4">Månedsprisen historiseres og bruges senere som dokumenteret eksponeringsproxy i FAIR. Den er ikke i sig selv et tabsestimat.</p>
          {riskInputs?.current ? (
            <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded border border-emerald-100 bg-emerald-50 px-3 py-2">
              <span className="text-lg font-semibold text-emerald-900">{riskInputs.current.monthly_service_price.toLocaleString('da-DK', { minimumFractionDigits: 2 })} DKK/md.</span>
              <span className="text-xs text-emerald-700">Fra {riskInputs.current.effective_from} · {riskInputs.current.source} · valideret af {riskInputs.current.validated_by}</span>
            </div>
          ) : <p className="mb-4 text-xs text-amber-700">Der er endnu ingen valideret månedspris.</p>}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <label className="text-xs text-gray-500">Månedspris (DKK)
              <input type="number" min="0.01" step="0.01" value={monthlyPrice} onChange={e => setMonthlyPrice(e.target.value)} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-gray-500">Ikrafttrædelse
              <input type="date" value={priceEffectiveFrom} onChange={e => setPriceEffectiveFrom(e.target.value)} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-gray-500">Kilde
              <select value={priceSource} onChange={e => setPriceSource(e.target.value)} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm">
                <option value="customer_contract">Kundekontrakt</option>
                <option value="approved_quote">Godkendt tilbud</option>
                <option value="finance_system">Økonomisystem</option>
              </select>
            </label>
            <label className="text-xs text-gray-500">Reference/note
              <input value={priceNote} onChange={e => setPriceNote(e.target.value)} placeholder="Kontrakt eller sag" className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
            </label>
          </div>
          {priceError && <p className="mt-2 text-xs text-red-600">{priceError}</p>}
          <button onClick={saveMonthlyPrice} disabled={priceSaving || !monthlyPrice || !priceEffectiveFrom} className="mt-3 px-3 py-2 rounded bg-slate-900 text-white text-xs disabled:opacity-40">
            {priceSaving ? 'Gemmer…' : 'Opret ny prisversion'}
          </button>
          {(riskInputs?.history.length ?? 0) > 1 && (
            <details className="mt-4 border-t border-gray-100 pt-3">
              <summary className="text-xs text-sky-700 cursor-pointer">Vis prishistorik ({riskInputs?.history.length})</summary>
              <div className="mt-2 divide-y divide-gray-100 text-xs">
                {riskInputs?.history.map(row => (
                  <div key={row.id} className="grid grid-cols-4 gap-3 py-2">
                    <span>{row.monthly_service_price.toLocaleString('da-DK', { minimumFractionDigits: 2 })} {row.currency}</span>
                    <span>{row.effective_from} – {row.effective_to || 'aktiv'}</span>
                    <span>{row.source}</span><span>{row.validated_by}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {['admin', 'super_admin'].includes(user?.role || '') && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700">Kundens forretningsmæssige risikoprofil</h2>
          <p className="text-xs text-gray-400 mt-1 mb-4">Kunden angiver værdi, afhængighed og konsekvenser. En indsendt version anvendes først som valideret FAIR-input efter platformgodkendelse.</p>
          {riskProfileData?.validated && (
            <div className="mb-4 rounded border border-emerald-100 bg-emerald-50 p-3 text-xs text-emerald-800">
              Valideret profil v{riskProfileData.validated.version}: produktværdi {riskProfileData.validated.product_value_dkk?.toLocaleString('da-DK') ?? 'ikke angivet'} DKK · afhængighed {riskProfileData.validated.business_dependency}/5 · tilgængelighed {riskProfileData.validated.availability_impact}/5
            </div>
          )}
          {riskProfileData?.pending ? (
            <div className="rounded border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-medium text-amber-900">Version {riskProfileData.pending.version} afventer validering</p>
              <p className="mt-1 text-xs text-amber-800">Indsendt af {riskProfileData.pending.submitted_by}. Produktværdi: {riskProfileData.pending.product_value_dkk?.toLocaleString('da-DK') ?? 'ikke angivet'} DKK. Afhængighed/tilgængelighed/integritet/fortrolighed: {riskProfileData.pending.business_dependency}/{riskProfileData.pending.availability_impact}/{riskProfileData.pending.integrity_impact}/{riskProfileData.pending.confidentiality_impact}.</p>
              {user?.role === 'super_admin' && (
                <div className="mt-3">
                  <input value={decisionNote} onChange={e => setDecisionNote(e.target.value)} placeholder="Valideringsnote" className="w-full border border-amber-200 rounded px-3 py-2 text-sm" />
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => decideRiskProfile('validated')} disabled={profileSaving} className="px-3 py-1.5 rounded bg-emerald-600 text-white text-xs">Valider</button>
                    <button onClick={() => decideRiskProfile('rejected')} disabled={profileSaving || !decisionNote.trim()} className="px-3 py-1.5 rounded border border-red-200 text-red-700 text-xs">Afvis</button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                {([
                  ['product_value_dkk', 'Produktets/projektets værdi (DKK)'], ['daily_downtime_cost_dkk', 'Nedetidsomkostning pr. dag'],
                  ['recreation_cost_dkk', 'Genskabelsesomkostning'], ['contractual_penalty_dkk', 'Kontraktuelle bod/krav'],
                ] as const).map(([key, label]) => (
                  <label key={key} className="text-xs text-gray-500">{label}
                    <input type="number" min="0" value={riskForm[key]} onChange={e => setRiskForm(v => ({ ...v, [key]: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
                  </label>
                ))}
                {([
                  ['business_dependency', 'Forretningsafhængighed'], ['availability_impact', 'Tilgængelighedskonsekvens'],
                  ['integrity_impact', 'Integritetskonsekvens'], ['confidentiality_impact', 'Fortrolighedskonsekvens'],
                ] as const).map(([key, label]) => (
                  <label key={key} className="text-xs text-gray-500">{label} (1-5)
                    <select value={riskForm[key]} onChange={e => setRiskForm(v => ({ ...v, [key]: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm">
                      {[1,2,3,4,5].map(value => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </label>
                ))}
                <label className="text-xs text-gray-500">Recovery objective (timer)
                  <input type="number" min="0" value={riskForm.recovery_objective_hours} onChange={e => setRiskForm(v => ({ ...v, recovery_objective_hours: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
                </label>
                <label className="text-xs text-gray-500">Maksimal tolerabel nedetid (timer)
                  <input type="number" min="0" value={riskForm.max_tolerable_downtime_hours} onChange={e => setRiskForm(v => ({ ...v, max_tolerable_downtime_hours: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
                </label>
                <label className="text-xs text-gray-500">Persondata
                  <select value={riskForm.personal_data_level} onChange={e => setRiskForm(v => ({ ...v, personal_data_level: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm">
                    <option value="none">Ingen</option><option value="limited">Begrænset</option><option value="significant">Betydelig</option><option value="special_category">Særlige kategorier</option>
                  </select>
                </label>
                <label className="text-xs text-gray-500 md:col-span-1">Antagelser og kontekst
                  <input value={riskForm.assumptions} onChange={e => setRiskForm(v => ({ ...v, assumptions: e.target.value }))} className="mt-1 w-full border border-gray-200 rounded px-3 py-2 text-sm" />
                </label>
              </div>
              <button onClick={submitRiskProfile} disabled={profileSaving} className="mt-3 px-3 py-2 rounded bg-slate-900 text-white text-xs disabled:opacity-40">Indsend ny risikoprofil til validering</button>
            </>
          )}
          {profileError && <p className="mt-2 text-xs text-red-600">{profileError}</p>}
          {(riskProfileData?.history.length ?? 0) > 0 && <p className="mt-3 text-[11px] text-gray-400">{riskProfileData?.history.length} version(er) bevaret som audit-evidens.</p>}
        </div>
      )}

      {/* BT PAN TOTP — kunde-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">BT PAN TOTP — kunde-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Gælder alle kameraer hos denne kunde (overstyrer global/fabriksstandard, overstyres af site/kamera-lag).
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Secret (Base32)</label>
              <span className="text-xs text-gray-300 cursor-help" title="TOTP secret til Bluetooth PAN auth. Base32 encoded. Tom = arv fra global. Overstyres af site/kamera.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Tom = ingen kunde-override"
              value={btTotpSecret} onChange={e => setBtTotpSecret(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">SID</label>
              <span className="text-xs text-gray-300 cursor-help" title="Unikt kunde ID til TOTP authentication. Identificerer kunden i TOTP systemet. Tom = brug kundenavn.">ⓘ</span>
            </div>
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
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Edge AI</label>
              <span className="text-xs text-gray-300 cursor-help" title="Aktiverer AI-baseret kvalitetsanalyse på edge. Sløring, mørk, lens obstruction. Anbefales altid.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiEnabled} onChange={e => setEdgeAiEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">AI mode</label>
              <span className="text-xs text-gray-300 cursor-help" title="AI adfærd: off, monitor (log kun), assist (advar), autonomous (rett), npu_first, lab. Assist anbefales.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={edgeAiMode} onChange={e => setEdgeAiMode(e.target.value)}>
              <option value="">Arv</option>
              {AI_MODES.map(mode => <option key={mode} value={mode}>{mode}</option>)}
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Foretræk NPU</label>
              <span className="text-xs text-gray-300 cursor-help" title="Brug hardware accelerator (NPU) frem for CPU. Hurtigere og mindre strøm. Anbefales til NPU-hardware.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={preferNpu} onChange={e => setPreferNpu(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Ja</option>
              <option value="false">Nej</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Adaptiv EV</label>
              <span className="text-xs text-gray-300 cursor-help" title="Auto-juster EV baseret på brightness. Kompenserer for skygge, sol, overskyet. Anbefales ved variable lys.">ⓘ</span>
            </div>
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
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">EV trin</label>
              <span className="text-xs text-gray-300 cursor-help" title="EV step per justering (0.1-3.0). Mindre = finere justering men flere cycles. Typisk 0.3-0.7.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={evStep} onChange={e => setEvStep(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">NPU runner</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til NPU runner script. Standard path er korrekt for default installation.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiRunner} onChange={e => setEdgeAiRunner(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">NPU modelsti</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til NPU model fil (.nb format). Tom = brug built-in model. Ændres kun ved custom models.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiModel} onChange={e => setEdgeAiModel(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">VIPLite wrapper</label>
              <span className="text-xs text-gray-300 cursor-help" title="Sti til vendor NPU wrapper (VIPLite). Tom = brug built-in wrapper. Ændres kun ved custom driver.">ⓘ</span>
            </div>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={edgeAiVendorBinary} onChange={e => setEdgeAiVendorBinary(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Drift-detektion — kunde-lag */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Drift-detektion — kunde-override</h2>
        <p className="text-xs text-gray-400 mb-4">
          Alarmerer hvis fokus/eksponering/hvidbalance systematisk skifter over tid for et kamera. Blank betyder arv fra globalt niveau.
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Fokus-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis skarphed systematisk falder. Detekterer manuel fokus der glider (vibration, temperatur).">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftFocusEnabled} onChange={e => setDriftFocusEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Fokus-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.0-4.0). Lavere = mere følsom. Typisk 2.0-3.0.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftFocusZ} onChange={e => setDriftFocusZ(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Eksponerings-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis eksponering systematisk skifter. Detekterer støv, tåge, sæson ændringer.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftExposureEnabled} onChange={e => setDriftExposureEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Eksponerings-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.5-4.0). Højere end focus da lysstyrke varierer mere.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftExposureZ} onChange={e => setDriftExposureZ(e.target.value)} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Hvidbalance-drift-alarm</label>
              <span className="text-xs text-gray-300 cursor-help" title="Alarmer hvis hvidbalance systematisk skifter. Kræver at edge-optimizer rapporterer hvidbalance-data.">ⓘ</span>
            </div>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={driftWbEnabled} onChange={e => setDriftWbEnabled(e.target.value)}>
              <option value="">Arv</option>
              <option value="true">Aktiver</option>
              <option value="false">Deaktiver</option>
            </select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs text-gray-400">Hvidbalance-følsomhed</label>
              <span className="text-xs text-gray-300 cursor-help" title="Antal standardafvigelser før alarm (2.0-3.0). Typisk 2.0-3.0.">ⓘ</span>
            </div>
            <input type="number" step="0.1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="Arv"
              value={driftWbZ} onChange={e => setDriftWbZ(e.target.value)} />
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
