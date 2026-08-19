# Edge Polling — Data og Strøm Forbrug

**Version:** 1.0
**Dato:** 13. juli 2026
**Fokus:** Mobildata og batteri forbrug på Edge enheder
**Kritisk:** Edge enheder kører på 4G/5G modem og batteri

---

## Problemstilling

Edge enheder (OrangePi, Jetson, etc.) kører på:
- **Mobildata** (4G/5G via USB modem)
- **Batteri** (ved strømsvigt)
- **Solceller** (ofte limited output)

Hver HTTP request koster:
- **Data:** ~500-2000 bytes per request/response
- **Strøm:** Modem active + CPU processing
- **Latency:** 100-500ms per request

---

## Edge Polling Oversigt

### 1. LAB Mode Poll (Kritisk!)

**Fil:** `edge/agent.py:1983-2245`
**Interval:** **1 sekund** (default `config_poll_s = 1`)
**Formål:** Poller for LAB kommandoer fra headend

```python
poll_s = int(debug_cfg.get("config_poll_s", 1))
```

**Data forbrug:**
- Requests per time: **3600**
- Data per request: ~800 bytes (config JSON)
- **Data per time: ~2.9 MB**
- **Data per dag (8t LAB): ~23 MB**

**Strøm forbrug:**
- Modem active 24/7 i LAB mode
- CPU processing hver 1. sekund
- **Batteri drain: Høj**

**Problemer:**
- 🔴 Ekstremt højt dataforbrug
- 🔴 Batteri drænes hurtigt
- 🔴 Unødvendig hyppig for de fleste kommandoer

---

### 2. Normal Mode Config Poll (⚠️ konsolideret 2026-08-19 — se pkt. 5 nedenfor)

**Fil:** `edge/agent.py:687`
**Interval:** **5 minutter** (default `config_poll_interval_minutes = 5`)
**Formål:** Henter config ændringer fra headend

```python
config_interval = timedelta(minutes=int(
    self._cfg.get("diagnostics", {}).get("config_poll_interval_minutes", 5)
))
```

**Data forbrug:**
- Requests per time: **12**
- Data per request: ~1200 bytes
- **Data per time: ~14 KB**
- **Data per dag: ~336 KB**

**Strøm forbrug:**
- Lav - modem sleeper mellem requests
- **Batteri drain: Lav**

**Problemer:**
- 🟢 Acceptabelt ❌

---

### 3. SIEM Event Forward (⚠️ konsolideret 2026-08-19 — se pkt. 5 nedenfor)

**Fil:** `edge/agent.py` (SIEM module)
**Interval:** **5 minutter** (default `forward_interval_s = 300`)
**Formål:** Sender security events til headend

```python
interval_s = int(cfg.get("forward_interval_s", 300))
```

**Data forbrug:**
- Requests per time: **12**
- Data per request: ~2000 bytes (events batch)
- **Data per time: ~24 KB**
- **Data per dag: ~576 KB**

**Problemer:**
- 🟢 Acceptabelt ❌

---

### 4. SSH Tunnel Manager

**Fil:** `edge/tunnel/ssh_manager.py:197-258`
**Interval:** **30 sekunder** (`TUNNEL_CHECK_INTERVAL_S = 30`)
**Formål:** Overvåger SSH tunnel status

**Data forbrug:**
- Requests per time: **120**
- Data per request: ~200 bytes (status check)
- **Data per time: ~24 KB**
- **Data per dag: ~576 KB**

**Problemer:**
- 🟡 Kun når SSH tunnel er aktiv
- 🟡 Kan reduceres til 60-120 sekunder

---

### 5. Site Look AI Config Poll

**Fil:** `edge/ai/site_look_config_client.py:209-241`
**Interval:** **5 minutter** (default `poll_interval_seconds = 300`)
**Formål:** Henter AI config ændringer

**Data for brug:**
- Requests per time: **12**
- Data per request: ~1500 bytes
- **Data per time: ~18 KB**
- **Data per dag: ~432 KB**

**Problemer:**
- 🟢 Acceptabelt ❌

---

## Data Forbrug Sammenligning

