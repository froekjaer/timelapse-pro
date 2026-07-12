# TimeLapse Pro — Edge Arkitektur

**Version:** 3.2.0
**Dato:** 12. juli 2026
**Status:** Produktion

---

## 📋 Indhold

1. [Overblik](#overblik)
2. [Komponenter](#komponenter)
3. [Dataflow](#dataflow)
4. [Hardware Abstraction](#hardware-abstraction)
5. [Kamera Integration](#kamera-integration)
6. [AI & Kvalitetssikring](#ai--kvalitetssikring)
7. [Upload & Synkronisering](#upload--synkronisering)
8. [Sikkerhed](#sikkerhed)
9. [Fejlfinding & Diagnostik](#fejlfinding--diagnostik)

---

## Overblik

TimeLapse Pro Edge Agent er en autonom applikation der kører på Linux-baserede enheder (Orange Pi, Raspberry Pi) og styrer timelapse-kameraer. Agenten implementerer fuld SABSA-compliance:

| SABSA Attribute | Implementation |
|----------------|----------------|
| **Availability** | Autonom drift, selv ved netbrud. Lokal cache af konfiguration og upload-kø. |
| **Integrity** | SHA-256 hashing af alle billeder. Kvalitetstjek før upload. |
| **Accountability** | SQLite database med fuld audit trail. SIEM-events til headend. |
| **Continuity** | Cirkulær buffer med automatisk oprydning. Natlig genstart for stabilitet. |

### Arkitektur Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EDGE AGENT (agent.py)                          │
│                       ┌───────────────────────┐                        │
│                       │   Main Loop &         │                        │
│                       │   Scheduler           │                        │
│                       └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────┘
          │              │              │              │              │
          ▼              ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Camera    │ │   Upload    │ │   Config    │ │  Diagnostics │ │  Security   │
│   Driver    │ │   Manager   │ │   Manager   │ │  Collector  │ │  Module     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
          │              │              │              │              │
          ▼              ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ gphoto2 /   │ │  API + SFTP │ │  bootstrap  │ │  System     │ │  Signing    │
│  PTP        │ │  Transports │ │  config     │ │  Metrics    │ │  Keys       │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Komponenter

### 1. Main Loop (`agent.py`)

Hovedfilen der orkestrerer alle komponenter.

**Klasser:**
- `EdgeAgent` — Main orchestrator

**Nøglefunktioner:**

```python
# Entry points
agent.run()                    # Main loop - kører til SIGTERM/SIGINT
agent.run_single_capture()    # En capture cycle - til test/commissioning

# Internal lifecycle
agent._startup()               # Bootstrap, config pull, tunnel, UI
agent._tick()                  # En iteration: capture check → heartbeat → sleep
agent._shutdown()              # Graceful cleanup
```

**Scheduling Modes:**
- `interval` — Fast interval (fx hver 30. minut)
- `fixed` — Specifikke tidspunkter (fx "08:00, 12:00, 16:00")

**Lab Mode:**
Debug mode hvor kameraet er tændt konstant og modtager kommandoer fra headend:
- Preview captures
- Focus slice tests
- Parameter ændringer
- Relay toggling

---

### 2. Kamera Driver (`camera/`)

Abstraktion over gphoto2/PTP for forskellige kameramodeller.

**Struktur:**
```
camera/
├── base.py           # Abstract base class
├── registry.py       # Driver factory
├── relay.py          # GPIO relay controller
└── drivers/
    ├── nikon_z30.py  # Nikon Z30 implementation
    ├── canon_eos.py  # Canon EOS implementation
    └── generic.py    # Fallback driver
```

**Relay Controller (`relay.py`):**

Styrer HW-383A dual-channel relay module:

| Relay | Funktion | GPIO (RK3588) | GPIO (H3) |
|-------|----------|---------------|-----------|
| Camera | Tænd/sluk kamera strøm | 356 | BOARD 7 |
| Modem  | Tænd/sluk 4G modem | 361 | — |

**Platform detection:**
- `rk3588` — Orange Pi 4 Pro (sysfs GPIO)
- `h3` — Orange Pi PC Plus (OPi.GPIO)

**Camera Registry (`registry.py`):**

```python
# Auto-detect driver based on camera model
driver = get_driver(config)
driver.connect()
driver.capture_image(dest_dir)
driver.disconnect()
```

---

### 3. Capture & Quality (`capture/`)

**Buffer Manager (`buffer.py`):**

Cirkulær buffer der begrænser diskforbrug:

```python
# Konfiguration
storage:
  local_path: "/data/captures"
  circular_buffer_gb: 50  # Maksimal diskforbrug

# Adfærd
buffer.enforce(db)  # Sletter oldest uploaded først
```

**Quality Checker (`quality.py`):**

Billedkvalitetsanalyse med OpenCV:

```python
# Kvalitetsmetrikker
quality.check(filepath, expected_sha256)

# Resultat
{
    "flag": "ok",           # ok / blurry / underexposed / overexposed / error
    "passed": true,
    "blur_score": 150.5,    # Laplacian variance (higher = sharper)
    "brightness_mean": 118, # 0-255 (128 = optimal)
    "message": "Quality OK"
}
```

**QA Sidecar:**

Hvert billede får en `.qa.json` sidecar fil:

```json
{
    "schema": "timelapse.edge_qa.v1",
    "generated_at": "2026-07-12T10:30:00Z",
    "device_id": "tlp-edge-001",
    "image_file": "IMG_1234.jpg",
    "quality": {
        "flag": "ok",
        "passed": true,
        "blur_score": 150.5
    }
}
```

---

### 4. AI & NPU Runtime (`ai/`)

CPU-only billedanalyse og Site-Wide Look Matching.

**Komponenter:**

| Fil | Funktion |
|-----|----------|
| `npu_runtime.py` | NPU abstraction layer (VIP Lite/QNN) |
| `autonomous_optimizer.py` | Adaptive exposure optimization |
| `site_look_manager.py` | Site-wide look matching (Feature F-012) |
| `site_look_config_client.py` | Config client for look profiles |
| `modes.py` | Capture mode logic |

**Site Look Manager (`site_look_manager.py`):**

Sikrer konsistent look på tværs af alle kameraer på en site:

```python
# Generate LUT for camera to match site reference
lut = manager.generate_camera_lut(
    reference_frame=site_ref,
    camera_frame=camera_frame,
    camera_model="Nikon Z30"
)
```

**Autonomous Optimizer (`autonomous_optimizer.py`):**

AI-drevet eksposure justering:

```python
# Analyserer sidste capture og foreslår EV adjustment
control_plan = optimizer.recommend_exposure_adjustment(
    last_quality_report=quality_report
)
# Resultat: {"next_capture_ev_delta": -0.3}  # Dæmp lyset
```

---

### 5. Config Management (`config/`)

**Tre-lags model:**

1. `bootstrap.yaml` — Device identitet (provisioning)
2. `local_network.yaml` — Netværksindstillinger
3. `config.yaml` — Operationel config (fra headend)

**Config Manager (`manager.py`):**

```python
cfg_mgr = ConfigManager()
config = cfg_mgr.load()  # Merger alle tre lag

# Live opdatering fra headend
cfg_mgr.save_config(new_config)
```

---

### 6. Database & State (`utils/database.py`)

SQLite med WAL mode for strømudholdenhed.

**Tabeller:**

| Tabel | Formål |
|-------|--------|
| `captures` | Metadata for alle billeder |
| `diagnostics` | Systemdiagnostik tidsserie |
| `events` | Event log (errors, state changes) |
| `upload_queue` | Upload retry tracking |
| `schema_version` | Database migration tracking |

**Vigtige felter i `captures`:**

```sql
CREATE TABLE captures (
    id              INTEGER PRIMARY KEY,
    device_id       TEXT NOT NULL,
    filepath        TEXT NOT NULL UNIQUE,
    sha256          TEXT NOT NULL,
    captured_at     TEXT NOT NULL,
    quality_flag    TEXT,        -- ok / blurry / underexposed / overexposed
    quality_passed  INTEGER,
    uploaded_primary   INTEGER DEFAULT 0,
    synced_to_headend  INTEGER DEFAULT 0
);
```

---

### 7. Upload & Sync (`upload/`)

**Headend Client (`headend_client.py`):**

REST API klient til headend:

```python
# Upload capture
ok, result = api.upload_capture_files(row, filepath)

# Heartbeat med diagnostik
ok, hb_resp = api.send_heartbeat(diag_data, capture_stats)

# Config pull
ok, config = api.fetch_config()
```

**SFTP Manager (`sftp.py`):**

Alternativ upload via SFTP:

```python
# Konfiguration
sftp:
  host: "sftp.example.com"
  remote_base: "/incoming"
  username: "timelapse"
  password: "xxx"

# Brug
sftp.upload_capture(capture_id, filepath, camera_id)
```

---

### 8. Diagnostics (`diagnostics/`)

**Collector (`collector.py`):**

Indsamler systemmetrik:

```python
diag = {
    "cpu_temp_c": 45.2,
    "cpu_load_pct": 12.5,
    "ram_used_mb": 512,
    "disk_used_gb": 23.4,
    "battery_v": 13.2,
    "solar_v": 18.5,
    "connectivity": "ethernet",
    "uptime_s": 1234567
}
```

**Camera Diagnostics (`camera_diagnostics.py`):**

Kamera-specifik diagnostik:

```python
diag = collect_camera_diagnostics(
    camera_model="Nikon Z30",
    expected_config={"iso": "200", "shutterspeed": "1/500"}
)
# Resultat: battery_pct, shutter_count, config_drift
```

**WiFi (`wifi.py`):**

WiFi scanning og forbindelse:

```python
# Scan netværk
networks = scan()

# Forbind
connect(ssid, password)
```

---

### 9. Security (`security.py`)

**Signering verification:**

```python
# Verificer opdaterings-artifact fra headend
ok, reason = verify_update_artifact(
    artifact=update,
    security_config=config["security"]
)
```

**Trust policy:**
- Kun headend-signerede artifacts må installeres
- Lokal git pull er kun tilladt i LAB mode
- API tokens roteres via headend

---

### 10. Technician Authentication (`technician_auth.py`, `technician_ui.py`)

QR-code baseret login for serviceteknikere:

**Flow:**
1. Edge genererer auth challenge + QR kode
2. Tekniker scanner QR → headend login
3. Headend bekræfter auth → edge modtager session
4. Tekniker får lokal adgang

**UI Server (`technician_ui.py`):**

```python
# Starter på port 8099
server = serve_technician_ui(auth, port=8099)
```

---

## Dataflow

### Normal Capture Cycle

```
1. Scheduler → capture_due
2. Relay → camera power ON
3. Driver → connect + configure
4. Driver → capture image
5. Quality → analyze
6. Database → insert capture record
7. Buffer → enforce disk limit
8. Upload → API + SFTP
9. Relay → camera power OFF
10. Heartbeat → send diagnostics
```

### Upload Retry

```
1. Check upload slot state
2. If slot open:
   - Retry pending API uploads
   - Retry SFTP uploads
3. Else: defer to next slot
```

---

## Hardware Abstraction

**HAL (`hal/`):**

Platform-specifik abstraction:

| Platform | HAL | GPIO |
|---------|-----|------|
| Orange Pi 4 Pro | `hal/orangepi.py` | sysfs (356, 361) |
| Orange Pi PC Plus | `hal/orangepi.py` | OPi.GPIO |
| Raspberry Pi | `hal/rpi.py` | RPi.GPIO |
| Jetson | `hal/jetson.py` | Jetson GPIO |

**Capabilities:**

```python
hal = get_adapter()
caps = hal.capabilities()
# {
#     "hal_id": "orangepi-4-pro",
#     "gpio": true,
#     "npu": "rk3588-vip-lite",
#     ...
# }
```

---

## Konfiguration

### bootstrap.yaml (Provisioning)

```yaml
device_id: "tlp-edge-001"
headend_url: "https://timelapse.example.com/api"
customer_id: "customer-123"
location_name: "Site A - North"
```

### config.yaml (Operational)

```yaml
# Kamera konfiguration
camera:
  model: "Nikon Z30"
  serial_number: "12345678"
  power_mode: "relay"
  relay_on_seconds_before: 10
  relay_off_seconds_after: 5

# Capture schedule
schedule:
  capture_mode: "interval"
  interval_minutes: 30
  timezone: "Europe/Copenhagen"
  active_hours: ["06:00", "22:00"]

# Upload
upload:
  api:
    base_url: "https://timelapse.example.com/api"
    timeslot:
      enabled: true
      enforced: true
      cycle_seconds: 600
      window_seconds: 90
  sftp:
    host: "sftp.example.com"
    remote_base: "/incoming"

# Storage
storage:
  local_path: "/data/captures"
  db_path: "/data/timelapse_edge.db"
  circular_buffer_gb: 50

# Quality
quality:
  adaptive_exposure:
    enabled: true
    min_ev: -2.0
    max_ev: 2.0
    step_ev: 0.3
```

---

## Fejlfinding

### Log levels

```bash
# Se log (stdout → journal)
journalctl -u timelapse-edge -f

# Se specifikke komponenter
journalctl -u timelapse-edge | grep "camera"
journalctl -u timelapse-edge | grep "upload"
```

### Fejlsøgning guide

| Symptom | Mulig årsag | Tjek |
|---------|-------------|------|
| Ingen billeder | Kamera ikke fundet | `ls -l /dev/timelapse-cam*` |
| Upload fejler | Netværk nede | `ping headend.local` |
| Disk fuld | Buffer ikke håndteret | `df -h /data` |
| Relay ikke tændt | GPIO forkert | `cat /sys/class/gpio/gpio356/value` |

---

## Version History

| Version | Dato | Ændringer |
|---------|------|-----------|
| 3.2.0 | 2026-05-06 | LAB capture bug fix: disconnect + power_off FØR _do_capture_cycle |
| 3.1.0 | 2026-04-12 | Stabile USB symlinks via /dev/timelapse-camN |
| 3.0.0 | 2026-04-12 | Multi-kamera burst capture (threading) |
| 2.9.0 | 2026-04-12 | relay_toggle lab_command |
| 2.8.0 | 2026-04-11 | PTP busy relay power cycle recovery |

---

**Dokument version:** 1.0
**Sidst opdateret:** 12. juli 2026
