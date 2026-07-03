# TimeLapse Pro — End-to-end installationsguide

**Version:** Sprint D · Juni 2026  
**Gælder for:** OrangePi PC Plus · Raspberry Pi 4 · OrangePi 4 Pro · Jetson Orin Nano

---

## Oversigt

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

## Del 1 — Forudsætninger

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

## Del 2 — Opret bootstrap token

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

## Del 3 — Byg flashbart image

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

## Del 4 — Flash til SSD eller SD-kort

### Mac / Linux — terminal

```bash
# Find din disk — TJEK DETTE GRUNDIGT inden du fortsætter
diskutil list          # macOS
lsblk                  # Linux

# Eksempel-output macOS:
# /dev/disk4 (external, physical):
#    #:  TYPE NAME    SIZE       IDENTIFIER
#    0:  FDisk_partition_scheme  *31.9 GB   disk4

# Unmount disken (macOS) — erstat diskN med din disk
diskutil unmountDisk /dev/disk4

# Flash (erstat disk4 med din disk — IKKE diskN's med data!)
gunzip -c timelapse-edge-rpi4-20260614120000.img.gz \
  | sudo dd of=/dev/rdisk4 bs=4m status=progress

# rdisk er hurtigere end disk på macOS (raw device)
```

```bash
# Linux
lsblk  # find /dev/sdX eller /dev/mmcblkX

gunzip -c timelapse-edge-orangepi-pc-plus-*.img.gz \
  | sudo dd of=/dev/sdb bs=4M status=progress conv=fsync
```

> ⚠️ **Advarsel:** `dd` overskriver disken uden bekræftelse. Dobbelttjek at `/dev/rdisk4` / `/dev/sdb` er din SSD eller SD-kort og ikke din Mac's interne disk.

### Windows — balenaEtcher