| Poll Type | Interval | Req/time | KB/time | KB/dag | Prioritet |
|-----------|----------|----------|---------|--------|-----------|
| **LAB mode** | 1s | 3600 | 2880 | 69120 | 🔴 Kritisk |
| SSH Tunnel | 30s | 120 | 24 | 576 | 🟡 Medium |
| SIEM Forward | 5m | 12 | 24 | 576 | 🟢 Lav |
| Config Poll | 5m | 12 | 14 | 336 | 🟢 Lav |
| AI Config | 5m | 12 | 18 | 432 | 🟢 Lav |
| **TOTAL (normal)** | - | 168 | 80 | 1920 | - |
| **TOTAL (LAB)** | - | 3768 | 2960 | 71040 | - |

**Konklusion:** LAB mode bruger **37x mere data** end normal mode!

---

## Batteri Forbrug Analyse

### LAB Mode vs Normal Mode

| Mode | Modem Active | CPU Freq | Battery Drain (estimeret) |
|------|--------------|----------|---------------------------|
| Normal | 5% | Lav | ~5-10% per dag |
| LAB (1s poll) | 95%+ | Høj | ~50-80% per dag |
| LAB (5s poll) | 60% | Medium | ~20-30% per dag |
| LAB (10s poll) | 40% | Lav-Medium | ~10-15% per dag |

**Bemærk:** Disse er estimater afhængig af hardware, batteri kapacitet, og signal styrke.

---

## Optimerings Anbefalinger

### 🔴 Kritiske Optimeringer (LAB Mode)

#### 1. Øg LAB poll interval fra 1s til 5s

**Ændring:** `edge/agent.py:1985`

```python
# Før
poll_s = int(debug_cfg.get("config_poll_s", 1))

# Efter
poll_s = int(debug_cfg.get("config_poll_s", 5))  # 5 sekunder default
```

**Effekt:**
- Data reduceret fra 69 MB/dag til **14 MB/dag** (80% reduktion)
- Batteri drain reduceret fra 50-80%/dag til **20-30%/dag**
- Stadig hurtig respons til preview/kommandoer (max 5s ventetid)

---

#### 2. Implementer "Smart Poll" - adaptive interval

**Idé:** Poll hyppigere når aktiv, langsommere når idle

```python
# edge/agent.py
class SmartLabPoll:
    def __init__(self):
        self.last_activity = time.time()
        self.active_interval = 2   # 2s når aktiv
        self.idle_interval = 10    # 10s når idle
        self.idle_threshold = 30   # 30s inaktiv før idle mode

    def get_interval(self):
        since_active = time.time() - self.last_activity
        if since_active > self.idle_threshold:
            return self.idle_interval
        return self.active_interval

    def record_activity(self):
        self.last_activity = time.time()
```

**Effekt:**
- **Data:** ~5-10 MB/dag (afhængig af aktivitet)
- **Batteri:** ~10-20%/dag
- **UX:** Hurtig respons når bruger aktiv, sparker når idle

---

#### 3. WebSocket eller Long-Polling i LAB mode

**Idé:** Erstat kort polling med long-polling (30s timeout)

```python
def lab_tick_long_poll():
    """Long-poll for LAB commands - server svarer når kommando klar"""
    response = self._api.long_poll(
        endpoint="/lab/{device_id}/wait-command",
        timeout=30
    )
    # Process command immediately
```

**Effekt:**
- **Data:** ~1-2 MB/dag (kun ved kommandoer)
- **Batteri:** ~5-10%/dag
- **UX:** Øjeblikkelig respons når kommando sendes
- **Kræver:** Backend ændringer

---

### 🟡 Medium Optimeringer

#### 4. SSH Tunnel Check Interval

**Ændring:** `edge/tunnel/ssh_manager.py`

```python
# Før
TUNNEL_CHECK_INTERVAL_S = 30

# Efter
TUNNEL_CHECK_INTERVAL_S = 60  # eller 120
```

**Effekt:**
- SSH tunnel data: 576 KB/dag → **288 KB/dag**
- Minimal risiko - tunnel genetableres automatisk

---

### 🟢 Andre Optimeringer

#### 5. Batch Config Polls

**Idé:** Kombiner config, AI config, og SIEM forward i én request

```python
def unified_config_poll():
    """Henter alt config i én request"""
    response = self._api.get("/edge/unified-config")
    return {
        "config": response.config,
        "ai_config": response.ai_config,
        "siem_pending": response.siem_pending
    }
```

**Effekt:**
- Færre HTTP requests
- Mindst modem wake-ups
- Data besparelse: ~20-30%

