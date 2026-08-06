import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, ArrowRightLeft, Camera, CheckSquare, ChevronDown, ChevronUp, Download, Film, HardDrive, Image as ImageIcon, Loader2, Settings, ShieldAlert, Square, Trash2 } from 'lucide-react'
import { deleteCapturesBulk, getApiUrl, getDevices, pathSegment } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import { Lightbox } from './DevicePage'
import type { Capture, Device } from '../types'

type ExportVolume = { path: string; name: string; free_gb: number; total_gb: number }
type ExportDest = 'download' | 'volume' | 'path'

type CameraLocation = {
  id: string
  camera_name?: string
  customer_id?: string
  customer_name?: string
  site_name?: string
  site_id?: string
  current_device_id?: string | null
}

function api(path: string, options?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  }).then(async response => {
    if (!response.ok) throw new Error(`${response.status}`)
    return response.json()
  })
}

export function CameraLocationGalleryPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const { user } = useAuth()
  const [camera, setCamera] = useState<CameraLocation | null>(null)
  const [otherCameras, setOtherCameras] = useState<CameraLocation[]>([])
  const [captures, setCaptures] = useState<Capture[]>([])
  const [siteDevices, setSiteDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [manageOpen, setManageOpen] = useState(false)
  const [moveTargetId, setMoveTargetId] = useState('')
  const [moving, setMoving] = useState(false)
  const [moveError, setMoveError] = useState<string | null>(null)
  const [forceConfirmText, setForceConfirmText] = useState('')
  const [forceDeleting, setForceDeleting] = useState(false)
  const [forceError, setForceError] = useState<string | null>(null)
  const [exportVolumes, setExportVolumes] = useState<ExportVolume[]>([])
  const [exportDest, setExportDest] = useState<ExportDest>('download')
  const [exportVolumePath, setExportVolumePath] = useState('')
  const [exportCustomPath, setExportCustomPath] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportResult, setExportResult] = useState<string | null>(null)
  const [gdprConfirmText, setGdprConfirmText] = useState('')
  const [gdprDeleting, setGdprDeleting] = useState(false)
  const [gdprError, setGdprError] = useState<string | null>(null)
  const [selectMode, setSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkError, setBulkError] = useState<string | null>(null)

  function reload() {
    if (!cameraId) return
    setLoading(true)
    setError(null)
    Promise.all([
      api('/api/admin/cameras'),
      api(`/api/admin/captures?camera_id=${encodeURIComponent(cameraId)}&limit=500`),
      getDevices(),
    ]).then(([allCameras, cameraCaptures, allDevices]) => {
      const list: CameraLocation[] = Array.isArray(allCameras) ? allCameras : []
      const foundCamera = list.find(entry => entry.id === cameraId) ?? null
      setCamera(foundCamera)
      // Flyt-mål: samme kunde, ikke sig selv — flytning på tværs af kunder ville
      // være en tenant-lækage, ikke oprydning (håndhæves også i backend).
      setOtherCameras(list.filter(c => c.id !== cameraId && (!foundCamera?.customer_id || c.customer_id === foundCamera.customer_id)))
      setCaptures(Array.isArray(cameraCaptures) ? cameraCaptures : [])
      // Fysiske enheder på samme site — vist som genvej, uanset om denne
      // kameralokation formelt har en aktiv Edge-tildeling endnu.
      setSiteDevices(
        foundCamera?.site_id
          ? (Array.isArray(allDevices) ? allDevices : []).filter(d => d.site_id === foundCamera.site_id)
          : []
      )
    }).catch(() => setError('Billederne kunne ikke hentes')).finally(() => setLoading(false))
  }

  useEffect(reload, [cameraId])

  const backUrl = camera?.site_id ? `/sites/${camera.site_id}` : '/'
  const isAdmin = Boolean(user && ['super_admin', 'admin'].includes(user.role))
  const isSuperAdmin = user?.role === 'super_admin'
  const canDelete = Boolean(isAdmin && camera && !camera.current_device_id && captures.length === 0)
  const canGenerateTimelapse = isAdmin

  // 2026-08-06 (Peter): kameralokationen er den PERMANENTE enhed — billeder og
  // timelapse-generering skal altid være tilgængelige her, uanset om der aktuelt
  // er et Edge-device tilknyttet. Devices flyttes/udskiftes; lokationen og dens
  // optagelseshistorik (nu bundet til camera_id, ikke device_id) består. Denne
  // side redirecter derfor ALDRIG væk længere — se HANDOVER_LOG.md 2026-08-06.
  // Er der aktuelt et tilsluttet device, tilbydes et link til dets side som en
  // ekstra, valgfri indgang til device-specifik hardware-administration (SSH,
  // live diagnostik, netværkskonfig) — ikke som en påkrævet omvej.

  async function deleteEmptyLocation() {
    if (!cameraId || !camera || !confirm(`Fjern den tomme kameralokation "${camera.camera_name ?? cameraId}"? Dette påvirker ikke billeder.`)) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await api(`/api/admin/cameras/${encodeURIComponent(cameraId)}`, { method: 'DELETE' })
      window.location.assign(backUrl)
    } catch {
      setDeleteError('Kameralokationen kunne ikke fjernes. Den kan have billeder eller en aktiv Edge-binding.')
    } finally {
      setDeleting(false)
    }
  }

  async function moveCaptures() {
    if (!cameraId || !moveTargetId) return
    const target = otherCameras.find(c => c.id === moveTargetId)
    if (!confirm(`Flyt alle ${captures.length} billeder til "${target?.camera_name ?? moveTargetId}"? Dette kan ikke fortrydes.`)) return
    setMoving(true)
    setMoveError(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraId)}/move-captures`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_camera_id: moveTargetId }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      setMoveTargetId('')
      reload()
    } catch (e: any) {
      setMoveError(e?.message || 'Flytning fejlede')
    } finally {
      setMoving(false)
    }
  }

  function loadExportVolumes() {
    api('/api/admin/export/volumes').then(vols => setExportVolumes(Array.isArray(vols) ? vols : [])).catch(() => {})
  }

  function exportDestinationPayload(): { destination: string; path?: string } | null {
    if (exportDest === 'download') return { destination: 'download' }
    if (exportDest === 'volume') {
      if (!exportVolumePath) { setExportError('Vælg en tilsluttet disk'); return null }
      return { destination: 'path', path: exportVolumePath }
    }
    if (!exportCustomPath.trim()) { setExportError('Angiv en destinationssti'); return null }
    return { destination: 'path', path: exportCustomPath.trim() }
  }

  async function runExport(body: Record<string, unknown>) {
    setExporting(true)
    setExportError(null)
    setExportResult(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/admin/export/captures`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}))
        throw new Error(errBody.detail || `HTTP ${res.status}`)
      }
      if (body.destination === 'download') {
        const blob = await res.blob()
        const disposition = res.headers.get('Content-Disposition') ?? ''
        const match = /filename="?([^"]+)"?/.exec(disposition)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = match?.[1] ?? 'eksport.zip'
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        setExportResult('Download startet')
      } else {
        const result = await res.json()
        setExportResult(`${result.count} billeder skrevet til ${result.written_to}`)
      }
    } catch (e: any) {
      setExportError(e?.message || 'Eksport fejlede')
    } finally {
      setExporting(false)
    }
  }

  async function exportLocation() {
    if (!cameraId) return
    const dest = exportDestinationPayload()
    if (!dest) return
    await runExport({ camera_id: cameraId, ...dest })
  }

  async function exportSelection() {
    const dest = exportDestinationPayload()
    if (!dest) return
    await runExport({ capture_ids: [...selectedIds], ...dest })
  }

  async function gdprDeleteAllCaptures() {
    if (!cameraId || !camera) return
    setGdprDeleting(true)
    setGdprError(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraId)}/gdpr-delete-captures`, {
        method: 'DELETE', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deletion_details: 'GDPR-anmodning: hele kameralokationen' }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      setGdprConfirmText('')
      reload()
    } catch (e: any) {
      setGdprError(e?.message || 'GDPR-sletning fejlede')
    } finally {
      setGdprDeleting(false)
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function gdprDeleteSelected() {
    if (selectedIds.size === 0) return
    if (!confirm(`Slet ${selectedIds.size} valgte billeder permanent (fil + database) som GDPR-anmodning? Kan ikke fortrydes.`)) return
    setBulkBusy(true)
    setBulkError(null)
    try {
      await deleteCapturesBulk([...selectedIds], 'gdpr_request', 'Valgt i kameralokations-galleriet')
      setSelectedIds(new Set())
      setSelectMode(false)
      reload()
    } catch {
      setBulkError('Sletning fejlede')
    } finally {
      setBulkBusy(false)
    }
  }

  async function forceDeleteLocation() {
    if (!cameraId || !camera) return
    setForceDeleting(true)
    setForceError(null)
    try {
      const res = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraId)}/force`, {
        method: 'DELETE', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_name: forceConfirmText }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      window.location.assign(backUrl)
    } catch (e: any) {
      setForceError(e?.message || 'Sletning fejlede')
    } finally {
      setForceDeleting(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-start gap-3 mb-6">
        <Link to={backUrl} className="p-2 hover:bg-gray-100 rounded-lg" title="Tilbage til site">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Camera className="w-5 h-5 text-sky-600" />
            <h1 className="text-xl font-semibold text-gray-900">{camera?.camera_name ?? 'Kameralokation'}</h1>
            <div className="flex-1" />
            {canGenerateTimelapse && cameraId && (
              <Link to={`/camera-locations/${pathSegment(cameraId)}/timelapse`}
                className="inline-flex items-center gap-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                <Film className="w-4 h-4" />
                Generér timelapse
              </Link>
            )}
            {camera?.current_device_id && (
              <Link to={`/devices/${pathSegment(camera.current_device_id)}`}
                className="inline-flex items-center gap-1.5 border border-gray-200 hover:border-sky-300 hover:bg-sky-50 text-gray-700 hover:text-sky-700 rounded-lg px-3 py-1.5 text-sm font-medium"
                title="Enhedsadministration: live diagnostik, SSH, netværkskonfig">
                <Settings className="w-4 h-4" />
                Administrér Edge-enhed
              </Link>
            )}
          </div>
          <p className="text-sm text-gray-400 mt-1">
            {[camera?.customer_name, camera?.site_name].filter(Boolean).join(' · ')}
            {camera?.current_device_id ? (
              <> · Edge <Link to={`/devices/${pathSegment(camera.current_device_id)}`} className="text-sky-600 hover:underline font-medium">{camera.current_device_id}</Link></>
            ) : ' · Ingen aktiv Edge tildelt'}
          </p>
          {!camera?.current_device_id && siteDevices.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-gray-400">Fysiske enheder på dette site (endnu ikke tildelt dette kamera):</span>
              {siteDevices.map(d => (
                <Link key={d.device_id} to={`/devices/${pathSegment(d.device_id)}`}
                  className="inline-flex items-center gap-1.5 border border-gray-200 rounded-lg px-2.5 py-1 text-xs font-mono text-gray-700 hover:border-sky-300 hover:text-sky-700 hover:bg-sky-50">
                  <HardDrive className="w-3.5 h-3.5" />{d.device_id}
                </Link>
              ))}
            </div>
          )}
          {canDelete && (
            <button onClick={deleteEmptyLocation} disabled={deleting} className="mt-3 inline-flex items-center gap-1.5 border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 rounded-lg px-3 py-2 text-sm">
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Fjern tom kameralokation
            </button>
          )}
          {deleteError && <p className="mt-2 text-sm text-red-600">{deleteError}</p>}
          {isAdmin && (captures.length > 0 || isSuperAdmin) && (
            <button onClick={() => { setManageOpen(o => !o); if (!manageOpen) loadExportVolumes() }}
              className="mt-3 inline-flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600">
              {manageOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              Administrér kameralokation
            </button>
          )}
        </div>
      </div>

      {manageOpen && (
        <div className="mb-6 border border-gray-200 rounded-xl p-4 space-y-4">
          {captures.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-1">Eksportér billeder til koldt backup</p>
              <p className="text-xs text-gray-400 mb-2">
                Pakker alle {captures.length} billeder + metadata i en ZIP. Vælg destination:
              </p>
              <div className="flex flex-wrap items-center gap-3 mb-2 text-sm">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" checked={exportDest === 'download'} onChange={() => setExportDest('download')} />
                  Download via browser
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" checked={exportDest === 'volume'} onChange={() => setExportDest('volume')} disabled={exportVolumes.length === 0} />
                  Tilsluttet disk {exportVolumes.length === 0 && <span className="text-gray-300">(ingen fundet)</span>}
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" checked={exportDest === 'path'} onChange={() => setExportDest('path')} />
                  Fast sti på serveren
                </label>
              </div>
              {exportDest === 'volume' && (
                <select value={exportVolumePath} onChange={e => setExportVolumePath(e.target.value)}
                  className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-gray-700 mb-2 min-w-[16rem]">
                  <option value="">Vælg disk…</option>
                  {exportVolumes.map(v => (
                    <option key={v.path} value={v.path}>{v.name} — {v.free_gb} GB ledigt af {v.total_gb} GB</option>
                  ))}
                </select>
              )}
              {exportDest === 'path' && (
                <input type="text" value={exportCustomPath} onChange={e => setExportCustomPath(e.target.value)}
                  placeholder="/Volumes/Backup/timelapse-eksport eller anden fast sti"
                  className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm mb-2 min-w-[20rem] block" />
              )}
              <button onClick={exportLocation} disabled={exporting}
                className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Eksportér alle {captures.length} billeder
              </button>
              {exportError && <p className="mt-2 text-sm text-red-600">{exportError}</p>}
              {exportResult && <p className="mt-2 text-sm text-emerald-700">{exportResult}</p>}
            </div>
          )}
          {captures.length > 0 && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-amber-600" />
                GDPR-sletning af alle billeder på lokationen
              </p>
              <p className="text-xs text-gray-400 mb-2">
                Sletter samtlige {captures.length} billeder PERMANENT — fil, thumbnail og metadata på disk, ikke kun
                databasen. Selve kameralokationen består, og kan fortsat tage nye billeder. Brug ved en formel
                GDPR-anmodning ("retten til at blive glemt"), ikke ved en fejlagtig oprettelse (brug "Flyt billeder"
                eller "Slet permanent" til det).
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <input type="text" value={gdprConfirmText} onChange={e => setGdprConfirmText(e.target.value)}
                  placeholder={`Indtast "${camera?.camera_name ?? ''}" for at bekræfte`}
                  className="border border-amber-200 rounded-lg px-2.5 py-1.5 text-sm min-w-[16rem]" />
                <button onClick={gdprDeleteAllCaptures}
                  disabled={gdprDeleting || !camera || gdprConfirmText !== camera.camera_name}
                  className="inline-flex items-center gap-1.5 bg-amber-700 hover:bg-amber-800 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                  {gdprDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldAlert className="w-4 h-4" />}
                  GDPR-slet alle billeder
                </button>
              </div>
              {gdprError && <p className="mt-2 text-sm text-red-600">{gdprError}</p>}
            </div>
          )}
          {captures.length > 0 && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-sm font-medium text-gray-700 mb-1">Flyt billeder til en anden kameralokation</p>
              <p className="text-xs text-gray-400 mb-2">
                For en fejlagtigt oprettet eller forkert tildelt lokation — flytter alle {captures.length} billeder,
                sletter ikke data. Når lokationen er tom, kan den fjernes trygt ovenfor.
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <select value={moveTargetId} onChange={e => setMoveTargetId(e.target.value)}
                  className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-gray-700 min-w-[16rem]">
                  <option value="">Vælg mål-kameralokation…</option>
                  {otherCameras.map(c => (
                    <option key={c.id} value={c.id}>{c.camera_name} — {[c.site_name].filter(Boolean).join(', ')}</option>
                  ))}
                </select>
                <button onClick={moveCaptures} disabled={!moveTargetId || moving}
                  className="inline-flex items-center gap-1.5 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                  {moving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRightLeft className="w-4 h-4" />}
                  Flyt billeder
                </button>
              </div>
              {moveError && <p className="mt-2 text-sm text-red-600">{moveError}</p>}
            </div>
          )}
          {isSuperAdmin && (
            <div className="border-t border-red-100 pt-4">
              <p className="text-sm font-medium text-red-700 mb-1 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                Slet kameralokation permanent
              </p>
              <p className="text-xs text-gray-400 mb-2">
                Sletter lokationen og {captures.length > 0 ? `alle ${captures.length} billed-rækker` : 'lokationen'} fra
                databasen. Kan IKKE fortrydes. Billedfiler på disk slettes ikke. Brug kun dette hvis billederne selv
                også var en fejl — ellers brug "Flyt billeder" ovenfor.
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <input type="text" value={forceConfirmText} onChange={e => setForceConfirmText(e.target.value)}
                  placeholder={`Indtast "${camera?.camera_name ?? ''}" for at bekræfte`}
                  className="border border-red-200 rounded-lg px-2.5 py-1.5 text-sm min-w-[16rem]" />
                <button onClick={forceDeleteLocation}
                  disabled={forceDeleting || !camera || forceConfirmText !== camera.camera_name}
                  className="inline-flex items-center gap-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                  {forceDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  Slet permanent
                </button>
              </div>
              {forceError && <p className="mt-2 text-sm text-red-600">{forceError}</p>}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400"><Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />Indlæser billeder…</div>
      ) : error ? (
        <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      ) : captures.length === 0 ? (
        <div className="py-20 text-center text-gray-400"><ImageIcon className="w-8 h-8 mx-auto mb-3 text-gray-300" />Ingen billeder er endnu registreret på denne kameralokation.</div>
      ) : (
        <>
          <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
            <p className="text-sm text-gray-500">
              {selectMode
                ? `${selectedIds.size} af ${captures.length} billeder valgt`
                : `Viser de seneste ${captures.length} billeder. Klik på et billede for fuld størrelse og metadata.`}
            </p>
            <div className="flex items-center gap-2 flex-wrap">
              {selectMode && selectedIds.size > 0 && isAdmin && (
                <>
                  <button onClick={exportSelection} disabled={exporting}
                    className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                    {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                    Eksportér valgte
                  </button>
                  <button onClick={gdprDeleteSelected} disabled={bulkBusy}
                    className="inline-flex items-center gap-1.5 bg-amber-700 hover:bg-amber-800 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-sm font-medium">
                    {bulkBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldAlert className="w-4 h-4" />}
                    GDPR-slet valgte
                  </button>
                </>
              )}
              {isAdmin && (
                <button onClick={() => { setSelectMode(m => !m); setSelectedIds(new Set()) }}
                  className="inline-flex items-center gap-1.5 border border-gray-200 hover:border-sky-300 hover:bg-sky-50 text-gray-600 hover:text-sky-700 rounded-lg px-3 py-1.5 text-sm font-medium">
                  <CheckSquare className="w-4 h-4" />
                  {selectMode ? 'Afslut valg' : 'Vælg billeder'}
                </button>
              )}
            </div>
          </div>
          {bulkError && <p className="mb-3 text-sm text-red-600">{bulkError}</p>}
          {selectMode && exportDest === 'volume' && exportVolumes.length === 0 && (
            <p className="mb-3 text-xs text-gray-400">Tip: åbn "Administrér kameralokation" ovenfor for at vælge eksport-destination.</p>
          )}
          {exportError && selectMode && <p className="mb-3 text-sm text-red-600">{exportError}</p>}
          {exportResult && selectMode && <p className="mb-3 text-sm text-emerald-700">{exportResult}</p>}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {captures.map((capture, index) => (
              <CaptureThumbnailCard
                key={capture.id}
                capture={capture}
                compact
                selected={selectMode && selectedIds.has(capture.id)}
                onClick={() => selectMode ? toggleSelect(capture.id) : setLightboxIndex(index)}
                overlay={selectMode ? (
                  <div className="pointer-events-none absolute top-1.5 left-1.5">
                    {selectedIds.has(capture.id)
                      ? <CheckSquare className="w-5 h-5 text-sky-600 drop-shadow-[0_1px_2px_rgba(255,255,255,0.9)]" />
                      : <Square className="w-5 h-5 text-white/70 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />}
                  </div>
                ) : null}
              />
            ))}
          </div>
        </>
      )}
      {lightboxIndex !== null && <Lightbox captures={captures} index={lightboxIndex} onClose={() => setLightboxIndex(null)} />}
    </div>
  )
}
