# TimeLapse Pro — Administratormanual (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02 (opdateret 2026-07-06 med juli-sikkerhedsforbedringer)
**Målgruppe:** TimeLapse Pro-administrator (Peter Frøkjær), drift, sikkerhedsansvarlig, teknisk projektleder
**Konsoliderer:** `ADMIN_MANUAL_2026-06-23.md` + `Claude_ADMIN_MANUAL_2026-06-23.md` (operationel backbone) samt `ADMINISTRATORMANUAL_2026-06-23.md` + `Codex_ADMINISTRATORMANUAL_2026-06-23.md` (governance/proces — foldet ind som §15–§19). Tidligere versioner arkiveret i `Gamle versioner/`.

**Seneste ændringer (2026-07-06):** Tilføjet §1.5 med nye sikkerheds- og compliance-opdateringer: M-05 agent-lockdown, R17 debug/lab mode forbedringer, G-05 download-/adgangslog, R09 backup forbedringer.

**Se også:** `MENUGUIDE_ADMIN_v1.md` — menu-for-menu beskrivelse af alle admin-sider og undermenuer (felt-for-felt, inkl. Lokal adgang, Import, SIEM, GDPR Sløring og Drift). `FAQ_og_fejlsøgning.md` — selvbetjenings-fejlfinding.

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

## 1.5 Nye sikkerheds- og compliance-opdateringer (juli 2026)

Følgende væsentlige sikkerheds- og compliance-forbedringer er implementeret i juli 2026 og bør være en del af administratorviden:

### 1.5.1 M-05: Agent-role lockdown (PR #2)

**Status:** Kode skrevet, testet (24/24 tests passed), committet, PR #2 åben, afventer review+merge.

**Formål:** Forhindre at AI-agenter (Claude/Codex) ved en fejl kan få adgang til staging/production-systemer. Implementerer en "default-deny" politik med hård kodespærre.

**Implementering:**
- Ny reserveret rolle `role="agent"` i User-model
- `_agent_role_blocked_in_this_environment()` afviser agent-login i staging/prod/production miljøer
- Håndhævet to steder: `/api/auth/login` (før password-tjek) og `get_current_user()` (central auth-guard)
- SIEM-logging ved opstart (`_log_agent_lockdown_status()`)

**Forudsætning:** `TIMELAPSE_ENV` skal være sat korrekt (`rd`/`staging`/`prod`).

**Dokumentation:** Se `GO_LIVE_CHECKLIST_v10.md` §M, `RISK_ASSESSMENT_v10.md` R19.

### 1.5.2 R17: Debug/lab mode forbedringer

**Status:** Kode deployet (commit `44b78fb7`), health 200 OK, manuel smoketest udestår.

**Problem:** Lab mode (`debug_mode.enabled`) kunne efterlades aktiveret uden nogen synlighed eller automatisk slukning, hvilket gav operationel risiko (konstant relæ-belastning, GPS-problemer).

**Løsning:**
- CMDB-dashboard indikator: `debug_mode_enabled`/`debug_mode_enabled_at` badge i SystemAdminPage og LabPage
- Auto-timeout: `_debug_mode_auto_timeout_loop()` slukker automatisk efter `TIMELAPSE_DEBUG_MODE_MAX_HOURS` (default 8t)
- SIEM-logging: `debug_mode_change` og `debug_mode_auto_timeout` events logges med ikon/label

**Dokumentation:** Se `RISK_ASSESSMENT_v10.md` R17.

### 1.5.3 G-05: Download-/adgangslog pr. billede

**Status:** Implementeret og testverificeret (4/4 tests + 41/41 total tests passed).

**Formål:** GDPR-compliance — log hvornår et billede downloades (fuld opløsning), af hvem, til hvilken kunde/site.

**Implementering:**
- Ny `CaptureAccessLog`-tabel (`capture_id`, `accessed_at`, `user_id`, `customer_id`, `site_id`, `purpose`)
- `_log_capture_access()` kaldes fra `GET /api/images/{device_id}/{filename}`
- Kun fuldopløsningsbilleder logges (thumbnails ikke)

**Dokumentation:** Se `GO_LIVE_CHECKLIST_v10.md` §G-05, `KRAVREGISTER_og_STATUS_v10.md` CAP-008/ADM-012.

