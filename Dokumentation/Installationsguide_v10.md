# TimeLapse Pro — Installationsguide (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Konsoliderer:** `Headend_Installationsguide_Mac_Mini.md` (Del A), `TimeLapse_Pro_Installationsguide.md` (Del B), `Edge_Local_Provisioning_Runbook_2026-06-03.md` (Del C). Tidligere versioner arkiveret i `Gamle versioner/`.

Denne guide har **tre klart adskilte dele**:

- **Del A — Installation af HEADEND** (Mac Mini): PostgreSQL, repo, venv, migrationer, launchd, nginx, UI, node-agent, SFTP.
- **Del B — Installation af EDGE** (end-to-end): bootstrap token, disk image build, flash, boot/enrollment, site-tildeling, verifikation.
- **Del C — Edge lokal provisioning**: lokal netværksopsætning (CLI / AP-mode / captive portal) før stabil Headend-forbindelse.

> Bemærk: Del A stammer fra lab-æraen (`/Volumes/data`, `timelapse.froekjaer.dk`). Aktuel canonical storage er `/Volumes/data-fast`; se `ADMINISTRATORMANUAL_v10.md` og `00_START_HER.md` for gældende driftsdetaljer.

---

# Del A — Installation af HEADEND (Mac Mini)

## TimeLapse Pro — Headend Installationsguide (Mac Mini)

**Version:** 2.9 | **Dato:** 2026-05-11 | **Platform:** macOS Sequoia (Apple Silicon)

---

### Forudsætninger

- Mac Mini med macOS Sequoia (Darwin 25+)
- Homebrew installeret
- GitHub SSH-adgang konfigureret
- Ekstern harddisk formateret som `data` (mountes automatisk som `/Volumes/data`)

---

### 1. PostgreSQL

```bash
brew install postgresql@16
brew services start postgresql@16

## Opret database og bruger
createdb timelapse_db
psql timelapse_db -c "CREATE USER timelapse WITH PASSWORD 'dit-password';"
psql timelapse_db -c "GRANT ALL PRIVILEGES ON DATABASE timelapse_db TO timelapse;"
psql timelapse_db -c "GRANT ALL ON SCHEMA public TO timelapse;"
```

> ⚠️ **Vigtigt:** På macOS er PostgreSQL superuseren dit eget login-navn (ikke `postgres`).
> Brug `psql -d timelapse_db` (uden `-U postgres`) til alle operationer.

#### Efter nye migrationer — giv altid rettigheder:
```bash
psql -d timelapse_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO timelapse;"
psql -d timelapse_db -c "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO timelapse;"
```

---

### 2. Repository

```bash
mkdir -p ~/projects
cd ~/projects
git clone git@github.com:froekjaer/timelapse-pro.git
cd timelapse-pro
```

---

### 3. Python venv (headend)

```bash
cd ~/projects/timelapse-pro/headend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 4. Database migrationer

Kør i rækkefølge:

```bash
cd ~/projects/timelapse-pro/headend
psql -d timelapse_db -f migrations/v2_8_cmdb.sql
psql -d timelapse_db -f migrations/v2_9_security.sql
```

---

### 5. Launchd plist

Opret `/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dk.froekjaer.timelapse-headend</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/peter/projects/timelapse-pro/headend/venv/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/peter/projects/timelapse-pro/headend</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/timelapse-headend.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/timelapse-headend.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL</key>
        <string>postgresql://timelapse@localhost/timelapse_db</string>
        <key>JWT_SECRET</key>
        <string>GENERER-MED: python3 -c "import secrets; print(secrets.token_hex(32))"</string>
        <key>BREAK_GLASS_ENC_KEY</key>
        <string>GENERER-MED: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</string>
        <key>SFTP_BASE</key>
        <string>/Volumes/data</string>
        <key>FFMPEG_PATH</key>
        <string>/opt/homebrew/bin/ffmpeg</string>
        <key>ALLOWED_ORIGIN</key>
        <string>https://timelapse.froekjaer.dk</string>
        <key>COOKIE_SECURE</key>
        <string>true</string>
        <key>WEBAUTHN_RP_ID</key>
        <string>timelapse.froekjaer.dk</string>
        <key>WEBAUTHN_ORIGIN</key>
        <string>https://timelapse.froekjaer.dk</string>
        <key>TIMELAPSE_REPO_DIR</key>
        <string>/Users/peter/projects/timelapse-pro</string>
    </dict>
