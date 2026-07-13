# LAB Mode Test Guide

**Dato:** 2026-07-13
**Formål:** Systematisk test af alle LAB mode features efter 503 error fix

## Forberedelse

1. **Sørg for at edge er tilgængelig:**
   ```bash
   ssh -p 2201 root@edge
   systemctl status timelapse-edge
   ```

2. **Genstart edge med nye ændringer:**
   ```bash
   systemctl restart timelapse-edge
   journalctl -u timelapse-edge -f  # Følg logs
   ```

3. **Åbn LAB mode i UI:**
   - Naviger til: `/devices/{device_id}/lab`
   - Vent på at kamera forbinder

---

## Test 1: Live Video (F-013C)

| Test | Forventet resultat | Status |
|------|-------------------|--------|
| **1.1** Live video vises automatisk når LAB mode starter | MJPEG stream vises i UI | ⬜ |
| **1.2** Klik på video → fullscreen | Fuldscreen åbnes, klik igen → luk | ⬜ |
| **1.3** Frame rate er ~5 FPS (ikke 10) | Jævn video, ikke for hurtig | ⬜ |
| **1.4** Ingen 503 errors i edge log | Maksimalt få 503 (headend busy) | ⬜ |
| **1.5** Video stopper når LAB mode deaktiveres | Sort skærm/frame stopper | ⬜ |

**Kommandoer til verification:**
```bash
# Tjek frame push logs
ssh -p 2201 root@edge "grep 'LIVE VIDEO' /var/log/timelapse-edge.log | tail -20"

# Tjek 503 errors
ssh -p 2201 root@edge "grep '503' /var/log/timelapse-edge.log | wc -l"
```

---

## Test 2: Camera Operations

| Test | Handling | Forventet resultat | Status |
|------|----------|-------------------|--------|
| **2.1** | Klik "Indlæs parametre" | Parametre indlæses i UI | ⬜ |
| **2.2** | Tjek logs for get_params | "LAB — sent XX params" | ⬜ |
| **2.3** | Ændr en parameter (fx shutterspeed) | Parameter sættes på kamera | ⬜ |
| **2.4** | Klik "Preview capture" | Preview billede vises | ⬜ |
| **2.5** | Klik "Full capture" | Fuldt capture uploades | ⬜ |
| **2.6** | Tjek at frame push genstarter | Video fortsætter efter operation | ⬜ |
| **2.7** | Klik "Autofocus" | Kamera fokusere | ⬜ |
| **2.8** | Klik "Focus Drive" (-5 til +5) | Fokus flytter | ⬜ |

**Kommandoer til verification:**
```bash
# Følg LAB commands i logs
ssh -p 2201 root@edge "grep 'LAB —' /var/log/timelapse-edge.log | tail -20"

# Tjek frame push status
ssh -p 2201 root@edge "grep 'Frame push' /var/log/timelapse-edge.log | tail -10"
```

---

## Test 3: Health Check

| Test | Handling | Forventet resultat | Status |
|------|----------|-------------------|--------|
| **3.1** | Lad LAB mode køre 5 minutter | Ingen frame push crashes | ⬜ |
| **3.2** | Tjek health check logs | "Health check: frame_push OK" | ⬜ |
| **3.3** | Hvis frame push crasher | "Health check: frame_push stopped" | ⬜ |
| **3.4** | Efter crash | Frame push genstarter automatisk | ⬜ |

**Kommandoer til verification:**
```bash
# Tjek health check
ssh -p 2201 root@edge "grep 'Health check' /var/log/timelapse-edge.log"
```

---

## Test 4: Relay Toggle

| Test | Handling | Forventet resultat | Status |
|------|----------|-------------------|--------|
| **4.1** | Klik "Camera OFF" | Kamera slukker (relay klik) | ⬜ |
| **4.2** | Vent 10 sekunder | Kamera er offline | ⬜ |
| **4.3** | Klik "Camera ON" | Kamera tænder (relay klik) | ⬜ |
| **4.4** | Vent 10 sekunder | Kamera forbinder igen | ⬜ |
| **4.5** | Video genstarter | Live video kommer igen | ⬜ |

---

## Test 5: WiFi Operations

| Test | Handling | Forventet resultat | Status |
|------|----------|-------------------|--------|
| **5.1** | Klik "WiFi Scan" | Liste af netværk vises | ⬜ |
| **5.2** | Tjek logs | "LAB — WiFi scan: X netværk" | ⬜ |
| **5.3** | Forbind til kendt netværk | "WiFi connect: OK" | ⬜ |
| **5.4** | Forget et netværk | "WiFi forget: OK" | ⬜ |

---

## Test 6: Config Version Tracking

| Test | Handling | Forventet resultat | Status |
|------|----------|-------------------|--------|
| **6.1** | Ændr en global config i headend | Edge logger "Config version ændret" | ⬜ |
| **6.2** | Tjek logs | "Config version ændret via API" | ⬜ |
| **6.3** | Edge henter ny config | "Henter ny config" | ⬜ |

---

## Resultater

**Dato:** _______________
**Tester:** _______________
**Device:** TL-C87FF9587CA0

| Test kategori | Pass | Fail | Kommentarer |
|---------------|------|------|-------------|
| 1. Live Video | ⬜ | ⬜ | |
| 2. Camera Ops | ⬜ | ⬜ | |
| 3. Health Check | ⬜ | ⬜ | |
| 4. Relay Toggle | ⬜ | ⬜ | |
| 5. WiFi Ops | ⬜ | ⬜ | |
| 6. Config Track | ⬜ | ⬜ | |

**Total:** __ / 6 bestået

---

## Fejlfinding

### Ingen video vises
```bash
# Tjek om frame push kører
ssh -p 2201 root@edge "ps aux | grep frame_push"

# Tjek om gphoto2 kan tilgå kamera
ssh -p 2201 root@edge "gphoto2 --auto-detect"
```

### 503 errors
```bash
# Tjek headend status
curl http://localhost:8000/api/health

# Tjek headend logs
tail -100 ~/Library/Logs/timelapse-headend.log | grep 503
```

### Camera operations virker ikke
```bash
# Tjek om frame push stoppes før operation
ssh -p 2201 root@edge "grep 'LAB.*stop_frame_push' /var/log/timelapse-edge.log"

# Tjek om driver er forbundet
ssh -p 2201 root@edge "grep 'Driver.*connect' /var/log/timelapse-edge.log"
```
