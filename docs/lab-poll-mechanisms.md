# LAB Mode — Headend Poll Mekanismer

**Version:** 1.0
**Dato:** 13. juli 2026
**Fil:** `timelapse-ui/src/pages/LabPage.tsx`
**Formål:** Dokumentation af alle polling mekanismer i LAB mode

---

## Oversigt

LAB mode har **9 forskellige polling mekanismer** der kører mod headend/API. Flere af disse kører samtidigt, hvilket kan belaste systemet og gøre LAB mode "langsom" til at starte op.

---

## Polling Mekanismer

### 1. checkExistingLab Poll

**Lokation:** `LabPage.tsx:384-425`
**Interval:** **3000 ms** (3 sekunder)
**Formål:** Tjekker om LAB mode allerede er aktiv ved page load/refresh

```typescript
const iv = window.setInterval(checkExistingLab, 3000)
```

**Hvordan virker det:**
- Kalder `getDevice(deviceId)` for at hente device config
- Læser `debug_mode.enabled` og `lab_camera_ready` flags
- Opdaterer UI state baseret på fundet status

**Kører når:**
- Page mountes
- Kører indtil component unmountes

**Problemer:**
- Kører konstant selv når LAB er inaktiv
- Kan reduceres når ikke i connecting state

---

### 2. Preview List Poll

**Lokation:** `LabPage.tsx:441-457`
**Interval:** **3000 ms** (3 sekunder)
**Formål:** Opdaterer preview listen når LAB er aktiv

```typescript
const iv = setInterval(() => {
  listPreviews(deviceId).then(p => {
    setPreviews(p)
    // Auto-select nyeste hvis bruger ikke har valgt manuelt
    if (p.length > 0 && !userSelectedRef.current && p[0].filename !== selectedPreviewRef.current?.filename) {
      setSelectedPreview(p[0])
    }
  })
}, 3000)
```

**Kører når:**
- `labActive === true`
- Stopper når LAB deaktiveres