### 1.5.4 R09: Backup og resilience forbedringer

**Status:** Kode klar (2026-07-04 nat), IKKE bekræftet kørt i produktion — kræver verifikation.

**Problem:** Billedbackup (`backup_include_images`) fandtes i UI, men blev aldrig læst af `_run_backup_archive()`. Derfor blev 27.000+ produktionsbilleder ALDRIG backet op. Også `backup_auto_interval` blev ikke brugt — ingen automatisk backup.

**Løsning:**
- `_get_backup_include_images()` wired ind i `_run_backup_archive()` — rsync af `_sftp_base_path()` til `{base_dir}/timelapse-images-mirror/`
- `_backup_auto_loop()` tjekker `backup_auto_interval` hvert 10. min og kører automatisk backup ved `daily`/`weekly`

**VIGTIGT:** Peter/Codex bør manuelt trigge en backup og bekræfte at billed-mirror opfører som forventet på Mac Mini'en.

**Fortsat åbent:** Off-site/3-2-1-kopi, reel restore-test, RTO/RPO-dokumentation.

**Dokumentation:** Se `RISK_ASSESSMENT_v10.md` R09, `GO_LIVE_CHECKLIST_v10.md` §E.

### 1.5.5 P0-05: Retention Policy (GDPR G-02)

**Status:** Implementeret og testet (2026-07-07) — backend, UI og tests 100% komplet.

**Formål:** GDPR-compliant automatisk sletning af gamle billeder. Forhindrer uendelig lagring af persondata og sikrer at data slettes når retentionsperioden udløber.

**Implementering:**
- Database migration v15: `Camera.retention_days` (default 365 dage) + `CaptureDeletionLog` tabel
- Backend cleanup loop: `_retention_cleanup_loop()` og `_run_retention_cleanup()` i main.py
- API endpoints:
  - `POST /api/admin/retention/trigger` — manuelt trigger cleanup
  - `GET /api/admin/retention/status` — se status, progress og deleted_count
  - `GET/PUT /api/admin/retention/settings` — konfigurer cleanup interval
  - `GET /api/admin/retention/deletion-log` — revisionslog (pagineret, filtrérbar)
- Frontend UI: `RetentionPage.tsx` med tre tabs (status/settings/deletion-log)
- Per-kamera config: `CameraPage.tsx` "Retention (dage)" felt

**Betjening:**
1. Gå til **Retention** i menuen (admin/super_admin).
2. **Status-tab:** Se om cleanup kører, progress log og antal slettede captures.
3. **Indstillinger-tab:** Vælg cleanup interval (manuel/dagligt/ugentligt/månedligt).
4. **Sletningslog-tab:** Filtrer på kamera/device, se alle sletninger med detaljer.

**Per-kamera retention:**
- Hvert kamera har sin egen `retention_days` værdi (default: 365).
- Ændr via kamera-konfiguration → "Kamera identitet" → "Retention (dage)".
- `NULL` deaktiverer automatisk sletning for det specifikke kamera.

**Sikkerhed og compliance:**
- Sletning er permanent — ingen gendannelse mulig.
- Alle sletninger logges med: capture_id, device_id, camera_id, filename, deleted_at, deletion_reason, retention_days, performed_by.
- Downloadlog (`CaptureAccessLog`) sporer hvem der har adgang til billeder før sletning.

**Test:**
- Unit tests: 8/8 bestået (pytest `tests/test_retention_policy.py -m "not integration"`)
- Integration tests: 10 klar (kræver kørende headend)

**Dokumentation:** Se BRUGERMANUAL v10 §7.2, `tests/test_retention_policy.py`.

### 1.5.6 SEC-013: Incident Response Procedure

**Status:** Procedure oprettet (2026-07-07) — ikke testet i praksis endnu.

**Formål:** Struktureret incident response med GDPR Art. 33/34 notifikationskrav (72 timer).

**Implementering:**
- `SEC-013_Incident_Response_Procedure.md` med klassifikation, triage, containment, recovery
- GDPR notifikationskrav: Art. 33 (tilsynsførhed inden 72t) og Art. 34 (registrerede uden unødig forsinkelse)
- Template for incident log og post-incident review
- Klassifikationer: Low/Medium/High/Critical med tidsfrister

