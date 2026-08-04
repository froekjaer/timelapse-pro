import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Camera, HardDrive, Image as ImageIcon, Loader2, Trash2 } from 'lucide-react'
import { getApiUrl, getDevices, pathSegment } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import { Lightbox } from './DevicePage'
import type { Capture, Device } from '../types'

type CameraLocation = {
  id: string
  camera_name?: string
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
  const [captures, setCaptures] = useState<Capture[]>([])
  const [siteDevices, setSiteDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    if (!cameraId) return
    setLoading(true)
    setError(null)
    Promise.all([
      api('/api/admin/cameras'),
      api(`/api/admin/captures?camera_id=${encodeURIComponent(cameraId)}&limit=500`),
      getDevices(),
    ]).then(([allCameras, cameraCaptures, allDevices]) => {
      const foundCamera = (Array.isArray(allCameras) ? allCameras : []).find(entry => entry.id === cameraId) ?? null
      setCamera(foundCamera)
      setCaptures(Array.isArray(cameraCaptures) ? cameraCaptures : [])
      // Fysiske enheder på samme site — vist som genvej, uanset om denne
      // kameralokation formelt har en aktiv Edge-tildeling endnu.
      setSiteDevices(
        foundCamera?.site_id
          ? (Array.isArray(allDevices) ? allDevices : []).filter(d => d.site_id === foundCamera.site_id)
          : []
      )
    }).catch(() => setError('Billederne kunne ikke hentes')).finally(() => setLoading(false))
  }, [cameraId])

  const backUrl = camera?.site_id ? `/sites/${camera.site_id}` : '/'
  const canDelete = Boolean(user && ['super_admin', 'admin'].includes(user.role) && camera && !camera.current_device_id && captures.length === 0)

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

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-start gap-3 mb-6">
        <Link to={backUrl} className="p-2 hover:bg-gray-100 rounded-lg" title="Tilbage til site">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-sky-600" />
            <h1 className="text-xl font-semibold text-gray-900">{camera?.camera_name ?? 'Kameralokation'}</h1>
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
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-gray-400"><Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />Indlæser billeder…</div>
      ) : error ? (
        <div className="border border-red-200 bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      ) : captures.length === 0 ? (
        <div className="py-20 text-center text-gray-400"><ImageIcon className="w-8 h-8 mx-auto mb-3 text-gray-300" />Ingen billeder er endnu registreret på denne kameralokation.</div>
      ) : (
        <>
          <p className="text-sm text-gray-500 mb-4">Viser de seneste {captures.length} billeder. Klik på et billede for fuld størrelse og metadata.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {captures.map((capture, index) => (
              <CaptureThumbnailCard key={capture.id} capture={capture} onClick={() => setLightboxIndex(index)} compact />
            ))}
          </div>
        </>
      )}
      {lightboxIndex !== null && <Lightbox captures={captures} index={lightboxIndex} onClose={() => setLightboxIndex(null)} />}
    </div>
  )
}
