# TimeLapse Pro — Installationsmanual: Ny Edge (flashbart image ELLER oven på eksisterende Linux)

**Version:** v1.1 · 2026-07-24 · **Forfattere:** Claude/Codex · **Status:** OrangePi 4 Pro image-input er checksum-pinnet og image-flowet er fail-closed. RPi 5 er blokeret, indtil leverandørarchivet har en valideret SHA-256. Jetson kræver et Headend-genereret offline wheelhouse.
**To spor:**
- **Spor A (primært):** Flashbart disk-image (`.img.gz` — "ISO'en") genereret af headenden, med alt bagt ind. Zero-touch: flash → strøm → enheden enroller selv.
- **Spor B:** Installation **oven på et eksisterende Linux-system** (i dag: Jetson/JetPack via `install_timelapse_edge.sh`; mønsteret er generaliserbart).

**Relaterede dokumenter:** `Installationsguide_v10.md` Del B/C (detaljer + skærmbilleder-niveau), `TimeLapse_Edge_Runbook_v10.md` (drift), `PROVISIONERING_EDGE_OG_MAC_HEADEND_v1.md`.

---

## 1. Fælles forudsætninger (begge spor)

- Headend kører og er tilgængelig fra edge-netværket; du er logget ind som admin.
- Kunde/site (og evt. kamera-lokation) er oprettet i UI'et — så bootstrap-tokenet kan bindes til lokationen og enheden auto-tildeles ved enrollment.
- **Understøttet hardware:** OrangePi 4 Pro (primær), OrangePi PC Plus og
  RPi 4 har pinned base-archive. RPi 5 vises som blokeret, indtil checksum er
  registreret. Jetson Orin Nano bruger det separate offline-spor.
- Ved ny staging/prod-headend: gennemfør headend-manualens §7 (SFTP 22222 +
  settings) FØRST. Port 22 er afvist i generatoren.

## 2. Trin 1 — Klargør provisionering på headenden (fælles)

UI: **Backup → Edge ISO → "Klargør ny Edge"** (eller `POST /api/edge/provisioning/prepare`):

1. Udfyld kunde/site/kamera-navn, netværk (Ethernet/WiFi/4G — WiFi-SSID/password hvis relevant).
2. Klik "Klargør Edge" → notér **bootstrap-token** (engangs, default 48 t gyldighed, max 14 dage).
3. Headenden genererer samtidig SSH-nøglepar + reverse-tunnel-port til enheden og gemmer netværkskonfig på kamera-lokationen.

Tokenet er en hemmelighed. Ét token = én enhed (batch-tokens findes til serieproduktion).

---

## 3. Spor A — Flashbart image (.img.gz)

### 3.1 Byg image

UI: **Backup → Edge ISO → "Edge disk image"**:

1. Vælg hardware-target (fx `orangepi4pro`) og mode **"Flashbart .img.gz"**.
2. Indsæt bootstrap-tokenet fra trin 2 → "Byg flashbart image".
3. Kræver **Docker Desktop** kørende på headend-maskinen (buildx). Byggetid: adskillige minutter; følg progress-loggen.
4. Download `.img.gz` når build + injection er færdig. Manifest (GPG-signeret, med SBOM) registreres som artifact.

Buildet stopper, hvis base-archivets SHA-256 ikke matcher target-profilen, SBOM
er tom, GPG-nøglen mangler, eller Edge-buildinput har uncommittede ændringer.
Der findes ingen hash-only-signaturfallback.

Hvad der bages ind i imaget: bootstrap.yaml (device-hint, headend-URL, token), WiFi-credentials, headend'ens SSH-pubkey, enhedens SSH-privatnøgle + tunnel-port.

**⚠️ SIKKERHEDSREGEL (GEN-09): Et flashbart image er en komplet credential-pakke.** Behandl det som en hemmelighed: flyt det ikke ud af kontrolleret storage, del det aldrig, og **slet den downloadede kopi efter flash**. Tokenet udløber af sig selv, men SSH-nøglen og WiFi-passwordet gør ikke.

### 3.2 Flash

```bash
# macOS/Linux (find disken FØRST med diskutil list / lsblk — dd er nådesløs):
gunzip -c timelapse-edge-<target>-<ver>.img.gz | sudo dd of=/dev/diskX bs=4m status=progress
# eller balenaEtcher (alle platforme) — kan flashe .img.gz direkte
```

