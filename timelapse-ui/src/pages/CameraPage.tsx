import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Building2, MapPin, Camera, Save, Trash2, ChevronRight,
         CheckCircle, Beaker, Image, PlusCircle } from 'lucide-react'
import { getApiUrl, pathSegment } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    ...opts
  }).then(r => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
}

interface CameraDevice {
  device_id: string
  site_id?: string
  camera_name?: string
  camera_index: number
  relay_gpio_camera: number
  relay_gpio_modem: number
  camera_model?: string
  status: string
  last_seen?: string
  first_seen?: string
  app_version?: string
  config_overrides: Record<string, unknown>
  customer_name?: string
  site_name?: string
  location_name?: string
}

interface CameraLocation {
  id: string
  camera_name: string
  site_id: string | null
  site_name: string | null
  customer_id: string | null
  customer_name: string | null
  model: string | null
  notes: string | null
  baseline_description: string | null
  context_notes: string | null
  retention_days?: number | null  // P0-05: Antal dage billeder skal opbevares (default 365)
}

interface CameraOption { id: string; camera_name: string; site_name?: string; customer_name?: string; customer_id?: string; site_id?: string }

interface ConfigResolutionLayer {
  key: 'global' | 'customer' | 'site' | 'camera'
  config: Record<string, unknown>
}

interface ConfigResolution {
  layers: ConfigResolutionLayer[]
  effective_config: Record<string, unknown>
}

interface ParamRow {
  key: string
  label: string
  section: string
  type: 'number' | 'text' | 'select' | 'boolean'
  options?: string[]
  unit?: string
  placeholder?: string
  description?: string
  tooltip?: string
}

interface DriftDimension {
  dimension: 'focus' | 'exposure' | 'white_balance'
  enabled: boolean
  sufficient_data: boolean
  baseline_n: number
  recent_n: number
  baseline_mean: number | null
  baseline_stdev: number | null
  recent_mean: number | null
  delta: number | null
  z_score: number | null
  drift_suspected: boolean
  message: string
  config: Record<string, unknown>
  recommendations: Array<{
    type: string
    reason: string
    confidence: number
    params?: Record<string, unknown>
  }>
}

interface DriftAnalysis {
  camera_id: string
  camera_name: string
  dimensions: {
    focus: DriftDimension
    exposure: DriftDimension
    white_balance: DriftDimension
  }
}

