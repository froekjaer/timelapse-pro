# TimeLapse Pro — Administratormanual (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Målgruppe:** TimeLapse Pro-administrator (Peter Frøkjær), drift, sikkerhedsansvarlig, teknisk projektleder
**Konsoliderer:** `ADMIN_MANUAL_2026-06-23.md` + `Claude_ADMIN_MANUAL_2026-06-23.md` (operationel backbone) samt `ADMINISTRATORMANUAL_2026-06-23.md` + `Codex_ADMINISTRATORMANUAL_2026-06-23.md` (governance/proces — foldet ind som §15–§19). Tidligere versioner arkiveret i `Gamle versioner/`.

---

## 1. Systemarkitektur

```
[OrangePi 4 Pro edge]  ──SFTP/HTTPS──►  [Mac Mini Headend]  ──nginx──►  [Browser UI]
    Nikon Z30 kamera                        FastAPI / PostgreSQL
    timelapse-edge service                  Ollama (AI)
    gphoto2 / GPIO relay                    /Volumes/data-fast
```

**Aktiv edge:** TL-C87FF9587CA0 (OrangePi 4 Pro, IP: 192.168.86.134, Nikon Z30)
**Headend URL (intern):** http://127.0.0.1:8000
**Headend URL (public):** https://timelapse.froekjaer.dk
**Repo:** ~/projects/timelapse-pro → /Volumes/data-fast/peter-home/projects/timelapse-pro

---

## 2. Daglig drift

### 2.1 Tjek systemstatus

```bash
# Headend health
curl http://127.0.0.1:8000/api/health

# LaunchAgent status
launchctl print gui/$(id -u)/dk.froekjaer.timelapse-headend | grep -E "state =|pid ="

# Seneste log (200 linjer)
tail -200 ~/Library/Logs/timelapse-headend.log

# PostgreSQL
pg_isready -U timelapse
```

### 2.2 Genstart Headend

```bash
# Normal genstart (samme plist)
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend

# Genindlæs plist (efter konfigurationsændring)
launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

### 2.3 Se captures og uploads

```bash
# Antal captures i dag
psql -U timelapse timelapse_db -c \
  "SELECT COUNT(*) FROM captures WHERE captured_at > NOW()-INTERVAL '24h'"

# Seneste 10 uploads
psql -U timelapse timelapse_db -c \
  "SELECT filename, uploaded, captured_at FROM captures ORDER BY id DESC LIMIT 10"

# Storage-brug
df -h /Volumes/data-fast
```

---

## 3. Headend — opsætning og konfiguration

### 3.1 Venv og services

```
Venv:             ~/.venvs/timelapse-headend/
LaunchAgent:      ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
Arbejdsmappe:     ~/projects/timelapse-pro/headend/
Log:              ~/Library/Logs/timelapse-headend.log
Captures:         /Volumes/data-fast/
Artifacts:        /Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/
```

### 3.2 Miljøvariable (i LaunchAgent plist)

| Variabel | Formål |
|---|---|
| `JWT_SECRET` | Signering af JWT-tokens (skal være stabilt på tværs af genstarter) |
| `BREAK_GLASS_ENC_KEY` | Krypteringsnøgle til break-glass funktion |
| `DATABASE_URL` | PostgreSQL-forbindelsesstring |
| `TIMELAPSE_GPG_KEY` | GPG-nøgle-ID til artifact-signering |

> **VIGTIGT:** Disse secrets må IKKE committes til Git. Prod-plist'en ligger i `~/Library/LaunchAgents/` og er ikke i repo.

### 3.3 Opdater headend-kode (ny version)

```bash
cd ~/projects/timelapse-pro
git pull origin main

# Geninstaller Python-dependencies hvis nødvendigt
~/.venvs/timelapse-headend/bin/pip install -r headend/requirements.txt --break-system-packages

# Byg ny UI
cd timelapse-ui && npm install && npm run build && cd ..