Medie pr. board: se Installationsguide_v10 Del B (OrangePi 4 Pro: NVMe/SD; PC Plus: SD/eMMC; RPi: SD).

### 3.3 Første boot — zero-touch

1. Sæt medie i boardet, tilslut kamera (USB) og strøm.
2. `timelapse-bootstrap.service` kalder `POST /api/devices/enroll` med tokenet: enheden får API-credential (HMAC/request-signering aktiveret), gamle credentials roteres, og enheden auto-tildeles kamera-lokationen hvis tokenet var bundet til én.
3. Enheden dukker op under **Enheder** (state `active`, eller `unassigned` hvis tokenet ikke havde site → tildel manuelt: Enheder → vælg site → "Tildel").

### 3.4 Verifikation

- Enheder-listen: enheden online, heartbeat < 5 min.
- CMDB: inventory + SBOM rapporteret af node-agent.
- Første capture/preview kommer ind (LAB-siden eller galleri).
- Tunnel: "Åbn tunnel" fra Enheder-siden virker (⚠️ på staging/prod: kræver at tunnel-ingress er afklaret — GEN-03).
- Baseline edge-backup registreret (Drift & Resilience), jf. prepare-svarets next_steps.

---

## 4. Spor B — Oven på eksisterende Linux (Jetson)

Jetson Orin Nano på JetPack 6.x installeres uden direkte internetadgang. Før
kørsel skal Headend/lab producere et komplet wheelhouse til Jetsons arkitektur.
Installeren accepterer kun en GPG-verificeret, detached release.

```bash
# Kopiér installeren til enheden:
scp headend/tools/hardware/jetson-orin-nano/install_timelapse_edge.sh <bruger>@<enhed>:

# Kør som root med token fra trin 2:
sudo bash install_timelapse_edge.sh \
  --headend-url https://<backend-domæne>:8443/api \
  --bootstrap-token-file /secure/bootstrap-token \
  --release-dir /media/timelapse/release \
  --release-tag v<X.Y.Z> \
  --expected-commit <fuld-40-tegns-SHA> \
  --wheelhouse /media/timelapse/wheelhouse
```

Installeren kører ikke `apt-get`, `pip` mod internettet eller GitHub. Den
verificerer tag, SHA, clean release, tokenformat og installerer Python-pakker
med `--no-index` fra wheelhouse. Mangler et input, stopper installationen.

**Verifikation:** som §3.4, plus `systemctl status timelapse-edge` på enheden og `edge/tools/bootstrap_cli.py doctor` (lokal diagnose af services/netværk/kamera — se Installationsguide_v10 Del C for CLI/AP-mode-detaljer).

**⚠️ Bemærk ved staging/prod-headend:** brug altid `https://<domæne>:8443/api` som `--headend-url` (aldrig portløst — CrushFTP ejer 443).

---

## 5. Fejlfinding (hyppigste)

| Symptom | Sandsynlig årsag |
|---|---|
| Enheden dukker aldrig op i Enheder | Token udløbet/allerede brugt (engangslogik) — klargør ny; eller enheden kan ikke nå headend-URL'en (test `curl <headend-url>/health` fra nettet enheden står på) |
| `401 Ugyldigt bootstrap token` | Tokenet er revokeret (ny klargøring for samme lokation revokerer åbne tokens) — brug det NYESTE |
| Enrollment ok, men ingen billeder | Kamera-USB, eller upload-vej: tjek at `sftp.port` i enhedens config er 22222 og API-upload svarer (⚠️ GEN-02) |
| Build fejler straks | Docker Desktop kører ikke på headend-maskinen |
| Target vises blokeret | Base-image mangler en valideret SHA-256; registrér aldrig en rolling/latest-fil uden pin |
| Jetson stopper ved wheelhouse | Offline wheelhouse er ikke komplet for JetPack/arm64; byg og test det i lab |
| Tunnel virker ikke | Tunnel-ingress ikke opsat på headenden (GEN-03) eller reverse-port-konflikt (GEN-04) |

Mere: `FAQ_og_fejlsøgning.md`, `TimeLapse_Edge_Runbook_v10.md`.

---

*Denne manual er den korte, autoritative arbejdsgang; Installationsguide_v10 Del B/C har de udførlige skridt. Ved uoverensstemmelse: nyeste dokument vinder, og afvigelsen meldes i HANDOVER_LOG.*