</dict>
</plist>
```

```bash
sudo launchctl load /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
```

#### Genindlæs efter ændringer:
```bash
sudo launchctl unload /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
sudo launchctl load   /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
```

#### Log:
```bash
tail -f /var/log/timelapse-headend.log
```

---

### 6. Ekstern harddisk (SFTP-storage)

```bash
## Find disk UUID
diskutil info /Volumes/data | grep "Volume UUID"

## Tilføj til /etc/fstab for konsistent mount-punkt
echo "UUID=<DIN-UUID> /Volumes/data apfs rw" | sudo tee -a /etc/fstab

## Opret dataroden. Kunde/site/kamera-strukturen ligger direkte herunder.
sudo mkdir -p /Volumes/data
sudo chown peter:staff /Volumes/data
```

> ⚠️ **Diskskift:** Formatér ny disk med samme volumenavn `data` →
> monteres automatisk på `/Volumes/data` → ingen config-ændring nødvendig.

> ⚠️ **SIP (System Integrity Protection):** macOS tillader ikke `mv` eller `rm`
> på `/Users/Shared/` via terminal. Brug `rsync` til at kopiere data og
> opdatér `SFTP_BASE` i plist i stedet for at lave symlinks.

---

### 7. nginx

```bash
brew install nginx

## Kopiér konfiguration
sudo cp ~/projects/timelapse-pro/Dokumentation/nginx.conf \
        /opt/homebrew/etc/nginx/nginx.conf

## SSL-certifikater (Let's Encrypt via certbot)
brew install certbot
sudo certbot certonly --standalone -d timelapse.froekjaer.dk
sudo mkdir -p /opt/homebrew/etc/nginx/ssl
sudo cp /etc/letsencrypt/live/timelapse.froekjaer.dk/fullchain.pem \
        /opt/homebrew/etc/nginx/ssl/
sudo cp /etc/letsencrypt/live/timelapse.froekjaer.dk/privkey.pem \
        /opt/homebrew/etc/nginx/ssl/

## Test og start
sudo nginx -t
brew services start nginx
```

---

### 8. UI (React/TypeScript)

```bash
cd ~/projects/timelapse-pro/timelapse-ui
npm install
npm run build
## dist/ serveres af nginx
```

---

### 9. Node Agent (SIEM + CMDB inventar)

```bash
sudo bash ~/projects/timelapse-pro/node-agent/install/macos.sh
```

Konfigurationsfil: `/etc/timelapse/node-agent.conf`

```ini
[agent]
device_id          = TL-MACMINI-HEADEND-TEST-1
headend_url        = https://timelapse.froekjaer.dk
inventory_interval = 300
security_interval  = 60
security_lookback  = 120
```

Log: `tail -f /var/log/timelapse-node-agent.log`

---

### 10. SSH logging (macOS Sequoia)

> ⚠️ **macOS Sequoia begrænsning:** SSH auth-events (`Failed password`,
> `Accepted publickey`) er ikke tilgængelige via `log show` eller klassiske
> logfiler. `SyslogFacility AUTH` og `LogLevel VERBOSE` i `sshd_config`
> har ingen effekt på Sequoia.
>
> SIEM-collectoren bruger i stedet:
> - `last` kommandoen for succesfulde SSH-logins
> - nginx access log for HTTP/HTTPS security events

Aktiver nginx access log (allerede i nginx.conf):
```
access_log /var/log/nginx-timelapse-access.log timelapse;
error_log  /var/log/nginx-timelapse-error.log warn;
```

---

### 11. GitHub Actions self-hosted runner

```bash
## Følg GitHub's vejledning under:
## Settings → Actions → Runners → New self-hosted runner (macOS)
```

CI-workflowen (`deploy-macmini`) kræver at runneren kan:
```bash
sudo launchctl stop/start dk.froekjaer.timelapse-headend
```

Tilføj til `/etc/sudoers` (via `sudo visudo`):
```
peter ALL=(ALL) NOPASSWD: /bin/launchctl
```

---

### 12. SFTP-bruger til edge

```bash
## Opret dedikeret SFTP-bruger
sudo dscl . -create /Users/sftpuser
sudo dscl . -create /Users/sftpuser UserShell /usr/bin/false
sudo dscl . -create /Users/sftpuser NFSHomeDirectory /Volumes/data
sudo dscl . -passwd /Users/sftpuser <password>