# Genstart headend
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend
```

---

## 4. Edge-management

### 4.1 SSH adgang til edge

```bash
# Via reverse tunnel (anbefalet — virker selv uden direkte netværksadgang)
# Åbn tunnel fra headend-UI: Admin → CMDB → [device] → SSH Tunnel
ssh -p <tunnel-port> pi@127.0.0.1

# Direkte SSH (kræver lokal netværksadgang)
ssh pi@192.168.86.134
```

### 4.2 Se edge-logs

```bash
# Via SSH til edge
sudo journalctl -u timelapse-edge -f
sudo journalctl -u timelapse-edge --since "1 hour ago"
```

### 4.3 Manuelt billede nu

```bash
# Via SSH til edge
sudo systemctl stop timelapse-edge
cd /opt/timelapse/edge
sudo /opt/timelapse/venv/bin/python agent.py --capture-once
sudo systemctl start timelapse-edge
```

### 4.4 Edge-konfiguration

Konfigurationen administreres fra **Admin UI → Global Config**. Hierarki:
1. Global default
2. Kunde-override
3. Site-override
4. Kamera-override (vinder)

Skift interval (fx til hvert 5. minut):
- Gå til Global Config
- Vælg kunde/site/kamera
- Sæt `capture_interval_seconds = 300` på det ønskede lag

---

## 5. Provisioning af ny edge-enhed

### 5.1 Byg disk image

1. Gå til **Admin UI → Backup → Edge disk image**
2. Vælg target hardware (OrangePi 4 Pro), kunde og kamera-lokation
3. Indtast WiFi SSID og password
4. Klik **"Byg image"** — processen tager 15–30 min
5. Download det færdige `.img.gz`-image fra listen "Færdige images"

### 5.2 Flash image

```bash
# Udpak og flash til SD-kort (erstat /dev/diskN med korrekt disk)
gunzip -c timelapse-edge-orangepi4pro-*.img.gz | sudo dd of=/dev/diskN bs=4m status=progress
```

### 5.3 Første boot

1. Indsæt SD-kort i OrangePi 4 Pro
2. Boot — enheden finder automatisk WiFi og registrerer sig mod Headend
3. Bekræft i **Admin UI → CMDB** at ny enhed dukker op
4. Tildel kamera-lokation i **Admin UI → Kameraer**

---

## 6. Update-flow

### 6.1 App-opdatering til edge

1. CI på GitHub bygger ny version og opretter change ticket
2. Gå til **Admin UI → Updates**
3. Review change ticket (type, scope, version, teststatus)
4. Klik **"Godkend"** — edge henter og installerer automatisk ved næste maintenance window
5. Bekræft i CMDB at edge rapporterer ny version

### 6.2 OS-sikkerhedsopdatering

1. CMDB opdager tilgængelige pakke-opdateringer automatisk
2. System opretter `os_security` update med change ticket
3. Review og godkend som ovenfor
4. Edge-agenten installerer via offline apt-bundle (ingen internet fra edge)

### 6.3 Rollback

Hvis en opdatering fejler, ruller edge automatisk tilbage til forrige version. Status vises i **Admin UI → Updates** som `rolled_back`. Undersøg fejl i CMDB-log.

---

## 7. GPG og artifact-signering

```bash
# Verificer GPG-nøgle er til stede
gpg --list-secret-keys F75C248F694C097F

# Test signering
echo "test" | gpg --clearsign --default-key F75C248F694C097F

# Verificer signeret artifact
gpg --verify TL-EDGE-IMG-*.manifest.json.sig

# Vis trust niveau
gpg --edit-key F75C248F694C097F
# > trust (skal være "ultimate" for headend-nøglen)
```

> Nøglen er i `~/.gnupg` (peter's keyring, IKKE root). Backup nøglen offline.

---

## 8. Backup

### 8.1 Manuel backup

```bash
# Backup til /Volumes/Backup (kør fra headend)
# Trigger via Admin UI → Backup → Kør backup nu
```

### 8.2 Verificer backup

```bash
ls -la /Volumes/Backup/timelapse/
# Bekræft nyeste backup er inden for de seneste 24 timer
```

### 8.3 Restore (procedure)

```bash
# STOP headend først
launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend

