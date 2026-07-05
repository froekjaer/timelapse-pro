# TimeLapse Pro — Samlet kravregister, implementeringsstatus og tidslinje (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Kilder:** Alle dokumenter i Dokumentation/, kodebase-gennemgang, sessionhistorik
**Konsoliderer:** `KRAVREGISTER_og_STATUS_2026-06-23.md`, `Claude_KRAVREGISTER_og_STATUS_2026-06-23.md`, `Codex_KRAVREGISTER_og_STATUS_2026-06-23.md`, samt essens af de oprindelige krav-kilder `Startkrav.docx` og `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` (§6–§8). Tidligere versioner arkiveret i `Gamle versioner/`.

---

## 1. Systemvision

TimeLapse Pro er et professionelt byggeplacerings-overvågningssystem med:
- **Edge-enheder** (OrangePi 4 Pro) på byggepladser med DSLR-kameraer
- **Headend** (Mac Mini) som central management, storage og update authority
- **Kundevendt UI** til billedvisning, tag-søgning og rapportering
- **Admin UI** til kameramanagement, opdateringer, CMDB og compliance

Styrende principper: SABSA-arkitektur, IEC 62443, ISO 27001, CRA, NIS2, GDPR.

---

## 2. Kravregister med implementeringsstatus

### Kategori: Capture og billedhåndtering

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| CAP-001 | Edge tager automatiske tidtagsbilleder | ✅ Implementeret | gphoto2-driver, Canon + Nikon Z30 |
| CAP-002 | Store-and-forward ved netværksudfald | ✅ Implementeret | Circular buffer 50 GB |
| CAP-003 | Thumbnail generering ved upload | ✅ Implementeret | PIL/Pillow |
| CAP-004 | Billedkvalitets-check (blur, QA) | ✅ Implementeret | Blur-score, QA-flag |
| CAP-005 | AI-analyse og tagging af billeder | ✅ Delvist | Gemini cloud + Ollama; tag-backlog 3033 |
| CAP-006 | Thumbnail postprocessing (baggrundsgenerering) | 🟡 Delvist | Trigger eksisterer; backlog genereres ikke automatisk |
| CAP-007 | Retention policy pr. kamera | 🔴 Mangler | Ingen retention implementeret |
| CAP-008 | Download/adgangslog pr. billede | ✅ Implementeret (2026-07-05) | Ny `CaptureAccessLog`-tabel + `_log_capture_access()`, kaldt fra `GET /api/images/{device_id}/{filename}` (kun fuldopløsning, ikke thumbnails). Testverificeret (4/4 + 41/41), committet/pushet af Codex. Se `GO_LIVE_CHECKLIST_v10.md` §G-05 |
| CAP-009 | Sidecar JSON med XMP-metadata | ✅ Implementeret | |
| CAP-010 | Relay-styring (kamera strøm) | ✅ Implementeret | GPIO pin 356 |

### Kategori: Kundevendt UI

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| UI-001 | Billedgalleri med thumbnails | ✅ Implementeret | CaptureThumbnailCard |
| UI-002 | Lightbox med fuld billede | ✅ Implementeret | DevicePage |
| UI-003 | Tag-søgning og filtrering | ✅ Implementeret | TagSearchPage |
| UI-004 | Danske tag-navne i kundevendt UI | ✅ Implementeret | useTagLabels hook |
| UI-005 | QA-badge (alarm, afvigelse, OK) | ✅ Implementeret | |
| UI-006 | Blur-score visning | ✅ Implementeret | |
| UI-007 | Tidszone-support | ✅ Implementeret | localStorage timezone |
| UI-008 | Kundelogin med RBAC | ✅ Implementeret | JWT, 4 roller |
| UI-009 | MFA/WebAuthn til admin-login | ✅ Implementeret (2026-07-02) | Policy-drevet TOTP, enforced for admin/super_admin; WebAuthn separat flag (off) |
| UI-010 | Sløring/redaction workflow | 🔴 Mangler | GDPR |
| UI-011 | Downloadbar timelapse-video | 🔴 Mangler | |

