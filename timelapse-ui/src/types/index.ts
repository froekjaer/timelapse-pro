export interface Device {
  device_id: string
  customer_id: string | null
  site_id: string | null
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
  has_own_bt_totp?: boolean
  factory_totp_disabled?: boolean
  has_own_ssh_key?: boolean
  shared_ssh_key_disabled?: boolean
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
  camera_model?: string | null
  iso?: number | null
  aperture?: string | null
  shutter_speed?: string | null
  exposure_time?: string | null
  gps_lat?: number | null
  gps_lon?: number | null
  gps_alt_m?: number | null
  gps_source?: string | null
  azimuth_deg?: number | null
  tilt_deg?: number | null
  mount_height_m?: number | null
  fov_horizontal_deg?: number | null
  fov_vertical_deg?: number | null
  perspective?: string | null
  xmp_written?: boolean | null
  ai_result?:      string | null
  ai_analyzed_at?: string | null
  ai_tags?:        string[] | null
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
  cam_non_enforceable_json: string | null
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
    power_mode?: 'relay' | 'usb_powered'
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
  bottom?: string
  top?: string
  step?: string
  choices: { index: string; label: string }[]
  readonly: boolean
}

export interface CameraProfile {
  driver: string
  profile_key: string
  profile_name: string
  detected_model: string
  gphoto2_port: string
  features: Record<string, boolean>
  camera_capabilities?: Record<string, boolean>
  capture_settings: Record<string, string[]>
  config_commands?: Record<string, { path?: string; skip?: boolean; value_map?: Record<string, string>; skip_values?: string[] }>
  focus_controls?: Record<string, any>
  actions: Record<string, string>
}

export interface DebugMode {
  enabled: boolean
  relay_always_on: boolean
  config_poll_s: number
  support_tier: string
  // R17 (2026-07-05): tidsstempler til audit-spor + auto-timeout-håndhævelse
  // (se _debug_mode_auto_timeout_loop i headend/main.py) — enabled_at kan
  // mangle for ældre aktiveringer fra før dette blev indført.
  enabled_at?: string | null
  disabled_at?: string | null
  disabled_reason?: 'manual' | 'auto_timeout' | string
}
