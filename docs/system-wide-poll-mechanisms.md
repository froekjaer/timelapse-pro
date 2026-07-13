# System-Wide Polling Mekanismer

**Version:** 2.1
**Dato:** 13. juli 2026
**Omfang:** Hele TimeLapse Pro systemet (Frontend + Backend)
**Formål:** Komplet dokumentation af alle polling mekanismer

---

## Oversigt

TimeLapse Pro har **25+ forskellige polling mekanismer** fordelt på UI pages, backend services, og edge agents.

### Sammenfatning

| Kategori | Antal Polls | Samlet Load |
|----------|-------------|-------------|
| **Dashboard & Observability** | 4 | Lav |
| **LAB Mode** | 9 | Høj |
| **Backup & DR** | 3 | Medium |
| **Post-Processing** | 2 | Medium |
| **Import & Retention** | 2 | Lav |
| **Video & Rendering** | 1 | Lav |
| **SSH Tunnels** | 2 | Lav |
| **Backend Edge Agent** | 3 | Medium |
| **Total** | **26** | **Medium** |

---

## Del 1: UI Polling (Frontend)

### 1. Dashboard Poll

**Fil:** `timelapse-ui/src/pages/Dashboard.tsx:242`
**Interval:** **60.000 ms** (60 sekunder)
**Formål:** Opdaterer dashboard stats, devices, customers, sites

```typescript
useEffect(() => {
  const id = setInterval(load, 60_000)
  return () => clearInterval(id)
}, [])
```

**Kører når:** Page er mountet
**Henter:** Stats, Devices, Customers, Sites
**Problemer:** Ingen ❌

---

### 2. DriftPage Poll

**Fil:** `timelapse-ui/src/pages/DriftPage.tsx:132`
**Interval:** **30.000 ms** (30 sekunder)
**Formål:** Opdaterer drifts-overblik (health tiles, alerts)

```typescript
useEffect(() => {
  const t = window.setInterval(loadHealth, 30000)
  return () => window.clearInterval(t)
}, [loadHealth])
```

**Kører når:** Page er mountet
**Henter:** Health, Alerts
**Problemer:** Ingen ❌

---

### 3. SIEMPage Poll

**Fil:** `timelapse-ui/src/pages/SIEMPage.tsx:180`
**Interval:** **30.000 ms** (30 sekunder)
**Formål:** Auto-refresh af security events

```typescript
useEffect(() => {
  if (!autoRefresh) return
  const t = setInterval(load, 30000)
  return () => clearInterval(t)
}, [autoRefresh, load])
```

**Kører når:** `autoRefresh === true`
**Henter:** Events, Summary, Threats
**Problemer:** Kan slås fra via toggle ✅

---

### 4. PostProcessingPage Polls

#### 4a. Job Status Poll
**Fil:** `timelapse-ui/src/pages/PostProcessingPage.tsx:179`
**Interval:** **2000 ms** (2 sekunder)
**Kører når:** `status.running === true`

#### 4b. Batch Jobs Poll
**Fil:** `timelapse-ui/src/pages/PostProcessingPage.tsx:189`
**Interval:** **30.000 ms** (30 sekunder)
**Kører når:** Aktive batch jobs

---

### 5. BackupPage Polls

#### 5a. Backup Status Poll
**Fil:** `timelapse-ui/src/pages/BackupPage.tsx:459`
**Interval:** **1500 ms** (1.5 sekunder)
**Kører når:** Backup kører
**Stopper:** Når `!running`

#### 5b. Disk Build Poll
**Fil:** `timelapse-ui/src/pages/BackupPage.tsx:525`
**Interval:** **2000 ms** (2 sekunder)
**Kører når:** Disk build kører

#### 5c. WiFi Inject Poll
**Fil:** `timelapse-ui/src/pages/BackupPage.tsx:1164`
**Interval:** **2000 ms** (2 sekunder)
**Kører når:** WiFi inject aktiv

---

### 6. ImportPage Poll

