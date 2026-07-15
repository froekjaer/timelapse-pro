/**
 * Site-Wide Look Matching Configuration Panel
 *
 * Allows admins to configure Site-Wide Look Matching at different hierarchy levels:
 * - Global: System-wide defaults
 * - Customer: Per-customer overrides
 * - Site: Per-site overrides
 * - Camera: Per-camera overrides
 *
 * Configuration is stored in database and syncs to edge nodes via polling.
 */

import { useState, useEffect, useCallback } from 'react'
import { Save, RotateCcw, Trash2, ChevronDown, ChevronUp, Info, CheckCircle, AlertCircle } from 'lucide-react'

interface ConfigLevel {
  level: 'global' | 'customer' | 'site' | 'camera'
  label: string
  description: string
  requiresCustomer?: boolean
  requiresSite?: boolean
  requiresCamera?: boolean
}

interface SiteLookConfig {
  enabled: boolean
  storage_path?: string
  reference_quality_threshold: number
  auto_create_reference: boolean
  auto_update_reference: boolean
  lut_auto_generate: boolean
  lut_regeneration_interval_hours: number
  config_poll_interval_seconds: number
  config_cache_ttl_seconds: number
  // Extended color science settings
  neutral_kelvin?: number
  warm_lab_threshold?: number
  cool_lab_threshold?: number
  warm_kelvin_multiplier?: number
  cool_kelvin_multiplier?: number
  kelvin_min?: number
  kelvin_max?: number
}

const LEVELS: ConfigLevel[] = [
  { level: 'global', label: 'Global (System)', description: 'System-wide standard indstillinger' },
  { level: 'customer', label: 'Kunde', description: 'Kunde-specifikke indstillinger', requiresCustomer: true },
  { level: 'site', label: 'Site', description: 'Site-specifikke indstillinger', requiresCustomer: true, requiresSite: true },
  { level: 'camera', label: 'Kamera', description: 'Kamera-specifikke indstillinger', requiresCustomer: true, requiresSite: true, requiresCamera: true },
]

interface SiteLookConfigPanelProps {
  customerId?: string
  siteId?: string
  cameraId?: string
}