## Tilføj til sshd_config
sudo bash -c 'cat >> /etc/ssh/sshd_config << EOF
Match User sftpuser
    ChrootDirectory /Volumes/data
    ForceCommand internal-sftp
    AllowTcpForwarding no
EOF'
```

---

### Verifikation

```bash
## Headend kører
curl -s http://localhost:8000/health | python3 -m json.tool

## CMDB API
curl -s http://localhost:8000/api/cmdb/ | python3 -m json.tool

## SIEM API
curl -s http://localhost:8000/api/siem/summary | python3 -m json.tool

## Node agent kører
sudo launchctl list | grep timelapse-node-agent

## Ekstern disk monteret
ls /Volumes/data/
```

---

### Nøglegenerering (reference)

```bash
## JWT_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"

## BREAK_GLASS_ENC_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### Kendte problemer

| Problem | Årsag | Løsning |
|---------|-------|---------|
| `role "postgres" does not exist` | macOS bruger login-navn som PG superuser | Brug `psql -d timelapse_db` uden `-U` |
| `permission denied for table device_inventory` | Nye tabeller mangler GRANT | `GRANT ALL ON ALL TABLES TO timelapse;` |
| `mv: Operation not permitted` på `/Users/Shared/` | macOS SIP | Brug `rsync` + opdatér `SFTP_BASE` |
| SSH auth events mangler i SIEM | macOS Sequoia logger ikke til klassiske filer | Brug nginx access log + `last` |
| `inventory.py` fejler med `/sys/class/net` | Linux-kode på macOS | Platform-check i `_primary_interface()` |
| `DB_USER` fejler i migrations-script | macOS har ikke `postgres` bruger | Kør `DB_USER=peter bash script.sh` eller brug `psql` direkte |
---

### 13. Full Disk Access (macOS krav)

LaunchDaemon-processer har IKKE automatisk adgang til bruger-monterede volumes (ekstern disk, NAS).

**Påkrævet for at headend kan tilgå billeder på ekstern disk:**
Systemindstillinger → Beskyttelse og sikkerhed → Fuld diskadgang
→ Klik + → Navigér til:
/Users/peter/projects/timelapse-pro/headend/venv/bin/python
→ Tilføj

Genstart headend efter tilføjelse:
```bash
sudo launchctl stop dk.froekjaer.timelapse-headend
sudo launchctl start dk.froekjaer.timelapse-headend
```

> ⚠️ Uden Full Disk Access fejler `glob()` og `iterdir()` på externe diske
> med `[Errno 1] Operation not permitted` — selv for root-processer.


---

# Del B — Installation af EDGE (end-to-end provisioning)

## TimeLapse Pro — End-to-end installationsguide

**Version:** Sprint D · Juni 2026  
**Gælder for:** OrangePi PC Plus · Raspberry Pi 4 · OrangePi 4 Pro · Jetson Orin Nano

---

### Oversigt

```
1. Backup → Edge ISO → "Klargør ny Edge"
     Udfyld formular → klik "Klargør Edge" → kopiér bootstrap token

2. Backup → Edge ISO → "Edge disk image"
     Vælg hardware target → vælg "Flashbart .img.gz"
     Indsæt token → klik "Byg flashbart image" → Download .img.gz

3. Flash til SSD/SD-kort
     gunzip -c *.img.gz | sudo dd of=/dev/sdX bs=4m status=progress
     (eller balenaEtcher på Windows)

4. Sæt SSD/SD i boardet → strøm til
     timelapse-bootstrap.service kører automatisk
     Enheden vises i Enheder-listen (Dashboard)

5. Enheder → klik på enheden → vælg site → "Tildel"
```