const CAMERA_PARAMS: ParamRow[] = [
  // Optagelse
  { key: 'schedule.interval_minutes', label: 'Optagelsesinterval', section: 'Optagelse', type: 'number', unit: 'min', placeholder: '60', description: 'Minutter mellem hvert billede', tooltip: 'Minutter mellem captures. 60 = et billede i minuttet, 10 = hvert 10. minut. Kortere interval = flere billeder men mere disk/usage. Typisk 10-120 minutter.' },
  { key: 'schedule.capture_mode',     label: 'Tilstand', section: 'Optagelse', type: 'select', options: ['interval', 'fixed_times'], description: 'Interval = hvert N min, Fixed = faste tidspunkter', tooltip: 'Interval tager billeder med fast mellemrum. Fixed tager billeder på specifikke tidspunkter (fx 08:00, 12:00, 16:00). Koordineres på tværs af kameraer på samme site.' },
  // Kamera
  { key: 'camera.iso',               label: 'ISO', section: 'Kamera', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400'], description: 'Lysfølsomhed — Auto anbefales til varierende lys', tooltip: 'ISO lysfølsomhed. Lav ISO (100-200) = mindre støj men kræver mere lys. Høj ISO (1600+) = kan bruges i mørke men med mere støj. Auto anbefales til varierende vejr.' },
  { key: 'camera.shutter_speed',     label: 'Lukkerhastiged', section: 'Kamera', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500', '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'], description: 'Eksponeringstid i sekunder', tooltip: 'Eksponeringstid. Hurtig (1/1000+) fryser bevægelse men kræver meget lys. Langsom (1/15) kan give motion blur i mørke. Auto anbefales til timelapse.' },
  { key: 'camera.aperture',          label: 'Blænde', section: 'Kamera', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '8', '9', '10', '11', '13', '14', '16', '18', '20', '22'], description: 'f-tal — højere = skarpere baggrund', tooltip: 'Blændeåbning (f-tal). Lav f-tal (3.5-5.6) = sløret baggrund (bokeh). Høj f-tal (11-22) = skarpe forgrund og baggrund. Påvirker også hvor meget lys der kommer ind.' },
  { key: 'camera.exposurecompensation', label: 'Eksponeringskompensation', section: 'Kamera', type: 'select', options: ['-2.0', '-1.7', '-1.3', '-1.0', '-0.7', '-0.3', '0', '+0.3', '+0.7', '+1.0', '+1.3', '+1.7', '+2.0'], description: 'EV justering. Negativ dæmper direkte sol/refleks, positiv hjælper mørke billeder', tooltip: 'EV (exposure value) kompensation. Negativ (-1 til -2) dæmper direkte sol og refleks. Positiv (+0.3 til +1) hjælper mørke scener. Autogen values for perioder med ekstremt lys.' },
  { key: 'camera.whitebalance',      label: 'Hvidbalance', section: 'Kamera', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluorescent', 'Flash'], description: 'Auto anbefales til varierende vejr', tooltip: 'Hvidbalance indstilling. Auto tilpasser sig vejr og lysforhold. Daylight til solrige dage. Cloudy til overskyet vejr. Bruges til at undgå orange/blue farvestik.' },
  { key: 'camera.serial_number',     label: 'Kamera serienummer', section: 'Hardware', type: 'text', placeholder: 'fx d12b869bf88a4b719094a801bdaa41c7', description: 'gphoto2 serienummer — bruges til stabil USB port identificering ved multi-kamera', tooltip: 'gphoto2 unikt serienummer. Bruges til at identificere kameraet selvom USB porten ændres. Findes med gphoto2 --auto-detect. Nødvendig ved multi-kamera opsætninger.' },
  { key: 'camera.power_mode',        label: 'Strømstyring', section: 'Hardware', type: 'select', options: ['relay', 'usb_powered'], description: 'relay = agenten tænder/slukker via GPIO; usb_powered = kameraet har konstant strøm og går selv i standby', tooltip: 'Relay = fuld strømstyring via GPIO (tænd/sluk). usb_powered = kameraet har konstant strøm og går selv i standby. Relay sparer strøm men kræver ekstra hardware.' },
  { key: 'camera.relay_gpio_pin',    label: 'Relay GPIO (kamera)', section: 'Hardware', type: 'number', placeholder: '356', description: 'GPIO pin til kamera relay', tooltip: 'GPIO pin nummer til kamera relay. Pin skal være tilgængelig på Edge board og konfigureret i overlay. Typisk 356 for standard Orange Pi setup.' },
  { key: 'camera.relay_on_seconds_before', label: 'Varmetid (sekunder)', section: 'Hardware', type: 'number', placeholder: '10', description: 'Sekunder relay er tændt før capture', tooltip: 'Sekunder kameraet skal varme op før capture. Kameraer bruger tid på at initialisere. 10 sekunder er typisk. For kort kan give fejl ved capture.' },
  { key: 'camera.relay_off_seconds_after', label: 'Nedkølingstid (sekunder)', section: 'Hardware', type: 'number', placeholder: '5', description: 'Sekunder relay er tændt efter capture', tooltip: 'Sekunder kameraet forbliver tændt efter capture for at gemme billede. 5 sekunder er typisk. For kort kan afbryde skrivning til SD kort.' },
  // Orientering og montering
  { key: 'camera.azimuth_deg',       label: 'Azimut (retning)', section: 'Orientering', type: 'number', unit: '°', placeholder: '247', description: 'Retning kameraet peger — 0=Nord, 90=Øst, 180=Syd, 270=Vest', tooltip: 'Kompass-retning kameraet peger. 0° = Nord, 90° = Øst, 180° = Syd, 270° = Vest. Bruges til solberegning og site dokumentation.' },
  { key: 'camera.tilt_deg',          label: 'Vertikal vinkel (tilt)', section: 'Orientering', type: 'number', unit: '°', placeholder: '-15', description: 'Negativ = skrå ned, 0 = vandret, positiv = skrå op', tooltip: 'Vertikal vinkel i grader. Negativ = kamera peger nedad. 0° = horisontal. Positiv = kamera peger opad. Typisk -10° til -30° for timelapse.' },
  { key: 'camera.mount_height_m',    label: 'Montagehøjde', section: 'Orientering', type: 'number', unit: 'm', placeholder: '8', description: 'Meter over terræn', tooltip: 'Montagehøjde i meter over jorden. Bruges til dokumentation og planlægning. Typisk 3-15m for bygninger.' },
  { key: 'camera.fov_horizontal_deg',label: 'Horisontalt FOV', section: 'Orientering', type: 'number', unit: '°', placeholder: '62', description: 'Synsfelt horisontalt — afhænger af linse og sensor', tooltip: 'Synsfelt (Field of View) horisontalt i grader. Bestemt af linse og sensor. Typisk 45-75°. Bruges til beregne coveret område.' },
  { key: 'camera.fov_vertical_deg',  label: 'Vertikalt FOV', section: 'Orientering', type: 'number', unit: '°', placeholder: '40', description: 'Synsfelt vertikalt', tooltip: 'Synsfelt (Field of View) vertikalt i grader. Bestemt af linse og sensor. Typisk 30-50°. Bruges til beregne coveret område.' },
  { key: 'camera.perspective',       label: 'Perspektiv', section: 'Orientering', type: 'select', options: ['eye_level', 'high_angle', 'low_angle', 'birds_eye', 'worms_eye'], description: 'Beskriver kameravinklen til billedredigering', tooltip: 'Kameraperspektiv til billedbehandling. eye_level = normal øhøjde, high_angle = fra oven, low_angle = fra neden, birds_eye = fugleperspektiv, worms_eye = ormeperspektiv.' },
  // Kvalitet
  { key: 'quality.blur_threshold',   label: 'Skarphed minimum', section: 'Kvalitet', type: 'number', placeholder: '80', description: 'Billeder under denne score markeres som fejl', tooltip: 'Minimum blur_score (0-100). Billeder under denne værdi markeres som uskarpe. 80 = moderat krav, 90+ = høj krav. For lav risikerer uskarpe billeder i timelapse.' },
  { key: 'quality.dark_threshold',   label: 'Mørk grænse', section: 'Kvalitet', type: 'number', placeholder: '25', description: 'Gennemsnitlig lysstyrke under denne = for mørkt', tooltip: 'Minimum brightness_mean (0-255). Billeder under denne værdi er for mørke. 25 = typisk nat-grænse. Lavere = accepterer mørkere billeder.' },
  { key: 'quality.bright_threshold', label: 'Lys grænse', section: 'Kvalitet', type: 'number', placeholder: '230', description: 'Gennemsnitlig lysstyrke over denne = overbelyst', tooltip: 'Maximum brightness_mean (0-255). Billeder over denne værdi er overbelyste. 230 = typisk dag-grænse. Højere = accepterer lysere billeder.' },
  { key: 'quality.adaptive_exposure.enabled', label: 'Adaptiv EV', section: 'Kvalitet', type: 'boolean', description: 'Edge justerer næste billede +/- efter lys/refleks QA', tooltip: 'Aktiver automatisk eksponeringsjustering baseret på QA-feedback. Edge justerer EV op/ned hvis billeder er for mørke/lyse. Kræver adaptive_exposure.step_ev.' },
  { key: 'quality.adaptive_exposure.step_ev', label: 'EV trin', section: 'Kvalitet', type: 'number', placeholder: '0.3', description: 'Hvor meget kompensation ændres per QA-signal', tooltip: 'EV justering per QA-feedback (0.1-1.0). 0.3 = typisk. Lavere = finere justering. Højere = hurtigere men kan oscillere.' },
  { key: 'quality.edge_ai.enabled', label: 'Edge QA AI', section: 'Kvalitet', type: 'boolean', description: 'Aktiver lokal QA for snavs, sne, dug og refleks', tooltip: 'Aktiver Edge AI for kvalitetssikring. Detekterer snavs på linsen, sne, dug, og refleksproblemer. Kræver edge_ai.mode og NPU runner/model konfiguration.' },
  { key: 'quality.edge_ai.mode', label: 'AI mode', section: 'Kvalitet', type: 'select', options: ['off', 'monitor', 'assist', 'autonomous', 'npu_first', 'lab'], description: 'Monitor analyserer kun; assist/autonomous kan justere EV; lab er til aktiv kalibrering', tooltip: 'AI drift mode. off = deaktiveret. monitor = analyse kun. assist = foreslår EV. autonomous = auto-juster EV. npu_first = brug NPU først. lab = kalibreringstilstand.' },
  { key: 'quality.edge_ai.prefer_npu', label: 'Brug NPU hvis mulig', section: 'Kvalitet', type: 'boolean', description: 'Bruger lokal NPU-runner/model når installeret på Edge', tooltip: 'Foretræk lokal NPU acceleration hvis tilgængelig. NPU er hurtigere og bruger mindre strøm end CPU. Fallback til CPU hvis NPU ikke tilgængelig.' },
  { key: 'quality.edge_ai.runner', label: 'NPU runner', section: 'Kvalitet', type: 'text', placeholder: '/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py', description: 'Lokal kommando der returnerer QA JSON', tooltip: 'Kommando til NPU runner script. Skal returnere JSON med QA scores. Typisk Python script der wrapper NPU binary. Skel mellem case-sti og permissions.' },
  { key: 'quality.edge_ai.model_path', label: 'NPU model', section: 'Kvalitet', type: 'text', placeholder: '/opt/timelapse/models/edge_qa.nb', description: 'Vendor/NPU modelsti på Edge', tooltip: 'Sti til NPU model fil (.nb format). Model skal være kompatibel med NPU hardware. Kontroller størrelse og version ved opdatering.' },
  { key: 'quality.edge_ai.vendor_binary', label: 'VIPLite wrapper', section: 'Kvalitet', type: 'text', placeholder: '/opt/timelapse/bin/edge_qa_viplite', description: 'Valgfri board-lokal binary der kører .nb modellen og returnerer scores JSON', tooltip: 'Valgfri vendor binary der kører .nb modellen. Bruges hvis NPU kræver specifik wrapper.typisk VIPLite på Orange Pi. Lad være tom hvis ikke nødvendigt.' },
  { key: 'quality.drift_detection.focus.enabled', label: 'Fokus-drift-alarm', section: 'Kvalitet', type: 'boolean', description: 'Alarmerer hvis skarpheden systematisk falder over tid (manuel fokus kan glide)', tooltip: 'Aktiver drift-detektion for fokus. Manuel fokus kan glide over uger/måneder. Alarmer når z_score over tærskel. Kræver tilstrækkelig historik (7+ dage).' },
  { key: 'quality.drift_detection.focus.z_threshold', label: 'Fokus-følsomhed', section: 'Kvalitet', type: 'number', placeholder: '2.0', description: 'Antal standardafvigelser fra kameraets egen baseline før der alarmeres — lavere = mere følsom', tooltip: 'Z-score tærskel for fokus-drift. 2.0 = typisk. Lavere = mere følsom (flere alarms). Højere = mindre følsom (kan gå glip af reel drift).' },
  { key: 'quality.drift_detection.exposure.enabled', label: 'Eksponerings-drift-alarm', section: 'Kvalitet', type: 'boolean', description: 'Alarmerer hvis lysstyrken systematisk skifter over tid (støv/tåge/sæson)', tooltip: 'Aktiver drift-detektion for eksponering. Detekterer støv, tåge, og sæson-ændringer. Alarmer når brightness_mean ændrer sig systematisk.' },
  { key: 'quality.drift_detection.exposure.z_threshold', label: 'Eksponerings-følsomhed', section: 'Kvalitet', type: 'number', placeholder: '2.5', tooltip: 'Z-score tærskel for eksponerings-drift. 2.5 = typisk (højere end fokus da lys naturligt variere mere). Lavere = mere følsom.' },
  { key: 'quality.drift_detection.white_balance.enabled', label: 'Hvidbalance-drift-alarm', section: 'Kvalitet', type: 'boolean', description: 'Kræver at edge-optimizeren rapporterer hvidbalance-data — slået fra som default', tooltip: 'Aktiver drift-detektion for hvidbalance. Kræver at edge-optimizeren rapporterer wb_cast_strength. Default OFF da data ofte mangler.' },
  { key: 'quality.drift_detection.white_balance.z_threshold', label: 'Hvidbalance-følsomhed', section: 'Kvalitet', type: 'number', placeholder: '2.0', tooltip: 'Z-score tærskel for hvidbalance-drift. 2.0 = typisk. Kun relevant hvis enabled og wb data rapporteres.' },
  // Diagnostik
  { key: 'diagnostics.sync_poll_interval_minutes', label: 'Sync-poll interval', section: 'Diagnostik', type: 'number', unit: 'min', placeholder: '5', description: 'Minutter mellem konsolideret sync (config + diagnostik + SIEM + opdateringer)', tooltip: 'Minutter mellem hver samlet sync-poll til headend. Ét kald dækker config-hentning, diagnostik-upload, SIEM-log-forward og tjek for opdateringer. 5 = hvert 5. minut. Kortere = hurtigere respons men mere trafik.' },
]

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const parts = path.split('.')
  let val: unknown = obj
  for (const p of parts) {
    if (val && typeof val === 'object') val = (val as Record<string, unknown>)[p]
    else return ''
  }
  return val != null ? String(val) : ''
}

function setNestedValue(obj: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const result = { ...obj }
  const parts = path.split('.')
  if (parts.length === 1) {
    result[parts[0]] = value
  } else {
    const section = parts[0]
    const rest = parts.slice(1).join('.')
    result[section] = setNestedValue((result[section] as Record<string, unknown>) || {}, rest, value)
  }
  return result
}

const TZ = () => localStorage.getItem('timelapse_timezone') ?? 'Europe/Copenhagen'

export function CameraPage() {
  const { deviceId } = useParams<{ deviceId: string }>()
  const navigate = useNavigate()
  const [device, setDevice]           = useState<CameraDevice | null>(null)
  const [loading, setLoading]         = useState(true)
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError]             = useState<string | null>(null)

  // Editable fields
  const [cameraName, setCameraName]   = useState('')
  const [baselineDescription, setBaselineDescription] = useState('')
  const [contextNotes, setContextNotes]               = useState('')
  const [retentionDays, setRetentionDays]             = useState(99999)  // P0-05: Retention policy (default)
  const [cameraIndex, setCameraIndex] = useState(0)
  const [relayCamera, setRelayCamera] = useState(356)
  const [relayModem, setRelayModem]   = useState(361)
  const [overrides, setOverrides]     = useState<Record<string, unknown>>({})
  const [sites, setSites]             = useState<{id:string, name:string, customer_name:string}[]>([])
  const [assignSiteId, setAssignSiteId] = useState('')
  const [assigning, setAssigning]     = useState(false)

  // ── Kamera lokation ──────────────────────────────────────────────────────
  const [cameraLocation, setCameraLocation] = useState<CameraLocation | null>(null)
  const [allCameras, setAllCameras]         = useState<CameraOption[]>([])
  const [reassignCamId, setReassignCamId]   = useState('')
  const [reassigning, setReassigning]       = useState(false)
  const [creatingLocation, setCreatingLocation] = useState(false)
  const [locationExpanded, setLocationExpanded] = useState(false)

  // ── BT TOTP QR ───────────────────────────────────────────────────────────
  const [btTotp, setBtTotp]               = useState<{secret:string,sid:string,source:string,uri:string,qr_code:string,account_name:string,device_id:string|null,is_factory_default:boolean,current_code:string,seconds_remaining:number}|null>(null)
  const [btTotpLoading, setBtTotpLoading] = useState(false)
  const [btTotpRegen, setBtTotpRegen]     = useState(false)
  const [btTotpError, setBtTotpError]     = useState<string | null>(null)
  const [btTotpCopied, setBtTotpCopied]   = useState(false)
  const [btTotpCountdown, setBtTotpCountdown] = useState(0)

  // ── Drift-analyse (fase 1, 2026-07-07) ─────────────────────────────────────
  const [driftData, setDriftData]         = useState<DriftAnalysis | null>(null)
  const [driftLoading, setDriftLoading]   = useState(false)
  const [driftError, setDriftError]       = useState<string | null>(null)

  useEffect(() => {
    fetch(`${getApiUrl()}/api/admin/sites`).then(r=>r.json()).then((ss:any[]) => setSites(ss)).catch(()=>{})
    // Load all cameras for reassignment picker
    fetch(`${getApiUrl()}/api/admin/cameras`).then(r=>r.json()).then((cs:any[]) => setAllCameras(cs)).catch(()=>{})
  }, [])

  async function loadCameraLocation(): Promise<CameraLocation | null> {
    if (!deviceId) return null
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/devices/${encodeURIComponent(deviceId)}/camera-location`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      if (r.ok) {
        const data = await r.json()
        const cam = data.camera ?? null
        console.log('DEBUG loadCameraLocation:', { deviceId, camera: cam, retention_days: cam?.retention_days })
        setCameraLocation(cam)
        if (cam) {
          setBaselineDescription(cam.baseline_description ?? '')
          setContextNotes(cam.context_notes ?? '')
          setRetentionDays(cam.retention_days ?? 99999)  // P0-05: Load retention
        }
        return cam
      } else {
        console.error('DEBUG loadCameraLocation failed:', r.status)
      }
    } catch (e) {
      console.error('DEBUG loadCameraLocation error:', e)
    }
    return null
  }

  async function loadResolvedConfig() {
    if (!deviceId) return
    try {
      const data: ConfigResolution = await api(`/api/admin/config-resolution?device_id=${encodeURIComponent(deviceId)}`)
      const cameraLayer = data.layers?.find(layer => layer.key === 'camera')
      setOverrides(cameraLayer?.config ?? {})
      const cameraConfig = (data.effective_config?.camera ?? {}) as Record<string, unknown>
      if (cameraConfig.relay_gpio_pin != null) setRelayCamera(Number(cameraConfig.relay_gpio_pin) || 356)
      const modemConfig = (data.effective_config?.modem ?? {}) as Record<string, unknown>
      if (modemConfig.modem_relay_gpio_pin != null) setRelayModem(Number(modemConfig.modem_relay_gpio_pin) || 361)
    } catch {
      setOverrides({})
    }
  }

  async function loadDriftAnalysis(cameraId: string) {
    setDriftLoading(true)
    setDriftError(null)
    try {
      const data: DriftAnalysis = await api(`/api/cameras/${encodeURIComponent(cameraId)}/drift-analysis`)
      setDriftData(data)
    } catch (e: any) {
      console.error('Failed to load drift analysis:', e)
      setDriftError(e?.message ?? 'Kunne ikke hente drift-analyse')
    } finally {
      setDriftLoading(false)
    }
  }

  // Live-koden roterer hvert 30. sekund — tæl ned lokalt, og hent den næste
  // kode fra headend når den nuværende udløber. Kun aktiv mens panelet
  // faktisk er åbent for dette kamera. Placeret før komponentens early
  // returns (loading/!device nedenfor) — Hooks skal kaldes ubetinget.
  useEffect(() => {
    if (!btTotp) return
    let refreshing = false
    const id = window.setInterval(() => {
      setBtTotpCountdown(prev => {
        if (prev <= 1) {
          if (!refreshing) { refreshing = true; loadBtTotp() }
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => window.clearInterval(id)
  }, [btTotp?.current_code])

  useEffect(() => {
    if (!deviceId) return
    api(`/api/admin/devices/${pathSegment(deviceId)}`)
      .then(async (d: any) => {
        const dev = d.device ?? d
        setDevice(dev)
        setCameraName(dev.camera_name ?? '')
        setCameraIndex(dev.camera_index ?? 0)
        setRelayCamera(dev.relay_gpio_camera ?? 356)
        setRelayModem(dev.relay_gpio_modem ?? 361)
        const camLoc = await loadCameraLocation()
        await loadResolvedConfig()
        // Load drift analysis when we have a camera location
        if (camLoc?.id) {
          loadDriftAnalysis(camLoc.id)
        }
      })
      .catch(() => setError('Kunne ikke hente enhed'))
      .finally(() => setLoading(false))
    loadCameraLocation()
  }, [deviceId])

  function setParam(path: string, value: string) {
    setOverrides(prev => setNestedValue(prev, path, value === '' ? null : value))
  }

  async function save() {
    setSaving(true)
    try {
      const nextOverrides = setNestedValue(
        setNestedValue(overrides, 'camera.relay_gpio_pin', relayCamera),
        'modem.modem_relay_gpio_pin',
        relayModem,
      )
      if (cameraLocation?.id) {
        const payload = {
          camera_name: cameraName,
          baseline_description: baselineDescription,
          context_notes: contextNotes,
          retention_days: retentionDays,
        }
        console.log('DEBUG save: sending payload:', { cameraId: cameraLocation.id, payload })
        await api(`/api/admin/cameras/${encodeURIComponent(cameraLocation.id)}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        console.log('DEBUG save: after PUT, retentionDays =', retentionDays)
        await api(`/api/admin/config-overrides/camera/${encodeURIComponent(cameraLocation.id)}`, {
          method: 'PUT',
          body: JSON.stringify({ mode: 'merge', config_overrides: nextOverrides }),
        })
        setOverrides(nextOverrides)
        console.log('DEBUG save: before loadCameraLocation, retentionDays =', retentionDays)
        await loadCameraLocation()
        console.log('DEBUG save: after loadCameraLocation, retentionDays =', retentionDays)
      } else {
        await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}/info`, {
          method: 'PUT',
          body: JSON.stringify({ camera_name: cameraName }),
        })
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error('DEBUG save error:', e)
      setError('Kunne ikke gemme')
    } finally {
      setSaving(false)
    }
  }

  async function deleteDevice() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}`, { method: 'DELETE' })
      navigate('/')
    } catch {
      setError('Sletning fejlede')
      setConfirmDelete(false)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>
  if (!device) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-500">{error}</div>

  const sections = [...new Set(CAMERA_PARAMS.map(p => p.section))]
  const lastSeen = device.last_seen
    ? new Date(device.last_seen + 'Z').toLocaleString('da-DK', { timeZone: TZ(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '–'

  async function assignToSite() {
    if (!assignSiteId) return
    setAssigning(true)
    try {
      await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}/assign`, {
        method: 'PUT',
        body: JSON.stringify({ site_id: assignSiteId })
      })
      const d = await api(`/api/admin/devices/${pathSegment(deviceId ?? '')}`)
      setDevice(d)
    } catch { /* bevidst ignoreret — setAssigning(false) i finally rydder UI-tilstanden */ } finally { setAssigning(false) }
  }

  async function loadBtTotp() {
    if (!cameraLocation?.id) return
    setBtTotpLoading(true)
    setBtTotpError(null)
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraLocation.id)}/bt-totp-qr`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      if (r.ok) {
        const data = await r.json()
        setBtTotp(data)
        setBtTotpCountdown(data.seconds_remaining ?? 0)
      } else {
        const body = await r.json().catch(() => ({}))
        setBtTotpError(body.detail ?? 'Kunne ikke hente lokal adgang')
      }
    } catch { setBtTotpError('Netværksfejl ved hentning af lokal adgang') }
    finally { setBtTotpLoading(false) }
  }

  async function provisionBtTotp(rotate = false) {
    if (!cameraLocation?.id) return
    if (rotate && !confirm('Rotér lokal adgang? Den eksisterende QR-kode og TOTP-registrering bliver ugyldig.')) return
    setBtTotpRegen(true)
    setBtTotpError(null)
    try {
      const r = await fetch(`${getApiUrl()}/api/admin/cameras/${encodeURIComponent(cameraLocation.id)}/bt-totp-regenerate`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? 'Kunne ikke oprette lokal adgang')
      }
      await loadBtTotp()
    } catch (error) { setBtTotpError(error instanceof Error ? error.message : 'Kunne ikke oprette lokal adgang') }
    finally { setBtTotpRegen(false) }
  }

  function addBtTotpToAuthenticator() {
    if (btTotp?.uri) window.location.assign(btTotp.uri)
  }

  async function copyBtTotpSetupKey() {
    if (!btTotp?.secret) return
    try {
      await navigator.clipboard.writeText(btTotp.secret)
      setBtTotpCopied(true)
      window.setTimeout(() => setBtTotpCopied(false), 5000)
    } catch {
      setBtTotpError('Browseren kunne ikke kopiere opsætningsnøglen')
    }
  }

  async function reassignToCamera() {
    if (!reassignCamId || !deviceId) return
    setReassigning(true)
    try {
      await api(`/api/admin/cameras/${encodeURIComponent(reassignCamId)}/assign`, {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, assigned_by: 'admin-ui' }),
      })
      await loadCameraLocation()
      const d = await api(`/api/admin/devices/${pathSegment(deviceId)}`)
      setDevice(d.device ?? d)
      setReassignCamId('')
    } catch { setError('Omtildeling fejlede') }
    finally { setReassigning(false) }
  }

  async function createAndAssignLocation() {
    if (!deviceId || !device?.site_id) {
      setError('Enheden skal først være tildelt et site')
      return
    }
    setCreatingLocation(true)
    try {
      const created = await api('/api/admin/cameras', {
        method: 'POST',
        body: JSON.stringify({
          site_id: device.site_id,
          camera_name: cameraName || device.camera_name || 'Kamera 1',
          model: device.camera_model || undefined,
          config: overrides,
        }),
      })
      await api(`/api/admin/cameras/${encodeURIComponent(created.id)}/assign`, {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, assigned_by: 'admin-ui', assignment_type: 'manual' }),
      })
      await loadCameraLocation()
      await loadResolvedConfig()
      const d = await api(`/api/admin/devices/${pathSegment(deviceId)}`)
      setDevice(d.device ?? d)
      setAllCameras(await api('/api/admin/cameras'))
    } catch {
      setError('Kunne ikke oprette og binde kamera-lokation')
    } finally {
      setCreatingLocation(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6 text-sm text-gray-400">
        <Link to="/" className="p-1 rounded hover:bg-gray-100">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        {device.customer_name && (
          <>
            <Building2 className="w-3.5 h-3.5" />
            <span>{device.customer_name}</span>
            <ChevronRight className="w-3 h-3" />
          </>
        )}
        {device.site_name && (
          <>
            <MapPin className="w-3.5 h-3.5" />
            <span>{device.site_name}</span>
            <ChevronRight className="w-3 h-3" />
          </>
        )}
        <Camera className="w-3.5 h-3.5 text-sky-500" />
        <span className="text-gray-700 font-medium">{device.camera_name || device.device_id}</span>
        <Link to={`/global-config?device_id=${encodeURIComponent(device.device_id)}`}
          className="ml-auto text-xs text-sky-600 hover:text-sky-700 hover:underline flex items-center gap-1"
          title="Se hvilken værdi hvert felt reelt bruger (arvet fra Global/Kunde/Site/Kamera) og hvor den kommer fra">
          Arvet konfiguration →
        </Link>
      </div>

      {/* ── Kamera lokation ─────────────────────────────────────────────── */}
      {cameraLocation ? (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <Camera className="w-4 h-4 text-sky-500" />
              <span className="font-medium">{cameraLocation.camera_name}</span>
              {cameraLocation.site_name && (
                <span className="text-gray-400">
                  — {cameraLocation.customer_name && `${cameraLocation.customer_name} / `}{cameraLocation.site_name}
                </span>
              )}
            </div>
            <button
              onClick={() => setLocationExpanded(v => !v)}
              className="text-xs text-sky-600 hover:underline">
              {locationExpanded ? 'Luk' : 'Omassign til anden lokation'}
            </button>
          </div>
          {locationExpanded && (
            <div className="mt-3 flex gap-2">
              <select className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
                value={reassignCamId} onChange={e => setReassignCamId(e.target.value)}>
                <option value="">Vælg kamera-lokation…</option>
                {allCameras
                  .filter(c => c.id !== cameraLocation.id)
                  .map(c => (
                    <option key={c.id} value={c.id}>
                      {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                    </option>
                  ))}
              </select>
              <button onClick={reassignToCamera} disabled={!reassignCamId || reassigning}
                className="px-3 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
                {reassigning ? '…' : 'Omassign'}
              </button>
            </div>
          )}
          <p className="mt-2 text-xs text-gray-400">
            Billeder er knyttet til lokationen — overlever udskiftning af Edge-hardware.
          </p>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
          <p className="text-sm font-medium text-amber-800 mb-1">⚠️ Ikke tildelt en kamera-lokation</p>
          <p className="text-xs text-amber-600 mb-3">
            Vælg en eksisterende lokation eller tildel via site (nedenfor) for at knytte billeder til en stabil lokation.
          </p>
          <div className="flex gap-2">
            <select className="flex-1 border border-amber-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={reassignCamId} onChange={e => setReassignCamId(e.target.value)}>
              <option value="">Vælg kamera-lokation…</option>
              {allCameras.map(c => (
                <option key={c.id} value={c.id}>
                  {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                </option>
              ))}
            </select>
            <button onClick={reassignToCamera} disabled={!reassignCamId || reassigning}
              className="px-4 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 disabled:opacity-50">
              {reassigning ? 'Tildeler…' : 'Tildel'}
            </button>
            <button onClick={createAndAssignLocation} disabled={creatingLocation || !device.site_id}
              className="inline-flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
              <PlusCircle className="w-4 h-4" />
              {creatingLocation ? 'Opretter…' : 'Opret og bind'}
            </button>
          </div>
          {/* Fallback: site-baseret tildeling */}
          {(!device.site_name || !device.customer_name) && (
            <div className="mt-3 pt-3 border-t border-amber-200">
              <p className="text-xs text-amber-700 mb-2">Eller tildel direkte til site:</p>
              <div className="flex gap-2">
                <select className="flex-1 border border-amber-200 rounded-lg px-3 py-2 text-sm bg-white"
                  value={assignSiteId} onChange={e => setAssignSiteId(e.target.value)}>
                  <option value="">Vælg site…</option>
                  {sites.map(s => (
                    <option key={s.id} value={s.id}>{s.customer_name} — {s.name}</option>
                  ))}
                </select>
                <button onClick={assignToSite} disabled={!assignSiteId || assigning}
                  className="px-4 py-2 bg-amber-400 text-white text-sm rounded-lg hover:bg-amber-500 disabled:opacity-50">
                  {assigning ? 'Tildeler…' : 'Tildel site'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      {/* Status kort */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium mb-1 ${
            device.status === 'online' ? 'bg-emerald-50 text-emerald-600' :
            device.status === 'offline' ? 'bg-red-50 text-red-500' : 'bg-gray-100 text-gray-400'
          }`}>{device.status}</div>
          <p className="text-xs text-gray-400">Sidst set {lastSeen}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-sm font-mono text-gray-600 truncate">{device.device_id}</p>
          <p className="text-xs text-gray-400 mt-1">Device ID</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <p className="text-sm text-gray-600">{device.camera_model || '–'}</p>
          <p className="text-xs text-gray-400 mt-1">Kameramodel</p>
        </div>
      </div>

      {/* Kamera identitet */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Kamera identitet</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Kamera navn</label>
            <input type="text" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="fx Kamera 1 — Nordøst"
              value={cameraName} onChange={e => setCameraName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Kamera index</label>
            <input type="number" min={0} max={7} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={cameraIndex} onChange={e => setCameraIndex(parseInt(e.target.value) || 0)} />
            <p className="text-xs text-gray-300 mt-1">Fysisk node-index. Kamera-config gemmes på lokationen.</p>
          </div>
          {cameraLocation?.id ? (
            <div>
              <label className="text-xs text-gray-400 block mb-1">Retention (dage)</label>
              <input type="number" min={1} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={retentionDays} onChange={e => setRetentionDays(parseInt(e.target.value) || 99999)} />
              <p className="text-xs text-gray-300 mt-1">Antal dage billeder opbevares før automatisk sletning (GDPR)</p>
            </div>
          ) : (
            <div>
              <label className="text-xs text-gray-400 block mb-1">Retention (dage)</label>
              <div className="text-xs text-gray-400 italic">Tildel en kamera-lokation for at konfigurere retention</div>
            </div>
          )}
          <div>
            <label className="text-xs text-gray-400 block mb-1">Relay GPIO (kamera)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={relayCamera} onChange={e => setRelayCamera(parseInt(e.target.value) || 356)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Relay GPIO (modem)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={relayModem} onChange={e => setRelayModem(parseInt(e.target.value) || 361)} />
          </div>
        </div>
      </div>

      {/* AI-kontekst / baseline — fodres til vision-prompten pr. billede */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">AI-kontekst</h2>
        <p className="text-xs text-gray-400 mb-4">
          Hjælper AI'en med at vurdere afvigelser (ny bil, personer om natten, røg osv.). Fodres til hver billedanalyse — indeholder aldrig persondata.
        </p>
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Normalbillede — hvad viser kameraet normalt?</label>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={3}
              placeholder="fx: Udsigt over byggegrund med ét kranfundament. Indkørsel til venstre er normalt tom. Ingen aktivitet om natten."
              value={baselineDescription} onChange={e => setBaselineDescription(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Driftsnoter (hvad skal IKKE udløse falsk anomali)</label>
            <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2}
              placeholder="fx: Nabogrund til højre er under byggeri — kran dér er normal. Vej med trafik i baggrunden."
              value={contextNotes} onChange={e => setContextNotes(e.target.value)} />
          </div>
        </div>
      </div>

      {/* ── Drift-analyse (fase 1) ───────────────────────────────────────────── */}
      {driftLoading && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-5">
          <p className="text-sm text-gray-500">Indlæser drift-analyse…</p>
        </div>
      )}
      {driftError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5">
          <p className="text-sm text-amber-800">⚠️ {driftError}</p>
        </div>
      )}
      {driftData && !driftLoading && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Drift-analyse</h2>
          <p className="text-xs text-gray-400 mb-4">
            Opdager om kameraet glider ud af kalibrering over tid (fokus, eksponering, hvidbalance).
            Sammenligner nyeste billeder med ældre baseline — kun hvis nok data er tilgængeligt.
          </p>
          <div className="space-y-3">
            {(['focus', 'exposure', 'white_balance'] as const).map(dim => {
              const d = driftData.dimensions?.[dim]
              if (!d?.enabled) return null
              const icon = d.drift_suspected ? '⚠️' : d.sufficient_data ? '✓' : '○'
              const color = d.drift_suspected ? 'text-red-600' : d.sufficient_data ? 'text-green-600' : 'text-gray-400'
              const label = {
                focus: 'Fokus',
                exposure: 'Eksponering',
                white_balance: 'Hvidbalance'
              }[dim]
              return (
                <div key={dim} className="flex items-start gap-2 text-sm">
                  <span className={color}>{icon}</span>
                  <div className="flex-1">
                    <span className="font-medium text-gray-700">{label}</span>
                    {!d.sufficient_data && (
                      <span className="text-xs text-gray-400 ml-2">(ikke nok data endnu)</span>
                    )}
                    {d.sufficient_data && d.z_score !== null && (
                      <span className="text-xs text-gray-500 ml-2">
                        z-score: {d.z_score.toFixed(1)} / {((d.config?.z_threshold as number) ?? 2.0).toFixed(1)}
                      </span>
                    )}
                    <p className="text-xs text-gray-500 mt-0.5">{d.message}</p>
                  </div>
                </div>
              )
            })}
            {!driftData.dimensions?.focus?.enabled && !driftData.dimensions?.exposure?.enabled && !driftData.dimensions?.white_balance?.enabled && (
              <p className="text-xs text-gray-400 italic">
                Drift-analyse er slået fra i konfigurationen. Slå til under "Kvalitet" ovenfor.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Kamera-niveau config overrides */}
      {sections.map(section => (
        <div key={section} className="bg-white rounded-xl border border-gray-200 p-6 mb-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">{section}</h2>
          <p className="text-xs text-gray-400 mb-4">
            Kamera-niveau override — overstyrer globale defaults, kunde og site indstillinger
          </p>
          <div className="space-y-4">
            {CAMERA_PARAMS.filter(p => p.section === section).map(param => {
              const val = getNestedValue(overrides, param.key)
              return (
                <div key={param.key}>
                  <div className="flex items-center gap-2 mb-1">
                    <label className="text-xs text-gray-500 font-medium" title={param.tooltip}>{param.label}</label>
                    {param.tooltip && (
                      <span className="text-xs text-gray-400 cursor-help" title={param.tooltip}>ⓘ</span>
                    )}
                    {param.unit && <span className="text-xs text-gray-300">{param.unit}</span>}
                    {val && <span className="text-xs text-sky-500 font-medium">● Override aktiv</span>}
                  </div>
                  {param.type === 'select' ? (
                    <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                      value={val} onChange={e => setParam(param.key, e.target.value)}>
                      <option value="">— Arv fra overliggende lag —</option>
                      {param.options?.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input type={param.type} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                      placeholder={`${param.placeholder ?? ''} (tom = arv fra overliggende lag)`}
                      value={val} onChange={e => setParam(param.key, e.target.value)} />
                  )}
                  {param.description && (
                    <p className="text-xs text-gray-300 mt-0.5">{param.description}</p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* ── BT PAN TOTP QR-kode ──────────────────────────────────────────── */}
      {cameraLocation && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">BT PAN TOTP</h3>
              <p className="text-xs text-gray-400">QR-kode til lokal management adgang via Bluetooth</p>
            </div>
            <div className="flex gap-2">
              {!btTotp && !btTotpError && (
                <button onClick={loadBtTotp} disabled={btTotpLoading}
                  className="px-3 py-1.5 text-xs bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
                  {btTotpLoading ? 'Henter…' : 'Vis QR-kode'}
                </button>
              )}
              {btTotp && (
                <button onClick={() => provisionBtTotp(true)} disabled={btTotpRegen}
                  className="px-3 py-1.5 text-xs bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50">
                  {btTotpRegen ? 'Roterer…' : 'Rotér adgang'}
                </button>
              )}
            </div>
          </div>
          {btTotpError && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs text-amber-900">{btTotpError}</p>
              <button onClick={() => provisionBtTotp(false)} disabled={btTotpRegen}
                className="mt-2 px-3 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50">
                {btTotpRegen ? 'Opretter…' : 'Opret unik lokal adgang'}
              </button>
            </div>
          )}
          {btTotp && (
            <div className="flex flex-col sm:flex-row gap-4 items-start">
              <img src={btTotp.qr_code} alt="TOTP QR" className="w-36 h-36 rounded-lg border border-gray-100" />
              <div className="flex-1 text-xs space-y-2">
                {(() => {
                  const srcLabel: Record<string,string> = {
                    'global':          '🌐 Global',
                    'kunde':           '🏢 Kunde',
                    'site':            '📍 Site',
                    'kamera':          '📷 Kamera',
                  }
                  const srcColor: Record<string,string> = {
                    'global':          'bg-purple-50 text-purple-700 border-purple-200',
                    'kunde':           'bg-blue-50 text-blue-700 border-blue-200',
                    'site':            'bg-teal-50 text-teal-700 border-teal-200',
                    'kamera':          'bg-green-50 text-green-700 border-green-200',
                  }
                  const src = btTotp!.source
                  return (
                    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium border ${srcColor[src] ?? srcColor['kamera']}`}>
                      {srcLabel[src] ?? src}
                    </div>
                  )
                })()}
                <p className="text-gray-500 mt-1">
                  QR-koden er kun til lokal Edge-adgang for denne binding.
                  {btTotp!.source === 'kunde' && ' Gælder alle kameraer hos denne kunde.'}
                  {btTotp!.source === 'site' && ' Gælder alle kameraer på dette site.'}
                  {btTotp!.source === 'kamera' && ' Specifik for dette kamera.'}
                </p>
                <p className="text-gray-400 font-mono">SID: {btTotp.sid}</p>
                {btTotp.current_code && (
                  <div className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                    <span className="font-mono text-2xl tracking-[0.2em] text-gray-800">
                      {btTotp.current_code}
                    </span>
                    <span className="text-xs text-gray-400">
                      Ny kode om {btTotpCountdown}s — til direkte indtastning uden authenticator-app
                    </span>
                  </div>
                )}
                <p className="text-gray-500 font-medium">Authenticator-navn: {btTotp.account_name}</p>
                <button onClick={addBtTotpToAuthenticator}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-white bg-sky-600 rounded-lg hover:bg-sky-700">
                  Åbn i Apple Adgangskoder
                </button>
                <button onClick={copyBtTotpSetupKey}
                  className="ml-2 inline-flex items-center px-3 py-1.5 text-xs font-medium text-sky-700 border border-sky-200 rounded-lg hover:bg-sky-50">
                  {btTotpCopied ? 'Opsætningsnøgle kopieret' : 'Kopiér opsætningsnøgle'}
                </button>
                <p className="text-gray-400">På iPhone åbner standardlinket Apple Adgangskoder. Til en anden app vælges “indtast opsætningsnøgle” i appen og den kopierede nøgle indsættes. iOS tillader ikke, at en webside vælger authenticator-app for brugeren.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Hurtige links */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <Link to={`/devices/${pathSegment(deviceId ?? '')}`}
          className="flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
          <Image className="w-5 h-5 text-gray-400" />
          <div>
            <p className="text-sm font-medium text-gray-700">Billeder og captures</p>
            <p className="text-xs text-gray-400">Se tidslinje og lightbox</p>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-300 ml-auto" />
        </Link>
        <Link to={`/devices/${pathSegment(deviceId ?? '')}/lab`}
          className="flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
          <Beaker className="w-5 h-5 text-purple-400" />
          <div>
            <p className="text-sm font-medium text-gray-700">LAB mode</p>
            <p className="text-xs text-gray-400">Live preview og parametre</p>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-300 ml-auto" />
        </Link>
      </div>

      {/* Gem og slet */}
      <div className="flex items-center justify-between">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Gemt!' : saving ? 'Gemmer…' : 'Gem ændringer'}
        </button>
        <button onClick={deleteDevice}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors ${
            confirmDelete ? 'bg-red-500 text-white border-red-500' : 'text-red-400 border-red-200 hover:bg-red-50'
          }`}>
          <Trash2 className="w-4 h-4" />
          {confirmDelete ? 'Bekræft sletning' : 'Slet kamera'}
        </button>
      </div>
      {confirmDelete && (
        <p className="text-xs text-red-400 mt-2 text-right">
          Klik igen for at bekræfte — dette kan ikke fortrydes!
        </p>
      )}
    </div>
  )
}