**Anvendelse ved incident:**
1. Klassificer incident (Low/Medium/High/Critical)
2. Triage og containment (isolér berørte systemer)
3. Recovery (gendannelse fra backup hvis nødvendigt)
4. GDPR notifikation (inden 72t for persondata-incidents)
5. Post-incident review og læring

**Dokumentation:** Se `SEC-013_Incident_Response_Procedure.md`, `GO_LIVE_CHECKLIST_v10.md` §G-06, `RISK_ASSESSMENT_v10.md` R20.

### 1.5.7 SEC-014: Vulnerability Handling og CVE-proces

**Status:** Procedure oprettet (2026-07-07) — ikke testet i praksis endnu.

**Formål:** Struktureret håndtering af sårbarheder (CVE) med patch process og rollback plan.

**Implementering:**
- `SEC-014_Vulnerability_Handling_CVE_Process.md` med CVE overvågning, triage, patch process
- Kilder: NVD (National Vulnerability Database), vendor advisories, GitHub Security Advisories
- Triage: Severity (Low/Medium/High/Critical), eksponering, impact
- Patch process: Test i staging → patch → verify → monitor
- Rollback plan: Hurtig tilbagefald til tidligere version hvis patch fejler

**CVE-håndtering:**
1. Overvåg CVE kilder (dagligt/ugentligt)
2. Triage: Er systemet eksponeret? Hvor alvorlig er sårbarheden?
3. Prioritér: Critical/High først, derefter Medium/Low
4. Patch i test-miljø først (staging/rd)
5. Deploy til production med rollback plan klar
6. Verificer at patch løser problemet
7. Dokumenter i change ticket

**Dokumentation:** Se `SEC-014_Vulnerability_Handling_CVE_Process.md`, `GO_LIVE_CHECKLIST_v10.md` §G-08.

### 1.5.8 F-012: Site-Wide Look Matching (2026-07-12)

**Status:** ✅ **Go-Live Approved** — Fully implemented, tested (127/127 passed), documented.

**Formål:** Sikrer at alle kameraer på et site producerer timelapse-videoer med ensartede farver og eksponering. Uden denne funktion ville Nikon Z30 kameraer producere varme, mættede billeder, mens Canon EOS kameraer ville producere køligere, neutrale billeder — med synlige farvespring når klipper mellem kameravinkler.

**Implementering:**
- **Golden Reference Frame:** Site-bred farvestandard skabt fra høj-kvalitet capture (>= 75% quality score)
- **Per-Camera LUTs:** Farvetransformationer (Look-Up Tables) beregnet for hvert kamera
- **Capture Hints:** Realtids anbefalinger til kameraindstillinger (WB, Picture Control, EV)
- **Match Quality Scoring:** 0-100% score der viser hvor godt kamera matcher reference
- **Camera-Specific Profiles:** Optimeret for Nikon Z30 og Canon EOS 1300D/2000D
- **Quality Threshold:** Reference oprettes kun fra captures med score >= 75%
- **Fallback Mode:** Graceful degradation hvis reference ikke er tilgængelig

**Database-driven Configuration:**
- Hierarkisk konfiguration: global → kunde → site → kamera (lavere niveau vinder)
- Edge caching med TTL (default 24 timer)
- Audit logging af alle konfigurationsændringer
- API endpoints til CRUD operations på config

**Teknisk placering:**
- `edge/ai/site_look_manager.py` — Core engine (600+ lines)
- `edge/ai/autonomous_optimizer.py` — Integration point
- `headend/services/site_look_config_service.py` — Database service
- `headend/api/site_look_config_api.py` — Admin API
- `timelapse-ui/src/components/SiteLookConfigPanel.tsx` — UI config panel
- `timelapse-ui/src/components/SiteLookCard.tsx` — Device view component

**API endpoints (admin):**
- `GET /api/admin/site-look/health` — Health check
- `GET/PUT/DELETE /api/admin/site-look/config` — CRUD på konfiguration
- `GET /api/admin/site-look/edge/{id}/config` — Edge cache fetch
- `GET /api/admin/site-look/audit/log` — Audit log

