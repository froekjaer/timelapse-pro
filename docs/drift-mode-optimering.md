# Drift Mode Optimering — Data og Strøm

> ⚠️ **Historisk design-dokument (2026-08-20):** Poll-arkitekturen beskrevet her (separate `heartbeat_interval_minutes` / `config_poll_interval_minutes`-loops) er erstattet af én konsolideret sync-poll (`sync_poll_interval_minutes`, `POST /api/edge/sync/{device_id}`) pr. PR #76, 2026-08-19. For aktuel adfærd se `docs/admin-guide.md`. Dokumentet beholdes som designhistorik.

**Version:** 1.0
**Dato:** 13. juli 2026
**Fokus:** Normal drift mode (ikke LAB mode)
**Mål:** Reducere dataforbrug og batteri drain i daglig drift

---

## Drift Mode Polling Oversigt

I normal drift (ikke LAB mode) kører følgende polling mekanismer:

| Poll Type | Interval | Fil | Formål |
|-----------|----------|-----|---------|
| Config poll | 5 minutter | agent.py:687 | Hent config ændringer |
| Heartbeat | 60 minutter | agent.py:737 | Rapporter status |
| SIEM forward | 5 minutter | agent.py | Send security events |
| Wake-up check | 60 sekunder | agent.py:751 | **Skjult wake-up loop!** |
| SSH tunnel | 30 sekunder | ssh_manager.py | Kun når aktiv |

---

## 🔴 Skjult Problem: 60-Sekunders Wake-Up Loop

**Fil:** `edge/agent.py:751`

```python
# Calculate sleep until next event
sleep_s = self._seconds_until_next_event(now, mode)

if sleep_s > 60:
    log.info("Sleeping %ds until next capture…", sleep_s)
self._stop_event.wait(min(sleep_s, 60))   # wake at least every 60s to check signals
```

### Hvad sker der?

Agenten beregner hvor længe der er til næste capture (f.eks. 3600 sekunder), men vågner alligevel **hvert 60 sekund** for at:

1. Tjekke `_stop_event` (SIGTERM/SIGINT for graceful shutdown)
2. Tjekke `_capture_suppressed_by_headend_signal()` (capture avoid windows)
3. Tjekke om heartbeat skal sendes

### Problem

Når næste capture er > 60 sekunder væk:
- Agenten vågner unødvendigt hver 60s
- CPU bruges til at tjekke conditions
- Batteri drænes unødvendigt
- **Ingen data sendes (kun internt tjek)**

### Eksempel

```
Capture interval: 60 minutter
Wake-ups per time: 60 (én gang hvert minut!)
CPU wake-ups: 1440 gange per dag
Batteri impact: Lav-mid (CPU wake-ups konstant)
```

---

## 🟡 Andre Drift Mode Polls

### Config Poll (5 minutter)

**Fil:** `edge/agent.py:687`
```python
config_interval = timedelta(minutes=int(
    self._cfg.get("diagnostics", {}).get("config_poll_interval_minutes", 5)
))
```

**Data forbrug:** ~14 KB/time → **336 KB/dag**

**Problemer:**
- 🟢 Acceptabelt - config ændringer er sjældne
- 🟡 Kunne øges til 10-15 minutter for mere data besparelse

---

### Heartbeat (60 minutter)

**Fil:** `edge/agent.py:737`
```python
heartbeat_interval = timedelta(minutes=int(
    self._cfg.get("diagnostics", {}).get("heartbeat_interval_minutes", 60)
))
```

**Data forbrug:** ~2 KB/time → **48 KB/dag**

**Problemer:**
- 🟡 60 minutter er lang tid for drifts overvågning
- 🟡 Kunne reduceres til 15-30 minutter for bedre visibility

---

### SIEM Forward (5 minutter)

**Fil:** `edge/agent.py` (SIEM module)
```python
interval_s = int(cfg.get("forward_interval_s", 300))
```

**Data forbrug:** ~24 KB/time → **576 KB/dag**

**Problemer:**
- 🟢 Acceptabelt - security events er vigtige
- 🟡 Kunne øges til 10 minutter for mindre data

---

## 💡 Optimerings Anbefalinger

### 1. Fjern 60-sekunders wake-up loop (Smart Wake)

**Ændring:** `edge/agent.py:751`

```python
# Før
sleep_s = self._seconds_until_next_event(now, mode)
if sleep_s > 60:
    log.info("Sleeping %ds until next capture…", sleep_s)
self._stop_event.wait(min(sleep_s, 60))  # wakes every 60s

# Efter
sleep_s = self._seconds_until_next_event(now, mode)
if sleep_s > 60:
    log.info("Sleeping %ds until next capture…", sleep_s)
    # Wake 60s before next event, not every 60s
    smart_sleep = min(sleep_s - 60, sleep_s) if sleep_s > 120 else sleep_s
    self._stop_event.wait(max(60, smart_sleep))
else:
    self._stop_event.wait(sleep_s)
```

**Eller endnu bedre - brug et configured max sleep:**

```python
max_idle_sleep_s = int(self._cfg.get("system", {}).get("max_idle_sleep_s", 300))  # 5 min default
sleep_s = self._seconds_until_next_event(now, mode)
if sleep_s > max_idle_sleep_s:
    log.info("Sleeping %ds until next capture… (waking every %ds)", sleep_s, max_idle_sleep_s)
    self._stop_event.wait(max_idle_sleep_s)
else:
    self._stop_event.wait(sleep_s)
```