**Fil:** `timelapse-ui/src/pages/ImportPage.tsx:69`
**Interval:** **2000 ms** (2 sekunder)
**Kører når:** Aktivt import job
**Stopper:** Når `status === 'done'`

---

### 7. RetentionPage Poll

**Fil:** `timelapse-ui/src/pages/RetentionPage.tsx:108`
**Interval:** **2000 ms** (2 sekunder)
**Kører når:** Retention cleanup kører

---

### 8. TimelapseVideoPage Poll

**Fil:** `timelapse-ui/src/pages/TimelapseVideoPage.tsx:278`
**Interval:** **1000 ms** (1 sekund)
**Formål:** Poller render job status

```typescript
pollRef.current = setInterval(async () => {
  const status = await apiCall(`/api/timelapse/status/${result.job_id}`)
  setJob(s => ({ ...s, ...status }))
  if (status.status === 'done' || status.status === 'error') {
    clearInterval(pollRef.current!)
    setRendering(false)
  }
}, 1000)
```

**Kører når:** Video rendering er startet
**Stopper:** Når done eller error

---

### 9. SSH Tunnel Page Polls

#### 9a. Active Tunnels Poll
**Fil:** `timelapse-ui/src/pages/SshTunnelPage.tsx:162`
**Interval:** **30.000 ms** (30 sekunder)
**Formål:** Opdaterer active SSH tunnels liste

```typescript
useEffect(() => {
  load()
  const t = setInterval(() => load(), 30_000)
  return () => clearInterval(t)
}, [load])
```

**Kører når:** Page er mountet

---

### 10. LAB Mode Polls (9 mekanismer)

Se detaljeret dokumentation i `lab-poll-mechanisms.md`.

Kort opsummering:

| # | Navn | Interval | Formål |
|---|------|----------|---------|
| 1 | checkExistingLab | 3s | Tjekker LAB state ved page load |
| 2 | Preview List | 3s | Opdaterer preview liste |
| 3 | Live Preview Loop | 4s + 750ms×8 | Auto-preview generation |
| 4 | Camera-Ready | 3s | Venter på kamera ready signal |
| 5 | Take Preview | 1.5s | Venter på preview efter request |
| 6 | Load Params | 1.5s | Venter på kamera parametre |
| 7 | waitForLabResult | 1.5s | Generisk vent på LAB resultat |
| 8 | WiFi Scan | 1.5s | Venter på WiFi scan resultat |
| 9 | WiFi Connect | 1.5s | Venter på WiFi connect resultat |

**Problemer:**
- ✋ Flere polls kører samtidigt
- ✋ Ingen timeout på Camera-Ready poll
- ✋ Live Preview retry loop ineffektiv

---

## Del 2: Backend Polling (Edge/Headend)

### 11. Edge Agent — Config Poll

**Fil:** `edge/agent.py:687`
**Interval:** **5 minutter** (300 sekunder, konfigurerbar)
**Formål:** Agent henter config fra headend

```python
config_interval = timedelta(minutes=int(
    self._cfg.get("diagnostics", {}).get("config_poll_interval_minutes", 5)
))
```

**Kører når:** Edge agent kører
**Konfigurerbar:** `config_poll_interval_minutes`

---

### 12. Edge Agent — Heartbeat Poll

**Fil:** `edge/agent.py:737`
**Interval:** **60 minutter**
**Formål:** Rapporter status til headend

**Kører når:** Edge agent kører
**Problemer:** Meget lang interval - kunne være hyppigere

---

### 13. Edge Agent — LAB Mode Poll

**Fil:** `edge/agent.py:1983-2245`
**Interval:** **1 sekund** (i LAB mode, konfigurerbar)
**Formål:** LAB mode poller for kommandoer fra headend

```python
# I lab mode: config_poll_s default 1 sekund
```

**Kører når:** LAB mode er aktiv
**Problemer:** Høj frekvens - kan belaste systemet

---

### 14. SSH Tunnel Manager Poll

**Fil:** `edge/tunnel/ssh_manager.py:197-258`
**Interval:** **30 sekunder** (`TUNNEL_CHECK_INTERVAL_S = 30`)
**Formål:** Overvåger og maintain SSH tunnels