# Restore PostgreSQL
pg_restore -U timelapse -d timelapse_db /Volumes/Backup/timelapse/db/latest.dump

# Restore captures (rsync fra backup)
rsync -avz /Volumes/Backup/timelapse/captures/ /Volumes/data-fast/

# Genstart headend
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

---

## 9. nginx og offentlig adgang

### 9.1 Konfigurationsfil

```
~/projects/timelapse-pro/deploy/nginx/timelapse.froekjaer.dk.conf
```

Kopier til og reload:
```bash
sudo cp deploy/nginx/timelapse.froekjaer.dk.conf \
  /opt/homebrew/etc/nginx/nginx.conf
brew services restart nginx
# eller
sudo nginx -s reload
```

### 9.2 TLS-certifikat fornyelse

```bash
# Let's Encrypt via certbot
sudo certbot renew --webroot -w /private/tmp/timelapse-acme-webroot
sudo nginx -s reload
```

### 9.3 Tjek nginx status

```bash
brew services info nginx
sudo nginx -t  # Konfigurationstest
tail -50 /opt/homebrew/var/log/nginx-timelapse-access.log
tail -50 /opt/homebrew/var/log/nginx-timelapse-error.log
```

---

## 10. Databaseadministration

```bash
# Log ind i PostgreSQL
psql -U timelapse timelapse_db

# Se captures pr. kamera
SELECT d.device_id, COUNT(*) as captures
FROM captures c JOIN devices d ON c.device_id = d.id
GROUP BY d.device_id;

# Se aktive brugere
SELECT username, role, last_login FROM users ORDER BY last_login DESC;

# Se pending updates
SELECT id, update_type, status, created_at FROM pending_updates ORDER BY id DESC LIMIT 10;

# Opret ny bruger (via API er bedre)
INSERT INTO users (username, hashed_password, role, customer_id)
VALUES ('ny_bruger', '<bcrypt-hash>', 'viewer', 1);
```

---

## 11. Brugerstyring

### 11.1 Opret bruger

1. Log ind med super_admin-konto
2. Gå til **Admin UI → Brugere**
3. Klik **"Opret bruger"**
4. Angiv brugernavn, rolle og evt. customer_id

### 11.2 Roller

| Rolle | Adgang |
|---|---|
| `viewer` | Læs billeder, CMDB (read-only) |
| `operator` | Viewer + kamera-status, SSH tunnel (read) |
| `admin` | Operator + updates, config, konfiguration (per customer) |
| `super_admin` | Fuld adgang til alt |

### 11.3 Nulstil password

```bash
# Via API (kræver super_admin-token)
curl -X POST https://timelapse.froekjaer.dk/api/admin/users/<id>/reset-password \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"new_password": "nyt-password"}'
```

---

## 12. Troubleshooting

### Headend starter ikke

```bash
# Se fejl
tail -100 ~/Library/Logs/timelapse-headend.log

# Check venv
~/.venvs/timelapse-headend/bin/python -c "import fastapi; print('OK')"

# Check PostgreSQL
pg_isready -U timelapse
psql -U timelapse timelapse_db -c "SELECT 1"

# Check disk mount
ls /Volumes/data-fast/
```

### Edge uploader ikke

```bash
# Via SSH til edge
sudo journalctl -u timelapse-edge --since "1 hour ago" | grep -i "error\|upload\|sftp"

# Test SFTP manuelt fra edge
sftp -P 22222 sftp_nvj17c@timelapse.froekjaer.dk
```

### CI fejler

```bash
# Se GitHub Actions log
open https://github.com/[repo]/actions

# Lokal test
cd ~/projects/timelapse-pro
pytest tests/ -v
cd timelapse-ui && npm run build && npx tsc --noEmit
```

### GPG-signering fejler

```bash
# Tjek nøgle
gpg --list-secret-keys
# Skal vise F75C248F694C097F

# Tjek trust
gpg --edit-key F75C248F694C097F
> trust
# Skal vise "ultimate"
```

