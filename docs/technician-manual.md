# TimeLapse Pro — Servicetekniker Manual

**Version:** 2.0
**Dato:** 12. juli 2026
**Målgruppe:** Serviceteknikere der installerer og vedligeholder TimeLapse Pro enheder

---

## 📋 Indhold

1. [Klargøring & Installation](#klargøring--installation)
2. [Første Opsætning](#første-opsætning)
3. [Daglig Drift](#daglig-drift)
4. [Fejlfinding](#fejlfinding)
5. [Kamera Justering](#kamera-justering)
6. [Vedligeholdelse](#vedligeholdelse)
7. [Nødsituationer](#nødsituationer)

---

## Klargøring & Installation

### Værktøj & Udstyr

| Værktøj | Anvendelse |
|---------|------------|
| PoE injector eller strømadapter | Strømforsyning |
| USB kabel (USB-C til USB-C) | Kamera forbindelse |
| Netværkskabel (Cat5e+) | Ethernet forbindelse |
| Laptop/tablet | Lokal konfiguration |
| Smartphone (med QR scanner) | Tekniker login |

### Hardware Komponenter

```
┌─────────────────────────────────────────────────────┐
│              TIME LAPSE PRO ENHED                   │
│  ┌──────────────┐         ┌──────────────┐        │
│  │  Orange Pi   │         │   KAMERA     │        │
│  │  4 Pro / PC  │◄───────►│   (Nikon/    │        │
│  │              │  USB    │    Canon)    │        │
│  │  ┌────────┐  │         │              │        │
│  │  │ Relay  │  │         └──────────────┘        │
│  │  │ Module │───┼───► 5V Out                    │
│  │  └────────┘  │                                 │
│  └──────────────┘                                 │
│         │                                          │
│    PoE / DC In                                   │
└─────────────────────────────────────────────────────┘
```

### Installation Trin-for-Trin

#### Trin 1: Fysisk Installation

1. **Montér kameraet**
   - Ret kameraet mod motivet
   - Sørg for stabil montering (ingen vibrationer)
   - Beskyt mod direkte sollys (regn/UV hætte)

2. **Tilslut kabling**
   ```
   Orange Pi ──USB──► Kamera
   Orange Pi ──LAN───► Switch/Router
   Orange Pi ──DC────► Relay ──► Kamera strøm
   ```

3. **Tænd strømmen**
   - Vent 2-3 minutter for boot
   - Check LED indikatorer på Orange Pi

#### Trin 2: Netværksforbindelse

**Option A: Ethernet (Anbefalet)**

```bash
# Find enheden på netværket
nmap -sn 192.168.1.0/24 | grep -B 2 "MAC.*Orange"

# Eller check DHCP leases
cat /var/log/dhcpd.log | grep "orangepi"
```

**Option B: WiFi (Hvis ethernet ikke er muligt)**

```bash
# SSH ind på enheden (via seriell konsol eller lokal)
ssh root@orangepi

# Scan for WiFi netværk
nmcli dev wifi

# Forbind til netværk
nmcli dev wifi connect "SSID-NAME" password "WIFI-PASSWORD"
```

#### Trin 3: Verificer Forbindelse

```bash
# Ping enheden
ping tlp-edge-001.local

# SSH ind (standard password er sat ved provisionering)
ssh root@tlp-edge-001.local
```

---

## Første Opsætning

### Bootstrap Provisioning

Enheden provisioneres med `bootstrap.yaml` der indeholder:

```yaml
device_id: "tlp-edge-001"
headend_url: "https://timelapse.example.com/api"
customer_id: "customer-123"
location_name: "Site A - North"
```

### Trin 1: Opret Device på Headend

1. Log ind på headend web UI
2. Gå til **Enheder → Ny Enhed**
3. Indtast:
   - Device ID (fra label på enheden)
   - Location / Site
   - Kamera model
   - Kunde
4. Gem — enheden får en unik API token

### Trin 2: Indlæs API Token

```bash
# SSH ind på enheden
ssh root@tlp-edge-001.local

# Indlæs token (kopieret fra headend)
echo "API-TOKEN-FRA-HEADEND" > /opt/timelapse/edge/api_token.txt
chmod 600 /opt/timelapse/edge/api_token.txt

# Genstart agenten
systemctl restart timelapse-edge
```

### Trin 3: Verificer Forbindelse til Headend

```bash
# Tjek log
journalctl -u timelapse-edge -n 50 -f

# Du skal se:
# "Config loaded — device_id=tlp-edge-001"
# "Heartbeat sent OK"
```

### Trin 4: Konfigurer Kamera

Via headend web UI:

1. Gå til **Enheder → tlp-edge-001 → Kamera**
2. Konfigurer:
   - ISO (typisk 100-200 for udendørs)
   - Lukker tid (afhænger af lysforhold)
   - Blænde (typisk f/8-f/11 for dybdeskarphed)
   - Hvidbalance (Auto eller manuel Kelvin)
3. Gem — konfigurationen pushes til edge

### Trin 5: Test Capture

```bash
# Kør en enkelt capture (uden at forstyrre schedule)
ssh root@tlp-edge-001.local
cd /opt/timelapse/edge
python3 agent.py --single-capture

# Tjek resultatet
ls -lh /data/captures/ | tail -5
```

---

## Daglig Drift

### Overvågning

#### Via Headend Web UI

1. **Dashboard**
   - Enhed status (online/offline)
   - Seneste billeder
   - Systemdiagnostik

2. **Enhedsdetaljer**
   - Capture historik
   - Upload status
   - Kamera diagnostik

#### Via SSH (On-site)

```bash
# Tjek agent status
systemctl status timelapse-edge

# Se live log
journalctl -u timelapse-edge -f

# Tjek disk forbrug
df -h /data

# Tjek database
sqlite3 /data/timelapse_edge.db "SELECT COUNT(*) FROM captures;"
```

### Tekniker Login (QR Kode)

For lokal adgang uden SSH password:

1. **Åbn technician UI**
   ```
   http://tlp-edge-001.local:8099
   ```

2. **Scan QR koden**
   - Åbn på smartphone
   - Du viderestilles til headend login
   - Log ind med dine techniker credentials

3. **Lokal adgang**
   - Efter login har du adgang til:
     - Device status
     - Kamera preview
     - Logfiler
     - Restart kommandoer

### Log Parsing

Vigtige log beskeder:

```
✅ SUCCESS
"Heartbeat sent OK"
"Config loaded — device_id=xxx"
"Capture cycle complete (success=True)"
"Upload results: {'primary': True}"

⚠️  WARNING
"Config pull failed — using cached config"
"Capture suppressed: solar_reflection"
"Camera config drift: ['shutterspeed']"

❌ ERROR
"Camera connect failed"
"Capture failed"
"Upload failed"
```

---

## Fejlfinding

### Problemer og Løsninger

#### Problem: Kamera ikke fundet

**Symptomer:**
- `"Camera connect failed"`
- Ingen nye billeder i `/data/captures/`

**Diagnose:**
```bash
# Tjek USB forbindelse
ls -l /dev/timelapse-cam*

# Tjek om kameraet er tændt (relay check)
cat /sys/class/gpio/gpio356/value  # Skal være 0 for ON (active-low)

# Manuell gphoto2 test
gphoto2 --auto-detect
gphoto2 --summary
```

**Løsning:**
1. Check USB kabel er sat korrekt i
2. Check relay tænder kameraet (lyd/LED)
3. Prøv at genstarte kameraet via relay:
   ```bash
   ssh root@tlp-edge-001.local
   python3 -c "
   import sys; sys.path.insert(0, '/opt/timelapse/edge')
   from camera.relay import RelayController
   import yaml
   cfg = yaml.safe_load(open('/opt/timelapse/edge/config.yaml'))
   relay = RelayController(cfg)
   relay.camera.power_cycle()
   "
   ```

#### Problem: Upload fejler

**Symptomer:**
- `"Heartbeat failed — headend unreachable"`
- Billeder i `/data/captures/` men ikke på headend

**Diagnose:**
```bash
# Ping headend
ping -c 5 timelapse.example.com

# Tjek netværk
ip addr show
ip route show

# DNS lookup
nslookup timelapse.example.com
```

**Løsning:**
1. Check netværkskabel
2. Check switch/router
3. Hvis WiFi: check signalstyrke
   ```bash
   nmcli dev wifi list
   ```
4. Check firewall på enheden
   ```bash
   iptables -L -n
   ```

#### Problem: Disk fuld

**Symptomer:**
- `"Buffer full: XX GB / XX GB — pruning…"`
- Ingen capture plads

**Diagnose:**
```bash
df -h /data

# Tjek buffer status
du -sh /data/captures/*
```

**Løsning:**
1. Vent — buffer rydder automatisk uploaded files
2. Hvis akut:
   ```bash
   # Slet uploaded files manuelt
   sqlite3 /data/timelapse_edge.db "SELECT filepath FROM captures WHERE uploaded_primary=1;" | \
       xargs -I {} rm /data/captures/{}
   ```
3. Øg `circular_buffer_gb` i config hvis problemet gentager sig

#### Problem: Relay ikke tændende

**Symptomer:**
- Kameraet tænder ikke
- Relay klikker ikke

**Diagnose:**
```bash
# Check GPIO status
cat /sys/class/gpio/gpio356/value  # Skal være 0 for ON

# Tjek at GPIO er exporteret
ls -l /sys/class/gpio/ | grep gpio356
```

**Løsning:**
1. Check wiring til relay modulet
2. Check relay strømforsyning (5V)
3. Manual test:
   ```bash
   # Turn ON
   echo 0 > /sys/class/gpio/gpio356/value

   # Turn OFF
   echo 1 > /sys/class/gpio/gpio356/value
   ```

#### Problem: Enhed ikke tilgængelig på netværk

**Diagnose:**
```bash
# Check DHCP (fra router)
# Find MAC adresse på enheden og se om den har fået IP

# Lokalt på enheden (via seriell):
ip addr show
ip route show
```

**Løsning:**
1. Check netværkskabel
2. Check PoE injector/strømforsyning
3. Check forbindelse til switch
4. Prøv at pinge fra enheden:
   ```bash
   ping 8.8.8.8
   ping gateway-ip
   ```

---

## Kamera Justering

### Lab Mode (Remote Justering)

Headend web UI har en "Lab Mode" til kamera justering:

1. Gå til **Enheder → tlp-edge-001 → Lab Mode**
2. Aktiver Lab Mode (kameraet tændes og forbliver tændt)
3. Brug kommandoer:
   - **Preview** — Hent live preview
   - **Focus Slice** — Test fokus ved forskellige afstande
   - **Autofocus** — Kør autofocus
   - **Set Parameter** — Ændr kamera indstillinger

### Fokus Justering

**Procedur:**
1. Placér et testobjekt ved den forventede afstand
2. Start "Focus Slice" i Lab Mode
3. Systemet tager en serie billeder med forskellig fokus
4. Væg det skarpeste billede
5. Noter den optimale fokus-indstilling
6. Gem som permanent i kamera profilen

### Eksposure Justering

**Procedur:**
1. Start Lab Mode
2. Tag et preview
3. Check histogram i headend UI
4. Juster ISO, lukker tid, eller blænde
5. Tag nyt preview indtil eksponering er korrekt

**Tips:**
- Udendørs: ISO 100-200, f/8-11, lukker 1/125-1/500
- Indendørs: ISO 400-800, f/4-5.6, lukker 1/60-1/125
- Mod lys: Luk ned 1-2 stops
- Skygge: Åbn 0.5-1 stops

### White Balance

**Procedur:**
1. I Lab Mode, sæt hvidbalance
2. Valgmuligheder:
   - Auto (fungerer oftest godt)
   - Dagslys (5500-6500K)
   - Skygge (7000-8000K)
   - Overskyet (6500-7500K)

**Tip:** For timelapse med variable lysforhold, brug Auto.

---

## Vedligeholdelse

### Månedlig

1. **Rens kamera linse**
   - Brug linseklud evt. med lens cleaner
   - Undgå at ridse optikken

2. **Tjek kabling**
   - Stram eventuelle løse forbindelser
   - Check for slid på kabler

3. **Tjek montering**
   - Sikker at kameraet ikke har flyttet sig
   - Tjek skruer/bolte

4. **Verificer netværk**
   - Ping enheden
   - Check headend for offline alerts

### Kvartalsvis

1. **Opdater firmware**
   - SSH ind på enheden
   - Kør opdateringer via headend:
     ```bash
     # Opdatering pushes fra headend
     systemctl status timelapse-edge  # Tjek version
     ```

2. **Backup database**
   ```bash
   cp /data/timelapse_edge.db /data/timelapse_edge.db.bak
   ```

3. **Test backup power**
   - Hvis enheden har batteri backup, test funktion

4. **Review capture kvalitet**
   - Gennemgå de sidste 100 captures på headend
   - Tjek for trends (udvaskede farver, undereksponering, etc.)

### Årlig

1. **Fuld hardware review**
   - Inspektér kamera for tegn på slid
   - Check kabling for UV skader
   - Test alle relays og GPIO

2. **Opdater dokumentation**
   - Noter ændringer i opsætning
   - Opdater site diagrammer

---

## Nødsituationer

### Strøm Svigt

**Handling:**
1. Enheden genstarter automatisk når strøm vender tilbage
2. Check at alle captures siden sidste upload er synkroniseret
3. Hvis captures mangler, check `/data/captures/`

### Netværks Nedbrud

**Hvis netværket er nede > 24 timer:**

1. **On-site:**
   ```bash
   # Check local status
   systemctl status timelapse-edge
   df -h /data
   sqlite3 /data/timelapse_edge.db "SELECT COUNT(*) FROM captures WHERE uploaded_primary=0;"
   ```

2. **When netværk vender tilbage:**
   - Uploads resume automatisk
   - Check headend for huller i tidslinjen

### Kamera Svigt

**Hvis kameraet ikke responderer:**

1. **Power cycle via relay:**
   ```bash
   ssh root@tlp-edge-001.local
   python3 -c "
   import sys; sys.path.insert(0, '/opt/timelapse/edge')
   from camera.relay import RelayController
   import yaml
   cfg = yaml.safe_load(open('/opt/timelapse/edge/config.yaml'))
   relay = RelayController(cfg)
   relay.camera.power_cycle()
   "
   ```

2. **Hvis dette ikke virker:**
   - Fysisk kamera genstart (sluk/til)
   - Check USB kabel
   - Overvej kamera udskiftning

### Enhed Total Svigt

**Hvis enheden ikke reagerer:**

1. **Fysisk genstart:**
   - Sluk strøm
   - Vent 10 sekunder
   - Tænd igen

2. **Hvis boot fejler:**
   - Check for SD korte fejl (hvis relevant)
   - Overvej OS reinstall

3. **Data recovery:**
   - Fjern disk/SD kort
   - Mount på anden enhed
   - Kopier `/data/timelapse_edge.db` og `/data/captures/`

---

## Quick Reference

### SSH Kommandoer

```bash
# Status
systemctl status timelapse-edge

# Logs
journalctl -u timelapse-edge -f          # Live
journalctl -u timelapse-edge -n 100      # Sidste 100 linjer

# Disk
df -h /data

# Database
sqlite3 /data/timelapse_edge.db

# Restart
systemctl restart timelapse-edge

# Stop/Start
systemctl stop timelapse-edge
systemctl start timelapse-edge

# Test capture
cd /opt/timelapse/edge && python3 agent.py --single-capture
```

### File Locations

| Fil/Mappe | Formål |
|-----------|--------|
| `/opt/timelapse/edge/` | Applikationskode |
| `/data/captures/` | Billeder |
| `/data/timelapse_edge.db` | Database |
| `/opt/timelapse/edge/config.yaml` | Konfiguration |
| `/var/log/timelapse/` | Logfiler (hvis konfigureret) |

### Vigtige Ports

| Port | Formål |
|------|--------|
| 22 | SSH |
| 8099 | Technician UI |

---

## Support

### Henvendelse

Ved problemer der ikke kan løses med denne manual:

1. **Akut (nedlagt system):**
   - Ring hotline: +45 XX XX XX XX

2. **Ikke-akut:**
   - Email: support@timelapse.example.com
   - Inkluder:
     - Device ID
     - Beskrivelse af problem
     - Relevante logfiler (`journalctl -u timelapse-edge -n 200 > edge.log`)

### Dokumentation

Opdateret dokumentation findes altid på:
- https://docs.timelapse.example.com

---

**Manual version:** 2.0
**Sidst opdateret:** 12. juli 2026
