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
| `timezone` | select | Europe/Copenhagen | Tidszone for schedule |
| `capture_mode` | select | interval | `interval` eller `fixed_times` |
| `interval_minutes` | number | 60 | Minutter mellem captures (interval mode) |
| `active_hours` | array | ["06:00", "21:00"] | Start/slut tid for daglig capture |

#### 2. Kamera (Camera)

Kamerastyring og eksponering.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `power_mode` | select | relay | `relay` eller `usb_powered` |
| `iso` | select | Auto | ISO følsomhed |
| `shutter_speed` | select | Auto | Lukker tid |
| `aperture` | select | Auto | Blændeåbning |
| `whitebalance` | select | Auto | Hvidbalance |
| `relay_gpio_pin` | number | 356 | GPIO pin nummer (RK3588: 356, H3: BOARD 7) |
| `relay_on_seconds_before` | number | 10 | Sekunder kameraet skal være tændt før capture |
| `relay_off_seconds_after` | number | 5 | Sekunder før strøm slukkes efter capture |
| `delete_after_download` | boolean | true | Slet billeder fra kamera efter download |
| `gphoto2_port` | text | usb: | gPhoto2 port streng |
| `azimuth_deg` | number | - | Kamera retning (grader)
| `tilt_deg` | number | - | Kamera tilt (grader, negativ = nedad)
| `mount_height_m` | number | - | Montering højde (meter)
| `fov_horizontal_deg` | number | - | Horisontalt felt af syn (grader)
| `fov_vertical_deg` | number | - | Vertikalt felt af syn (grader)
| `perspective` | select | eye_level | `eye_level`, `high_angle`, `low_angle`, `birds_eye`, `worms_eye` |

#### 3. Kvalitet (Quality)

Automatisk billedkvalitetskontrol.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `check_enabled` | boolean | true | Aktivér kvalitetstjek |
| `blur_threshold` | number | 80 | Minimum skarpheds-score (Laplacian variance) |
| `dark_threshold` | number | 25 | Minimum lysstyrke (0-255) |
| `bright_threshold` | number | 230 | Maksimum lysstyrke (0-255) |

**Adaptiv Eksponering:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `adaptive_exposure.enabled` | boolean | false | Auto-juster EV baseret på brightness |
| `adaptive_exposure.target_brightness` | number | 118 | Mål lysstyrke (0-255, 128 = optimal) |
| `adaptive_exposure.brightness_tolerance` | number | 32 | Acceptabel afvigelse fra mål |
| `adaptive_exposure.step_ev` | number | 0.3 | EV step per justering |
| `adaptive_exposure.min_ev` | number | -2.0 | Minimum EV korrektion |
| `adaptive_exposure.max_ev` | number | 2.0 | Maksimum EV korrektion |

**Edge AI Kvalitet:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `edge_ai.enabled` | boolean | true | Aktivér AI kvalitetsanalyse |
| `edge_ai.mode` | select | assist | `off`, `monitor`, `assist`, `autonomous`, `npu_first`, `lab` |
| `edge_ai.prefer_npu` | boolean | true | Foretræk NPU frem for CPU |
| `edge_ai.runner` | text | - | Sti til NPU runner script |
| `edge_ai.model_path` | text | - | Sti til NPU model fil |
| `edge_ai.vendor_binary` | text | - | Sti til vendor wrapper (VIPLite) |

**Drift Detektion:**

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `drift_detection.focus.enabled` | boolean | true | Alarmer på fokus-drift |
| `drift_detection.focus.z_threshold` | number | 2.0 | Standardafvigelser før alarm |
| `drift_detection.exposure.enabled` | boolean | true | Alarmer på eksponerings-drift |
| `drift_detection.exposure.z_threshold` | number | 2.5 | Standardafvigelser før alarm |
| `drift_detection.white_balance.enabled` | boolean | false | Alarmer på hvidbalance-drift |
| `drift_detection.white_balance.z_threshold` | number | 2.0 | Standardafvigelser før alarm |

#### 4. Edge-lagring (Storage)

Lokal lagring på Edge-enheder.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `local_path` | text | /data/captures | Sti til billedlagring |
| `circular_buffer_gb` | number | 50 | Maksimal GB før oprydning |
| `db_path` | text | /data/timelapse_edge.db | Sti til SQLite database |

#### 5. Diagnostik (Diagnostics)

System overvågning og rapportering.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `heartbeat_interval_minutes` | number | 60 | Minutter mellem heartbeats til headend |
| `config_poll_interval_minutes` | number | 5 | Minutter mellem config pulls |
| `update_poll_interval_minutes` | number | 5 | Minutter mellem opdateringstjek |
| `inventory_report_interval_hours` | number | 24 | Timer mellem inventory rapporter |

#### 6. System (System)

Timeouts og recovery parametre.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `error_recovery_sleep_s` | number | 30 | Sekunder at vente efter fejl før retry |
| `min_sleep_s` | number | 60 | Minimum søvn mellem captures |
| `api_timeout_s` | number | 15 | Timeout for API kald (sekunder) |

#### 7. Session og MFA (Session Policy)

Login sikkerhed og MFA konfiguration.

| Parameter | Type | Default | Beskrivelse |
|-----------|------|---------|-------------|
| `session_duration_hours` | number | 12 | Session levetid (timer) |
| `remember_me_days` | number | 30 | "Husk mig" varighed (dage) |
| `remember_me_allowed` | boolean | true | Tillad "Husk mig" funktion |
| `mfa_required` | boolean | false | Kræv MFA for alle roller |
| `mfa_required_by_role.super_admin` | boolean | true | Kræv MFA for super_admin |
| `mfa_required_by_role.admin` | boolean | true | Kræv MFA for admin |
| `mfa_required_by_role.operator` | boolean | false | Kræv MFA for operator |
| `mfa_required_by_role.viewer` | boolean | false | Kræv MFA for viewer |
| `mfa_exempt_usernames` | list | [] | Brugere undtaget fra MFA |

### Brug af Global Config UI

#### Navigation

1. Gå til **Settings → Global Config** eller klik på "Global Config" i navigationen
2. Vælg kontekst (Kunde/Site/Kamera) via dropdowns
3. Vælg hvilket lag du vil redigere

#### Læsning af Konfiguration

Tabellen viser:
- **Parameter**: Navn og technical path
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

**Guide version:** 1.0
**Sidst opdateret:** 13. juli 2026