**Test results:**
- Unit tests: 72/72 passed
- Integration tests: 15/15 passed
- Manual checklist: 26/26 passed
- Config service tests: 14/14 passed
- **TOTAL: 127/127 passed**

**Performance:**
- Reference creation: < 200ms (actual: < 100ms)
- LUT generation: < 150ms (actual: < 100ms)
- Feature extraction: < 50ms
- Config resolution: < 100ms (actual: < 50ms)
- Edge cache fetch: < 50ms (actual: < 20ms)

**Betjening (administrator):**
1. Gå til **Settings → Site-Wide Look Matching**
2. Konfigurer hierarkisk konfiguration (global/kunde/site/kamera)
3. Set `enabled: true` for at aktivere
4. Adjust `reference_quality_threshold` (default: 75.0%)
5. Configure `auto_create_reference` og `auto_update_reference`
6. Set LUT regeneration interval (default: 168 timer/uge)

**Betjening (slutbruger):**
1. Gå til **Devices → Vælg kamera**
2. Se **SiteLookCard** i kolonne 5
3. Hvis ingen site reference: Klik "Opret Site Reference" (kræver quality >= 75%)
4. Når reference findes: Klik "Regenerer Kamera LUT"
5. Følg capture hints (Picture Control, WB Kelvin, EV)

**Troubleshooting:**
- Ingen reference oprettet? Tjek at captures har quality score >= 75%
- Lav match quality? Tjek at alle kameraer har lignende belysning og WB
- Capture hints virker ikke? Tjek `edge_ai_policy.allow_camera_commands: true`

**Dokumentation:** Se `docs/feature-site-look-matching.md`, `docs/admin-guide-site-look-matching.md`, `docs/user-guide-site-look-matching.md`, `docs/risk-assessment-site-look-matching.md`, `docs/go-live-status-f012-site-look-matching.md`.

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

### 2.4 Compliance, backup og resilience-status

Administrations-UI'et bruger nu en mere stabil compliance- og backup-API, hvor endpointene returnerer konsistente felter selv når DB'en endnu ikke har fuld evidence. Det betyder at Compliance cockpit og Backup/Resilience-sider kan vise tydelige tilstande som "ikke data endnu" eller "ikke tilgængelig" i stedet for at bryde eller fremstå inkonsistente.

For drift og governance er det vigtigt at følge:
- Compliance summary og standard reports efter større ændringer i CMDB, opdateringer, backup-evidence eller access-log. 
- Backup status og resilience summary for at sikre at NAS-path, include-images-setting og sidste backup-operation er tilgængelige.
- Daglige smoke-tests og regressionstests i CI for hurtig feedback på kerne-routes og UI-build.

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

**Brug verify_backup.sh scriptet (anbefalet):**

```bash
# Kør fra repo rod
./deploy/scripts/verify_backup.sh

# Valg:
# --dry-run        Vis hvad der ville blive tjekket uden at udføre handlinger
# --test-restore   Udfør faktisk restore til /tmp/timelapse-restore-test og verifikation
# --max-age HOURS  Maximal alder af backup i timer (default: 48)

# Eksempler:
./deploy/scripts/verify_backup.sh                          # Tjek backup eksisterer og er ny nok
./deploy/scripts/verify_backup.sh --max-age 24             # Kræv backup inden for 24 timer
./deploy/scripts/verify_backup.sh --test-restore           # Fuld restore test
```

**Manuel tjek:**

```bash
ls -la /Volumes/Backup/timelapse/
# Bekræft nyeste backup er inden for de seneste 24 timer
```

**Tjek backup via API:**

```bash
# Headend skal køre
curl http://127.0.0.1:8000/api/admin/backup/status | jq .
curl http://127.0.0.1:8000/api/admin/backup/settings | jq .
```

### 8.3 Restore procedure

**RTO (Recovery Time Objective):** 1-2 timer for fuld systemgendannelse (forventet)
**RPO (Recovery Point Objective):** 24 timer (maksimalt datatab ved backup interval daglig)

**⚠️ ADVARSEL:** Restore stopper headend og er midlertidig nedetid. Udfør kun ved nødvendigt driftsstop eller planlagt maintenance.

**Fuld restore procedure (trin-for-trin):**