export function SiteLookConfigPanel({ customerId, siteId, cameraId }: SiteLookConfigPanelProps) {
  const [level, setLevel] = useState<'global' | 'customer' | 'site' | 'camera'>('global')
  const [config, setConfig] = useState<SiteLookConfig>({
    enabled: true,
    reference_quality_threshold: 75.0,
    auto_create_reference: true,
    auto_update_reference: false,
    lut_auto_generate: true,
    lut_regeneration_interval_hours: 168,
    config_poll_interval_seconds: 300,
    config_cache_ttl_seconds: 86400,
    neutral_kelvin: 6500,
    warm_lab_threshold: 20,
    cool_lab_threshold: -10,
    warm_kelvin_multiplier: 50,
    cool_kelvin_multiplier: 80,
    kelvin_min: 2700,
    kelvin_max: 10000,
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (level !== 'global' && customerId) params.append('customer_id', customerId)
      if ((level === 'site' || level === 'camera') && siteId) params.append('site_id', siteId)
      if (level === 'camera' && cameraId) params.append('camera_id', cameraId)

      const response = await fetch(`/api/admin/site-look/config?${params}`)
      if (response.ok) {
        const data = await response.json()
        setConfig(data)
      } else if (response.status === 404) {
        // No config at this level - use defaults
        setConfig({
          enabled: true,
          reference_quality_threshold: 75.0,
          auto_create_reference: true,
          auto_update_reference: false,
          lut_auto_generate: true,
          lut_regeneration_interval_hours: 168,
          config_poll_interval_seconds: 300,
          config_cache_ttl_seconds: 86400,
          neutral_kelvin: 6500,
          warm_lab_threshold: 20,
          cool_lab_threshold: -10,
          warm_kelvin_multiplier: 50,
          cool_kelvin_multiplier: 80,
          kelvin_min: 2700,
          kelvin_max: 10000,
        })
      } else {
        throw new Error('Failed to fetch config')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [level, customerId, siteId, cameraId])

  // Fetch config when level or IDs change
  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const body = {
        level,
        customer_id: level !== 'global' ? customerId : null,
        site_id: level === 'site' || level === 'camera' ? siteId : null,
        camera_id: level === 'camera' ? cameraId : null,
        ...config,
      }

      const response = await fetch('/api/admin/site-look/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (response.ok) {
        setSuccess(true)
        setTimeout(() => setSuccess(false), 3000)
      } else {
        const data = await response.json()
        throw new Error(data.error || 'Failed to save config')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('Er du sikker på at du vil nulstille til standardværdier?')) return

    setSaving(true)
    setError(null)

    try {
      const body = {
        level,
        customer_id: level !== 'global' ? customerId : null,
        site_id: level === 'site' || level === 'camera' ? siteId : null,
        camera_id: level === 'camera' ? cameraId : null,
      }

      const response = await fetch('/api/admin/site-look/config/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (response.ok) {
        await fetchConfig()
        setSuccess(true)
        setTimeout(() => setSuccess(false), 3000)
      } else {
        throw new Error('Failed to reset config')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Er du sikker på at du vil slette denne konfiguration?')) return

    setSaving(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      params.append('level', level)
      if (customerId) params.append('customer_id', customerId)
      if (siteId) params.append('site_id', siteId)
      if (cameraId) params.append('camera_id', cameraId)

      const response = await fetch(`/api/admin/site-look/config?${params}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        await fetchConfig()
        setSuccess(true)
        setTimeout(() => setSuccess(false), 3000)
      } else {
        throw new Error('Failed to delete config')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Site-Wide Look Matching Konfiguration</h2>
          <p className="text-gray-600 mt-1">
            Hierarkisk konfiguration: global → kunde → site → kamera
          </p>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {success && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-600" />
          <span className="text-emerald-800">Konfiguration gemt!</span>
        </div>
      )}

      {/* Level Selection */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Konfigurationsniveau</h3>
        <div className="grid grid-cols-4 gap-4">
          {LEVELS.map((lvl) => {
            const isDisabled =
              (lvl.requiresCustomer && !customerId) ||
              (lvl.requiresSite && !siteId) ||
              (lvl.requiresCamera && !cameraId)

            return (
              <button
                key={lvl.level}
                onClick={() => setLevel(lvl.level)}
                disabled={isDisabled}
                className={`p-4 rounded-lg border-2 text-left transition-colors ${
                  level === lvl.level
                    ? 'border-sky-500 bg-sky-50'
                    : isDisabled
                    ? 'border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'border-gray-200 hover:border-sky-300'
                }`}
              >
                <div className="font-medium">{lvl.label}</div>
                <div className="text-sm text-gray-600 mt-1">{lvl.description}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Loading State */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-sky-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-600">Indlæser konfiguration...</p>
        </div>
      ) : (
        <>
          {/* Basic Settings */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Info className="w-4 h-4 text-sky-500" />
              Grundlæggende Indstillinger
            </h3>

            <div className="space-y-4">
              {/* Enable/Disable */}
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <div className="font-medium text-gray-900">Aktiver Site-Wide Look Matching</div>
                  <div className="text-sm text-gray-600">Slår farve-matching til eller fra</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.enabled}
                    onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
                </label>
              </div>

              {/* Quality Threshold */}
              <div className="py-3 border-b border-gray-100">
                <label className="block font-medium text-gray-900 mb-2">
                  Kvalitetstærskel for Reference: {config.reference_quality_threshold}%
                </label>
                <input
                  type="range"
                  min="50"
                  max="100"
                  step="0.5"
                  value={config.reference_quality_threshold}
                  onChange={(e) => setConfig({ ...config, reference_quality_threshold: parseFloat(e.target.value) })}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>50%</span>
                  <span>75%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Auto Create Reference */}
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <div className="font-medium text-gray-900">Auto-opret Reference</div>
                  <div className="text-sm text-gray-600">Opret automatisk fra kvalitetsbilleder</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.auto_create_reference}
                    onChange={(e) => setConfig({ ...config, auto_create_reference: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
                </label>
              </div>

              {/* Auto Update Reference */}
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <div className="font-medium text-gray-900">Auto-opdater Reference</div>
                  <div className="text-sm text-gray-600">Opdater reference automatisk (anbefales: false)</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.auto_update_reference}
                    onChange={(e) => setConfig({ ...config, auto_update_reference: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
                </label>
              </div>

              {/* LUT Auto Generate */}
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <div className="font-medium text-gray-900">Auto-generer LUT</div>
                  <div className="text-sm text-gray-600">Generer LUT automatisk for hver capture</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.lut_auto_generate}
                    onChange={(e) => setConfig({ ...config, lut_auto_generate: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
                </label>
              </div>

              {/* LUT Regeneration Interval */}
              <div className="py-3">
                <label className="block font-medium text-gray-900 mb-2">
                  LUT Regenereringsinterval: {config.lut_regeneration_interval_hours} timer
                </label>
                <input
                  type="number"
                  min="24"
                  max="720"
                  step="24"
                  value={config.lut_regeneration_interval_hours}
                  onChange={(e) => setConfig({ ...config, lut_regeneration_interval_hours: parseInt(e.target.value) || 168 })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                />
                <p className="text-xs text-gray-500 mt-1">Hvor ofte LUT'er skal regenereres (24-720 timer)</p>
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full"
            >
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                Avancerede Indstillinger
              </h3>
              {showAdvanced ? <ChevronUp className="w-5 h-5 text-gray-500" /> : <ChevronDown className="w-5 h-5 text-gray-500" />}
            </button>

            {showAdvanced && (
              <div className="mt-4 space-y-4">
                {/* Poll Interval */}
                <div className="py-3 border-b border-gray-100">
                  <label className="block font-medium text-gray-900 mb-2">
                    Config Poll Interval: {config.config_poll_interval_seconds} sekunder
                  </label>
                  <input
                    type="number"
                    min="60"
                    max="3600"
                    step="60"
                    value={config.config_poll_interval_seconds}
                    onChange={(e) => setConfig({ ...config, config_poll_interval_seconds: parseInt(e.target.value) || 300 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Hvor ofte edge nodes skal polle for config ændringer</p>
                </div>

                {/* Cache TTL */}
                <div className="py-3 border-b border-gray-100">
                  <label className="block font-medium text-gray-900 mb-2">
                    Cache TTL: {config.config_cache_ttl_seconds} sekunder ({Math.round(config.config_cache_ttl_seconds / 86400)} dage)
                  </label>
                  <input
                    type="number"
                    min="3600"
                    max="604800"
                    step="3600"
                    value={config.config_cache_ttl_seconds}
                    onChange={(e) => setConfig({ ...config, config_cache_ttl_seconds: parseInt(e.target.value) || 86400 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Max tid edge kan bruge cache hvis DB er utilgængelig</p>
                </div>

                {/* Color Science Settings */}
                <div className="py-3 border-b border-gray-100">
                  <label className="block font-medium text-gray-900 mb-2">
                    Neutral Kelvin: {config.neutral_kelvin}K
                  </label>
                  <input
                    type="number"
                    min="4000"
                    max="8000"
                    step="100"
                    value={config.neutral_kelvin}
                    onChange={(e) => setConfig({ ...config, neutral_kelvin: parseInt(e.target.value) || 6500 })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4 py-3 border-b border-gray-100">
                  <div>
                    <label className="block font-medium text-gray-900 mb-2">Kelvin Min</label>
                    <input
                      type="number"
                      min="2000"
                      max="5000"
                      value={config.kelvin_min}
                      onChange={(e) => setConfig({ ...config, kelvin_min: parseInt(e.target.value) || 2700 })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500"
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-gray-900 mb-2">Kelvin Max</label>
                    <input
                      type="number"
                      min="8000"
                      max="15000"
                      value={config.kelvin_max}
                      onChange={(e) => setConfig({ ...config, kelvin_max: parseInt(e.target.value) || 10000 })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-sky-500"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-3 px-6 bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium flex items-center justify-center gap-2"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Gemmer...' : 'Gem Konfiguration'}
            </button>

            <button
              onClick={handleReset}
              disabled={saving || level === 'global'}
              className="py-3 px-6 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>

            {level !== 'global' && (
              <button
                onClick={handleDelete}
                disabled={saving}
                className="py-3 px-6 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center justify-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Slet
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