**Kører når:** SSH tunnel service kører
**Stopper:** `stop()` kaldes

---

### 15. Site Look Config Poll

**Fil:** `edge/ai/site_look_config_client.py:209-241`
**Interval:** **300 sekunder** (5 minutter, default)
**Formål:** Holder AI config opdateret

```python
self._poll_interval = config.get('poll_interval_seconds', 300)
```

**Kører når:** Site Look Manager kører
**Konfigurerbar:** Per kunde/site/kamera

---

### 16. Technician UI — QR Login Poll

**Fil:** `edge/technician_ui.py:338-370`
**Interval:** **2 sekunder**
**Formål:** Tjekker QR code login status
**Max polls:** 180 (15 minutter timeout)

```javascript
// Generated JavaScript poll
setTimeout(pollFunction, 2000)
```

**Kører når:** QR code login er aktiveret
**Stopper:** Efter 15 minutter eller successful login

---

## Del 3: Polling Analyse

### Poll Intervaller Fordeling

| Interval | Antal | Procent |
|----------|-------|---------|
| 1 sekund | 3 | 12% |
| 1.5-2 sekunder | 10 | 38% |
| 3 sekunder | 3 | 12% |
| 30 sekunder | 5 | 19% |
| 60+ sekunder | 5 | 19% |

### Poll Kategorier

| Kategori | Antal | Load |
|----------|-------|------|
| **Kortvarige** (<3s, stopper når færdig) | 13 | Medium |
| **Lange** (≥30s, continuous) | 8 | Lav |
| **LAB specifikke** | 9 | Høj |

### Problemområder

| Prioritet | Problem | Påvirkning | Løsning |
|-----------|---------|-------------|---------|
| 🔴 Høj | LAB mode: 3+ polls samtidig | Performance | Stop preview ved live preview |
| 🔴 Høj | LAB mode: Ingen timeout på Camera-Ready | Kan hænge | Tilføj 120s timeout |
| 🔴 Høj | LAB agent: 1s poll konstant | CPU/Battery | Øg til 2-5s |
| 🟡 Medium | Dashboard: 60s poll kunne være længere | UX | Øg til 120s |
| 🟡 Medium | Heartbeat: 60min er for langt | Drift | Reduce til 15-30min |
| 🟢 Lav | SSH tunnel: 30s poll | Lav | Acceptabelt |

---

## Del 4: Optimeringsanbefalinger

### Kortvarige (Quick Wins)

#### 1. LAB Mode: Stop Preview List når Live Preview aktiv
```typescript
// LabPage.tsx:441
useEffect(() => {
  if (labActive && !livePreview) {  // ← Tilføj !livePreview
    const iv = setInterval(() => listPreviews(deviceId).then(p => { /* ... */ }), 3000)
    setPollInterval(iv)
    return () => clearInterval(iv)
  } else {
    if (pollInterval) clearInterval(pollInterval)
  }
}, [labActive, livePreview, deviceId])
```

#### 2. LAB Mode: Tilføj timeout på Camera-Ready poll
```typescript
// LabPage.tsx:527
let readyAttempts = 0
const check = setInterval(async () => {
  readyAttempts++
  if (readyAttempts > 40) {  // 120 sekunder timeout
    clearInterval(check)
    clearInterval(countdown)
    setStatusMsg('Timeout - kamera svarede ikke')
    setLabConnecting(false)
    return
  }
  // ... eksisterende logik
}, 3000)
```

#### 3. LAB Mode: Øg agent poll interval
```python
# edge/agent.py
# Ændr default fra 1s til 2s i LAB mode
config_poll_s = 2  # i stedet for 1
```

#### 4. Heartbeat: Reduce interval
```python
# edge/agent.py:737
# Ændr fra 60min til 30min
heartbeat_interval_minutes = 30
```

### Langvarige (Architectural)

#### 1. WebSocket baseret opdatering

Erstat polling med WebSocket push for:
- LAB mode events (preview ready, camera ready, params loaded)
- Backup status updates
- Import job progress
- Post-processing updates