**Effekt:**
- Wake-ups reduceret fra 1440/dag til **~288/dag** (80% reduktion)
- Batteri besparelse: ~5-10%
- Ingen funktionel ændring (capture timing unchanged)

---

### 2. Konfigurerbare max idle sleep

**Tilføj til config:**

```yaml
# edge config
system:
  max_idle_sleep_s: 300  # 5 minutter (default)
```

**Fordel:**
- Kan justeres per installation
- Strømbesparende deployment kan bruge 600s (10 min)
- Hurtig response deployment kan bruge 60s

---

### 3. Øg config poll interval

**Ændring:** Config file eller default

```yaml
# edge config
diagnostics:
  config_poll_interval_minutes: 10  # 5 → 10 minutter
```

**Effekt:**
- Config polls: 288/dag → **144/dag** (50% reduktion)
- Data: 336 KB/dag → **168 KB/dag**

**Risk:**
- Lav - config ændringer er sjældne
- 10 minutters delay er acceptabelt

---

### 4. Juster heartbeat interval

**Ændring:** Config file

```yaml
# edge config
diagnostics:
  heartbeat_interval_minutes: 30  # 60 → 30 minutter
```

**Effekt:**
- Hyppigere drifts overvågning
- Data: 48 KB/dag → **96 KB/dag** (doble, men stadig lav)

**Alternativ:** Hold på 60 minutter for min data, men brug SIEM events til akut alert.

---

### 5. SIEM forward interval

**Ændring:** Config file

```yaml
# edge config
siem:
  forward_interval_s: 600  # 300 → 600 sekunder (10 minutter)
```

**Effekt:**
- SIEM forwards: 288/dag → **144/dag** (50% reduktion)
- Data: 576 KB/dag → **288 KB/dag**

**Risk:**
- Lav - security events er fortsat logget lokalt
- Lille forsinkelse på alert delivery

---

## Samlet Effekt af Optimeringer

### Før (Current State)

| Metric | Værdi |
|--------|-------|
| Wake-ups per dag | 1440 (hvert 60s) |
| Config polls | 288 |
| SIEM forwards | 288 |
| Total HTTP requests | ~600 |
| Data per dag | ~1 MB |
| CPU wake-ups | 1440 |

### Efter (Med alle optimeringer)

| Metric | Værdi | Reduktion |
|--------|-------|-----------|
| Wake-ups per dag | 288 (hvert 5min) | **80%** |
| Config polls | 144 | **50%** |
| SIEM forwards | 144 | **50%** |
| Total HTTP requests | ~300 | **50%** |
| Data per dag | ~500 KB | **50%** |
| CPU wake-ups | 288 | **80%** |

### Batteri Estimat

| Scenario | Batteri drain |
|----------|---------------|
| Før (current) | 5-10% per dag |
| Efter (optimeret) | **2-5% per dag** |

---

## Implementerings Plan

### Fase 1: Smart Wake-Up (Quick Win)

**Fil:** `edge/agent.py:751`

```python
# Tilføj til __init__
self._max_idle_sleep_s = int(self._cfg.get("system", {}).get("max_idle_sleep_s", 300))

# Ændr i _tick
sleep_s = self._seconds_until_next_event(now, mode)
if sleep_s > 60:
    log.info("Sleeping %ds until next capture…", sleep_s)
    self._stop_event.wait(min(sleep_s, self._max_idle_sleep_s))
else:
    self._stop_event.wait(sleep_s)
```

**Risk:** Lav
**Effekt:** 80% færre wake-ups

---

### Fase 2: Config Intervals

**Tilføj til edge config:**

```yaml
diagnostics:
  config_poll_interval_minutes: 10

siem:
  forward_interval_s: 600
```

**Risk:** Lav
**Effekt:** 50% færre HTTP requests

---

### Fase 3: Heartbeat Justering

Valgfri - afhængig af drifts behov:

```yaml
diagnostics:
  heartbeat_interval_minutes: 30  # for hyppigere overvågning
```

Eller hold på 60 minutter for minimal data.

---

## Monitoring

### Tilføj wake-up statistik

```python
class WakeUpTracker:
    def __init__(self):
        self.wake_count = 0
        self.last_wake_time = None

    def record_wake(self):
        self.wake_count += 1
        self.last_wake_time = datetime.now(timezone.utc)

    def get_daily_wakeups(self):
        # Simple estimation based on runtime
        return self.wake_count
```

**Vis i UI:** Dashboard → Device → System Stats

---

## Risk Assessment

| Ændring | Risk | Effekt | Anbefaling |
|---------|-------|--------|-------------|
| Smart wake-up (60s→300s) | Lav | 80% færre wake-ups | ✅ Implementer |
| Config poll (5m→10m) | Lav | 50% færre requests | ✅ Implementer |
| SIEM forward (5m→10m) | Lav | 50% færre forwards | ✅ Implementer |
| Heartbeat (60m→30m) | Lav | 2x data, bedre visibility | ⚠️ Valgfrit |

---

## Konklusion

**Største problem:** 60-sekunders wake-up loop der køre 1440 gange per dag unødvendigt.

**Største gevinst:** Smart wake-up (60s → 300s) = 80% reduktion i CPU wake-ups og batteri drain.

**Samlet effekt:** Med alle optimeringer kan data forbrug halveres og batteri drain reduceres med 50-75%.

---

**Dokument version:** 1.0
**Sidst opdateret:** 13. juli 2026
**Relateret:** `edge-polling-data-usage.md`, `system-wide-poll-mechanisms.md`