---

## 13. Sikkerhedsprocedurer

### 13.1 Kompromitteret edge-enhed

1. Revokér edge-credentials i **Admin UI → Key Management → [device] → Revokér**
2. Sæt deny-flag på SSH-tunnel: **Admin UI → CMDB → [device] → Forbyd tunnel**
3. Notér hændelsen i incident-log (opret ny fil i Dokumentation/)
4. Udsted ny enhed med nyt keypair via provisioning-flow

### 13.2 Mistanke om uautoriseret adgang til UI

1. Invalider alle sessioner ved at ændre `JWT_SECRET` i LaunchAgent og genstarte
2. Tjek login-log i PostgreSQL: `SELECT * FROM login_events ORDER BY created_at DESC LIMIT 50;`
3. Deaktiver kompromitteret brugerkonto
4. Kontakt eventuel kunde

### 13.3 Rotation af JWT_SECRET

```bash
# Generer ny secret
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Opdater i LaunchAgent plist
nano ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
# Ændr JWT_SECRET-værdien

# Genindlæs (invaliderer alle eksisterende sessions)
launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
```

---

## 14. Vigtige stier og referencer

| Ressource | Sti |
|---|---|
| Repo | ~/projects/timelapse-pro |
| Headend kode | ~/projects/timelapse-pro/headend/ |
| UI kildekode | ~/projects/timelapse-pro/timelapse-ui/ |
| UI dist (nginx) | ~/projects/timelapse-pro/timelapse-ui/dist/ |
| LaunchAgent | ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist |
| Log | ~/Library/Logs/timelapse-headend.log |
| Venv | ~/.venvs/timelapse-headend/ |
| Captures | /Volumes/data-fast/ |
| Backup | /Volumes/Backup/ |
| Edge images | /Volumes/data-fast/peter-home/timelapse-artifacts/edge-images/ |
| Base image cache | ~/projects/timelapse-pro/.base_image_cache/ |
| nginx config | deploy/nginx/timelapse.froekjaer.dk.conf |
| GPG keyring | ~/.gnupg/ (nøgle: F75C248F694C097F) |
| GCP credentials | ~/projects/timelapse-pro/secrets/gcp-service-account.json |
| Dokumentation | ~/projects/timelapse-pro/Dokumentation/ |

---

## 15. Roller og RBAC (governance)

Ud over rollerne i §11.2 opererer governance-dokumentationen med rollen `technician` (mellem operator og admin). Adminopgaver: opret bruger → tildel rolle + evt. kunde-scope → aktivér MFA/WebAuthn for admin/high-risk → gennemgå brugerliste jævnligt → fjern/deaktivér ubrugte konti → gennemgå audit-logs. Før Internet-go-live skal super_admin-password være ændret fra default, og højrisiko-operationer bør kræve MFA.

## 16. Startup-preflight (før production)

Headend skal ved opstart verificere: `/Volumes/data-fast` monteret (forventet mount/UUID), skriveadgang til capture-root, nok ledig disk, PostgreSQL kører, Headend health svarer, node-agent kører, nginx på prod-kompliant portmodel.

## 17. Kunde/site/kamera-model og Global Config

Datamodel: `devices` (fysisk edge/node), `cameras` (logisk kamera-lokation), `device_assignments` (binding). Ny installation: opret kunde → site → kamera-lokation → generér bootstrap token → klargør edge image/lokal provisioning → bind edge til kamera-lokation → verificér heartbeat → verificér preview/full capture/upload.

Global Config arves i fire lag: `global → kunde → site → kamera` (lavere lag vinder). UI skal vise arvet værdi, direkte override, effektiv værdi, vindende lag og farvemarkering for afvigelse fra global. Brug kamera-laget til relay power, ISO, fokusstrategi, storage-overrides og Nikon Z30-profildata.

## 18. CMDB, SBOM og GRC (detaljeret)

**CMDB** skal vise: installeret OS/version, systempakker, Python/venv-pakker, TimeLapse Pro-version, hardware model, firmware/kernel, seneste tilgængelige version, risikoklassifikation, update-status, evidence-freshness.

