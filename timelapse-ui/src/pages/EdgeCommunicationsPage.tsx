import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Filter, RefreshCw,
  Router, Search, Shield, XCircle,
} from 'lucide-react'
import { getApiUrl } from '../api/client'

interface DeviceOption {
  device_id: string
  label: string | null
  customer_name: string | null
  site_name: string | null
  last_seen: string | null
}

interface CommunicationRow {
  id: number
  created_at: string | null
  device_id: string | null
  direction: string
  method: string
  path: string
  query_string: string | null
  status_code: number | null
  transport_scheme: string | null
  transport_security: 'encrypted' | 'unencrypted' | 'unknown' | string
  client_host: string | null
  user_agent: string | null
  request_content_type: string | null
  request_bytes: number | null
  request_body_truncated: boolean
  request_body: unknown
  interpretation: string | null
}

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`, { credentials: 'include' }).then(async response => {
    if (!response.ok) {
      let detail = `${response.status}`
      try {
        const payload = await response.json()
        detail = payload.detail || JSON.stringify(payload)
      } catch { /* ignore */ }
      throw new Error(detail)
    }
    return response.json()
  })
}

function fmtDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString('da-DK', { dateStyle: 'short', timeStyle: 'medium' })
}

function fmtJson(value: unknown) {
  if (value === null || value === undefined || value === '') return 'Ingen JSON payload gemt'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function TransportBadge({ value }: { value: string }) {
  if (value === 'encrypted') {
    return <span className="inline-flex items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700"><Shield className="h-3 w-3" />Krypteret</span>
  }
  if (value === 'unencrypted') {
    return <span className="inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"><AlertTriangle className="h-3 w-3" />Ukrypteret</span>
  }
  return <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600"><XCircle className="h-3 w-3" />Ukendt</span>
}

function StatusBadge({ code }: { code: number | null }) {
  if (!code) return <span className="text-xs text-slate-400">—</span>
  const ok = code < 400
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      {code}
    </span>
  )
}

export function EdgeCommunicationsPage() {
  const [devices, setDevices] = useState<DeviceOption[]>([])
  const [rows, setRows] = useState<CommunicationRow[]>([])
  const [deviceId, setDeviceId] = useState('')
  const [transport, setTransport] = useState('')
  const [search, setSearch] = useState('')
  const [limit, setLimit] = useState(200)
  const [selected, setSelected] = useState<CommunicationRow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: String(limit) })
      if (deviceId) params.set('device_id', deviceId)
      if (transport) params.set('transport_security', transport)
      const [deviceData, rowData] = await Promise.all([
        api('/api/admin/edge-communications/devices'),
        api(`/api/admin/edge-communications?${params}`),
      ])
      setDevices(deviceData)
      setRows(rowData)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kunne ikke hente kommunikationsdata')
    } finally {
      setLoading(false)
    }
  }, [deviceId, transport, limit])

  useEffect(() => { load() }, [load])

  const filteredRows = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter(row =>
      [row.device_id, row.path, row.method, row.transport_security, row.interpretation, fmtJson(row.request_body)]
        .some(value => String(value || '').toLowerCase().includes(needle))
    )
  }, [rows, search])

  const encrypted = rows.filter(row => row.transport_security === 'encrypted').length
  const unencrypted = rows.filter(row => row.transport_security === 'unencrypted').length
  const failing = rows.filter(row => (row.status_code || 0) >= 400).length

  function exportExcel() {
    const params = new URLSearchParams({ limit: String(Math.max(limit, 1000)) })
    if (deviceId) params.set('device_id', deviceId)
    if (transport) params.set('transport_security', transport)
    window.location.href = `${getApiUrl()}/api/admin/edge-communications/export.xlsx?${params}`
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm font-medium text-sky-700">
            <Router className="h-4 w-4" />
            Edge til Headend
          </div>
          <h1 className="text-2xl font-semibold text-slate-900">Kommunikations-debug</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Sanitiserede API-observationer fra Edge-kald. Secrets og private nøgler vises ikke.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={load} className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Opdater
          </button>
          <button onClick={exportExcel} className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800">
            <FileSpreadsheet className="h-4 w-4" />
            Excel
          </button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="text-xs font-medium text-emerald-700">Krypterede observationer</div>
          <div className="mt-1 text-2xl font-semibold text-emerald-900">{encrypted}</div>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs font-medium text-amber-700">Ukrypterede observationer</div>
          <div className="mt-1 text-2xl font-semibold text-amber-900">{unencrypted}</div>
        </div>
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
          <div className="text-xs font-medium text-rose-700">Fejlstatus</div>
          <div className="mt-1 text-2xl font-semibold text-rose-900">{failing}</div>
        </div>
      </div>

      <div className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-3 lg:grid-cols-[1.4fr_1fr_1fr_auto]">
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-600"><Filter className="h-3 w-3" />Edge</span>
          <select value={deviceId} onChange={event => setDeviceId(event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="">Alle Edges</option>
            {devices.map(device => (
              <option key={device.device_id} value={device.device_id}>
                {device.device_id}{device.site_name ? ` · ${device.site_name}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Transport</span>
          <select value={transport} onChange={event => setTransport(event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="">Alle</option>
            <option value="encrypted">Krypteret</option>
            <option value="unencrypted">Ukrypteret</option>
            <option value="unknown">Ukendt</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-600"><Search className="h-3 w-3" />Søg</span>
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Path, status, payload..." className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Antal</span>
          <select value={limit} onChange={event => setLimit(Number(event.target.value))} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value={100}>100</option>
            <option value={200}>200</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
          </select>
        </label>
      </div>

      {error && <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Tid</th>
                <th className="px-3 py-2">Edge</th>
                <th className="px-3 py-2">Kald</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Transport</th>
                <th className="px-3 py-2">Fortolkning</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map(row => (
                <tr key={row.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="whitespace-nowrap px-3 py-2 text-slate-600">{fmtDate(row.created_at)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{row.device_id || '—'}</td>
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs text-slate-900">{row.method} {row.path}</div>
                    {row.query_string && <div className="font-mono text-[11px] text-slate-400">?{row.query_string}</div>}
                  </td>
                  <td className="px-3 py-2"><StatusBadge code={row.status_code} /></td>
                  <td className="px-3 py-2"><TransportBadge value={row.transport_security} /></td>
                  <td className="max-w-xl px-3 py-2 text-xs text-slate-600">{row.interpretation}</td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => setSelected(row)} className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100">
                      <Download className="h-3 w-3" />
                      Rå data
                    </button>
                  </td>
                </tr>
              ))}
              {!filteredRows.length && (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-sm text-slate-500">{loading ? 'Indlæser...' : 'Ingen observationer matcher filteret endnu.'}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <div className="max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-lg bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 className="font-semibold text-slate-900">Rå kommunikationsdata</h2>
                <p className="text-xs text-slate-500">{selected.method} {selected.path}</p>
              </div>
              <button onClick={() => setSelected(null)} className="rounded-md p-2 text-slate-500 hover:bg-slate-100">Luk</button>
            </div>
            <div className="grid max-h-[calc(85vh-64px)] gap-4 overflow-y-auto p-4 lg:grid-cols-[1fr_1.3fr]">
              <div className="space-y-3 text-sm">
                <div><div className="text-xs font-medium text-slate-500">Edge</div><div className="font-mono">{selected.device_id || '—'}</div></div>
                <div><div className="text-xs font-medium text-slate-500">Tidspunkt</div><div>{fmtDate(selected.created_at)}</div></div>
                <div><div className="text-xs font-medium text-slate-500">Transport</div><div className="mt-1"><TransportBadge value={selected.transport_security} /></div></div>
                <div><div className="text-xs font-medium text-slate-500">Klient</div><div className="break-all">{selected.client_host || '—'}</div></div>
                <div><div className="text-xs font-medium text-slate-500">Fortolkning</div><div className="text-slate-700">{selected.interpretation}</div></div>
              </div>
              <pre className="max-h-[60vh] overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{fmtJson(selected.request_body)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
