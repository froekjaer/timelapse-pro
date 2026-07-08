// ═══════════════════════════════════════════════════════════════
// RetentionPage.tsx
// Version: 1.0.0  |  7. juli 2026
// ───────────────────────────────────────────────────────────────
// P0-05 Retention Policy UI
// Viser retention status, settings og deletion log
// ═══════════════════════════════════════════════════════════════
import { useCallback, useEffect, useState } from 'react'
import {
  Calendar, CheckCircle, Clock, Database, RefreshCw, Shield,
  Trash2, XCircle, Settings, FileText, AlertTriangle
} from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  }).then(r => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
}

interface RetentionStatus {
  running: boolean
  progress: string[]
  deleted_count: number
  error: string | null
}

interface RetentionSettings {
  retention_cleanup_interval: string
  retention_days?: number  // P0-05: Global retention default
}

interface DeletionLogEntry {
  id: string
  capture_id: string
  device_id: string
  camera_id: string
  filename: string
  deleted_at: string
  deletion_reason: string
  retention_days: number
  performed_by: string
  capture_taken_at?: string
  camera_name?: string
  device_name?: string
}

type Tab = 'status' | 'settings' | 'deletion-log'

export function RetentionPage() {
  const [tab, setTab] = useState<Tab>('status')
  const [status, setStatus] = useState<RetentionStatus>({ running: false, progress: [], deleted_count: 0, error: null })
  const [settings, setSettings] = useState<RetentionSettings>({ retention_cleanup_interval: 'manual', retention_days: 99999 })
  const [deletionLog, setDeletionLog] = useState<DeletionLogEntry[]>([])
  const [logPage, setLogPage] = useState(1)
  const [logTotal, setLogTotal] = useState(0)
  const [logFilter, setLogFilter] = useState({ camera_id: '', device_id: '' })
  const [triggering, setTriggering] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const loadStatus = useCallback(() => {
    api('/admin/retention/status')
      .then(setStatus)
      .then(() => setLoading(false))
      .catch(err => {
        console.error('Failed to load retention status:', err)
        setLoading(false)
      })
  }, [])

  const loadSettings = useCallback(() => {
    api('/admin/retention/settings')
      .then(setSettings)
      .catch(err => console.error('Failed to load retention settings:', err))
  }, [])

  const loadDeletionLog = useCallback(() => {
    const params = new URLSearchParams({
      page: String(logPage),
      limit: '50',
      ...(logFilter.camera_id && { camera_id: logFilter.camera_id }),
      ...(logFilter.device_id && { device_id: logFilter.device_id }),
    })
    api(`/admin/retention/deletion-log?${params}`)
      .then(data => {
        setDeletionLog(data.log || [])
        setLogTotal(data.total || 0)
      })
      .catch(err => console.error('Failed to load deletion log:', err))
  }, [logFilter.camera_id, logFilter.device_id, logPage])

  // Hent initial data
  useEffect(() => {
    loadStatus()
    loadSettings()
  }, [loadSettings, loadStatus])

  // Auto-refresh status hvis running
  useEffect(() => {
    if (status.running) {
      const interval = setInterval(() => loadStatus(), 2000)
      return () => clearInterval(interval)
    }
  }, [status.running, loadStatus])

  // Hent deletion log når tab skifter til deletion-log
  useEffect(() => {
    if (tab === 'deletion-log') {
      loadDeletionLog()
    }
  }, [loadDeletionLog, tab])

  function triggerCleanup() {
    setTriggering(true)
    api('/admin/retention/trigger', { method: 'POST' })
      .then(() => {
        setMessage({ type: 'success', text: 'Retention cleanup startet' })
        loadStatus()
      })
      .catch(err => {
        setMessage({ type: 'error', text: `Fejl: ${err instanceof Error ? err.message : String(err)}` })
      })
      .finally(() => setTriggering(false))
  }

  function saveSettings() {
    setSaving(true)
    api('/admin/retention/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    })
      .then(() => {
        setMessage({ type: 'success', text: 'Indstillinger gemt' })
      })
      .catch(err => {
        setMessage({ type: 'error', text: `Fejl: ${err.message}` })
      })
      .finally(() => setSaving(false))
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString('da-DK')
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <Calendar className="w-6 h-6 text-sky-600" />
          Retention Policy
        </h1>
        <p className="text-gray-500 mt-1">
          Håndtering af automatisk sletning af gamle billeder i henhold til GDPR retention policy
        </p>
      </div>

      {/* Message banner */}
      {message && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          <span className="text-sm">{message.text}</span>
          <button onClick={() => setMessage(null)} className="ml-auto text-gray-400 hover:text-gray-600">
            ×
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {[
          { id: 'status' as Tab, label: 'Status', icon: Activity },
          { id: 'settings' as Tab, label: 'Indstillinger', icon: Settings },
          { id: 'deletion-log' as Tab, label: 'Sletningslog', icon: FileText },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-sky-500 text-sky-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Status tab */}
      {tab === 'status' && (
        <div className="space-y-4">
          {/* Status card */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Database className="w-5 h-5 text-gray-400" />
                Nuværende status
              </h2>
              <button
                onClick={loadStatus}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {loading ? (
              <div className="text-center py-8 text-gray-400">
                <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
                Indlæser...
              </div>
            ) : status.running ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-amber-600">
                  <Clock className="w-5 h-5 animate-pulse" />
                  <span className="font-medium">Retention cleanup kører...</span>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 max-h-60 overflow-y-auto">
                  {status.progress.map((line, i) => (
                    <div key={i} className="text-sm font-mono text-gray-600 py-0.5">
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            ) : status.error ? (
              <div className="flex items-center gap-2 text-red-600">
                <XCircle className="w-5 h-5" />
                <span>Fejl under cleanup: {status.error}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="w-5 h-5" />
                <span>Retention cleanup er inaktiv</span>
              </div>
            )}

            {status.deleted_count > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <div className="flex items-center gap-2 text-gray-700">
                  <Trash2 className="w-4 h-4 text-gray-400" />
                  <span className="text-sm">
                    Sidste kørsel slettede <strong>{status.deleted_count}</strong> captures
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Handlinger</h3>
            <button
              onClick={triggerCleanup}
              disabled={triggering || status.running}
              className="w-full sm:w-auto px-4 py-2 bg-sky-500 hover:bg-sky-600 disabled:bg-gray-300 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
            >
              {triggering ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Starter...
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4" />
                  Start retention cleanup nu
                </>
              )}
            </button>
          </div>

          {/* Info */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <strong>Vigtigt:</strong> Sletning er permanent. Captures fjernet via retention policy
              kan ikke gendannes. En log over alle sletninger gemmes i "Sletningslog"-tabben til compliance-formål.
            </div>
          </div>
        </div>
      )}

      {/* Settings tab */}
      {tab === 'settings' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2 mb-4">
              <Settings className="w-5 h-5 text-gray-400" />
              Retention indstillinger
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Cleanup interval
                </label>
                <select
                  value={settings.retention_cleanup_interval}
                  onChange={e => setSettings({ ...settings, retention_cleanup_interval: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="manual">Manuelt (kun ved manuelt trigger)</option>
                  <option value="daily">Dagligt</option>
                  <option value="weekly">Ugentligt</option>
                  <option value="monthly">Månedligt</option>
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Hvor ofte systemet automatisk skal køre retention cleanup
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Global retention (dage)
                </label>
                <input
                  type="number"
                  min={1}
                  value={settings.retention_days ?? 99999}
                  onChange={e => setSettings({ ...settings, retention_days: parseInt(e.target.value) || 99999 })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Default retention for nye kameraer. Anvendes hvis kameraet ikke har en egen retention værdi.
                </p>
              </div>

              <div className="pt-2">
                <button
                  onClick={saveSettings}
                  disabled={saving}
                  className="px-4 py-2 bg-sky-500 hover:bg-sky-600 disabled:bg-gray-300 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  {saving ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Gemmer...
                    </>
                  ) : (
                    <>
                      <Shield className="w-4 h-4" />
                      Gem indstillinger
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <p className="text-sm text-blue-800">
              <strong>Note:</strong> Global retention bruges som default for nye kameraer.
              Eksisterende kameraer beholder deres egen retention værdi indtil de ændres.
              Cleanup interval træder i kraft ved næste planlagte tjek (hvert 10. minut).
            </p>
          </div>
        </div>
      )}

      {/* Deletion log tab */}
      {tab === 'deletion-log' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex flex-wrap gap-3">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-gray-600 mb-1">Kamera ID</label>
                <input
                  type="text"
                  value={logFilter.camera_id}
                  onChange={e => setLogFilter({ ...logFilter, camera_id: e.target.value })}
                  placeholder="Filtrer på kamera ID..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
                />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-gray-600 mb-1">Device ID</label>
                <input
                  type="text"
                  value={logFilter.device_id}
                  onChange={e => setLogFilter({ ...logFilter, device_id: e.target.value })}
                  placeholder="Filtrer på device ID..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Log table */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 font-medium text-gray-600">Slettet</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Kamera</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Device</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Filename</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Retention</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Årsag</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Udført af</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {deletionLog.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                        Ingen sletninger fundet
                      </td>
                    </tr>
                  ) : (
                    deletionLog.map(entry => (
                      <tr key={entry.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                          {formatDate(entry.deleted_at)}
                        </td>
                        <td className="px-4 py-3 text-gray-800">
                          {entry.camera_name || entry.camera_id}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {entry.device_name || entry.device_id}
                        </td>
                        <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                          {entry.filename}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {entry.retention_days} dage
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            entry.deletion_reason === 'retention_policy'
                              ? 'bg-orange-100 text-orange-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}>
                            {entry.deletion_reason}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {entry.performed_by}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {logTotal > 50 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
                <div className="text-sm text-gray-500">
                  Viser {(logPage - 1) * 50 + 1}-{Math.min(logPage * 50, logTotal)} af {logTotal}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setLogPage(p => Math.max(1, p - 1))}
                    disabled={logPage === 1}
                    className="px-3 py-1 text-sm border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Forrige
                  </button>
                  <button
                    onClick={() => setLogPage(p => p + 1)}
                    disabled={logPage * 50 >= logTotal}
                    className="px-3 py-1 text-sm border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Næste
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Activity icon import
function Activity({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}