**SBOM** genereres ved: edge image build, TimeLapse Pro release, OS bundle build, større Headend dependency-update — og linkes til change ticket + artifact.

**GRC/compliance-dashboard** skal kunne rapportere mod: SABSA business attributes, ISO 27001 control evidence, IEC 62443 zones/conduits + patching, CRA secure update/SBOM/lifecycle, NIS2 risk/continuity/supply-chain, GDPR DPIA/retention/access. Før første kunde-site: DPIA-template klar, retention pr. kamera sætbar, databehandleraftale-template klar, subprocessor-liste dokumenteret (især Gemini/Google Cloud).

## 19. Kendte tekniske gældspunkter (governance-backlog)

- ~~`slowapi` importeres i backend men mangler i `headend/requirements.txt`~~ — **Rettet, committet (`b0e224c`) og live-verificeret 2026-07-03** (Claude/Peter): `requirements.txt` er pinnet til konkrete versioner (var 100% upinnet), `slowapi` tilføjet, installeret i prod-venv.
- ~~`/api/siem/*` havde ingen autentificering; CMDB/ITIM's lokale RBAC-broer håndhævede rolle men ikke MFA-politikken~~ — **Rettet, committet (`b0e224c`) og live-verificeret 2026-07-03** (Claude fandt+rettede, Peter deployede: health `200`, `GET /api/siem/events` uden auth → `401`). Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.1-§2.3.
- ~~`Capture` var kun knyttet til fysisk `device_id`, ikke logisk kamera-lokation — en defekt Edge kunne ikke udskiftes uden reelt at bryde sammenhængen mellem billedhistorik og lokation~~ — **Rettet, committet (`3a2c0a8`) og verificeret 2026-07-03** (Claude): schema-migration v12 (`Capture.camera_id`/`customer_id`), resolver der udfylder felterne automatisk ved skrivning, additivt `camera_id`-filter på `GET /api/admin/captures`, samt `headend/tools/backfill_capture_camera_customer.py` (default `--dry-run`) til historiske rækker. Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.4/§2.5. **NB:** backfillen Peter kørte 2026-07-03 (Travbyen/Nordre Villavej) var Codex' `backfill_capture_metadata.py` (EXIF/GPS) — `backfill_capture_camera_customer.py` afventer stadig en `--dry-run` mod produktion. **Åbent:** en dedikeret kamera-lokations-UI-side (fuld billedhistorik på tværs af Edge-udskiftninger) er ikke bygget.
- ~~Tenant-isolation på billeddata var udelukkende et live device→kunde-opslag~~ — **Fase 3, rettet i kode 2026-07-03** (Claude, godkendt af Peter): under implementeringen blev en konkret, udnyttelig kryds-kunde-lækage fundet (R16 i `RISK_ASSESSMENT_v10.md`) — en fysisk Edge-enhed, der genbruges og tildeles en ny kunde, gav tidligere den nye kunde adgang til den forrige kundes billedhistorik. Adgangskontrollen (`_capture_is_allowed`/`_capture_tenant_clause` i `main.py`) bruger nu `Capture.customer_id` (frosset ved optagelsestidspunkt) som primær kilde, med fallback for endnu ubackfillede rækker. Verificeret med TestClient. Afventer commit + live-verifikation.
- deploy LaunchAgent-template er ikke opdateret til aktiv venv/model.
- frontend lint-baseline er ikke grøn.
- Open WebUI skal besluttes som prod-komponent eller lab-only.
- postprocessing af manglende thumbnails skal gøres robust.
- per-target update-status skal vises tydeligere i UI.
- intern CA/mTLS er ikke implementeret.
- video-stream via reverse SSH extra forward + Nikon focus step/slice QA er åbne (jf. LAB, §4/§6).

---

*Se også: RISK_ASSESSMENT_v10.md, GO_LIVE_CHECKLIST_v10.md, HANDOVER_LOG.md, 00_START_HER.md*
