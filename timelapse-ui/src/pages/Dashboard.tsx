import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Camera, CheckCircle, Upload, Wifi } from 'lucide-react'
import { getStats, getDevices } from '../api/client'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import type { Stats, Device } from '../types'

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const load = async () => {
    setLoading(true)
    try {
      const [s, d] = await Promise.all([getStats(), getDevices()])
      setStats(s)
      setDevices(d)
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
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Opdateret {lastRefresh.toLocaleTimeString('da-DK')}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Opdater
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <StatCard
            label="Enheder online"
            value={`${online} / ${stats.total_devices}`}
            sub={`${stats.total_devices} total`}
            color="blue"
          />
          <StatCard
            label="Captures"
            value={stats.total_captures}
            sub="alle enheder"
            color="gray"
          />
          <StatCard
            label="Kvalitet OK"
            value={`${stats.quality_pass_pct}%`}
            sub="quality pass rate"
            color={stats.quality_pass_pct >= 95 ? 'green' : 'amber'}
          />
          <StatCard
            label="Upload OK"
            value={`${stats.upload_pct}%`}
            sub="upload success rate"
            color={stats.upload_pct >= 95 ? 'green' : 'amber'}
          />
        </div>
      )}

      <h2 className="text-lg font-semibold text-gray-900 mb-4">Enheder</h2>
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100 overflow-hidden">
        {devices.length === 0 && !loading && (
          <div className="py-12 text-center text-gray-400 text-sm">
            Ingen enheder registreret endnu
          </div>
        )}
        {devices.map(device => (
          <Link
            key={device.device_id}
            to={`/devices/${device.device_id}`}
            className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors"
          >
            <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
              <Camera className="w-5 h-5 text-slate-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {device.camera_name || device.location_name || device.device_id}
              </p>
              {(device.customer_name || device.site_name) && (
                <p className="text-xs text-gray-400 truncate">
                  {[device.customer_name, device.site_name].filter(Boolean).join(' — ')}
                </p>
              )}
              <p className="text-xs text-gray-400 font-mono mt-0.5">{device.device_id}</p>
            </div>
            <div className="flex items-center gap-6 text-sm text-gray-500">
              {device.ip_address && (
                <span className="hidden md:flex items-center gap-1.5">
                  <Wifi className="w-3.5 h-3.5" />
                  {device.ip_address}
                </span>
              )}
              {device.last_seen && (
                <span className="hidden md:block text-xs text-gray-400">
                  Sidst set {new Date(device.last_seen + 'Z').toLocaleString('da-DK', { timeZone: localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen' })}
                </span>
              )}
              <StatusBadge status={device.status} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
