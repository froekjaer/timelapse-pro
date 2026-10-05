// Camera's OWN choices on the Headend camera page (Peter, 2026-10-04: "det er
// rigtigt svært at sætte parametrene rigtigt"). Source: the latest LAB
// "Hent parametre" scan stored per device (camera_params + camera_profile in
// /api/config/{device}). The profile's config_commands maps a logical key
// (iso, shutter_speed, …) to the exact gphoto2 path the Edge uses, e.g. the
// Nikon Z30 sets shutter speed via /main/capturesettings/shutterspeed2.
import { useEffect, useState } from 'react'
import { getDeviceRawConfig } from '../api/client'

export interface ScannedParam {
  path: string
  label: string
  type: string
  current: string
  readonly: boolean
  choices: { index: string; label: string }[]
  bottom?: string
  top?: string
  step?: string
}

export interface CameraScan {
  params: ScannedParam[]
  configCommands: Record<string, { path?: string; skip?: boolean; value_map?: Record<string, string>; skip_values?: string[] }>
  model: string
  updatedAt: string | null
}

// Fallback when the profile has no path: the Edge's own default leaf names.
const DEFAULT_LEAF: Record<string, string[]> = {
  iso: ['iso'],
  shutter_speed: ['shutterspeed'],
  aperture: ['aperture', 'f-number'],
  whitebalance: ['whitebalance'],
  exposurecompensation: ['exposurecompensation'],
}

export function useCameraScan(deviceId: string | undefined): CameraScan | null {
  const [scan, setScan] = useState<CameraScan | null>(null)
  useEffect(() => {
    if (!deviceId) return
    getDeviceRawConfig(deviceId).then(cfg => {
      const params: ScannedParam[] = Array.isArray(cfg?.camera_params) ? cfg.camera_params : []
      setScan({
        params,
        configCommands: cfg?.camera_profile?.config_commands ?? {},
        model: cfg?.camera_profile?.detected_model ?? cfg?.camera_profile?.profile_name ?? '',
        updatedAt: cfg?.camera_params_updated_at ?? null,
      })
    }).catch(() => setScan(null))
  }, [deviceId])
  return scan
}

/** Scanned parameter behind a logical camera setting (camera.iso, …). */
export function scannedParamFor(scan: CameraScan | null, configKey: string): ScannedParam | null | 'skip' {
  if (!scan || scan.params.length === 0) return null
  const logical = configKey.replace(/^camera\./, '')
  const spec = scan.configCommands[logical]
  if (spec?.skip) return 'skip'
  const leaves = DEFAULT_LEAF[logical] ?? []
  return scan.params.find(p => spec?.path && p.path === spec.path)
    ?? leaves.map(l => scan.params.find(p => p.path.endsWith(`/${l}`))).find(Boolean)
    ?? null
}

/**
 * Options for a logical select (camera.iso, …) from the camera's own scan:
 * the profile's logical values first (e.g. "Auto", which the Edge maps or
 * skips), then exactly the camera's choice labels. The current override is
 * kept even if the camera does not list it, so nothing is silently lost.
 */
export function cameraOptionsFor(scan: CameraScan | null, configKey: string, current: string): string[] | null {
  const param = scannedParamFor(scan, configKey)
  if (!param || param === 'skip' || param.choices.length === 0) return null
  const spec = scan?.configCommands[configKey.replace(/^camera\./, '')]
  const labels = param.choices.map(c => c.label)
  // Logical values only when they add something: "Auto" the Edge skips (lets
  // the camera decide), not aliases that map onto a label already listed.
  const logical = [
    ...(spec?.skip_values ?? []),
    ...Object.entries(spec?.value_map ?? {}).filter(([, to]) => !labels.includes(to)).map(([from]) => from),
  ]
  const out: string[] = []
  const seen = new Set<string>()
  for (const v of [...logical, ...labels]) {
    if (v === '' || seen.has(v.toLowerCase())) continue
    seen.add(v.toLowerCase())
    out.push(v)
  }
  if (current && !seen.has(current.toLowerCase())) out.unshift(current)
  return out
}

/** Readable label for a camera value, e.g. "0.0020s" → "0.0020s (≈ 1/500)". */
export function optionLabel(value: string): string {
  const m = /^(\d*\.\d+)s$/.exec(value)
  if (!m) return value
  const sec = parseFloat(m[1])
  return sec > 0 && sec < 1 ? `${value} (≈ 1/${Math.round(1 / sec)})` : value
}

export function scanAge(scan: CameraScan | null): string {
  if (!scan?.updatedAt) return ''
  return new Date(scan.updatedAt).toLocaleString('da-DK', { dateStyle: 'short', timeStyle: 'short' })
}

export function leafOf(path: string) {
  return path.split('/').pop() ?? path
}