**Problemer:**
- Overlapper med Live Preview Loop (se #3)
- Kan reduceres når live preview er aktiv (da den opdaterer alligevel)

---

### 3. Live Preview Loop

**Lokation:** `LabPage.tsx:459-496`
**Interval:** **4000 ms** (4 sekunder) + 750 ms retry loop
**Formål:** Automatisk preview generation når "Preview loop" er aktiveret

```typescript
async function requestFrame() {
  await requestPreview(deviceId)
  for (let attempt = 0; attempt < 8 && !cancelled; attempt++) {
    await new Promise(resolve => window.setTimeout(resolve, 750))
    const p = await listPreviews(deviceId)
    // ... opdater preview hvis ny
  }
}
const iv = window.setInterval(requestFrame, 4000)
```

**Kører når:**
- `livePreview === true` && `labActive === true` && `!labConnecting`

**Problemer:**
- Kaster op til 8 polls à 750 ms efter hver request (6 sekunder total)
- Kan overlappe med Preview List Poll (#2)
- Total op til 10 sekunder per preview

---

### 4. Camera-Ready Poll (ved LAB start)

**Lokation:** `LabPage.tsx:527-544`
**Interval:** **3000 ms** (3 sekunder)
**Formål:** Venter på `lab_camera_ready` signal fra edge når LAB startes

```typescript
const check = setInterval(async () => {
  const r = await authFetch(`${apiUrl}/api/admin/devices/${pathSegment(deviceId)}`)
  const data = await r.json()
  const { cameraReady } = readLabState(data)
  if (cameraReady) {
    // LAB er klar!
  }
}, 3000)
```

**Kører når:**
- LAB aktiveres (`toggleLab(true)`)
- Stopper når `cameraReady === true`

**Begrænsning:**
- Ingen timeout - kan køre for evigt hvis edge aldrig sender ready signal
- Bør have en max timeout (f.eks. 120 sekunder)

---

### 5. Take Preview Poll

**Lokation:** `LabPage.tsx:615-633`
**Interval:** **1500 ms** (1.5 sekunder)
**Formål:** Venter på nyt preview efter manuel preview anmodning

```typescript
const check = setInterval(async () => {
  attempts++
  const p = await listPreviews(deviceId)
  if (p.length > 0 && p[0].filename !== prevFilename) {
    // Preview modtaget!
    clearInterval(check)
  }
  if (attempts > 20) {
    clearInterval(check)
    // Timeout
  }
}, 1500)
```

**Kører når:**
- Bruger klikker "Preview" knappen
- Stopper når preview modtages eller efter 20 attempts (30 sekunder)

---

### 6. Load Params Poll

**Lokation:** `LabPage.tsx:666-686`
**Interval:** **1500 ms** (1.5 sekunder)
**Formål:** Venter på `camera_params` fra config efter parameter anmodning

```typescript
const poll = setInterval(async () => {
  attempts++
  const cfg = await loadAdminDeviceConfig(deviceId)
  const camParams = cfg?.camera_params || []
  if (camParams.length > 0) {
    clearInterval(poll)
    setParams(camParams)
  }
  if (attempts > 20) {
    clearInterval(poll)
    // Timeout
  }
}, 1500)
```

**Kører når:**
- Bruger klikker "Hent parametre" knappen
- Stopper når params modtages eller efter 20 attempts (30 sekunder)

---

### 7. waitForLabResult (Generisk)

**Lokation:** `LabPage.tsx:693-711`
**Interval:** **1500 ms** (1.5 sekunder)
**Formål:** Generisk vent på enhver LAB operation resultat

```typescript
async function waitForLabResult(expected: string[]) {
  for (let attempt = 0; attempt < 30; attempt++) {
    await new Promise(resolve => window.setTimeout(resolve, 1500))
    const cfg = await loadAdminDeviceConfig(deviceId)
    if (cfg?.lab_result && expected.includes(cfg.lab_result.type)) {
      return cfg.lab_result
    }
  }
  throw new Error('Timeout')
}
```

**Kører når:**
- Fuld capture
- Focus drive
- Autofocus test
- Focus slice test
- Edge AI focus test

**Begrænsning:**
- 30 attempts × 1500 ms = **45 sekunder max ventetid**

---

### 8. WiFi Scan Poll

**Lokation:** `LabPage.tsx:771-784`
**Interval:** **1500 ms** (1.5 sekunder)
**Formål:** Venter på WiFi scan resultat

```typescript
const poll = setInterval(async () => {
  attempts++
  const cfg = await loadAdminDeviceConfig(deviceId)
  const wd = cfg?.wifi_data
  if (wd?.type === 'scan') {
    clearInterval(poll)
    setWifiData(wd)
  }
  if (attempts > 15) {
    clearInterval(poll)
    // Timeout
  }
}, 1500)
```

**Kører når:**
- Bruger klikker "Scan netværk" knappen
- Stopper efter 15 attempts (22.5 sekunder)

---

### 9. WiFi Connect Poll

**Lokation:** `LabPage.tsx:803-815`
**Interval:** **1500 ms** (1.5 sekunder)
**Formål:** Venter på WiFi connect resultat

```typescript
const poll = setInterval(async () => {
  attempts++
  const cfg = await loadAdminDeviceConfig(deviceId)
  const wd = cfg?.wifi_data
  if (wd?.type === 'connect') {
    clearInterval(poll)
    setWifiData((prev: any) => ({ ...prev, current: wd.current }))
  }
  if (attempts > 20) {
    clearInterval(poll)
    // Timeout
  }
}, 1500)
```

**Kører når:**
- Bruger klikker "Tilslut" på et WiFi netværk
- Stopper efter 20 attempts (30 sekunder)

---

## Sammenligningstabel

| # | Mekanisme | Interval | Max Tid | Kører Når | Overlap? |
|---|-----------|----------|---------|-----------|----------|
| 1 | checkExistingLab | 3s | ∞ | Altid (page mount) | ❌ |
| 2 | Preview List | 3s | ∞ | labActive | ✅ #3 |
| 3 | Live Preview Loop | 4s + 750ms×8 | ~10s | livePreview + labActive | ✅ #2 |
| 4 | Camera-Ready | 3s | ∞* | LAB start | ❌ |
| 5 | Take Preview | 1.5s | 30s | Manual preview | ❌ |
| 6 | Load Params | 1.5s | 30s | Manual params | ❌ |
| 7 | waitForLabResult | 1.5s | 45s | Diverse actions | ❌ |
| 8 | WiFi Scan | 1.5s | 22.5s | Manual WiFi scan | ❌ |
| 9 | WiFi Connect | 1.5s | 30s | Manual WiFi connect | ❌ |

*Ingen timeout - potentielt problem

---

## Problemer & Optimeringer

### Problem 1: For mange samtidige polls

Når LAB er aktiv og "Preview loop" er slået til:
- Preview List poll (#2) kører hver 3s
- Live Preview Loop (#3) kører hver 4s + 8 polls à 750ms

**Løsning:** Stop Preview List poll når Live Preview er aktiv.

### Problem 2: checkExistingLab kører altid

Poll #1 kører selv når LAB er inaktiv, bare for at tjekke state.

**Løsning:** Stop poll når vi har fastslået at LAB er inaktiv.

### Problem 3: Ingen timeout på Camera-Ready poll

Poll #4 har ingen max timeout, kan køre i det uendelige.

**Løsning:** Tilføj timeout på f.eks. 120 sekunder.

### Problem 4: Live Preview retry loop ineffektiv

Live Preview (#3) kaster 8 polls à 750ms = 6 sekunder efter hver request, selv hvis billedet kommer hurtigt.

**Løsning:** Stop loop hurtigere når nyt billede modtages.

---

## Anbefalinger

### Kortvarige rettelser

1. **Stop Preview List poll når Live Preview er aktiv**
   ```typescript
   if (labActive && !livePreview) {
     // kun kør preview list poll
   }
   ```

2. **Tilføj timeout på Camera-Ready poll**
   ```typescript
   let readyAttempts = 0
   const check = setInterval(async () => {
     readyAttempts++
     if (readyAttempts > 40) { // 120 sekunder
       clearInterval(check)
       // Timeout fejl
     }
     // ... eksisterende logik
   }, 3000)
   ```

3. **Stop checkExistingLab når inaktiv**
   ```typescript
   if (!debugEnabled && !cameraReady) {
     // LAB er inaktiv - stop polling
     clearInterval(iv)
   }
   ```

### Langvarige optimeringer

1. **WebSocket baseret opdatering**
   - Erstat polling med WebSocket push
   - Edge pusher events: `preview_ready`, `camera_ready`, `params_loaded`
   - Mindre load, hurtigere response

2. **Optimeret retry strategi**
   - Eksponentiel backoff i stedet for fast interval
   - Tidlig stop når succes opnås

3. **Batch API kald**
   - Kombiner flere requests i ét kald
   - `/api/lab/{id}/status` returnerer alt state på én gang

---

## Kode Referencer

| Fil | Linjer | Beskrivelse |
|-----|--------|-------------|
| `LabPage.tsx` | 384-425 | checkExistingLab poll |
| `LabPage.tsx` | 441-457 | Preview List poll |
| `LabPage.tsx` | 459-496 | Live Preview Loop |
| `LabPage.tsx` | 527-544 | Camera-Ready poll |
| `LabPage.tsx` | 615-633 | Take Preview poll |
| `LabPage.tsx` | 666-686 | Load Params poll |
| `LabPage.tsx` | 693-711 | waitForLabResult |
| `LabPage.tsx` | 771-784 | WiFi Scan poll |
| `LabPage.tsx` | 803-815 | WiFi Connect poll |

---

**Dokument version:** 1.0
**Sidst opdateret:** 13. juli 2026
