/**
 * Admin-oversigt over BT PAN TOTP-status for alle kameraer denne bruger har
 * adgang til (RBAC håndhævet server-side, se headend/local_access.py).
 *
 * Bygget 2026-08-19 efter Peter: "alle enheder der er konfigureret en TOTP
 * kode til [skal være] tilgængelige, og kan ses (jfr. RBAC)." Viser ikke
 * selve QR-koden/den live kode her — de findes allerede på kameraets egen
 * side (CameraPage) og duplikeres bevidst ikke; denne side er kun til at
 * hurtigt finde det rigtige kamera.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, QrCode, RefreshCw } from 'lucide-react'
import { getApiUrl } from '../api/client'
import { InfoTooltip } from '../components/InfoTooltip'

interface LocalAccessRow {
  camera_id: string
  camera_name: string
  device_id: string | null
  customer_name: string | null
  site_name: string | null
  sid: string | null
  source: 'global' | 'kunde' | 'site' | 'kamera' | 'unprovisioned'
}

const SOURCE_LABEL: Record<string, string> = {
  global:        '🌐 Global',
  kunde:         '🏢 Kunde',
  site:          '📍 Site',
  kamera:        '📷 Kamera',
  unprovisioned: '⚠️ Ikke oprettet',
}

const SOURCE_COLOR: Record<string, string> = {
  global:        'bg-purple-50 text-purple-700 border-purple-200',
  kunde:         'bg-blue-50 text-blue-700 border-blue-200',
  site:          'bg-teal-50 text-teal-700 border-teal-200',
  kamera:        'bg-green-50 text-green-700 border-green-200',
  unprovisioned: 'bg-amber-50 text-amber-700 border-amber-200',
}

export function LocalAccessOverviewPage() {
  const [rows, setRows]       = useState<LocalAccessRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/local-access`, { credentials: 'include' })
      if (!r.ok) throw new Error(`${r.status}`)
      setRows(await r.json())
    } catch {
      setError('Kunne ikke hente lokal adgang-oversigten')
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <QrCode className="w-5 h-5 text-gray-500" />
            Lokal adgang (BT PAN TOTP)
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Alle kameraer du har adgang til, og hvilket niveau deres lokale TOTP-adgang resolver fra.
            QR-kode og live kode åbnes fra det enkelte kamera.
          </p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white text-gray-700 border border-gray-200 rounded-lg disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Genindlæs
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 mb-4 text-sm text-amber-900">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="text-left px-4 py-2.5">Kunde</th>
              <th className="text-left px-4 py-2.5">Site</th>
              <th className="text-left px-4 py-2.5">Kamera</th>
              <th className="text-left px-4 py-2.5">Enhed</th>
              <th className="text-left px-4 py-2.5"><span className="inline-flex items-center gap-1">SID
                <InfoTooltip label="SID" text={'Session-ID for den lokale adgangs-binding.\nIdentificerer hvilken TOTP-nøgle kameraet bruger til Bluetooth-adgang.'} />
              </span></th>
              <th className="text-left px-4 py-2.5"><span className="inline-flex items-center gap-1">Kilde
                <InfoTooltip label="Kilde" text={'Hvilket konfigurationslag nøglen kommer fra.\nGlobal → Kunde → Site → Kamera: mest specifikke lag vinder.\nKamera-niveau giver unik adgang pr. kamera.'} />
              </span></th>
              <th className="text-right px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map(row => (
              <tr key={row.camera_id} className="hover:bg-gray-50">
                <td className="px-4 py-2.5 text-gray-600">{row.customer_name ?? '—'}</td>
                <td className="px-4 py-2.5 text-gray-600">{row.site_name ?? '—'}</td>
                <td className="px-4 py-2.5 font-medium text-gray-800">{row.camera_name}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{row.device_id ?? '—'}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-gray-400">{row.sid ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${SOURCE_COLOR[row.source]}`}>
                    {SOURCE_LABEL[row.source]}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {row.device_id && (
                    <Link to={`/cameras/${encodeURIComponent(row.device_id)}`}
                      className="text-xs font-medium text-sky-600 hover:text-sky-700">
                      Vis QR / kode →
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && !error && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">Ingen kameraer fundet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