1. **STOP headend service**
   ```bash
   launchctl bootout gui/$(id -u)/dk.froekjaer.timelapse-headend
   # Bekræft at processen er stoppet
   launchctl list | grep timelapse
   ```

2. **Vælg backup til restore**
   ```bash
   # Find seneste backup
   ls -lt /Volumes/Backup/timelapse/*.tar.gz | head -5

   # Eller brug scriptet
   LATEST_BACKUP=$(find /Volumes/Backup/timelapse -name "timelapse-backup-headend-*.tar.gz" -type f | sort -r | head -1)
   echo "Seneste backup: $LATEST_BACKUP"
   ```

3. **Opret midlertidig restore directory**
   ```bash
   mkdir -p /tmp/timelapse-restore
   cd /tmp/timelapse-restore
   ```

4. **Ekstraher backup**
   ```bash
   tar -xzf "$LATEST_BACKUP" -C /tmp/timelapse-restore
   # Verificer indhold
   ls -la /tmp/timelapse-restore/
   ```

5. **STOP PostgreSQL (vigtigt før db restore)**
   ```bash
   brew services stop postgresql@17
   # Eller hvis du bruger en anden version
   # brew services stop postgresql
   ```

6. **Backup eksisterende database (valgfrit men anbefalet)**
   ```bash
   pg_dump -U timelapse timelapse_db > /tmp/timelapse-pre-restore-$(date +%Y%m%d-%H%M%S).sql
   ```

7. **DROP og genskab database**
   ```bash
   psql -U timelapse postgres
   # I psql:
   DROP DATABASE timelapse_db;
   CREATE DATABASE timelapse_db OWNER timelapse;
   \q
   ```

8. **Restore database fra backup**
   ```bash
   # Find database dump i ekstraheret backup
   DB_DUMP=$(find /tmp/timelapse-restore -name "timelapse_db_*.sql" | head -1)
   echo "Restoring fra: $DB_DUMP"

   # Restore
   psql -U timelapse timelapse_db < "$DB_DUMP"
   ```

9. **Verificer database**
   ```bash
   psql -U timelapse timelapse_db -c "\dt"  # Vis alle tables
   psql -U timelapse timelapse_db -c "SELECT COUNT(*) FROM captures;"  # Tjek captures
   ```

10. **START PostgreSQL**
    ```bash
    brew services start postgresql@17
    # Vent til PostgreSQL er klar
    pg_isready -U timelapse
    ```

11. **Restore billeder (valgfrit — kun hvis billeddata mistet)**
    ```bash
    # Hvis backup inkluderede billed-mirror, rsync tilbage
    rsync -avz /Volumes/Backup/timelapse/timelapse-images-mirror/ /Volumes/data-fast/timelapse-incoming/canonical-images/

    # Eller hvis billeder er i en anden backup
    # rsync -avz /path/to/backup/captures/ /Volumes/data-fast/timelapse-incoming/canonical-images/
    ```

12. **Genstart headend**
    ```bash
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist
    ```

13. **Verificer system**
    ```bash
    # Tjek health endpoint
    curl http://127.0.0.1:8000/api/health

    # Tjek log
    tail -50 ~/Library/Logs/timelapse-headend.log

    # Tjek at CMDB loades korrekt
    curl http://127.0.0.1:8000/api/admin/stats | jq .
    ```

14. **Ryd op midlertidige filer**
    ```bash
    rm -rf /tmp/timelapse-restore
    ```

**Test restore (uden at stoppe produktion):**

```bash
# Brug verify_backup.sh --test-restore flaget
./deploy/scripts/verify_backup.sh --test-restore

# Dette udpakker backup til /tmp/timelapse-restore-test,
# verifikere indholdet, og rydder op igen — uden at påvirke kørende system
```

**Hvis restore fejler:**

1. Tjek at PostgreSQL kører: `brew services list | grep postgres`
2. Tjek at database dump er gyldig: `head -20 "$DB_DUMP"`
3. Tjek headend log for fejl: `tail -100 ~/Library/Logs/timelapse-headend.log`
4. Hvis alt andet fejler, kontakt support med databasen backup fil

**Dokumentation:** Se `GO_LIVE_CHECKLIST_v10.md` §E, `deploy/scripts/verify_backup.sh`

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