---

### Del 1 — Forudsætninger

**Headend:** kører og er tilgængeligt, du er logget ind som admin  
**Docker Desktop:** installeret på den Mac der kører headenden (kræves til image-build)  
**Flashe-computer:** Mac/Linux med `dd` og `gunzip`, eller [balenaEtcher](https://etcher.balena.io) (alle platforme)

| Board | Medie | Strøm |
|---|---|---|
| OrangePi PC Plus | MicroSD 16 GB+ (Class 10) eller eMMC | 5V 3A microUSB |
| Raspberry Pi 4 | USB 3.0 SSD via adapter, eller MicroSD | 5V 3A USB-C |
| OrangePi 4 Pro | M.2 NVMe SSD (PCIe slot) | 12V DC barrel |
| Jetson Orin Nano | NVMe SSD (M.2 2280) | 19V DC |

---

### Del 2 — Opret bootstrap token

Gå til **Backup** i topmenuen → klik fanen **Edge ISO**.

Du ser en sektion kaldet **"Klargør ny Edge"** til venstre. Udfyld felterne:

| Felt | Hvad du skriver |
|---|---|
| Device ID | Et kort navn, f.eks. `timelapse-rpi4-01` |
| Token levetid timer | `48` er passende (token udløber efter X timer) |
| Kunde | Kundenavn, f.eks. `Froekjaer` |
| Site | Byggeplads eller lokation, f.eks. `Kontor` |
| Kamera | `Kamera 1` (standard) |
| Headend API URL | Lad feltet stå tomt — auto-udfyldes |
| Note | Valgfri installationsnote |

Klik **Klargør Edge**.

Når det lykkes vises en grøn boks med:
- En `bootstrap_yaml` konfiguration
- Næste trin

**Kopiér token-strengen** fra `bootstrap_yaml` — den ser ud som `btk-XXXXXXXX`. Du skal bruge den i næste trin.

> **Note:** Denne knap opretter ét enkelt token. Til image-builds er det normalt nok — imaget bages med ét token og enrollment sker automatisk ved boot.

---

### Del 3 — Byg flashbart image

Stadig under **Backup → Edge ISO**, scroll ned til sektionen **"Edge disk image"**.

**1. Vælg Hardware target** i dropdown:
- `OrangePi PC Plus (armhf)` — dit PC Plus board
- `Raspberry Pi 4 Model B (arm64)` — din RPi4
- `OrangePi 4 Pro (arm64)` — ankommer om få dage

**2. Vælg Output type:**
- Vælg `Flashbart .img.gz — klar til dd/balenaEtcher (~20 min)`

**3. Batch bootstrap token (valgfri):**  
Indsæt token-strengen du kopierede i trin 2 (`btk-XXXXXXXX`).  
Lader du feltet stå tomt bages en placeholder ind — du kan injicere token bagefter via CLI (se Del 7).

**4. Klik "Byg flashbart image"**

Build-loggen vises i realtid under knappen:
- **Step 1/4** — Docker buildx (~3–8 min, afhænger af platform og om cache er varm)
- **Step 2/4** — Bootstrap.yaml bygges med din headend URL + token
- **Step 3/4** — Docker --privileged injection. **Første gang downloades base-image (~600 MB–1 GB)** og cachet lokalt — efterfølgende builds er hurtigere
- **Step 4/4** — Komprimering + GPG-signering

Når det er færdigt vises en grøn boks med filnavn, størrelse, sha256 og flash-kommandoen.

**5. Klik "Download .img.gz"**

---

### Del 4 — Flash til SSD eller SD-kort

#### Mac / Linux — terminal

```bash
## Find din disk — TJEK DETTE GRUNDIGT inden du fortsætter
diskutil list          # macOS
lsblk                  # Linux

## Eksempel-output macOS:
## /dev/disk4 (external, physical):
##    #:  TYPE NAME    SIZE       IDENTIFIER
##    0:  FDisk_partition_scheme  *31.9 GB   disk4

## Unmount disken (macOS) — erstat diskN med din disk
diskutil unmountDisk /dev/disk4

## Flash (erstat disk4 med din disk — IKKE diskN's med data!)
gunzip -c timelapse-edge-rpi4-20260614120000.img.gz \
  | sudo dd of=/dev/rdisk4 bs=4m status=progress

## rdisk er hurtigere end disk på macOS (raw device)
```

```bash
## Linux
lsblk  # find /dev/sdX eller /dev/mmcblkX

gunzip -c timelapse-edge-orangepi-pc-plus-*.img.gz \
  | sudo dd of=/dev/sdb bs=4M status=progress conv=fsync
```

> ⚠️ **Advarsel:** `dd` overskriver disken uden bekræftelse. Dobbelttjek at `/dev/rdisk4` / `/dev/sdb` er din SSD eller SD-kort og ikke din Mac's interne disk.

#### Windows — balenaEtcher

1. Download og åbn [balenaEtcher](https://etcher.balena.io)
2. Klik **Flash from file** → vælg `.img.gz` filen (Etcher udpakker automatisk)
3. Klik **Select target** → vælg din SSD eller SD-kort
4. Klik **Flash!**

---

### Del 5 — Boot og enrollment

#### OrangePi PC Plus
1. Sæt MicroSD-kortet i (eller brug eMMC via dedikeret slot)
2. Tilslut netværkskabel — DHCP skal være tilgængeligt
3. Tilslut strøm (5V 3A microUSB)
4. Vent ~2–3 minutter

#### Raspberry Pi 4
> Hvis du flasher til USB SSD kræves det at RPi 4's EEPROM er sat til USB Boot:
> ```bash
> # Fra et eksisterende kørende RPi OS:
> sudo raspi-config → Advanced Options → Bootloader Version → Latest → Finish → Reboot
> # EEPROM-opdatering er permanent
> ```

1. Tilslut USB SSD (brug den blå USB 3.0 port) — eller sæt MicroSD i
2. Tilslut netværkskabel
3. Tilslut strøm (5V 3A USB-C)
4. Vent ~2–3 minutter

#### OrangePi 4 Pro
1. Sæt M.2 NVMe SSD i PCIe-slotten under boardet
2. Tilslut netværkskabel
3. Tilslut 12V DC strøm
4. Vent ~2–3 minutter

#### Hvad sker der automatisk ved første boot

```
systemd starter
  → timelapse-bootstrap.service kører (kun hvis /etc/timelapse/.enrolled ikke findes)
      → Genererer SSH keypair (ed25519)
      → Finder primær MAC-adresse
      → Beregner Device ID = "TL-{MAC}" (f.eks. TL-DC2B2A112233)
      → POST https://timelapse.froekjaer.dk/api/devices/enroll
      → Gemmer API token og config URL
      → Opretter /etc/timelapse/.enrolled
      → Starter timelapse-edge.service
  → timelapse-edge.service kører herefter permanent
```

Bootstrap forsøger op til 10 gange med 15 sekunders mellemrum (max 10 min) i tilfælde af at netværket ikke er klar med det samme.

---

### Del 6 — Tildel til site

Gå til **Enheder** (første punkt i topmenuen — ikonet ligner et kamera).

Din nye enhed dukker op i listen med status `online`. Device ID er `TL-{MAC}`.

Klik på enheden → du kommer til enhedens detaljeside.

Øverst på siden vises en gul/orange boks hvis enheden ikke er tildelt et site endnu:

```
Denne enhed er ikke tildelt et site
[Dropdown: Vælg site…]  [Tildel]
```

1. Vælg site i dropdown
2. Klik **Tildel**

Enheden er nu aktiv og begynder at modtage konfiguration fra headenden.

---

### Del 7 — Verifikation

#### Headend UI
- **Enheder** → enhedens status bør vise `online` med grønt
- **Admin → CMDB** → inventory fra enheden vises inden for ~5 minutter (CPU, RAM, OS, pakkeliste)

#### SSH via reverse tunnel
```bash
## Fra headend-maskinen (SSH-tunnelen etableres automatisk ved enrollment)
ssh -p 2201 orangepi@localhost   # OrangePi boards
ssh -p 2201 ubuntu@localhost     # Raspberry Pi

## Tjek services på boardet
sudo systemctl status timelapse-edge
sudo journalctl -fu timelapse-edge --no-pager
```

#### Tjek direkte på boardet
Find IP-adressen i din router (kig efter hostname `orangepipcplus`, `ubuntu` e.l.):
```bash
ssh ubuntu@192.168.x.x      # RPi4 — brugernavn: ubuntu
ssh orangepi@192.168.x.x    # OrangePi — brugernavn: orangepi

## Er enrollment gået igennem?
cat /etc/timelapse/.enrolled          # fil eksisterer = enrolled
cat /etc/timelapse/node-agent.conf    # indeholder api_token og config_url

## Services
sudo systemctl status timelapse-edge timelapse-bootstrap
sudo journalctl -u timelapse-bootstrap -n 30
```

---

### Jetson Orin Nano — separat flow

Jetson kan **ikke** provisioneres via flashbart image. Brug install-scriptet:

```bash
## Trin 1: Flash Jetson med JetPack via NVIDIA SDK Manager
## https://developer.nvidia.com/sdk-manager

## Trin 2: Kopiér installer-scriptet til Jetson
scp headend/tools/hardware/jetson-orin-nano/install_timelapse_edge.sh \
  nvidia@<jetson-ip>:~/

## Trin 3: Kør på Jetson
ssh nvidia@<jetson-ip>
sudo bash install_timelapse_edge.sh \
  --headend-url https://timelapse.froekjaer.dk/api \
  --bootstrap-token btk-XXXXXXXX
```

Scriptet installerer venv, services, SSH hardening og skriver `bootstrap.yaml`. Herefter samme flow som ovenfor — enrollment sker ved reboot.

---

### Fejlfinding

#### Enheden vises ikke i Enheder-listen efter boot

```bash
## Tjek på boardet
sudo systemctl status timelapse-bootstrap
sudo journalctl -u timelapse-bootstrap -n 50

## Er der netværk?
ping timelapse.froekjaer.dk

## Er bootstrap config korrekt?
sudo cat /etc/timelapse/bootstrap.yaml
## Forventet indhold:
##   headend_url: "https://timelapse.froekjaer.dk/api"
##   bootstrap_token: "btk-XXXXXXXX"

## Genstart bootstrap manuelt
sudo rm -f /etc/timelapse/.enrolled
sudo systemctl restart timelapse-bootstrap
sudo journalctl -fu timelapse-bootstrap
```

#### "Bootstrap token allerede brugt"

Token er single-use og er allerede brugt. Gå til **Backup → Edge ISO → Klargør ny Edge** og opret et nyt token. Genbyg imaget med det nye token, eller brug CLI:

```bash
python headend/tools/inject_edge_image.py patch-token \
  timelapse-edge-rpi4-20260614.img.gz \
  btk-NYTTOKEN
## Producerer: timelapse-edge-rpi4-20260614-token.img.gz
```

#### "Bootstrap token udløbet"

Token har passeret sin levetid. Opret nyt token (Backup → Edge ISO → Klargør ny Edge) og injecér som ovenfor.

#### Image-build fejler under Docker injection

Docker Desktop skal have rettigheder til privileged containers:
- Docker Desktop → Settings → General → sæt flueben ved **"Allow privileged containers"** (eller tilsvarende) → Apply & Restart

#### OrangePi PC Plus booter ikke fra SD-kort

- Brug et Class 10 / A1 SD-kort (billige kort fra discount-butikker virker ofte ikke)
- Prøv at flashe igen med balenaEtcher i stedet for `dd`
- Armbian kræver at SD-kortet er korrekt unmountet inden flash

#### RPi4 booter ikke fra USB SSD

USB-boot skal aktiveres i EEPROM (gøres én gang):
```bash
## Fra Raspberry Pi OS på SD-kort:
sudo raspi-config
## → Advanced Options → Bootloader Version → Latest → Finish → Reboot
```

---

### Reference — filer og paths på edge-boardet

| Sti | Indhold |
|---|---|
| `/etc/timelapse/bootstrap.yaml` | Headend URL + bootstrap token (bagt ind ved image-build) |
| `/etc/timelapse/node-agent.conf` | API token + config URL (skrevet ved enrollment) |
| `/etc/timelapse/device_keys/id_ed25519` | Device SSH private key (genereret ved første boot) |
| `/etc/timelapse/.enrolled` | Markerfil — eksisterer = enrollment er gennemført |
| `/opt/timelapse/edge/` | Timelapse agent kode |
| `/opt/timelapse/venv/` | Python virtual environment |
| `/data/` | Captures og lokal storage |


---

# Del C — Edge lokal provisioning (CLI / AP-mode)

## TimeLapse Pro - Edge lokal provisioning

**Dato:** 2026-06-03  
**Scope:** Lokal netværksopsætning før Edge har stabil Headend-forbindelse.

### Princip

Edge må kun konfigureres lokalt for de minimumsparametre der kræves for at skabe kontakt til Headend:

- Headend API URL
- bootstrap token
- WiFi
- Ethernet
- 4G USB modem
- connectivity preference

Al rigtig driftskonfiguration, kameraopsætning, RBAC, kunde/site binding, capture schedule og update-policy skal fortsat komme fra Headend.

### CLI

På Edge:

```bash
cd /opt/timelapse
sudo edge/tools/bootstrap_cli.py
```

Status uden interaktiv menu:

```bash
sudo edge/tools/bootstrap_cli.py --status
sudo edge/tools/bootstrap_cli.py --test-headend
```

CLI'en skriver kun til:

- `/opt/timelapse/edge/bootstrap.yaml`
- `/opt/timelapse/edge/local_network.yaml`
- NetworkManager profiler via `nmcli`

WiFi-password gemmes ikke i TimeLapse config. Det gives direkte til NetworkManager.

### Production-sikkerhedsgrænse

- Ingen WiFi-passwords via Headend `lab_command` i production.
- Ingen kamera-, tenant- eller schedule-konfiguration lokalt.
- Ingen lokal brugeradministration.
- Ingen local bypass af RBAC.
- Bootstrap token skal være tidsbegrænset eller engangsbrug når production provisioning-flowet er færdigt.

### Captive portal / AP-mode design

Når Edge ikke har fungerende netværk eller ikke kan nå Headend, kan den i fremtiden starte et midlertidigt provisioning access point.

Anbefalet SSID:

```text
TLP-<device_id>
```

Eksempel:

```text
TLP-TL-C87FF9587CA0
```

Anbefalet lokal webadresse:

```text
http://192.168.77.1/
```

Webfladen må kun tilbyde:

- vis device_id og netværksstatus
- sæt Headend URL
- indtast bootstrap token
- scan/tilslut WiFi
- sæt Ethernet DHCP/static
- sæt 4G APN
- test Headend forbindelse
- stop AP-mode når Headend er nået

### AP-mode sikkerhed

- AP-mode må kun være aktiv når Edge ikke har Headend-forbindelse, eller ved fysisk lokal trigger.
- SSID skal være device-specifikt, ikke kundespecifikt.
- AP-password skal være unikt pr. device og ikke afledt kun af device_id.
- Web UI skal være local-only, uden adgang til capture data, logs med secrets, kamera-liveview eller Headend tokens.
- AP-mode skal auto-timeout'e, fx efter 30 minutter.
- Når Edge bootstrapper korrekt mod Headend, skal AP-mode stoppes.

### Næste implementeringstrin

1. Installer CLI i Edge image/service package.
2. Tilføj systemd unit for provisioning AP-mode.
3. Tilføj minimal lokal webserver der genbruger samme netværksfunktioner som CLI.
4. Generér device-specifikt AP-password under provisioning og registrér kun fingerprint/evidence i Headend.
5. Tilføj Headend evidence: local provisioning started/stopped, network configured, bootstrap succeeded.
