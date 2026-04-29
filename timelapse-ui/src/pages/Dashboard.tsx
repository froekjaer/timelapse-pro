import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Camera, Building2, MapPin, ChevronRight, Plus, CheckCircle, AlertCircle, Clock, Settings } from 'lucide-react'
import { getStats, getDevices, getApiUrl } from '../api/client'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import type { Stats, Device } from '../types'

interface Customer {
  id: string
  name: string
  contact_name?: string
  contact_email?: string
  sites_count: number
  config_overrides: Record<string, unknown>
}

interface Site {
  id: string
  customer_id: string
  customer_name: string
  name: string
  address?: string
  gps_lat?: number
  gps_lon?: number
  timezone: string
  devices_count: number
}

function api(path: string) {
  return fetch(`${getApiUrl()}${path}`).then(r => r.json())
}

const TZ = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

function DeviceRow({ device }: { device: Device }) {
  const lastSeen = device.last_seen
    ? new Date(device.last_seen + 'Z').toLocaleString('da-DK', { timeZone: TZ(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : null
  return (
    <Link to={`/devices/${device.device_id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors rounded-lg group">
      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
        <Camera className="w-4 h-4 text-slate-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {device.camera_name || device.location_name || device.device_id}
        </p>
        <p className="text-xs text-gray-400 font-mono">{device.device_id}</p>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-400">
        {lastSeen && <span className="hidden sm:block">{lastSeen}</span>}
        <StatusBadge status={device.status} />
        <ChevronRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-gray-400" />
      </div>
    </Link>
  )
}

function SiteCard({ site, devices }: { site: Site; devices: Device[] }) {
  const siteDevices = devices.filter(d => {
    // Match via customer_name + site_name da vi ikke har site_id i Device type endnu
    return d.site_name === site.name && d.customer_name === site.customer_name
  })
  const online = siteDevices.filter(d => d.status === 'online').length
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden mb-3">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left">
        <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-gray-800">{site.name}</span>
          {site.address && <span className="text-xs text-gray-400 ml-2">{site.address}</span>}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {site.gps_lat && site.gps_lon && (
            <a href={`https://www.openstreetmap.org/?mlat=${site.gps_lat}&mlon=${site.gps_lon}&zoom=17`}
              target="_blank" rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="hidden sm:flex items-center gap-1 hover:text-sky-500">
              🗺️ Kort
            </a>
          )}
          <span className={`flex items-center gap-1 ${online > 0 ? 'text-emerald-500' : 'text-gray-400'}`}>
            {online > 0
              ? <CheckCircle className="w-3.5 h-3.5" />
              : <Clock className="w-3.5 h-3.5" />}
            {online}/{siteDevices.length} online
          </span>
          <ChevronRight className={`w-3.5 h-3.5 text-gray-300 transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="divide-y divide-gray-100">
          {siteDevices.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400 italic">Ingen enheder på dette site</p>
          ) : (
            siteDevices.map(d => (
              <div key={d.device_id} className="flex items-center">
                <div className="flex-1"><DeviceRow device={d} /></div>
                <Link to={`/cameras/${d.device_id}`}
                  className="flex-shrink-0 p-2 mr-2 text-gray-300 hover:text-sky-500 hover:bg-sky-50 rounded-lg transition-colors"
                  title="Konfigurer kamera">
                  <Settings className="w-3.5 h-3.5" />
                </Link>
              </div>
            ))
          )}
          <div className="px-4 py-2 flex justify-end">
            <Link to={`/sites/${site.id}`}
              className="text-xs text-sky-500 hover:text-sky-700 flex items-center gap-1">
              Konfigurer site <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function CustomerCard({ customer, sites, devices }: { customer: Customer; sites: Site[]; devices: Device[] }) {
  const customerSites = sites.filter(s => s.customer_id === customer.id)
  const customerDevices = devices.filter(d => d.customer_name === customer.name)
  const online = customerDevices.filter(d => d.status === 'online').length
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-5 shadow-sm">
      {/* Kunde header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-5 py-4 bg-white hover:bg-gray-50 transition-colors text-left border-b border-gray-100">
        <div className="w-9 h-9 rounded-xl bg-sky-50 flex items-center justify-center flex-shrink-0">
          <Building2 className="w-5 h-5 text-sky-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-base font-semibold text-gray-900">{customer.name}</p>
          {customer.contact_name && (
            <p className="text-xs text-gray-400">{customer.contact_name}</p>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{customerSites.length} site{customerSites.length !== 1 ? 's' : ''}</span>
          <span className={`flex items-center gap-1 font-medium ${online > 0 ? 'text-emerald-500' : 'text-gray-400'}`}>
            {online > 0
              ? <CheckCircle className="w-3.5 h-3.5" />
              : <AlertCircle className="w-3.5 h-3.5" />}
            {online}/{customerDevices.length}
          </span>
          <ChevronRight className={`w-4 h-4 text-gray-300 transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </button>

      {/* Sites */}
      {expanded && (
        <div className="p-4">
          {customerSites.length === 0 ? (
            <p className="text-sm text-gray-400 italic px-1">Ingen sites oprettet</p>
          ) : (
            customerSites.map(site => (
              <SiteCard key={site.id} site={site} devices={devices} />
            ))
          )}
          <div className="flex justify-end pt-1">
            <Link to={`/customers/${customer.id}`}
              className="text-xs text-sky-500 hover:text-sky-700 flex items-center gap-1">
              Konfigurer kunde <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

export function Dashboard() {
  const [stats, setStats]         = useState<Stats | null>(null)
  const [devices, setDevices]     = useState<Device[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [sites, setSites]         = useState<Site[]>([])
  const [loading, setLoading]     = useState(true)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const load = async () => {
    setLoading(true)
    try {
      const [s, d, c, si] = await Promise.all([
        getStats(),
        getDevices(),
        api('/api/admin/customers'),
        api('/api/admin/sites'),
      ])
      setStats(s)
      setDevices(d)
      setCustomers(c)
      setSites(si)
      setLastRefresh(new Date())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  const online = devices.filter(d => d.status === 'online').length

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Opdateret {lastRefresh.toLocaleTimeString('da-DK')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Opdater
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Enheder online" value={`${online} / ${stats.total_devices}`} sub={`${stats.total_devices} total`} color="blue" />
          <StatCard label="Captures" value={stats.total_captures} sub="alle enheder" color="gray" />
          <StatCard label="Kvalitet OK" value={`${stats.quality_pass_pct}%`} sub="pass rate" color={stats.quality_pass_pct >= 95 ? 'green' : 'amber'} />
          <StatCard label="Upload OK" value={`${stats.upload_pct}%`} sub="success rate" color={stats.upload_pct >= 95 ? 'green' : 'amber'} />
        </div>
      )}

      {/* Kunder → Sites → Kameraer */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Kunder</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">{customers.length} kunde{customers.length !== 1 ? 'r' : ''} · {sites.length} site{sites.length !== 1 ? 's' : ''} · {devices.length} enhed{devices.length !== 1 ? 'er' : ''}</span>
          <Link to="/customers/new" className="flex items-center gap-1 text-xs text-sky-500 hover:text-sky-700">
            <Plus className="w-3.5 h-3.5" /> Ny kunde
          </Link>
        </div>
      </div>

      {loading && customers.length === 0 ? (
        <div className="py-12 text-center text-gray-400 text-sm">Indlæser…</div>
      ) : customers.length === 0 ? (
        <div className="py-12 text-center text-gray-400 text-sm">Ingen kunder registreret</div>
      ) : (
        customers.map(customer => (
          <CustomerCard key={customer.id} customer={customer} sites={sites} devices={devices} />
        ))
      )}

      {/* Enheder uden kunde/site (fallback) */}
      {(() => {
        const orphaned = devices.filter(d => !d.customer_name && !d.site_name)
        if (!orphaned.length) return null
        return (
          <div className="bg-white rounded-xl border border-amber-200 overflow-hidden mt-4">
            <div className="px-5 py-3 bg-amber-50 border-b border-amber-100">
              <p className="text-sm font-medium text-amber-700">Enheder uden kunde/site</p>
            </div>
            <div className="p-2">
              {orphaned.map(d => <DeviceRow key={d.device_id} device={d} />)}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