### Kategori: Admin UI

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| ADM-001 | CMDB med device-overblik | ✅ Implementeret | Freshness-baseret status |
| ADM-002 | Update-management (approve/reject/promote) | ✅ Delvist | UI OK; kamera/site-scope mangler |
| ADM-003 | Key Management UI | ✅ Implementeret | HMAC, revokering, cleanup-preview |
| ADM-004 | GRC/Compliance cockpit | ✅ Delvist | Dashboard implementeret; evidence-links ufuldstændige |
| ADM-005 | Global Config med hierarki | ✅ Implementeret | 4-lags: global→kunde→site→kamera |
| ADM-006 | LAB mode / kamera-test | ✅ Delvist | Nikon Z30 problemer åbne |
| ADM-007 | Post-processing admin-job | ✅ Delvist | Trigger OK; progress mangler |
| ADM-008 | Backup-UI | ✅ Implementeret | Til /Volumes/Backup |
| ADM-009 | Edge image build (disk image) | ✅ Implementeret | inject_edge_image.py, WiFi-inject |
| ADM-010 | DPIA-template pr. kunde/site | 🔴 Mangler | GDPR Art. 35 |
| ADM-011 | Rapporter pr. compliance-standard | 🟡 Delvist | GRC cockpit har rapport-skeleton |
| ADM-012 | Revision per billede/download | ✅ Implementeret (2026-07-05) | Samme løsning som CAP-008 — `CaptureAccessLog`, se `GO_LIVE_CHECKLIST_v10.md` §G-05 |
| ADM-013 | Billedhistorik følger kamera-lokation ved Edge-udskiftning (sidste led af ADM-005-hierarkiet) | ✅ Implementeret 2026-07-03 | Var reelt IKKE implementeret før 2026-07-03 (fundet ved frisk kodegennemgang, Claude) — `Capture` havde kun `device_id`, ikke `camera_id`. Rettet: schema-migration v12, resolver, additivt `camera_id`-filter på `/api/admin/captures`, backfill-script; committet+pushet (`3a2c0a8`). Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.4/§2.5. (Omdøbt fra det oprindelige, kolliderende ID "ADM-010" til ADM-013 2026-07-05 periodisk tjek #26 — se HANDOVER_LOG.) |

### Kategori: Edge-management og update

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| UPD-001 | Policy-drevet hierarkisk update | ✅ Delvist | Backend OK; UI kun global/device |
| UPD-002 | Update-scope: global/kunde/site/kamera/device | ✅ Delvist | Data-model OK; kamera-scope mangler i UI |
| UPD-003 | Edge opdateres via Headend, ikke direkte internet | ✅ Implementeret | Legacy git-update opt-in/disabled |
| UPD-004 | Verificerede update-artifacts | ✅ Implementeret | TL-QA-APP, TL-OS, TL-EDGE-IMG |
| UPD-005 | Signerede artifacts og change tickets | ✅ Delvist | GPG-signering virker; ticket-signatur mangler |
| UPD-006 | Maskin- og menneskelæsbare change tickets | 🟡 Delvist | JSON-format klar; signatur mangler |
| UPD-007 | UI med change ticket review + godkendelse | 🟡 Delvist | Grundlæggende OK; MFA/kundeaccept mangler |
| UPD-008 | Staged rollout: R&D → staging → prod | 🟡 Delvist | promote_update eksisterer; gating ufuldstændig |
| UPD-009 | Automatisk rollback ved fejlet update | 🟡 Delvist | Rollback-mekanisme eksisterer; ticket-binding mangler |
| UPD-010 | Maintenance window og reboot-policy | 🟡 Delvist | Policy returneres; enforcement mangler |
| UPD-011 | OS security og functional updates separat | ✅ Implementeret | os_security/os_updates typificeret |
| UPD-012 | Per-target deployment status | 🟡 Flush-regression rettet og deployet 2026-07-05 | `update_targets`-tabel + `/api/updates/{id}/flow-status` + UI fandtes allerede (siden juni); rettelsen for global `PendingUpdate.status` (`61802951`, deployet) manglede en `db.flush()`, så multi-target rollouts aldrig flippede til deployed/rolled_back (fundet via ny kontrakttest `headend/tests/test_report_update_rollup.py`). 1-linjes flush-rettelse committet af Codex (`1e3c3321`), deployet (health 200 OK), 13/13 tests bestået. Resterer kun: live multi-device-rollout-test — se GO_LIVE_CHECKLIST §K, RISK_ASSESSMENT R06 |
| UPD-013 | Komplet update audit trail | 🟡 Delvist | approved_by/at OK; fuld chain mangler |
| UPD-014 | SBOM pr. release | 🟡 Delvist | SBOM-felter i model; ikke auto-genereret |
| UPD-015 | Edge bevarer drift under update | ✅ Delvist | Circular buffer + rollback; atomisk staging mangler |

### Kategori: Provisioning og onboarding

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| PROV-001 | Zero/near-zero-touch Edge provisioning | 🟡 Delvist | /api/bootstrap OK; package-lifecycle ufærdig |
| PROV-002 | OS hardening og app-installation via Headend | ✅ Delvist | inject_edge_image.py; orchestreret provisioning mangler |
| PROV-003 | Device-nøgler: generering, rotation, revokering | 🟡 Delvist | Ed25519 keypair; CA/mTLS mangler |
| PROV-004 | Kold/varm backup Headend | 🔴 Mangler | Arkitektur ikke designet |
| PROV-005 | Backup + restore testet og dokumenteret | 🔴 Mangler | Restore-test mangler |
| PROV-006 | WiFi-konfiguration i disk image | ✅ Implementeret | inject_wifi_image.py |
| PROV-007 | SSH nøgler i disk image | ✅ Implementeret | authorized_keys injection |
| PROV-008 | Bootstrap token (engangsbrug/tidsbegrænset) | ✅ Implementeret | max_uses/use_count |
| PROV-009 | Multi-target build (OP4Pro, OP-PC+, RPi4, RPi5, Jetson) | ✅ Implementeret | HAL-abstraktion, target.yaml |

### Kategori: Sikkerhed og compliance

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| SEC-001 | ISO 27001/NIS2/CRA/IEC 62443 compliance-targets | 🟡 Delvist | Dokumenteret; ikke fuldt operationaliseret |
| SEC-002 | Secrets ikke i Git | ✅ Implementeret | .gitignore dækker secrets/ |
| SEC-003 | Test-gate før deploy (CI) | ✅ Delvist | Python + UI build OK; edge/headend contract-tests mangler |
| SEC-004 | RBAC med 4 roller | ✅ Implementeret | **NB 2026-07-03:** `/api/siem/*` manglede helt RBAC (fundet ved frisk kodegennemgang); rettet i kode, committet+pushet (`b0e224c`) og live-verificeret af Peter (401 uden auth) |
| SEC-005 | JWT med kort levetid | ✅ Implementeret | 12 timer |
| SEC-006 | HMAC request-signatur for device-tokens | ✅ Implementeret | Aktive noder + headend-agent |
| SEC-007 | SFTP chroot-isolation | ✅ Implementeret | per-site brugere |
| SEC-008 | MFA/WebAuthn | ✅ Delvist (2026-07-02; MFA-dækning korrigeret 2026-07-03) | MFA (TOTP) policy-drevet + enforced for admin/super_admin; WebAuthn stadig separat/off. **NB:** enforcement dækkede kun `main.py`-endpoints — CMDB/ITIM omgik reelt MFA indtil rettelse 2026-07-03, nu committet+pushet (`b0e224c`) og live-verificeret af Peter |
| SEC-009 | Intern CA + client-certs | 🔴 Mangler | |
| SEC-010 | Disk-kryptering på Edge | 🔴 Mangler | |
| SEC-011 | fail2ban | 🟡 Delvist | Konfigurationsfiler i Dokumentation/; drift-status ukendt |
| SEC-012 | DPIA og GDPR-evidens | 🔴 Mangler | |
| SEC-013 | Incident response procedure | 🔴 Mangler | |
| SEC-014 | Vulnerability handling og CVE-process | 🔴 Mangler | |

### Kategori: Konfiguration og arkitektur

| ID | Krav | Status | Kommentar |
|---|---|---|---|
| CFG-001 | Hierarkisk config: global→kunde→site→kamera | ✅ Implementeret | |
| CFG-002 | Effective config med provenance pr. felt | ✅ Implementeret | /api/admin/config-resolution |
| CFG-003 | Config-UI med farvemarkering | ✅ Implementeret | GlobalConfigPage |
| CFG-004 | Kamera-lokation adskilt fra fysisk Edge | ✅ Implementeret | Camera/DeviceAssignment |
| CFG-005 | Reverse SSH tunnel | ✅ Implementeret | autossh, deny-flag |
| CFG-006 | Bluetooth PAN management | ✅ Implementeret | bt-totp, TOTP-service |
| CFG-007 | GPS tidssynkronisering | 🔴 Mangler | |
| CFG-008 | Web terminal (xterm.js/websocket SSH) | 🔴 Mangler | |
| CFG-009 | Lokal management UI på Edge | 🔴 Mangler | |
| CFG-010 | Storage single source of truth | 🟡 Delvist | DB rettet; hardcoded paths kan stadig eksistere |

---

## 3. Implementeringsoverblik

| Kategori | Implementeret | Delvist | Mangler | Total |
|---|---:|---:|---:|---:|
| Capture | 8 | 2 | 1 | 11 |
| Kundevendt UI | 8 | 0 | 3 | 11 |
| Admin UI | 8 | 3 | 1 | 12 |
| Update/Edge | 6 | 7 | 2 | 15 |
| Provisioning | 5 | 3 | 2 | 10 |
| Sikkerhed | 7 | 3 | 6 | 16 |
| Konfiguration | 6 | 2 | 3 | 11 |
| **Total** | **48** | **20** | **18** | **86** |

**Samlet implementeringsgrad:** 56% fuldt implementeret, 23% delvist, 21% mangler.

*(Opdateret 2026-07-05, Claude periodisk tjek #25: CAP-008/ADM-012 rettet fra "🔴 Mangler" til "✅ Implementeret" — GDPR download-/adgangslog pr. billede blev implementeret og testverificeret 2026-07-05 (`CaptureAccessLog`, se `GO_LIVE_CHECKLIST_v10.md` §G-05), men dette register var ikke opdateret siden 2026-07-02 og viste stadig det gamle "mangler"-billede. Øvrige rækker i dette dokument er IKKE fuldt krydstjekket denne runde — kun disse to konkrete, verificerbare punkter.)*

---

## 4. Tidslinje

### Gennemførte sprints (retrospektivt)

| Sprint | Periode | Vigtigste leverancer |
|---|---|---|
| Sprint A | apr 2026 | Grundarkitektur: FastAPI, SQLite→PostgreSQL, React UI, SFTP, gphoto2 |
| Sprint B | apr 2026 | Multi-tenant, customer isolation, LAB mode, diagnostics |
| Sprint C | apr-maj 2026 | RBAC, reverse SSH tunnel, Camera/Pi-kobling, opdateringsstyring |
| Sprint D | maj 2026 | Intern PKI-plan, Key Management UI, CMDB, update artifact-model |
| Sprint E | maj-jun 2026 | HMAC, OS bundle, staged rollout, HAL-abstraktion, disk image build |
| Sprint F | jun 2026 | WiFi-inject, SSH-inject, BT PAN, TOTP, Gemini batch, danske tags |
| Sprint G | jun 2026 | GPG-fix, LaunchAgent, disk-migration, CI-fix, edge artifacts |

### Estimeret resterende arbejde

| Fase | Indhold | Estimat | Prioritet |
|---|---|---|---|
| **Pre-Internet gate** | Port-migration, backup+restore, node-agent, DPIA-template, HMAC cleanup, ESLint-gate | 2–3 uger | 🔴 Blocker |
| **Sprint H** | MFA/WebAuthn, per-target deployment, Nikon Z30 config-model, kamera/site-scope i update-UI | 3–4 uger | 🔴 Høj |
| **Sprint I** | Intern CA + client-certs, thumbnail postprocessing, retention policy, GDPR adgangslog | 3–4 uger | 🟠 Høj |
| **Sprint J** | Cloud tag-pipeline (Gemini, fast ontologi), GRC evidence-links, SAST triage | 2–3 uger | 🟡 Medium |
| **Sprint K** | GPS-sync, web terminal, lokal management UI, disk-kryptering på Edge | 4–6 uger | 🟡 Medium |
| **Sprint L** | www.timelapse-pro.dk marketing site, kunde/admin login-portal | 2–3 uger | 🟡 Medium |
| **Sprint M** | Kold/varm backup Headend, DR plan, incident response | 3–4 uger | 🟠 Høj |
| **Sprint N** | SBOM auto-generering, CRA-evidenspakke, NIS2-dokumentation | 2–3 uger | 🟡 Medium |

### Målpunkter

| Milepæl | Estimeret dato | Forudsætninger |
|---|---|---|
| Pre-Internet gate passed | Aug 2026 | Se GO_LIVE_CHECKLIST_2026-06-23.md |
| Første rigtige produktionssite | Sep 2026 | Sprint H afsluttet |
| timelapse-pro.dk live | Sep-okt 2026 | Go-live gate + Sprint L |
| GDPR-compliant | Okt 2026 | Sprint I afsluttet |
| CRA-dokumentation klar | Dec 2026 | Sprint N afsluttet |

---

## 5. Krav vs. ønsker — prioriteringsoversigt

### Skal (non-negotiable)
- Sikker edge-update uden direkte internet
- RBAC og auth på alle endpoints
- SFTP chroot-isolation
- Backup med restore-test
- DPIA og retention policy (GDPR)
- Signed artifacts

### Bør (stærkt anbefalet)
- MFA/WebAuthn
- Intern CA + client-certs
- Per-target deployment status
- CMDB freshness-baseret status overalt
- ESLint-gate i CI
- Incident response procedure

### Kan (nice-to-have)
- Disk-kryptering på Edge
- GPS-tidssynkronisering
- Web terminal
- Lokal management UI
- SBOM auto-generering
- Marketing website

---

## 6. Oprindelige krav (Startkrav — Peters grundbrief)

Founding-krav fra `Startkrav.docx` (bevaret som empiri; de fleste er nu reflekteret i CAP/UPD/CFG-ID'erne ovenfor):

- Central multi-tenant styring: mange kunder × mange lokationer × mange kameraer, typisk kamera i hus på mast.
- Edge = Orange Pi 4 Pro + 128 GB M.2 SSD; headend = Mac (test: Raspberry Pi 5).
- Meget stabil kamera-opsætning (svær fysisk adgang på mast).
- Strøm: 230V eller 12V batteri + solpanel; relæ på Pi tænder kun kamera ved behov.
- Internet via WiFi, kabel eller 5G USB-modem.
- Kamera oprindeligt Canon EOS 1300 via gphoto2 (nu Nikon Z30 — se konfliktnote).
- Bootstrap via device-ID (MAC-afledt) → henter konfiguration; lokal connection-setting overskrives af modtaget config.
- Config kan bede Pi om reverse SSH til headend + melde klar + IP via API.
- Circular buffer maks. 50 GB; tag billede → vent på kamera → hent → slet i kamera.
- Lokal kvalitetstest (manuelt fokus kan drive af; skidt/sne på glas).
- DB gemmer billed-metadata + kamera/Pi spænding og temperatur (config styrer hvad der gemmes + ekstra kamera-kommandoer).
- SFTP til headend + evt. 2. lokation; Pi opretter mapper så hvert kamera har egen folder.
- DB synkroniseres til headend via API. Headend multi-tenant, modtager SFTP + config-requests via API, kan sende billeder/kvalitet/statistik på e-mail, web-UI med al information.
- Hver lokation = separat SFTP-konto/folder; hvert kamera = underfolder. Ubuntu + Python foretrukket. SABSA-tænkning fra start.

## 7. Codex-supplement — NET/WEB-krav og P0/P1/P2

Yderligere krav-ID'er fra Codex-registeret:

| ID | Krav | Status | Mangler |
|---|---|---|---|
| NET-001 | Ikke bruge 80/443/21/22/8080 på Mac Headend-origin | Mangler i lab | Cloudflare Tunnel + origin-port 18443 |
| WEB-001 | Public website `www.timelapse-pro.dk` | Statisk draft | Hosting + endelig tekst/brand-QA |
| WEB-002 | Login-redirect til backend | Draft | Backend-domæne go-live |

**Prioritering (Codex P0/P1/P2):**
- **P0:** port-/proxy-migration; backup + restore-test; GDPR DPIA/retention/DPA; node-agent + frisk CMDB; stale credential cleanup + HMAC globalt.
- **P1:** MFA/WebAuthn; OS offline-update E2E på aktiv Edge; Nikon Z30 focus/video/LAB; per-target update-status i UI; frontend lint/test-gate.
- **P2:** cloud AI/tag-ontologi + dansk oversættelsestabel; GRC-rapportgenerator; incident response + vulnerability handling; edge disk-encryption; multi-headend/customer-owned governance.

## 8. Detaljeret update/provisioning-sub-register

`AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` (arbejdsversion 0.1, 2026-05-22) er et detaljeret krav-sub-register for update/change/deployment, signeret godkendelse, Edge/Headend-provisioning og backup/resiliens — udtrukket fra 47 kildefiler uden at reducere detaljegrad. Dets UPD-*-krav er reflekteret i §2 ovenfor. Målmodel (R&D/LAB → produktion): (1) udvikling/test på LAB, (2) QA via automatiske tests + signering + menneskelæsbart change ticket, (3) policy-godkendelse på global/kunde/site/kamera/device-niveau, (4) staged deployment test/staging → prod, (5) Headend-medieret distribution (edges kræver ikke direkte GitHub/Internet), (6) healthcheck/rollback/audit for app-, OS- og tredjepartsopdateringer, (7) dokumenteret provisioning af nye edges/headends inkl. kold/varm backup + restore. Dokumentet bevares som selvstændigt detalje-appendiks (arkiveres ikke).

---

*Se også: RISK_ASSESSMENT_v10.md, GO_LIVE_CHECKLIST_v10.md, 00_START_HER.md*