1. Download og åbn [balenaEtcher](https://etcher.balena.io)
2. Klik **Flash from file** → vælg `.img.gz` filen (Etcher udpakker automatisk)
3. Klik **Select target** → vælg din SSD eller SD-kort
4. Klik **Flash!**

---

## Del 5 — Boot og enrollment

### OrangePi PC Plus
1. Sæt MicroSD-kortet i (eller brug eMMC via dedikeret slot)
2. Tilslut netværkskabel — DHCP skal være tilgængeligt
3. Tilslut strøm (5V 3A microUSB)
4. Vent ~2–3 minutter

### Raspberry Pi 4
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

### OrangePi 4 Pro
1. Sæt M.2 NVMe SSD i PCIe-slotten under boardet
2. Tilslut netværkskabel
3. Tilslut 12V DC strøm
4. Vent ~2–3 minutter

### Hvad sker der automatisk ved første boot

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

## Del 6 — Tildel til site

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

## Del 7 — Verifikation

### Headend UI
- **Enheder** → enhedens status bør vise `online` med grønt
- **Admin → CMDB** → inventory fra enheden vises inden for ~5 minutter (CPU, RAM, OS, pakkeliste)

### SSH via reverse tunnel
```bash
# Fra headend-maskinen (SSH-tunnelen etableres automatisk ved enrollment)
ssh -p 2201 orangepi@localhost   # OrangePi boards
ssh -p 2201 ubuntu@localhost     # Raspberry Pi

# Tjek services på boardet
sudo systemctl status timelapse-edge
sudo journalctl -fu timelapse-edge --no-pager
```

### Tjek direkte på boardet
Find IP-adressen i din router (kig efter hostname `orangepipcplus`, `ubuntu` e.l.):
```bash
ssh ubuntu@192.168.x.x      # RPi4 — brugernavn: ubuntu
ssh orangepi@192.168.x.x    # OrangePi — brugernavn: orangepi

# Er enrollment gået igennem?
cat /etc/timelapse/.enrolled          # fil eksisterer = enrolled
cat /etc/timelapse/node-agent.conf    # indeholder api_token og config_url

# Services
sudo systemctl status timelapse-edge timelapse-bootstrap
sudo journalctl -u timelapse-bootstrap -n 30
```

---

## Jetson Orin Nano — separat flow

Jetson kan **ikke** provisioneres via flashbart image. Brug install-scriptet:

```bash
# Trin 1: Flash Jetson med JetPack via NVIDIA SDK Manager
# https://developer.nvidia.com/sdk-manager

# Trin 2: Kopiér installer-scriptet til Jetson
scp headend/tools/hardware/jetson-orin-nano/install_timelapse_edge.sh \
  nvidia@<jetson-ip>:~/

# Trin 3: Kør på Jetson
ssh nvidia@<jetson-ip>
sudo bash install_timelapse_edge.sh \
  --headend-url https://timelapse.froekjaer.dk/api \
  --bootstrap-token btk-XXXXXXXX
```

Scriptet installerer venv, services, SSH hardening og skriver `bootstrap.yaml`. Herefter samme flow som ovenfor — enrollment sker ved reboot.

---

## Fejlfinding

### Enheden vises ikke i Enheder-listen efter boot

```bash
# Tjek på boardet
sudo systemctl status timelapse-bootstrap
sudo journalctl -u timelapse-bootstrap -n 50

# Er der netværk?
ping timelapse.froekjaer.dk

# Er bootstrap config korrekt?
sudo cat /etc/timelapse/bootstrap.yaml
# Forventet indhold:
#   headend_url: "https://timelapse.froekjaer.dk/api"
#   bootstrap_token: "btk-XXXXXXXX"

# Genstart bootstrap manuelt
sudo rm -f /etc/timelapse/.enrolled
sudo systemctl restart timelapse-bootstrap
sudo journalctl -fu timelapse-bootstrap
```

### "Bootstrap token allerede brugt"

Token er single-use og er allerede brugt. Gå til **Backup → Edge ISO → Klargør ny Edge** og opret et nyt token. Genbyg imaget med det nye token, eller brug CLI:

```bash
python headend/tools/inject_edge_image.py patch-token \
  timelapse-edge-rpi4-20260614.img.gz \
  btk-NYTTOKEN
# Producerer: timelapse-edge-rpi4-20260614-token.img.gz
```

### "Bootstrap token udløbet"

Token har passeret sin levetid. Opret nyt token (Backup → Edge ISO → Klargør ny Edge) og injecér som ovenfor.

### Image-build fejler under Docker injection

Docker Desktop skal have rettigheder til privileged containers:
- Docker Desktop → Settings → General → sæt flueben ved **"Allow privileged containers"** (eller tilsvarende) → Apply & Restart

### OrangePi PC Plus booter ikke fra SD-kort

- Brug et Class 10 / A1 SD-kort (billige kort fra discount-butikker virker ofte ikke)
- Prøv at flashe igen med balenaEtcher i stedet for `dd`
- Armbian kræver at SD-kortet er korrekt unmountet inden flash

### RPi4 booter ikke fra USB SSD

USB-boot skal aktiveres i EEPROM (gøres én gang):
```bash
# Fra Raspberry Pi OS på SD-kort:
sudo raspi-config
# → Advanced Options → Bootloader Version → Latest → Finish → Reboot
```

---

## Reference — filer og paths på edge-boardet

| Sti | Indhold |
|---|---|
| `/etc/timelapse/bootstrap.yaml` | Headend URL + bootstrap token (bagt ind ved image-build) |
| `/etc/timelapse/node-agent.conf` | API token + config URL (skrevet ved enrollment) |
| `/etc/timelapse/device_keys/id_ed25519` | Device SSH private key (genereret ved første boot) |
| `/etc/timelapse/.enrolled` | Markerfil — eksisterer = enrollment er gennemført |
| `/opt/timelapse/edge/` | Timelapse agent kode |
| `/opt/timelapse/venv/` | Python virtual environment |
| `/data/` | Captures og lokal storage |
