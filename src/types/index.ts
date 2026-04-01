export interface Device {
  device_id: string
  location_name: string | null
  tenant_id: string | null
  ip_address: string | null
  status: 'online' | 'offline' | 'unknown'
  last_seen: string | null
  first_seen: string | null
  customer_name: string | null
  site_name: string | null
  camera_name: string | null
  installed_date: string | null
  installed_time: string | null
}

export interface DeviceInfo {
  customer_name?: string
  site_name?: string
  camera_name?: string
  installed_date?: string
  installed_time?: string
  location_name?: string
}

export interface Capture {
  id: number
  device_id: string
  filename: string
  captured_at: string | null
  quality_flag: string | null
  quality_passed: boolean | null
  blur_score: number | null
  filesize_mb: number | null
  uploaded: boolean
  brightness?: number
}

export interface Diagnostic {
  cpu_temp_c: number | null
  cpu_load_pct: number | null
  disk_used_gb: number | null
  connectivity: string | null
  uptime_s: number | null
  ntp_offset_s: number | null
  ssd_used_pct: number | null
  ssd_free_gb: number | null
  service_restarts: number | null
  upload_queue: number | null
  cam_battery_pct: number | null
  cam_shutter_cnt: number | null
  cam_shutter_pct: number | null
  cam_shutter_alarm: boolean | null
  cam_available_shots: number | null
  cam_lens_name: string | null
  cam_config_json: string | null
  cam_drift_json: string | null
  capture_total: number | null
  capture_passed: number | null
  capture_uploaded: number | null
}

export interface DeviceDetail {
  device: Device
  diagnostics: Diagnostic | null
  captures: Capture[]
}

export interface Stats {
  total_devices: number
  total_captures: number
  quality_pass_pct: number
  upload_pct: number
}

export interface DeviceConfig {
  schedule?: {
    interval_minutes?: number
    active_hours?: [string, string]
    timezone?: string
  }
  camera?: {
    relay_gpio_pin?: number
    relay_on_seconds_before?: number
    relay_off_seconds_after?: number
    relay_simulate?: boolean
  }
  modem?: {
    modem_relay_gpio_pin?: number
    modem_cycle_after_failures?: number
  }
}

export interface LabPreview {
  filename: string
  size_kb: number
  url: string
  thumb_url: string
}

export interface CameraParam {
  path: string
  label: string
  type: string
  current: string
  choices: { index: string; label: string }[]
  readonly: boolean
}

export interface DebugMode {
  enabled: boolean
  relay_always_on: boolean
  config_poll_s: number
  support_tier: string
}
