import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Camera, Image as ImageIcon, Loader2 } from 'lucide-react'
import { getApiUrl } from '../api/client'
import { CaptureThumbnailCard } from '../components/CaptureThumbnailCard'
import { Lightbox } from './DevicePage'
import type { Capture } from '../types'

type CameraLocation = {
  id: string
  camera_name?: string
  customer_name?: string
  site_name?: string
  site_id?: string
  current_device_id?: string | null
}

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  }).then(async response => {
    if (!response.ok) throw new Error(`${response.status}`)
    return response.json()
  })
}

export function CameraLocationGalleryPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const [camera, setCamera] = useState<CameraLocation | null>(null)
  const [captures, setCaptures] = useState<Capture[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  useEffect(() => {
    if (!cameraId) return
    setLoading(true)
    setError(null)
    Promise.all([
      api('/api/admin/cameras'),
      api(`/api/admin/captures?camera_id=${encodeURIComponent(cameraId)}&limit=500`),
    ]).then(([allCameras, cameraCaptures]) => {
      setCamera((Array.isArray(allCameras) ? allCameras : []).find(entry => entry.id === cameraId) ?? null)
      setCaptures(Array.isArray(cameraCaptures) ? cameraCaptures : [])
    }).catch(() => setError('Billederne kunne ikke hentes')).finally(() => setLoading(false))
  }, [cameraId])

  const backUrl = camera?.site_id ? `/sites/${camera.site_id}` : '/'

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
            {camera?.current_device_id ? ` · Edge ${camera.current_device_id}` : ' · Ingen aktiv Edge tildelt'}
          </p>
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
