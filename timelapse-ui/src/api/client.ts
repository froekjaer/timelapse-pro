import axios from 'axios'
import type { Device, DeviceDetail, Stats, Capture, DeviceConfig } from '../types'

export const DEFAULT_API_URL = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8000'

const isProductionHttpsOrigin = () =>
  typeof window !== 'undefined' &&
  window.location.protocol === 'https:' &&
  !['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)

export const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const runtimeApi = (window as any).__TIMELAPSE_API__
    if (runtimeApi) return String(runtimeApi).replace(/\/$/, '')
  }
  if (isProductionHttpsOrigin()) return window.location.origin
  if (typeof window !== 'undefined' && window.location.port === '5173') {
    return window.location.origin
  }
  return import.meta.env.VITE_API_URL ?? DEFAULT_API_URL
}

export const bootstrapToken = async () => {
  if (localStorage.getItem('timelapse_api_token')) return
  try {
    const res = await fetch(`${getApiUrl()}/api/admin/settings`)
    if (!res.ok) return
    const settings = await res.json()
    const token = settings['api_token']
    if (token) localStorage.setItem('timelapse_api_token', token)
  } catch { /* ignore */ }
}

const getClient = () => {
  return axios.create({
    baseURL:         getApiUrl(),
    withCredentials: true,
  })
}

export const pathSegment = (value: string) => encodeURIComponent(value)

export const getStats = () =>
  getClient().get<Stats>('/api/admin/stats').then(r => r.data)

export const getDevices = () =>
  getClient().get<Device[]>('/api/admin/devices').then(r => r.data)

export const getDevice = (id: string) =>
  getClient().get<DeviceDetail>(`/api/admin/devices/${pathSegment(id)}`).then(r => r.data)

export const getCaptures = (deviceId?: string, limit = 100) =>
  getClient().get<Capture[]>('/api/admin/captures', {
    params: { device_id: deviceId, limit },
  }).then(r => r.data)

export const getConfig = (deviceId: string) =>
  getClient().get(`/api/admin/devices/${pathSegment(deviceId)}/config`).then(r => r.data)

export const updateConfig = (deviceId: string, config: DeviceConfig) =>
  getClient().put(`/api/admin/devices/${pathSegment(deviceId)}/config`, config).then(r => r.data)

export const getImageUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/images/${encodeURIComponent(deviceId)}/${encodeURIComponent(filename)}`

export const getThumbnailUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/thumbnails/${encodeURIComponent(deviceId)}/${encodeURIComponent(filename)}`

export const requestThumbnailGeneration = (deviceId: string, filename: string) =>
  getClient().post(`/api/thumbnails/${pathSegment(deviceId)}/${pathSegment(filename)}/generate`).then(r => r.data)

export const updateDeviceInfo = (deviceId: string, info: import('../types').DeviceInfo) =>
  getClient().put(`/api/admin/devices/${pathSegment(deviceId)}/info`, info).then(r => r.data)

export const testConnection = () =>
  getClient().get('/api/health').then(r => r.data)

// ── Lab / Kamera-laboratorium ─────────────────────────────────────────────────

export const setDebugMode = (deviceId: string, enabled: boolean, pollS = 2) =>
  getClient().put(`/api/admin/devices/${pathSegment(deviceId)}/debug`, {
    enabled, config_poll_s: pollS, relay_always_on: true
  }).then(r => r.data)

export const requestPreview = (deviceId: string) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/preview`).then(r => r.data)

export const requestCapture = (deviceId: string) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/capture`).then(r => r.data)

export const setParam = async (deviceId: string, key: string, value: string) => {
  // Retry on 503 errors (headend busy)
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await getClient().post(`/api/lab/${pathSegment(deviceId)}/set-param`, { key, value }).then(r => r.data)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 503 && attempt < 2) {
        // Wait 500ms and retry
        await new Promise(resolve => setTimeout(resolve, 500))
        continue
      }
      throw err
    }
  }
  throw new Error('setParam failed after retries')
}

export const requestFocusDrive = (deviceId: string, value: string) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/focus-drive`, { value }).then(r => r.data)

export const requestAutofocus = (deviceId: string) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/autofocus`).then(r => r.data)

export const requestFocusSlice = (deviceId: string, payload: { step_value: string; count: number; run_autofocus_first?: boolean }) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/focus-slice`, payload).then(r => r.data)

export const requestEdgeAiFocusTest = (deviceId: string, payload: { step_value: string; count: number }) =>
  getClient().post(`/api/lab/${pathSegment(deviceId)}/edge-ai-focus-test`, payload).then(r => r.data)

export const listPreviews = (deviceId: string) =>
  getClient().get(`/api/lab/${pathSegment(deviceId)}/previews`).then(r => r.data)

export const getPreviewUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/lab/${encodeURIComponent(deviceId)}/preview-image/${encodeURIComponent(filename)}`

export const getPreviewThumbUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/lab/${encodeURIComponent(deviceId)}/preview-thumb/${encodeURIComponent(filename)}`

export const getDeviceRawConfig = (deviceId: string) =>
  getClient().get(`/api/config/${pathSegment(deviceId)}`).then(r => r.data)

export const deleteCapture = (id: number) =>
  getClient().delete(`/api/admin/captures/${id}`).then(r => r.data)

export const deleteCapturesBulk = (ids: number[]) =>
  getClient().post('/api/admin/captures/bulk-delete', { ids }).then(r => r.data.deleted as number)
