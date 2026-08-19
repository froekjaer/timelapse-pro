import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle, Globe, Layers, RotateCcw, Save } from 'lucide-react'
import { getApiUrl } from '../api/client'

function api(path: string, opts?: RequestInit) {
  return fetch(`${getApiUrl()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  }).then(async r => {
    if (!r.ok) throw new Error(await r.text().catch(() => `${r.status}`))
    return r.json()
  })
}

type ConfigObject = Record<string, any>
type LayerKey = 'global' | 'customer' | 'site' | 'camera'

interface ConfigDefaults {
  schedule: ConfigObject
  camera: ConfigObject
  quality: ConfigObject
  storage: ConfigObject
  diagnostics: ConfigObject
  system: ConfigObject
  session_policy: ConfigObject
}

interface EntityOption {
  id: string
  name?: string
  camera_name?: string
  customer_id?: string
  customer_name?: string
  site_id?: string
  site_name?: string
}

interface ResolvedField {
  path: string
  section: string
  key: string
  values: Record<LayerKey, any>
  effective_value: any
  inherited_value: any
  source: LayerKey | 'factory'
  changed_from_global: boolean
  overridden: boolean
}

interface Resolution {
  context: {
    customer_id?: string | null
    customer_name?: string | null
    site_id?: string | null
    site_name?: string | null
    camera_id?: string | null
    camera_name?: string | null
    device_id?: string | null
  }
  layers: Array<{ key: LayerKey; label: string; entity_id: string | null; entity_name: string | null; config: ConfigObject }>
  effective_config: ConfigObject
  fields: ResolvedField[]
}

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'text' | 'select' | 'boolean' | 'user_multiselect'
  options?: string[]
  unit?: string
  placeholder?: string
  description?: string
  tooltip?: string
  default?: string | number | boolean
}

const SECTIONS: { key: keyof ConfigDefaults; label: string; description: string; fields: FieldDef[] }[] = [
  {
    key: 'schedule',
    label: 'Optagelsesplan',
    description: 'Frekvens, tidszone og optagelseslogik.',
    fields: [
      { key: 'timezone', label: 'Tidszone', type: 'select', options: ['Europe/Copenhagen', 'Europe/London', 'Europe/Berlin', 'UTC'], default: 'Europe/Copenhagen',
        tooltip: 'Tidszone for schedule. Sikrer at captures sker på korrekte lokale tider for hver site. Vigtig når sites er i forskellige tidszoner. Ændringer påvirker alle fremtidige captures.' },
      { key: 'capture_mode', label: 'Tilstand', type: 'select', options: ['interval', 'fixed_times'], default: 'interval',
        tooltip: 'Interval (fast frekvens) eller fixed_times (specificerede tidspunkter). Interval bruges til kontinuerlig timelapse af byggeprocesser. Fixed times er til periodiske status-billeder. Vælg baseret på projektets behov.' },
      { key: 'interval_minutes', label: 'Interval', type: 'number', unit: 'min', placeholder: '60', default: 60,
        tooltip: 'Minutter mellem captures i interval mode. Lavere værdi = tættere timelapse men mere plads og strøm. Typisk 5-60 minutter for byggepladser. Juster baseret på projektets tempo og hændelser.' },
    ],
  },
  {
    key: 'camera',
    label: 'Kamera',
    description: 'Kamerastyring, eksponering, strøm og orientering.',
    fields: [
      { key: 'power_mode', label: 'Strømstyring', type: 'select', options: ['relay', 'usb_powered'], default: 'relay',
        tooltip: 'Relay (ekstern strømstyring via GPIO) eller usb_powered (kameraet tændt altid). Relay anbefales for battery saving og kamera levetid. USB kræver konstant forbindelse. Relay slukker kameraet mellem captures.' },
      { key: 'iso', label: 'ISO', type: 'select', options: ['Auto', '100', '200', '400', '800', '1600', '3200', '6400'],
        tooltip: 'Kameraets lysfølsomhed (100-6400). Lav ISO = mindre støj men kræver mere lys. Høj ISO for svage lysforhold men introducerer støj. Udendørs dagslys: 100-200. Indendørs/svagt: 400-800.' },
      { key: 'shutter_speed', label: 'Lukker', type: 'select', options: ['Auto', '1/4000', '1/2000', '1/1000', '1/500', '1/250', '1/125', '1/60', '1/30', '1/15', '1/8', '1/4', '1/2', '1'],
        tooltip: 'Lukkerhastighed der styrer eksponeringstid og bevægelsesuskarphed. Hurtige lukker (1/500+) fryser bevægelse men kræver meget lys. Langsomme (1/60-) kan blurre bevægelse. Udendørs: 1/125-1/500.' },
      { key: 'aperture', label: 'Blænde', type: 'select', options: ['Auto', '3.5', '4', '4.5', '5', '5.6', '6.3', '7.1', '8', '9', '10', '11', '13', '14', '16', '18', '20', '22'],
        tooltip: 'Blændeåbning (f-tal) der styrer dybdeskarphed og lysmængde. Lav f-tal (f/3.5) = lille dybde, mere lys. Højt f-tal (f/11) = stor dybde, mindre lys. Byggeplads: f/8-f/11 for maksimal dybdeskarphed.' },
      { key: 'whitebalance', label: 'Hvidbalance', type: 'select', options: ['Auto', 'Daylight', 'Cloudy', 'Tungsten', 'Fluorescent', 'Flash'],
        tooltip: 'Farvetemperatur korrektion for naturlige farver. Auto fungerer oftest godt i variable lysforhold. Daylight til solrigt vejr (5500K). Cloudy til overskyet (7000K). Tungsten til indendørs belysning (3200K).' },
      { key: 'relay_gpio_pin', label: 'Relay GPIO', type: 'number', placeholder: '356',
        tooltip: 'GPIO pin nummer til relay styring af kamera strøm. RK3588: 356, H3: BOARD 7. Forkert pin vil ikke virke eller kan skade hardware. Ændres kun hvis hardware ændres. Kontakt hardware dokumentation.' },
      { key: 'relay_on_seconds_before', label: 'Varmetid', type: 'number', unit: 'sek', placeholder: '10', default: 10,
        tooltip: 'Sekunder kameraet skal være tændt før capture. Kameraet skal varme op og stabilisere fx/iso. For kort tid kan give ustabile billeder. For langt spilder batteri. Typisk 5-15 sekunder afhængig af kamera model.' },
      { key: 'relay_off_seconds_after', label: 'Nedkøling', type: 'number', unit: 'sek', placeholder: '5', default: 5,
        tooltip: 'Sekunder at vente efter capture før strøm slukkes. Sikrer at download er færdig og kamera kan lukke korrekt. For kort kan beskadige SD kort. For langt spilder batteri. Typisk 3-10 sekunder.' },
      { key: 'delete_after_download', label: 'Slet på kamera', type: 'boolean', default: true,
        tooltip: 'Slet billeder fra kameraets SD kort efter download til edge. Frigør plads på kamera kortet. Anbefales da billeder gemmes lokalt på edge. Slå fra hvis kamera SD er backup.' },
      { key: 'gphoto2_port', label: 'gPhoto2 port', type: 'text', placeholder: 'usb:', default: 'usb:',
        tooltip: 'gPhoto2 port streng for kamera forbindelse. usb: er standard for USB forbundne kameraer. Andre typer: serial:, ip:. Ændres kun hvis kamera forbindelse ikke er USB. Se gPhoto2 dokumentation.' },
      { key: 'azimuth_deg', label: 'Azimut', type: 'number', unit: '°', placeholder: '247',
        tooltip: 'Kamera retning i grader (0=N, 90=Ø, 180=S, 270=V). Bruges til at dokumentere kamera orientering og til AI analyse. Hjælper med at forstå lysforhold og solvinkel. Indtast kompas retning.' },
      { key: 'tilt_deg', label: 'Tilt', type: 'number', unit: '°', placeholder: '-15',
        tooltip: 'Kamera vinkel i grader (0=horisont, positiv=opad, negativ=nedad). Negativ værdi (f.eks. -15) betyder kameraet peger nedad mod motivet. Vigtig for perspektiv og AI analyse. Typisk -10 til -45 grader.' },
      { key: 'mount_height_m', label: 'Montagehøjde', type: 'number', unit: 'm', placeholder: '8',
        tooltip: 'Kamera højde over jorden i meter. Bruges til at beregne afstand og skala i billederne. Hjælper AI med at forstå motivstørrelse. Vigtig for præcis dokumentation af byggeprocesser.' },
      { key: 'fov_horizontal_deg', label: 'Horisontalt FOV', type: 'number', unit: '°', placeholder: '62',
        tooltip: 'Horisontalt felt af syn i grader. Bestemmer hvor bredt billedet er. Typisk 50-70 grader for standard linser. Bruges til at beregne dækningsareal. Findes i kamera/linse specifikationer.' },
      { key: 'fov_vertical_deg', label: 'Vertikalt FOV', type: 'number', unit: '°', placeholder: '40',
        tooltip: 'Vertikalt felt af syn i grader. Bestemmer hvor højt billedet er. Typisk 35-50 grader for standard linser. Bruges sammen med horisontalt FOV til at beregne fuld dækning. Findes i kamera/linse specifikationer.' },
      { key: 'perspective', label: 'Perspektiv', type: 'select', options: ['eye_level', 'high_angle', 'low_angle', 'birds_eye', 'worms_eye'],
        tooltip: 'Kamera perspektiv type for AI analyse og metadata. eye_level (1.5-2m), high_angle (oppefra), low_angle (nedefra), birds_eye (lodret), worms_eye (fra jorden). Bruges til at forstå billedkomposition.' },
    ],
  },
  {
    key: 'quality',
    label: 'Kvalitet',
    description: 'Automatisk kvalitetstjek af billeder.',
    fields: [
      { key: 'check_enabled', label: 'Aktivt', type: 'boolean', default: true,
        tooltip: 'Aktiverer automatisk kvalitetstjek af alle captures. Billeder der ikke opfylder kriterier markeres som "failed" og kan slettes eller gen-tages. Anbefales altid aktiveret for kvalitetssikring. Slå kun midlertidigt fra ved fejlfinding.' },
      { key: 'blur_threshold', label: 'Skarphed min.', type: 'number', placeholder: '80', default: 80,
        tooltip: 'Minimum skarpheds-score (Laplacian variance 0-∞). Lavere værdi = mere tolerant over for uskarpe billeder. For høj kan give false positives ved bevægelse. Typisk 50-100. Juster baseret på kamera og motiv.' },
      { key: 'dark_threshold', label: 'Mørk grænse', type: 'number', placeholder: '25', default: 25,
        tooltip: 'Minimum lysstyrke i gennemsnit (0-255, hvor 0 er sort). Billeder mørkere end dette markeres som for mørke. Nat billeder kan fejle hvis for højt. Typisk 15-40. Juster for lysforhold.' },
      { key: 'bright_threshold', label: 'Lys grænse', type: 'number', placeholder: '230', default: 230,
        tooltip: 'Maksimum lysstyrke i gennemsnit (0-255, hvor 255 er hvid). Billeder lysere end dette markeres som overeksponerede. For lav kan give falske alarmer ved sollys. Typisk 220-245.' },
      { key: 'adaptive_exposure.enabled', label: 'Adaptiv EV', type: 'boolean', default: false,
        tooltip: 'Auto-juster EV baseret på brightness måling. Kompenserer for variable lysforhold (skygge, sol, overskyet). Justerer ISO/lukker for at holde konstant eksponering. Anbefales ved variable lysforhold.' },
      { key: 'adaptive_exposure.target_brightness', label: 'Mål-lys', type: 'number', placeholder: '118', default: 118,
        tooltip: 'Mål lysstyrke (0-255, 128 = optimal midtone). Systemet justerer EV for at nå denne værdi. Lavere = mørkere billeder, højere = lysere. Typisk 110-130 for timelapse. Juster efter ønsket look.' },
      { key: 'adaptive_exposure.brightness_tolerance', label: 'Lys tolerance', type: 'number', placeholder: '32', default: 32,
        tooltip: 'Acceptabel afvigelse fra mål brightness (± værdi). Mindre tolerance = hyppigere justering. Større tolerance = færre justeringer men mere variation. Typisk 20-50. For stor kan slå adaptive fra effektivt.' },
      { key: 'adaptive_exposure.step_ev', label: 'EV trin', type: 'number', placeholder: '0.3', default: 0.3,
        tooltip: 'EV step per justering (0.1-3.0 EV). Mindre step = finere justering men flere cycles. Større step = hurtigere men kan overshoot. Typisk 0.3-0.7. For meget aggressiv kan give oscillation.' },
      { key: 'adaptive_exposure.min_ev', label: 'EV min.', type: 'number', placeholder: '-2.0', default: -2.0,
        tooltip: 'Minimum EV korrektion (negativ = mørkere). Beskytter mod for mørke billeder ved at begrænse nedjustering. Typisk -2 til -3 EV. Kan hæves hvis billederne konstant bliver for mørke.' },
      { key: 'adaptive_exposure.max_ev', label: 'EV max.', type: 'number', placeholder: '2.0', default: 2.0,
        tooltip: 'Maksimum EV korrektion (positiv = lysere). Beskytter mod overeksponering ved at begrænse opjustering. Typisk +2 til +3 EV. Kan sænkes hvis billederne konstant bliver for lyse/brændt ud.' },
      { key: 'edge_ai.enabled', label: 'Edge QA AI', type: 'boolean', default: true,
        tooltip: 'Aktiverer AI-baseret kvalitetsanalyse på edge-enheden. Bruger NPU til at detektere problemer (sløring, mørk, lens obstruction). Hurtigere og mere præcis end traditionelle metoder. Kræver NPU hardware. Anbefales altid aktiveret.' },
      { key: 'edge_ai.mode', label: 'AI mode', type: 'select', options: ['off', 'monitor', 'assist', 'autonomous', 'npu_first', 'lab'], default: 'assist',
        tooltip: 'AI adfærdsmode: off (deaktiveret), monitor (log kun), assist (advar og vent), autonomous (rett automatisk), npu_first (prioriter NPU), lab (test mode). Assist anbefales til produktion. Lab til fejlfinding.' },
      { key: 'edge_ai.prefer_npu', label: 'Foretræk NPU', type: 'boolean', default: true,
        tooltip: 'Brug NPU (hardware accelerator) frem for CPU til AI inferens. NPU er hurtigere og bruger mindre strøm. Slå fra hvis NPU ikke er tilgængelig eller har problemer. Anbefales altid aktiveret på NPU-hardware.' },
      { key: 'edge_ai.runner', label: 'NPU runner', type: 'text', placeholder: '/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py',
        tooltip: 'Sti til NPU runner script der executerer AI modellen. Standard path er korrekt for default installation. Ændres kun hvis custom NPU setup. Kontakt dokumentationen før ændring.' },
      { key: 'edge_ai.model_path', label: 'NPU model', type: 'text', placeholder: '/opt/timelapse/models/edge_qa.nb',
        tooltip: 'Sti til NPU model fil (.nb format for RK3588). Tom = brug built-in model. Custom models kan bruges til specifikke use cases. Ændres kun hvis du har en trænet model. Kontakt dokumentationen.' },
      { key: 'edge_ai.vendor_binary', label: 'VIPLite wrapper', type: 'text', placeholder: '/opt/timelapse/bin/edge_qa_viplite',
        tooltip: 'Sti til vendor NPU wrapper (VIPLite). Bruges til at kalde NPU hardware. Tom = brug built-in wrapper. Ændres kun ved custom NPU driver installation. Kontakt dokumentationen.' },
      { key: 'drift_detection.focus.enabled', label: 'Fokus-drift-alarm', type: 'boolean', default: true, description: 'Alarmerer hvis skarpheden systematisk falder over tid (manuel fokus kan glide)',
        tooltip: 'Alarmer hvis skarpheden systematisk falder over tid. Detekterer manuel fokus der glider (vibrationer, temperatur). Vigtigt for langtidsprojekter hvor kamera kan flytte sig. Anbefales aktiveret.' },
      { key: 'drift_detection.focus.z_threshold', label: 'Fokus-følsomhed', type: 'number', placeholder: '2.0', default: 2.0, description: 'Antal standardafvigelser fra kameraets egen baseline før der alarmeres — lavere = mere følsom',
        tooltip: 'Antal standardafvigelser fra baseline før alarm. Lavere = mere følsom (flere alarmer). Højere = mindre følsom (færre alarmer). Typisk 2.0-3.0. Juster baseret på falske alarmer og ønsket følsomhed.' },
      { key: 'drift_detection.exposure.enabled', label: 'Eksponerings-drift-alarm', type: 'boolean', default: true, description: 'Alarmerer hvis lysstyrken systematisk skifter over tid (støv/tåge/sæson)',
        tooltip: 'Alarmer hvis eksponering systematisk skifter over tid. Detekterer støv på linse, tåge, eller sæson ændringer. Vigtigt for at opdage kamera der skal renses. Anbefales aktiveret.' },
      { key: 'drift_detection.exposure.z_threshold', label: 'Eksponerings-følsomhed', type: 'number', placeholder: '2.5', default: 2.5,
        tooltip: 'Antal standardafvigelser fra baseline før alarm. Højere end focus da lysstyrke naturligt varierer mere. Typisk 2.5-4.0. Juster baseret på falske alarmer og lysvariation på site.' },
      { key: 'drift_detection.white_balance.enabled', label: 'Hvidbalance-drift-alarm', type: 'boolean', default: false, description: 'Kræver at edge-optimizeren rapporterer hvidbalance-data — slået fra som default',
        tooltip: 'Alarmer hvis hvidbalance systematisk skifter. Kræver at edge-optimizeren rapporterer hvidbalance-data. Slået fra som default da det kræver extra data. Aktiver hvis farvenøjagtighed er kritisk.' },
      { key: 'drift_detection.white_balance.z_threshold', label: 'Hvidbalance-følsomhed', type: 'number', placeholder: '2.0', default: 2.0,
        tooltip: 'Antal standardafvigelser fra baseline før alarm. Typisk 2.0-3.0. Juster baseret på hvor meget farvevariation der forventes (belysning ændringer, etc.).' },
    ],
  },
  {
    key: 'storage',
    label: 'Edge-lagring',
    description: 'Lokal buffer og database på Edge.',
    fields: [
      { key: 'local_path', label: 'Capture sti', type: 'text', placeholder: '/data/captures', default: '/data/captures',
        tooltip: 'Lokal sti til billedlagring på edge-enheden. Billeder gemmes her før upload til headend. Skal have tilstrækkelig plads (se buffer). Standard: /data/captures. Ændres kun ved custom filsystem layout.' },
      { key: 'circular_buffer_gb', label: 'Buffer', type: 'number', unit: 'GB', placeholder: '50', default: 50,
        tooltip: 'Maksimal plads i GB før circular buffer sletter gamle uploaded billeder. Ældre uploaded filer slettes først for at make plads. Større buffer = mere offline tolerance. Minimum 20-30 GB anbefales.' },
      { key: 'db_path', label: 'DB sti', type: 'text', placeholder: '/data/timelapse_edge.db', default: '/data/timelapse_edge.db',
        tooltip: 'Sti til SQLite database med capture metadata, logs og lokal state. Database backupes sammen med billeder. Ændres kun ved custom setup. Standard path er normalt fin.' },
    ],
  },
  {
    key: 'diagnostics',
    label: 'Diagnostik',
    description: 'Sync-poll (heartbeat + config + SIEM samlet) og rapportering.',
    fields: [
      { key: 'sync_poll_interval_minutes', label: 'Sync-poll', type: 'number', unit: 'min', placeholder: '5', default: 5,
        tooltip: 'Minutter mellem den konsoliderede sync-poll til headend (POST /api/edge/sync). Ét kald dækker heartbeat/diagnostik, config-ændringer og SIEM-log-forward — erstatter de tidligere separate Heartbeat- (60 min) og Config poll- (5 min) indstillinger siden 2026-08-19. Lavere = hurtigere response men mere network trafik. Typisk 5-10 minutter.' },
      { key: 'update_poll_interval_minutes', label: 'Update poll', type: 'number', unit: 'min', placeholder: '5',
        tooltip: 'Minutter mellem tjek for systemopdateringer fra headend. Opdateringer downloades og installeres automatisk. Typisk 5-15 minutter sammen med config poll. Kan øges for at spare batteri.' },
      { key: 'inventory_report_interval_hours', label: 'Inventory', type: 'number', unit: 'timer', placeholder: '24', default: 24,
        tooltip: 'Timer mellem inventory rapporter til headend. Inventory indeholder hardware info, versions, og kapacitet. Bruges til asset tracking. Typisk 24 timer (daglig). Kan øges til 48-72 timer.' },
    ],
  },
  {
    key: 'system',
    label: 'System',
    description: 'Timeouts og recovery-parametre.',
    fields: [
      { key: 'error_recovery_sleep_s', label: 'Recovery pause', type: 'number', unit: 'sek', placeholder: '30', default: 30,
        tooltip: 'Sekunder at vente efter fejl før retry. Forhindrer hurtig retry loop der kan forværre problemer. Network timeout: 30-60 sekunder. Camera fejl: 60-120 sekunder. For kort kan spamme logs og API.' },
      { key: 'min_sleep_s', label: 'Minimum sleep', type: 'number', unit: 'sek', placeholder: '60', default: 60,
        tooltip: 'Minimum søvn mellem captures i sekunder. Selv ved fejl eller hurtig retry. Sikrer at systemet hviler og ikke overbelaster kamera eller network. Typisk 30-120 sekunder. Kan sænkes ved hyppige captures.' },
      { key: 'api_timeout_s', label: 'API timeout', type: 'number', unit: 'sek', placeholder: '15', default: 15,
        tooltip: 'Timeout i sekunder for API kald til headend. Upload, heartbeat, config fetch. For kort kan give fejler på slow networks. For langt kan hænge systemet. Typisk 10-30 sekunder. Øges ved slow network.' },
      { key: 'device_pki.certificate_lifetime_days', label: 'Device-certifikat levetid', type: 'number', unit: 'dage', placeholder: '3650', default: 3650,
        tooltip: 'Gyldighed ved udstedelse af nye device-certifikater. Eksisterende certifikater ændres ikke. Maksimum er 3650 dage.' },
      { key: 'device_pki.expired_certificate_policy', label: 'Udløbet device-certifikat', type: 'select', options: ['block', 'grace_period', 'continue_until_rotated'], default: 'grace_period',
        tooltip: 'block afviser straks ved udløb. grace_period tillader kun den konfigurerede periode. continue_until_rotated holder driften i gang og alarmerer indtil rotation. Revokerede certifikater afvises altid uanset dette valg.' },
      { key: 'device_pki.expired_certificate_grace_days', label: 'Grace ved udløb', type: 'number', unit: 'dage', placeholder: '7', default: 7,
        tooltip: 'Antal dage et udløbet, ikke-revokeret certifikat accepteres ved grace_period. Revokering, forkert signatur, ukendt issuer og forkert device-identitet kan aldrig få grace.' },
    ],
  },
  {
    key: 'session_policy',
    label: 'Session og MFA',
    description: 'Login-sessioner, MFA-krav og rollebaserede undtagelser.',
    fields: [
      { key: 'session_duration_hours', label: 'Session varighed', type: 'number', unit: 'timer', placeholder: '12', default: 12,
        tooltip: 'Session levetid i timer før bruger skal logge ind igen. Balancerer sikkerhed og convenience. Kortere = mere sikkerhed men hyppigere login. Typisk 8-24 timer. Admin roller: 4-12 timer for sikkerhed.' },
      { key: 'remember_me_days', label: 'Husk enhed', type: 'number', unit: 'dage', placeholder: '30', default: 30,
        tooltip: '"Husk mig" session levetid i dage. Brugeren forbliver logget ind på enheden. Typisk 30-90 dage. Kortere = mere sikkerhed men inconvenience. For langt kan være sikkerhedsrisiko.' },
      { key: 'remember_me_allowed', label: 'Tillad husk enhed', type: 'boolean', default: true,
        tooltip: 'Tillad "Husk mig" funktion på login. Brugere kan vælge at forblive logget ind. Slå fra for højere sikkerhed (kræver login hver gang). Anbefales aktiveret for convenience på trusted devices.' },
      { key: 'mfa_required', label: 'MFA for alle roller', type: 'boolean', default: false,
        tooltip: 'Kræv Multi-Factor Authentication for alle roller. Overrides rolle-specifikke indstillinger. Højeste sikkerhed men inconvenience. Anbefales kun for highly secure miljøer. Brug rolle-specifik i stedet.' },
      { key: 'mfa_required_by_role.super_admin', label: 'MFA Super Admin', type: 'boolean', default: true,
        tooltip: 'Kræv MFA for super_admin rolle. Super admin har fuld adgang inkl. brugerstyring. MFA anbefales altid. TOTP via authenticator app. Beskytter mod compromised passwords.' },
      { key: 'mfa_required_by_role.admin', label: 'MFA Admin', type: 'boolean', default: true,
        tooltip: 'Kræv MFA for admin rolle. Admin har bred adgang til systemet. MFA anbefales altid. TOTP via authenticator app. Samme sikkerhedsniveau som super admin.' },
      { key: 'mfa_required_by_role.operator', label: 'MFA Operatør', type: 'boolean', default: false,
        tooltip: 'Kræv MFA for operator rolle. Operator har limited adgang (kan redigere kameraer, se captures). MFA valgfrit baseret på risikovurdering. Kan aktiveres for højere sikkerhed.' },
      { key: 'mfa_required_by_role.viewer', label: 'MFA Seer', type: 'boolean', default: false,
        tooltip: 'Kræv MFA for viewer rolle. Viewer har read-only adgang. MFA typisk ikke nødvendig for read-only. Kan aktiveres for compliance eller highly sensitive data.' },
      { key: 'mfa_exempt_usernames', label: 'MFA-undtagelser', type: 'user_multiselect', description: 'Udvalgte admin/super_admin brugere undtages på dette lag.',
        tooltip: 'Udvalgte admin/super_admin brugere der undtages fra MFA krav. Backup adgang ved MFA system fejl. Should be minimal og begrænset til trusted personer. Review regelmæssigt.' },
    ],
  },
]

const FIELD_LOOKUP = new Map(SECTIONS.flatMap(section => section.fields.map(field => [`${section.key}.${field.key}`, field])))

function getNested(obj: ConfigObject, path: string): any {
  return path.split('.').reduce<any>((acc, part) => (acc && typeof acc === 'object' ? acc[part] : undefined), obj)
}

function setNested(obj: ConfigObject, path: string, value: any): ConfigObject {
  const result = { ...obj }
  const parts = path.split('.')
  let cursor: ConfigObject = result
  parts.forEach((part, index) => {
    if (index === parts.length - 1) cursor[part] = value
    else {
      cursor[part] = { ...(cursor[part] ?? {}) }
      cursor = cursor[part]
    }
  })
  return result
}

function formatValue(value: any): string {
  if (value === undefined || value === null || value === '') return 'Arver'
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nej'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function normaliseInput(field: FieldDef | undefined, value: string, checked?: boolean) {
  if (field?.type === 'boolean') return checked ? true : null
  if (value === '') return null
  if (field?.type === 'number') return Number(value)
  return value
}

function sourceClass(source: string, layer: LayerKey, changedFromGlobal: boolean) {
  if (source === layer) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (changedFromGlobal) return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-gray-200 bg-white text-gray-600'
}

export function GlobalConfigPage() {
  const [defaults, setDefaults] = useState<ConfigDefaults | null>(null)
  const [customers, setCustomers] = useState<EntityOption[]>([])
  const [sites, setSites] = useState<EntityOption[]>([])
  const [cameras, setCameras] = useState<EntityOption[]>([])
  const [adminUsers, setAdminUsers] = useState<Array<{ username: string; role: string }>>([])
  const [selectedCustomer, setSelectedCustomer] = useState('')
  const [selectedSite, setSelectedSite] = useState('')
  const [selectedCamera, setSelectedCamera] = useState('')
  const [editLayer, setEditLayer] = useState<LayerKey>('global')
  const [resolution, setResolution] = useState<Resolution | null>(null)
  const [draft, setDraft] = useState<ConfigObject>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const filteredSites = useMemo(
    () => sites.filter(site => !selectedCustomer || site.customer_id === selectedCustomer),
    [sites, selectedCustomer],
  )
  const filteredCameras = useMemo(
    () => cameras.filter(camera =>
      (!selectedCustomer || camera.customer_id === selectedCustomer) &&
      (!selectedSite || camera.site_id === selectedSite)
    ),
    [cameras, selectedCustomer, selectedSite],
  )

  async function loadBase() {
    setLoading(true)
    try {
      const [d, c, s, cams] = await Promise.all([
        api('/api/admin/config-defaults'),
        api('/api/admin/customers'),
        api('/api/admin/sites'),
        api('/api/admin/cameras'),
      ])
      const users = await api('/api/admin/users').catch(() => [])
      setDefaults({ system: {}, session_policy: {}, ...d })
      setCustomers(Array.isArray(c) ? c : [])
      setSites(Array.isArray(s) ? s : [])
      setCameras(Array.isArray(cams) ? cams : [])
      setAdminUsers((Array.isArray(users) ? users : (users.users ?? []))
        .filter((u: any) => ['super_admin', 'admin'].includes(u.role))
        .map((u: any) => ({ username: u.username, role: u.role })))
    } catch (e: any) {
      setError(`Kunne ikke hente konfiguration (${e.message})`)
    } finally {
      setLoading(false)
    }
  }

  async function loadResolution() {
    const params = new URLSearchParams()
    if (selectedCamera) params.set('camera_id', selectedCamera)
    else if (selectedSite) params.set('site_id', selectedSite)
    else if (selectedCustomer) params.set('customer_id', selectedCustomer)
    try {
      const data = await api(`/api/admin/config-resolution${params.toString() ? `?${params}` : ''}`)
      setResolution(data)
      const layer = data.layers?.find((l: any) => l.key === editLayer)
      setDraft(layer?.config ?? {})
    } catch (e: any) {
      setError(`Kunne ikke resolver konfiguration (${e.message})`)
    }
  }

  useEffect(() => { loadBase() }, [])
  useEffect(() => { if (!loading) loadResolution() }, [loading, selectedCustomer, selectedSite, selectedCamera])
  useEffect(() => {
    const layer = resolution?.layers.find(l => l.key === editLayer)
    setDraft(layer?.config ?? {})
  }, [editLayer, resolution])

  function setDraftField(path: string, value: any) {
    setDraft(prev => setNested(prev, path, value))
  }

  function layerEntityId() {
    if (editLayer === 'global') return 'global'
    const layer = resolution?.layers.find(l => l.key === editLayer)
    return layer?.entity_id || ''
  }

  async function saveLayer() {
    const entityId = layerEntityId()
    if (!entityId) {
      setError(`Vælg en ${editLayer === 'customer' ? 'kunde' : editLayer === 'site' ? 'site' : 'kamera-lokation'} før du gemmer.`)
      return
    }
    setSaving(true)
    try {
      await api(`/api/admin/config-overrides/${editLayer}/${encodeURIComponent(entityId)}`, {
        method: 'PUT',
        body: JSON.stringify({ mode: editLayer === 'global' ? 'replace' : 'merge', config_overrides: draft }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 1800)
      await loadResolution()
    } catch (e: any) {
      setError(`Kunne ikke gemme (${e.message})`)
    } finally {
      setSaving(false)
    }
  }

  function resetGlobalFactory() {
    if (!defaults || !confirm('Nulstil globale defaults til fabriksværdier i editoren? Gem bagefter for at aktivere.')) return
    const factory: ConfigDefaults = {
      schedule: { timezone: 'Europe/Copenhagen', capture_mode: 'interval', interval_minutes: 60, active_hours: ['06:00', '21:00'] },
      camera: { power_mode: 'relay', relay_gpio_pin: 356, relay_on_seconds_before: 10, relay_off_seconds_after: 5, delete_after_download: true, gphoto2_port: 'usb:' },
      quality: {
        check_enabled: true,
        blur_threshold: 80,
        dark_threshold: 25,
        bright_threshold: 230,
        adaptive_exposure: {
          enabled: false,
          target_brightness: 118,
          brightness_tolerance: 32,
          step_ev: 0.3,
          min_ev: -2.0,
          max_ev: 2.0,
        },
        edge_ai: {
          enabled: true,
          mode: 'assist',
          prefer_npu: true,
          runner: '/opt/timelapse/venv/bin/python /opt/timelapse/edge/tools/edge_qa_npu_runner.py',
          model_path: '',
          vendor_binary: '',
        },
      },
      storage: { local_path: '/data/captures', circular_buffer_gb: 50, db_path: '/data/timelapse_edge.db' },
      diagnostics: { sync_poll_interval_minutes: 5, update_poll_interval_minutes: 5, inventory_report_interval_hours: 24 },
      system: {
        error_recovery_sleep_s: 30,
        min_sleep_s: 60,
        api_timeout_s: 15,
        device_pki: {
          certificate_lifetime_days: 3650,
          expired_certificate_policy: 'grace_period',
          expired_certificate_grace_days: 7,
        },
      },
      session_policy: {
        session_duration_hours: 12,
        remember_me_days: 30,
        absolute_max_days: 90,
        rolling_enabled: true,
        remember_me_allowed: true,
        mfa_required: false,
        webauthn_required: false,
        mfa_required_by_role: {
          super_admin: true,
          admin: true,
          operator: false,
          viewer: false,
        },
        mfa_exempt_usernames: [],
      },
    }
    setEditLayer('global')
    setDraft(factory)
  }

  if (loading) return <div className="max-w-6xl mx-auto px-4 py-8 text-gray-400">Indlæser…</div>

  const knownFieldPaths = new Set(SECTIONS.flatMap(section => section.fields.map(field => `${section.key}.${field.key}`)))
  const knownFields = resolution?.fields.filter(field => knownFieldPaths.has(field.path)) ?? []
  const extraFields = resolution?.fields.filter(field => !knownFieldPaths.has(field.path)) ?? []
  const tableFields = [...knownFields, ...extraFields]

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/settings" className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <Globe className="w-5 h-5 text-sky-500" />
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Global Config</h1>
          <p className="text-xs text-gray-400">Global → kunde → site → kamera. Underliggende lag vinder.</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Luk</button>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Kunde</label>
            <select value={selectedCustomer} onChange={e => { setSelectedCustomer(e.target.value); setSelectedSite(''); setSelectedCamera('') }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="">Global kontekst</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Site</label>
            <select value={selectedSite} onChange={e => { setSelectedSite(e.target.value); setSelectedCamera('') }}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" disabled={!selectedCustomer && filteredSites.length === 0}>
              <option value="">Arv fra kunde/global</option>
              {filteredSites.map(s => <option key={s.id} value={s.id}>{s.customer_name ? `${s.customer_name} / ` : ''}{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Kamera-lokation</label>
            <select value={selectedCamera} onChange={e => setSelectedCamera(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" disabled={!selectedSite && filteredCameras.length === 0}>
              <option value="">Arv fra site/kunde/global</option>
              {filteredCameras.map(c => (
                <option key={c.id} value={c.id}>
                  {c.customer_name ? `${c.customer_name} / ` : ''}{c.site_name ? `${c.site_name} / ` : ''}{c.camera_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Rediger lag</label>
            <select value={editLayer} onChange={e => setEditLayer(e.target.value as LayerKey)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="global">Global</option>
              <option value="customer" disabled={!resolution?.context.customer_id}>Kunde</option>
              <option value="site" disabled={!resolution?.context.site_id}>Site</option>
              <option value="camera" disabled={!resolution?.context.camera_id}>Kamera</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-sky-50 border border-sky-100 rounded-xl px-4 py-3 mb-5">
        <div className="flex items-center gap-2 text-sm font-medium text-sky-900">
          <Layers className="w-4 h-4" />
          Effektiv kontekst
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {resolution?.layers.map(layer => (
            <span key={layer.key} className={`px-2 py-1 rounded-lg border ${
              layer.key === editLayer ? 'bg-white border-sky-300 text-sky-700' : 'bg-sky-100 border-sky-100 text-sky-700'
            }`}>
              {layer.label}: {layer.entity_name || (layer.key === 'global' ? 'Globale defaults' : 'ikke valgt')}
            </span>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Arv og overrides</h2>
            <p className="text-xs text-gray-400">Grøn = sat på valgte lag. Gul = afviger fra global default.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={saveLayer} disabled={saving}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-500 text-white text-xs hover:bg-sky-600 disabled:opacity-50">
              {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
              {saved ? 'Gemt' : saving ? 'Gemmer' : 'Gem lag'}
            </button>
            {editLayer === 'global' && (
              <button onClick={resetGlobalFactory}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-gray-500 text-xs hover:bg-gray-50">
                <RotateCcw className="w-4 h-4" />
                Fabrik
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="text-left font-medium px-4 py-2 min-w-[200px] max-w-[240px]">Parameter</th>
                <th className="text-left font-medium px-4 py-2 min-w-[120px] max-w-[160px]">Global</th>
                <th className="text-left font-medium px-4 py-2 min-w-[120px] max-w-[160px]">Kunde</th>
                <th className="text-left font-medium px-4 py-2 min-w-[120px] max-w-[160px]">Site</th>
                <th className="text-left font-medium px-4 py-2 min-w-[120px] max-w-[160px]">Kamera</th>
                <th className="text-left font-medium px-4 py-2 min-w-[120px] max-w-[160px]">Aktuel</th>
                <th className="text-left font-medium px-4 py-2 min-w-[180px] max-w-[220px]">Rediger valgt lag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tableFields.map(field => {
                const def = FIELD_LOOKUP.get(field.path)
                const draftValue = getNested(draft, field.path)
                return (
                  <tr key={field.path} className={field.changed_from_global ? 'bg-amber-50/30' : ''}>
                    <td className="px-4 py-3 align-top min-w-[200px] max-w-[240px]" title={def?.tooltip ?? 'Dynamisk parameter uden beskrivelse'}>
                      <div className="font-medium text-gray-800 break-words">{def?.label ?? field.key}</div>
                      <div className="text-[11px] text-gray-400 font-mono break-all">{field.path}</div>
                      {!def && <div className="text-[11px] text-amber-600 mt-1">Dynamisk parameter</div>}
                    </td>
                    {(['global', 'customer', 'site', 'camera'] as LayerKey[]).map(layer => (
                      <td key={layer} className="px-4 py-3 align-top min-w-[120px] max-w-[160px]">
                        <span className={`inline-flex w-full break-words rounded-lg border px-2 py-1 text-xs ${sourceClass(field.source, layer, field.changed_from_global)}`}>
                          {formatValue(field.values[layer])}
                        </span>
                      </td>
                    ))}
                    <td className="px-4 py-3 align-top min-w-[120px] max-w-[160px]">
                      <div className="text-gray-900 break-words">{formatValue(field.effective_value)}</div>
                      <div className="text-[11px] text-gray-400">fra {field.source}</div>
                    </td>
                    <td className="px-4 py-3 align-top min-w-[180px] max-w-[220px]">
                      {def?.type === 'boolean' ? (
                        <label className="inline-flex items-center gap-2 text-xs text-gray-600">
                          <input type="checkbox" checked={draftValue === true}
                            onChange={e => setDraftField(field.path, normaliseInput(def, '', e.target.checked))}
                            className="w-4 h-4 rounded" />
                          Aktiv
                        </label>
                      ) : def?.type === 'user_multiselect' ? (
                        <details className="relative">
                          <summary className="cursor-pointer list-none rounded-lg border border-gray-200 px-2 py-1.5 text-xs text-gray-700 hover:bg-gray-50">
                            {Array.isArray(draftValue) && draftValue.length ? `${draftValue.length} valgt` : 'Arv / ingen'}
                          </summary>
                          <div className="absolute right-0 z-20 mt-1 w-72 rounded-lg border border-gray-200 bg-white p-2 shadow-lg">
                            <div className="max-h-56 space-y-1 overflow-auto">
                              {adminUsers.length === 0 ? (
                                <p className="px-2 py-1 text-xs text-gray-400">Ingen admin-brugere hentet</p>
                              ) : adminUsers.map(user => {
                                const values = Array.isArray(draftValue) ? draftValue : []
                                const checked = values.includes(user.username)
                                return (
                                  <label key={user.username} className="flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1 text-xs hover:bg-gray-50">
                                    <span className="min-w-0 truncate">
                                      {user.username}
                                      <span className="ml-1 text-gray-400">({user.role})</span>
                                    </span>
                                    <input type="checkbox" checked={checked}
                                      onChange={e => {
                                        const next = e.target.checked
                                          ? [...values, user.username]
                                          : values.filter((v: string) => v !== user.username)
                                        setDraftField(field.path, next.length ? next : null)
                                      }}
                                      className="h-4 w-4 rounded" />
                                  </label>
                                )
                              })}
                            </div>
                          </div>
                        </details>
                      ) : def?.type === 'select' ? (
                        <select value={draftValue ?? ''} onChange={e => setDraftField(field.path, normaliseInput(def, e.target.value))}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs">
                          <option value="">Arv</option>
                          {def.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      ) : (
                        <input type={def?.type === 'number' ? 'number' : 'text'} value={draftValue ?? ''}
                          placeholder="Arv"
                          onChange={e => setDraftField(field.path, def ? normaliseInput(def, e.target.value) : (e.target.value === '' ? null : e.target.value))}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs" />
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