**Fordel:**
- Mindre load
- Hurtigere response
- Bedre UX

#### 2. Eksponentiel backoff

```typescript
function createBackoffPoll(initialMs: number, maxMs: number) {
  let attempts = 0
  return async function poll(fn: () => Promise<boolean>) {
    const delay = Math.min(initialMs * Math.pow(2, attempts), maxMs)
    const success = await fn()
    if (!success) {
      attempts++
      setTimeout(() => poll(fn), delay)
    } else {
      attempts = 0
    }
  }
}
```

#### 3. Batch API kald

Kombiner flere requests i ét kald:
- `/api/lab/{id}/status` returnerer alt LAB state
- `/api/admin/devices/status` returnerer alle device states

---

## Del 5: Polling Cheat Sheet

| Fil | Linje | Interval | Formål | Stop Condition |
|-----|-------|----------|---------|----------------|
| **Frontend** |||||
| Dashboard.tsx | 242 | 60s | Dashboard stats | Unmount |
| DriftPage.tsx | 132 | 30s | Health/alerts | Unmount |
| SIEMPage.tsx | 180 | 30s | Security events | Toggle off |
| PostProcessingPage.tsx | 179 | 2s | Job status | !running |
| PostProcessingPage.tsx | 189 | 30s | Batch jobs | All done |
| BackupPage.tsx | 459 | 1.5s | Backup status | !running |
| BackupPage.tsx | 525 | 2s | Disk build | !running |
| BackupPage.tsx | 1164 | 2s | WiFi inject | !running |
| ImportPage.tsx | 69 | 2s | Import job | done |
| RetentionPage.tsx | 108 | 2s | Cleanup status | !running |
| TimelapseVideoPage.tsx | 278 | 1s | Render job | done/error |
| SshTunnelPage.tsx | 162 | 30s | Tunnel status | Unmount |
| **LAB Mode** |||||
| LabPage.tsx | 423 | 3s | LAB state check | Unmount |
| LabPage.tsx | 443 | 3s | Preview list | !labActive |
| LabPage.tsx | 490 | 4s | Live preview | !livePreview |
| LabPage.tsx | 527 | 3s | Camera-ready | cameraReady |
| LabPage.tsx | 615 | 1.5s | Take preview | Preview received |
| LabPage.tsx | 667 | 1.5s | Load params | Params received |
| LabPage.tsx | 695 | 1.5s | waitForLabResult | Result received |
| LabPage.tsx | 772 | 1.5s | WiFi scan | Scan done |
| LabPage.tsx | 803 | 1.5s | WiFi connect | Connect done |
| **Backend** |||||
| agent.py | 687 | 5min | Config poll | Stop |
| agent.py | 737 | 60min | Heartbeat | Stop |
| agent.py | 1983 | 1s | LAB commands | LAB stop |
| ssh_manager.py | 197 | 30s | Tunnel status | Stop |
| site_look_config_client.py | 209 | 5min | AI config | Stop |
| technician_ui.py | 338 | 2s | QR login | Login/15min |

---

## Del 6: Statistik

### Totalt antal polling mekanismer: **26**

| Komponent | Antal |
|-----------|-------|
| Frontend UI | 20 |
| Backend Edge | 6 |

### Interval fordeling

| Range | Antal | Procent |
|-------|-------|---------|
| < 2s | 3 | 12% |
| 1.5-2s | 10 | 38% |
| 3s | 3 | 12% |
| 30s | 5 | 19% |
| ≥ 60s | 5 | 19% |

### Poll load estimation

| Component | Estimeret HTTP calls/min |
|----------|-------------------------|
| Dashboard (60s) | 1 |
| DriftPage (30s) | 2 |
| SIEMPage (30s) | 2 |
| LAB mode (aktiv) | 20-40 |
| Post-processing (aktiv) | 30 |
| SSH Tunnels (30s) | 2 |
| **Total (worst case)** | **~100** |

---

**Dokument version:** 2.1
**Sidst opdateret:** 13. juli 2026
**Relateret:** `lab-poll-mechanisms.md`