> ✅ **Implementeret 2026-08-19**, langt foran den oprindelige "Fase 3:
> Architectural (Måneder)"-tidsplan nedenfor. `POST /api/edge/sync/{device_id}`
> ([headend/edge_sync.py](../headend/edge_sync.py)) kombinerer config-pull,
> heartbeat/diagnostik, SIEM-forward og updates-policy-check i ét
> request/response, gated af ét interval (`diagnostics.sync_poll_interval_minutes`,
> default 5 min) i stedet for tre uafhængige timere. Fundet og bygget som del
> af opfølgning på en produktionshændelse (heartbeat bar aldrig `app_version`,
> så Headends app-update-auto-detektion aldrig kunne udløses) — se
> `Dokumentation/HANDOVER_LOG.md` 2026-08-19. Gamle enkelt-endpoints er bevaret
> uændrede som rollback-vej.

---

## Implementerings Plan

### Fase 1: Quick Wins (Dage)

1. **Ændr LAB poll default til 5s**
   - Fil: `edge/agent.py:1985`
   - Risk: Lav
   - Effekt: 80% data reduktion i LAB mode

2. **Ændr SSH tunnel check til 60s**
   - Fil: `edge/tunnel/ssh_manager.py`
   - Risk: Lav
   - Effekt: 50% data reduktion for SSH tunnels

### Fase 2: Smart Poll (Uger)

3. **Implementer smart poll**
   - Fil: `edge/agent.py`
   - Risk: Medium
   - Effekt: 85-90% data reduktion

### Fase 3: Architectural (Måneder)

4. **WebSocket/Long-poll**
   - Backend + Frontend + Edge ændringer
   - Risk: Høj
   - Effekt: 95%+ data reduktion

---

## Konfiguration Eksempler

### Normal Mode (Produktion)

```yaml
# edge config — opdateret 2026-08-19: config_poll_interval_minutes og
# siem.forward_interval_s er erstattet af ét samlet sync-interval (se pkt. 5
# ovenfor). Stadig konfigurerbare (fx per-device override), men styrer nu
# den samme konsoliderede /api/edge/sync-poll, ikke separate requests.
diagnostics:
  sync_poll_interval_minutes: 5  # 5 minutter — config+heartbeat+SIEM+updates i ét kald

ssh:
  tunnel_check_interval_s: 60  # 1 minut
```

**Estimeret dataforbrug:** ~1-2 MB/dag

### LAB Mode (Produktion - optimeret)

```yaml
# edge config - LAB mode
debug_mode:
  enabled: true
  config_poll_s: 5  # 5 sekunder (ikke 1!)

# Smart poll (fase 2)
lab_smart_poll:
  active_interval_s: 2
  idle_interval_s: 10
  idle_threshold_s: 30
```

**Estimeret dataforbrug:** ~10-15 MB/dag (vs 69 MB med 1s poll)

---

## Monitoring

### Overvåg dataforbrug på edge:

```python
# edge/agent.py
class DataUsageTracker:
    def __init__(self):
        self.bytes_sent = 0
        self.bytes_recv = 0
        self.request_count = 0

    def log_request(self, sent, recv):
        self.bytes_sent += sent
        self.bytes_recv += recv
        self.request_count += 1

    def get_daily_usage(self):
        return {
            "requests": self.request_count,
            "mb_sent": self.bytes_sent / 1024 / 1024,
            "mb_recv": self.bytes_recv / 1024 / 1024,
            "total_mb": (self.bytes_sent + self.bytes_recv) / 1024 / 1024
        }
```

**Vis i UI:** Dashboard → Device → Data Usage

---

## Risk Assessment

| Ændring | Risk | Data Besparelse | Implementering |
|---------|-------|-----------------|----------------|
| LAB poll 1s→5s | Lav | 80% | 1 linje ændring |
| LAB poll 1s→10s | Medium | 90% | 1 linje ændring |
| Smart poll | Medium | 85-90% | ~50 linjer |
| WebSocket/Long-poll | Høj | 95%+ | Måneder |
| SSH tunnel 30s→60s | Lav | 50% | 1 linje ændring |

---

## Anbefaling

**Start med fase 1 (Quick Wins):**
1. Ændr LAB poll default fra 1s til 5s → **80% data reduktion**
2. Ændr SSH tunnel check fra 30s til 60s → **50% data reduktion**

**Effekt:** LAB mode dataforbrug reduceret fra **69 MB/dag** til **~14 MB/dag**

---

**Dokument version:** 1.0
**Sidst opdateret:** 13. juli 2026
**Relateret:** `system-wide-poll-mechanisms.md`
