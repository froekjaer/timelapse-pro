import axios from 'axios'
import type { Device, DeviceDetail, Stats, Capture, DeviceConfig } from '../types'

export const API_STORAGE_KEY = 'timelapse_api_url'
export const DEFAULT_API_URL = typeof window !== 'undefined' ? window.location.origin : 'http://192.168.86.102:8000'

export const getApiUrl = () =>
  localStorage.getItem(API_STORAGE_KEY) ?? import.meta.env.VITE_API_URL ?? DEFAULT_API_URL

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

export const getStats = () =>
  getClient().get<Stats>('/api/admin/stats').then(r => r.data)

export const getDevices = () =>
  getClient().get<Device[]>('/api/admin/devices').then(r => r.data)

export const getDevice = (id: string) =>
  getClient().get<DeviceDetail>(`/api/admin/devices/${id}`).then(r => r.data)

export const getCaptures = (deviceId?: string, limit = 100) =>
  getClient().get<Capture[]>('/api/admin/captures', {
    params: { device_id: deviceId, limit },
  }).then(r => r.data)

export const getConfig = (deviceId: string) =>
  getClient().get(`/api/admin/devices/${deviceId}/config`).then(r => r.data)

export const updateConfig = (deviceId: string, config: DeviceConfig) =>
  getClient().put(`/api/admin/devices/${deviceId}/config`, config).then(r => r.data)

export const getImageUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/images/${encodeURIComponent(deviceId)}/${encodeURIComponent(filename)}`

export const getThumbnailUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/thumbnails/${encodeURIComponent(deviceId)}/${encodeURIComponent(filename)}`

export const updateDeviceInfo = (deviceId: string, info: import('../types').DeviceInfo) =>
  getClient().put(`/api/admin/devices/${deviceId}/info`, info).then(r => r.data)

export const testConnection = () =>
  getClient().get('/health').then(r => r.data)

// ── Lab / Kamera-laboratorium ─────────────────────────────────────────────────

export const setDebugMode = (deviceId: string, enabled: boolean, pollS = 2) =>
  getClient().put(`/api/admin/devices/${deviceId}/debug`, {
    enabled, config_poll_s: pollS, relay_always_on: true
  }).then(r => r.data)

export const requestPreview = (deviceId: string) =>
  getClient().post(`/api/lab/${deviceId}/preview`).then(r => r.data)

export const requestCapture = (deviceId: string) =>
  getClient().post(`/api/lab/${deviceId}/capture`).then(r => r.data)

export const setParam = (deviceId: string, key: string, value: string) =>
  getClient().post(`/api/lab/${deviceId}/set-param`, { key, value }).then(r => r.data)

export const listPreviews = (deviceId: string) =>
  getClient().get(`/api/lab/${deviceId}/previews`).then(r => r.data)

export const getPreviewUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/lab/${encodeURIComponent(deviceId)}/preview-image/${encodeURIComponent(filename)}`

export const getPreviewThumbUrl = (deviceId: string, filename: string) =>
  `${getApiUrl()}/api/lab/${encodeURIComponent(deviceId)}/preview-thumb/${encodeURIComponent(filename)}`

export const getDeviceRawConfig = (deviceId: string) =>
  getClient().get(`/api/config/${deviceId}`).then(r => r.data)

export const deleteCapture = (id: number) =>
  getClient().delete(`/api/admin/captures/${id}`).then(r => r.data)

export const deleteCapturesBulk = (ids: number[]) =>
  getClient().post('/api/admin/captures/bulk-delete', { ids }).then(r => r.data.deleted as number)
