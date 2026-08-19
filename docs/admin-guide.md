# TimeLapse Pro — Admin Guide

**Version:** 1.0
**Dato:** 13. juli 2026
**Målgruppe:** Systemadministratorer, teknisk personale

---

## 📋 Indhold

1. [Global Config](#global-config)
2. [Brugerstyring](#brugerstyring)
3. [Systemadministration](#systemadministration)
4. [Overvågning og Diagnostik](#overvågning-og-diagnostik)
5. [Sikkerhed](#sikkerhed)

---

## Global Config

### Overblik

Global Config er TimeLapse Pro's hierarkiske konfigurationssystem der giver mulighed for at styre systemets opførsel på tværs af alle lag — fra globale defaults ned til individuelt kamera.

**Tooltip ved hover:**
> Hierarkisk konfiguration: Global → Kunde → Site → Kamera. Arv og overrides for alle parametre.

### Konfigurations-lag

Systemet benytter et 4-lags hierarki hvor underliggende lag vinder over øverende lag:

| Lag | Prioritet | Scope | Eksempel |
|-----|-----------|-------|---------|
| **Kamera** | 1 (højest) | Enkelt kamera | Kamera-specifikke indstillinger |
| **Site** | 2 | Alle kameraer på en lokation | Fælles tidszone for byggeplads |
| **Kunde** | 3 | Alle sites for en kunde | Kundens kvalitetsstandard |
| **Global** | 4 (lavest) | Hele systemet | Fabriksdefaults |

### Konfigurationssektioner

#### 1. Optagelsesplan (Schedule)

Styrer hvornår billeder tages.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `timezone` | select | Europe/Copenhagen | Tidszone for schedule. Sikrer at captures sker på korrekte lokale tider for hver site. Vigtig når sites er i forskellige tidszoner. Ændringer påvirker alle fremtidige captures. |
| `capture_mode` | select | interval | Interval (fast frekvens) eller fixed_times (specificerede tidspunkter). Interval bruges til kontinuerlig timelapse af byggeprocesser. Fixed times er til periodiske status-billeder. |
| `interval_minutes` | number | 60 | Minutter mellem captures i interval mode. Lavere værdi = tættere timelapse men mere plads og strøm. Typisk 5-60 minutter for byggepladser. Juster baseret på projektets tempo. |
| `active_hours` | array | ["06:00", "21:00"] | Tidsvindue for daglig capture (f.eks. 06-21). Billeder uden for dette vindue saves ikke. Spar plads og strøm om natten. Bruges når der er minimal aktivitet. |

#### 2. Kamera (Camera)

Kamerastyring og eksponering.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `power_mode` | select | relay | Relay (ekstern strømstyring via GPIO) eller usb_powered (kameraet tændt altid). Relay anbefales for battery saving og kamera levetid. USB kræver konstant forbindelse. |
| `iso` | select | Auto | Kameraets lysfølsomhed (100-6400). Lav ISO = mindre støj men kræver mere lys. Høj ISO for svage lysforhold men introducerer støj. Udendørs dagslys: 100-200. |
| `shutter_speed` | select | Auto | Lukkerhastighed der styrer eksponeringstid og bevægelsesuskarphed. Hurtige lukker (1/500+) fryser bevægelse men kræver meget lys. Udendørs: 1/125-1/500. |
| `aperture` | select | Auto | Blændeåbning (f-tal) der styrer dybdeskarphed og lysmængde. Lav f-tal (f/3.5) = lille dybde. Højt f-tal (f/11) = stor dybde. Byggeplads: f/8-f/11. |
| `whitebalance` | select | Auto | Farvetemperatur korrektion for naturlige farver. Auto fungerer oftest godt i variable lysforhold. Daylight til solrigt vejr (5500K). Cloudy til overskyet (7000K). |
| `relay_gpio_pin` | number | 356 | GPIO pin nummer til relay styring af kamera strøm. RK3588: 356, H3: BOARD 7. Forkert pin vil ikke virke. Ændres kun hvis hardware ændres. |
| `relay_on_seconds_before` | number | 10 | Sekunder kameraet skal være tændt før capture. Kameraet skal varme op og stabilisere fx/iso. For kort tid kan give ustabile billeder. Typisk 5-15 sekunder. |
| `relay_off_seconds_after` | number | 5 | Sekunder at vente efter capture før strøm slukkes. Sikrer at download er færdig og kamera kan lukke korrekt. For kort kan beskadige SD kort. Typisk 3-10 sekunder. |
| `delete_after_download` | boolean | true | Slet billeder fra kameraets SD kort efter download til edge. Frigør plads på kamera kortet. Anbefales da billeder gemmes lokalt på edge. |
| `gphoto2_port` | text | usb: | gPhoto2 port streng for kamera forbindelse. usb: er standard for USB forbundne kameraer. Ændres kun hvis kamera forbindelse ikke er USB. |
| `azimuth_deg` | number | - | Kamera retning i grader (0=N, 90=Ø, 180=S, 270=V). Bruges til at dokumentere kamera orientering og til AI analyse. |
| `tilt_deg` | number | - | Kamera vinkel i grader (0=horisont, positiv=opad, negativ=nedad). Negativ værdi (f.eks. -15) betyder kameraet peger nedad mod motivet. |
| `mount_height_m` | number | - | Kamera højde over jorden i meter. Bruges til at beregne afstand og skala i billederne. Hjælper AI med at forstå motivstørrelse. |
| `fov_horizontal_deg` | number | - | Horisontalt felt af syn i grader. Bestemmer hvor bredt billedet er. Typisk 50-70 grader for standard linser. Findes i kamera/linse specifikationer. |
| `fov_vertical_deg` | number | - | Vertikalt felt af syn i grader. Bestemmer hvor højt billedet er. Typisk 35-50 grader for standard linser. Findes i kamera/linse specifikationer. |
| `perspective` | select | eye_level | Kamera perspektiv type for AI analyse og metadata. eye_level (1.5-2m), high_angle (oppefra), low_angle (nedefra), birds_eye (lodret), worms_eye (fra jorden). |

#### 3. Kvalitet (Quality)

Automatisk billedkvalitetskontrol.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `check_enabled` | boolean | true | Aktivérer automatisk kvalitetstjek af alle captures. Billeder der ikke opfylder kriterier markeres som "failed". Anbefales altid aktiveret for kvalitetssikring. |
| `blur_threshold` | number | 80 | Minimum skarpheds-score (Laplacian variance 0-∞). Lavere værdi = mere tolerant over for uskarpe billeder. Typisk 50-100. Juster baseret på kamera og motiv. |
| `dark_threshold` | number | 25 | Minimum lysstyrke i gennemsnit (0-255, hvor 0 er sort). Billeder mørkere end dette markeres som for mørke. Nat billeder kan fejle hvis for højt. Typisk 15-40. |
| `bright_threshold` | number | 230 | Maksimum lysstyrke i gennemsnit (0-255, hvor 255 er hvid). Billeder lysere end dette markeres som overeksponerede. Typisk 220-245. |

**Adaptiv Eksponering:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `adaptive_exposure.enabled` | boolean | false | Auto-juster EV baseret på brightness måling. Kompenserer for variable lysforhold (skygge, sol, overskyet). Anbefales ved variable lysforhold. |
| `adaptive_exposure.target_brightness` | number | 118 | Mål lysstyrke (0-255, 128 = optimal midtone). Systemet justerer EV for at nå denne værdi. Typisk 110-130 for timelapse. |
| `adaptive_exposure.brightness_tolerance` | number | 32 | Acceptabel afvigelse fra mål brightness (± værdi). Mindre tolerance = hyppigere justering. Typisk 20-50. |
| `adaptive_exposure.step_ev` | number | 0.3 | EV step per justering (0.1-3.0 EV). Mindre step = finere justering men flere cycles. Typisk 0.3-0.7. |
| `adaptive_exposure.min_ev` | number | -2.0 | Minimum EV korrektion (negativ = mørkere). Beskytter mod for mørke billeder. Typisk -2 til -3 EV. |
| `adaptive_exposure.max_ev` | number | 2.0 | Maksimum EV korrektion (positiv = lysere). Beskytter mod overeksponering. Typisk +2 til +3 EV. |

**Edge AI Kvalitet:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `edge_ai.enabled` | boolean | true | Aktiverer AI-baseret kvalitetsanalyse på edge-enheden. Bruger NPU til at detektere problemer (sløring, mørk, lens obstruction). Anbefales altid aktiveret. |
| `edge_ai.mode` | select | assist | AI adfærdsmode: off, monitor (log kun), assist (advar og vent), autonomous (rett automatisk), npu_first, lab. Assist anbefales til produktion. |
| `edge_ai.prefer_npu` | boolean | true | Brug NPU (hardware accelerator) frem for CPU. NPU er hurtigere og bruger mindre strøm. Anbefales altid aktiveret på NPU-hardware. |
| `edge_ai.runner` | text | - | Sti til NPU runner script der executerer AI modellen. Standard path er korrekt for default installation. |
| `edge_ai.model_path` | text | - | Sti til NPU model fil (.nb format for RK3588). Tom = brug built-in model. Ændres kun hvis du har en trænet model. |
| `edge_ai.vendor_binary` | text | - | Sti til vendor NPU wrapper (VIPLite). Tom = brug built-in wrapper. Ændres kun ved custom NPU driver installation. |

**Drift Detektion:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `drift_detection.focus.enabled` | boolean | true | Alarmer hvis skarpheden systematisk falder over tid. Detekterer manuel fokus der glider (vibrationer, temperatur). Anbefales aktiveret. |
| `drift_detection.focus.z_threshold` | number | 2.0 | Antal standardafvigelser fra baseline før alarm. Lavere = mere følsom. Typisk 2.0-3.0. |
| `drift_detection.exposure.enabled` | boolean | true | Alarmer hvis eksponering systematisk skifter over tid. Detekterer støv på linse, tåge, eller sæson ændringer. |
| `drift_detection.exposure.z_threshold` | number | 2.5 | Antal standardafvigelser fra baseline før alarm. Højere end focus da lysstyrke naturligt varierer mere. Typisk 2.5-4.0. |
| `drift_detection.white_balance.enabled` | boolean | false | Alarmer hvis hvidbalance systematisk skifter. Kræver at edge-optimizeren rapporterer hvidbalance-data. Slået fra som default. |
| `drift_detection.white_balance.z_threshold` | number | 2.0 | Antal standardafvigelser fra baseline før alarm. Typisk 2.0-3.0. |

#### 4. Edge-lagring (Storage)

Lokal lagring på Edge-enheder.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `local_path` | text | /data/captures | Lokal sti til billedlagring på edge-enheden. Billeder gemmes her før upload til headend. Skal have tilstrækkelig plads (se buffer). |
| `circular_buffer_gb` | number | 50 | Maksimal plads i GB før circular buffer sletter gamle uploaded billeder. Ældre uploaded filer slettes først. Større buffer = mere offline tolerance. Minimum 20-30 GB. |
| `db_path` | text | /data/timelapse_edge.db | Sti til SQLite database med capture metadata, logs og lokal state. Database backupes sammen med billeder. |

#### 5. Diagnostik (Diagnostics)

System overvågning og rapportering.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `sync_poll_interval_minutes` | number | 5 | Minutter mellem den konsoliderede sync-poll til headend (`POST /api/edge/sync/{device_id}`). Ét request/response dækker heartbeat/diagnostik, konfigurationsændringer og SIEM-log-forward — erstatter de tidligere separate `heartbeat_interval_minutes` (60 min) og `config_poll_interval_minutes` (5 min) siden 2026-08-19. Lavere = hurtigere response men mere network trafik. Typisk 5-10 minutter. |
| `update_poll_interval_minutes` | number | 5 | Minutter mellem tjek for systemopdateringer fra headend. Opdateringer downloades og installeres automatisk. Typisk 5-15 minutter. |
| `inventory_report_interval_hours` | number | 24 | Timer mellem inventory rapporter til headend. Inventory indeholder hardware info, versions, og kapacitet. Typisk 24 timer (daglig). |

#### 6. System (System)

Timeouts og recovery parametre.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `error_recovery_sleep_s` | number | 30 | Sekunder at vente efter fejl før retry. Forhindrer hurtig retry loop. Network timeout: 30-60 sekunder. Camera fejl: 60-120 sekunder. |
| `min_sleep_s` | number | 60 | Minimum søvn mellem captures i sekunder. Selv ved fejl eller hurtig retry. Sikrer at systemet hviler. Typisk 30-120 sekunder. |
| `api_timeout_s` | number | 15 | Timeout i sekunder for API kald til headend. Upload, heartbeat, config fetch. For kort kan give fejler på slow networks. Typisk 10-30 sekunder. |

#### 7. Session og MFA (Session Policy)

Login sikkerhed og MFA konfiguration.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `session_duration_hours` | number | 12 | Session levetid i timer før bruger skal logge ind igen. Balancerer sikkerhed og convenience. Typisk 8-24 timer. Admin roller: 4-12 timer. |
| `remember_me_days` | number | 30 | "Husk mig" session levetid i dage. Brugeren forbliver logget ind på enheden. Typisk 30-90 dage. |
| `remember_me_allowed` | boolean | true | Tillad "Husk mig" funktion på login. Brugere kan vælge at forblive logget ind. Slå fra for højere sikkerhed. |
| `mfa_required` | boolean | false | Kræv Multi-Factor Authentication for alle roller. Overrides rolle-specifikke indstillinger. Anbefales kun for highly secure miljøer. |
| `mfa_required_by_role.super_admin` | boolean | true | Kræv MFA for super_admin rolle. Super admin har fuld adgang. MFA anbefales altid. Beskytter mod compromised passwords. |
| `mfa_required_by_role.admin` | boolean | true | Kræv MFA for admin rolle. Admin har bred adgang til systemet. MFA anbefales altid. |
| `mfa_required_by_role.operator` | boolean | false | Kræv MFA for operator rolle. Operator har limited adgang. MFA valgfrit baseret på risikovurdering. |
| `mfa_required_by_role.viewer` | boolean | false | Kræv MFA for viewer rolle. Viewer har read-only adgang. MFA typisk ikke nødvendigt. |
| `mfa_exempt_usernames` | list | [] | Udvalgte admin/super_admin brugere der undtages fra MFA krav. Backup adgang ved MFA system fejl. Should be minimal. |

### Brug af Global Config UI

#### Navigation

1. Gå til **Settings → Global Config** eller klik på "Global Config" i navigationen
2. Vælg kontekst (Kunde/Site/Kamera) via dropdowns
3. Vælg hvilket lag du vil redigere

#### Parameterbeskrivelser via Hover

**Alle parametre har detaljerede tooltips der vises ved hover.**

Hold cursoren over et parameternavn (f.eks. "camera.delete_after_download") for at se en 4-linje beskrivelse skrevet for fotoeksperter:

- **Hvad parameteren gør** — praktisk forklaring
- **Anbefalede værdier** — typiske indstillinger
- **Konsekvenser** — hvad sker der hvis du ændrer det
- **Tips** — bed practices og gotchas

Tooltip informationen nedenfor i denne guide er en forkortet version. Se UI for fulde detaljer.

#### Læsning af Konfiguration

Tabellen viser:
- **Parameter**: Navn og technical path (hover for detaljeret beskrivelse)
- **Global/Kunde/Site/Kamera**: Værdi på hvert lag
- **Aktuel**: Effektiv værdi (efter arv)
- **Farver**:
  - 🟩 Grøn: Sat på valgte lag
  - 🟨 Gul: Afviger fra global default

#### Redigering af Konfiguration

1. Vælg lag du vil redigere (Global/Kunde/Site/Kamera)
2. Ændr værdier i "Rediger valgt lag" kolonnen
3. Klik "Gem lag" for at gemme
4. Ændringer pushes til edge-enheder ved næste config poll

**Bemærk**: Tomme felter betyder "arv fra overliggende lag".

#### Fabriksdefaults

For at nulstille globale defaults til fabriksværdier:
1. Vælg "Global" som rediger lag
2. Klik "Fabrik" knappen
3. Bekræft nulstilling
4. Klik "Gem lag" for at aktivere

### API Endpoints

```bash
# Hent config defaults
GET /api/admin/config-defaults

# Hent config resolution for kontekst
GET /api/admin/config-resolution?customer_id=xxx&site_id=yyy&camera_id=zzz

# Gem config overrides
PUT /api/admin/config-overrides/{layer}/{entity_id}
Body: {
  "mode": "merge" | "replace",
  "config_overrides": { ... }
}

# Slet config overrides
DELETE /api/admin/config-overrides/{layer}/{entity_id}
```

---

## Brugerstyring

### Roller

| Rolle | Rettigheder |
|------|-------------|
| `super_admin` | Fuld adgang, inkl. brugerstyring og systemændringer |
| `admin` | Adgang til alle funktioner undtagen brugerstyring |
| `operator` | Kan redigere kameraer, se captures, grundlæggende drift |
| `viewer` | Read-only adgang |

### Opret Bruger

Via Web UI:
1. Gå til **Admin → Brugere**
2. Klik "Ny bruger"
3. Indtast username, password og rolle
4. Vælg MFA krav

Via API:
```bash
curl -X POST http://localhost:8000/api/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "ny-bruger",
    "password": "sikkert-password",
    "role": "operator",
    "mfa_enabled": true
  }'
```

### MFA Opsætning

**TOTP (Time-based One-Time Password):**
1. Kræv TOTP for specifikke roller via Global Config
2. Bruger scanner QR kode ved første login
3. 6-digit kode indtastes ved login

**Hardware Tokens (YubiKey):**
```yaml
# Kommer i fremtidig version
```

---

## Systemadministration

### Service Management

```bash
# Headend service
sudo systemctl restart timelapse-headend

# Edge service (på enhed)
sudo systemctl restart timelapse-edge

# Tjek status
systemctl status timelapse-*
```

### Logfiler

```bash
# Live log
journalctl -u timelapse-headend -f

# Sidste 100 linjer
journalctl -u timelapse-headend -n 100

# Siden specificeret tid
journalctl -u timelapse-headend --since "1 hour ago"

# Filtrer på specifik komponent
journalctl -u timelapse-edge | grep -i "camera"
```

### Backup

```bash
# Database backup
sqlite3 /data/timelapse.db ".backup /backup/timelapse-$(date +%Y%m%d).db"

# Config backup
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
    /etc/timelapse/ \
    /opt/timelapse/edge/config.yaml
```

---

## Overvågning og Diagnostik

### Health Checks

```bash
# Headend health
curl http://localhost:8000/api/health

# Forventet response:
{
  "status": "ok",
  "version": "x.y.z",
  "database": "connected",
  "timestamp": "2026-07-13T10:00:00Z"
}
```

### Metrics

Vigtige metrics at overvåge:

| Metric | Sund | Warning | Kritisk |
|--------|------|---------|---------|
| CPU load | <50% | 50-80% | >80% |
| Memory | <70% | 70-90% | >90% |
| Disk /data | <70% | 70-90% | >90% |
| Capture success rate | >98% | 90-98% | <90% |
| Upload success rate | >99% | 95-99% | <95% |

---

## Site Konfiguration

### Overblik

Site-konfiguration giver mulighed for at styre indstillinger på tværs af alle kameraer på en specifik lokation. Site-niveau arver fra Kunde/Global og kan overstyres af Kamera-niveau.

**Tooltip ved hover:**
> Site-override gælder alle kameraer på dette site. Overstyrer kunde/global, men overstyres af kamera-lag.

### Site Oplysninger

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `name` | text | - | Navn på lokationen. Bruges til identifikation i rapporter og CMDB. Skal være unikt pr. kunde. |
| `address` | text | - | Fysisk adresse på lokationen. Bruges til navigering og dokumentation. Frit format. |
| `timezone` | select | Europe/Copenhagen | Tidszone for dette site. Sikrer at captures sker på korrekte lokale tider. Vigtig for tværl-okale sites. |
| `notes` | textarea | - | Interne noter om dette site. Kun synligt for admin-brugere. |

### SFTP Adgang

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `sftp.username` | text | - | Brugernavn til SFTP server hvor edge-enheder uploader billeder. Unik pr. site. Autogenereres typisk. |
| `sftp.password` | password | - | Password til SFTP auth. Gemmes sikkert og deles med edge-enheder. bør være stærkt og unikt. |
| `sftp.remote_base` | text | - | Sti på SFTP server hvor billeder gemmes. Typisk /Users/Shared/timelapse/incoming/[site]. Skal eksistere på server. |
| `sftp.port` | number | 22222 | SFTP server port. Standard 22222 for sikker SFTP. Skal matche server config. |

### GPS og Lokation

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `gps_lat` | number | - | GPS breddegrad i decimal format. Positiv for nordlige halvkugle, negativ for sydlige. Eksempel: 55.676098. |
| `gps_lon` | number | - | GPS længdegrad i decimal format. Positiv for østlig, negativ for vestlig. Eksempel: 9.535400. |
| `gps_alt` | number | - | GPS højde i meter over havets overflade. Positiv over hav, negativ under. Bruges til AI skala beregning. |

**Tip:** Brug OpenStreetMap linket i UI til at verificere koordinaterne.

### BT PAN TOTP (Site-override)

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `bt_totp.secret` | text | - | TOTP secret til Bluetooth PAN auth. Base32 encoded. Tom = arv fra kunde/global. Overstyres af kamera. |
| `bt_totp.sid` | text | - | Unikt site ID til TOTP authentication. Identificerer siteet i TOTP systemet. Tom = brug site navn. |

### Edge AI (Site-override)

Samme parametre som Global Config Quality sektion, men med site-override mulighed.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `quality.edge_ai.enabled` | boolean | arv | Aktiverer AI-baseret kvalitetsanalyse på edge. Sløring, mørk, lens obstruction. Anbefales altid. |
| `quality.edge_ai.mode` | select | arv | AI adfærd: off, monitor (log kun), assist (advar), autonomous (rett), npu_first, lab. Assist anbefales. |
| `quality.edge_ai.prefer_npu` | boolean | arv | Brug hardware accelerator (NPU) frem for CPU. Hurtigere og mindre strøm. Anbefales til NPU-hardware. |
| `quality.adaptive_exposure.enabled` | boolean | arv | Auto-juster EV baseret på brightness. Kompenserer for skygge, sol, overskyet. Anbefales ved variable lys. |
| `quality.adaptive_exposure.step_ev` | number | arv | EV step per justering (0.1-3.0). Mindre = finere justering men flere cycles. Typisk 0.3-0.7. |

### Drift Detektion (Site-override)

Samme parametre som Global Config Drift Detection sektion, men med site-override mulighed.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `quality.drift_detection.focus.enabled` | boolean | arv | Alarmer hvis skarphed systematisk falder. Detekterer manuel fokus der glider (vibration, temperatur). |
| `quality.drift_detection.focus.z_threshold` | number | arv | Antal standardafvigelser før alarm (2.0-4.0). Lavere = mere følsom. Typisk 2.0-3.0. |
| `quality.drift_detection.exposure.enabled` | boolean | arv | Alarmer hvis eksponering systematisk skifter. Detekterer støv, tåge, sæson ændringer. |
| `quality.drift_detection.exposure.z_threshold` | number | arv | Antal standardafvigelser før alarm (2.5-4.0). Højere end focus da lysstyrke varierer mere. |
| `quality.drift_detection.white_balance.enabled` | boolean | arv | Alarmer hvis hvidbalance systematisk skifter. Kræver at edge-optimizer rapporterer hvidbalance-data. |
| `quality.drift_detection.white_balance.z_threshold` | number | arv | Antal standardafvigelser før alarm (2.0-3.0). Typisk 2.0-3.0. |

---

## Kunde Konfiguration

### Overblik

Kunde-konfiguration giver mulighed for at styre indstillinger på tværs af alle sites for en kunde. Kunde-niveau arver fra Global og kan overstyres af Site/Kamera-niveau.

**Tooltip ved hover:**
> Kunde-override gælder alle sites for denne kunde. Overstyrer global/fabriksstandard, men overstyres af site/kamera-lag.

### Kundeoplysninger

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `name` | text | - | Navnet på kunden. Bruges til identifikation, rapportering og fakturering. Skal være unikt. |
| `contact_name` | text | - | Primær kontaktperson hos kunden. Bruges til kommunikation og support. |
| `contact_email` | email | - | Emailadresse til kontaktperson. Bruges til kommunikation og notifikationer. |
| `contact_phone` | tel | - | Telefonnummer til kontaktperson. Bruges til akutte henvendelser. Format: +45 XX XX XX XX. |
| `address` | text | - | Fysisk adresse til fakturering og korrespondance. Frit format. |
| `notes` | textarea | - | Interne noter om kunden. Kun synligt for admin-brugere. |

### BT PAN TOTP (Kunde-override)

Samme struktur som Site BT PAN TOTP, men på kunde-niveau.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `bt_totp.secret` | text | - | TOTP secret til Bluetooth PAN auth. Base32 encoded. Tom = arv fra global. Overstyres af site/kamera. |
| `bt_totp.sid` | text | - | Unikt kunde ID til TOTP authentication. Identificerer kunden i TOTP systemet. Tom = brug kundenavn. |

### Edge AI (Kunde-override)

Samme parametre som Global Config Quality sektion, men med kunde-override mulighed.

Se [Edge AI (Site-override)](#edge-ai-site-override) for parameter detaljer.

### Drift Detektion (Kunde-override)

Samme parametre som Global Config Drift Detection sektion, men med kunde-override mulighed.

Se [Drift Detektion (Site-override)](#drift-detektion-site-override) for parameter detaljer.

---

## Sikkerhed

### SSH Adgang

**Edge enheder:**
```bash
# Kun nøglebaseret auth tilladt
PasswordAuthentication no

# Root login ikke tilladt
PermitRootLogin no

# Whitelist admin brugere
AllowUsers timelapse admin
```

### API Tokens

Tokens roteres automatisk via headend:
- API tokens har 90-dages levetid
- Tokens gemmes i `/opt/timelapse/edge/api_token.txt`
- Rotering sker via UI: **Admin → Nøgler → Roter**

### Firewall

```bash
# Kun nødvendige porte åbne
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8099/tcp  # Technician UI (edge)
```

---

## Support

### Kontakt

| Type | Kontakt |
|------|---------|
| Akutte driftsproblemer | +45 XX XX XX XX |
| Teknisk support | support@timelapse.example.com |
| Feature requests | product@timelapse.example.com |

### Diagnostisk Information

Ved henvendelse inkluder venligst:
- System version: `git rev-parse HEAD`
- Service status: `systemctl status timelapse-*`
- Relevante logs: `journalctl -u timelapse-* -n 200`

---

**Guide version:** 1.2
**Sidst opdateret:** 13. juli 2026

---

## Changelog

### v1.2 (2026-07-13)
- Tilføjet Site Konfiguration sektion med alle parametre (Site oplysninger, SFTP, GPS, BT PAN TOTP, Edge AI, Drift Detektion)
- Tilføjet Kunde Konfiguration sektion med alle parametre (Kundeoplysninger, BT PAN TOTP, Edge AI, Drift Detektion)
- Dokumenteret tooltip funktionalitet på SitePage og CustomerPage
- Opdateret parameterbeskrivelser med tooltip tekst præcis som i UI

### v1.1 (2026-07-13)
- Tilføjet detaljerede parameterbeskrivelser i alle konfigurationssektioner
- Dokumenteret hover-tooltip funktionalitet i UI
- Udvidet beskrivelser for fotoeksperter med praktiske værdier og anbefalinger
