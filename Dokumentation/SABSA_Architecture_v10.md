# TimeLapse Pro — SABSA Enterprise Security Architecture (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Metode:** SABSA (Sherwood, Clark & Lynas) — forretningsdrevet sikkerhedsarkitektur
**Konsoliderer:** `TimeLapse_SABSA_Architecture.docx` + `_v3`…`_v9` (arkiveret i `Gamle versioner/`). v9 (14. apr 2026) er backbone.

> **Bemærk — arkitekturens udvikling:** Denne SABSA-arkitektur blev formet i Canon/Raspberry Pi-æraen (Sprint A–C). Systemet er siden udviklet: aktivt kamera er nu **Nikon Z30** (ikke Canon EOS 1300D/1000D), production-headend er **Mac Mini med PostgreSQL + nginx + HTTPS** (ikke RPi5/SQLite/HTTP), transport er hærdet (JWT/HMAC, SFTP port 22222), og RBAC/CMDB/update-flow er implementeret. SABSA-rygraden (forretningsmål → attributter → kontroller) er uændret gældende; de fysiske/komponent-lag skal læses sammen med `Timelapse_pro_full_documentation_v10.md` og `RISK_ASSESSMENT_v10.md` for aktuel tilstand.

> **Proposed principgrundlag (2026-07-31):** `Arkitektur/TimeLapse_Core_Design_Principles_v1.md` udvider SABSA-læsningen med Longevity, explicit disposition, Local Service Gateway og yderligere trust boundaries. Det erstatter ikke denne arkitektur eller accepterede ADR'er. Særligt den her beskrevne 50 GB circular buffer skal afstemmes med dokumentets foreslåede princip om ingen automatisk sletning af projektdata, før der træffes en eksplicit policy-/ADR-beslutning.

## 1. SABSA-framework — overblik

SABSA sikrer at alle sikkerhedsbeslutninger kan traceres tilbage til forretningsmål. TimeLapse Pro er designet med SABSA som arkitektonisk rygrad fra forretningsmål til systemkomponenter.

**Forretningsmission:** Levér pålidelige, autentificerede timelapse-optagelser fra ubemandede lokationer til betalende kunder, med central styring, multi-tenant isolation, tidssynkrone optagelser på site-niveau og dokumenterbar dataintegritet.

### 1.1 SABSA-matrice (v9-realisering)

| SABSA-lag | Perspektiv | Spørgsmål | TimeLapse Pro |
|---|---|---|---|
| Kontekstuelt | Forretningsmål | Hvorfor? | Pålidelig, uovervåget multi-tenant timelapse-dokumentation fra byggepladser. SHA-256 som ubestrideligt juridisk bevis. |
| Konceptuelt | Sikkerhedspolitik | Hvad? | Zero-trust, defense-in-depth, autonomi ved netværksudfald, tenant-isolation, NTP-synk, SHA-256-integritet. |
| Logisk | Sikkerhedsarkitektur | Hvordan? | Hierarki Tenant→Site→Kamera, JWT RBAC, customer approval for SSH, koordineret upload-throttling, dag/nat-filtrering. |
| Fysisk | Sikkerhedsdesign | Med hvad? | Orange Pi 4 Pro, kamera (nu Nikon Z30), Mac Mini (prod), Python, FastAPI, PostgreSQL, sysfs GPIO, udev, gphoto2, autossh. |
| Komponent | Sikkerhedsmekanismer | Hvilke? | SHA-256 sidecar JSON, Fernet, pyotp, PyJWT, bcrypt, FFmpeg, systemd watchdog, udev-symlinks, CircularBuffer, HMAC. |
| Operationelt | Driftssikkerhed | Hvornår? | Heartbeat pr. capture, nightly reboot, reverse SSH m. customer approval, nøglerotation, shutter-alarm, backup-plan. |

## 2. Business Attributes (SABSA F1)

| Attribut | Dansk | Definition | Realisering | Prioritet |
|---|---|---|---|---|
| Availability | Tilgængelighed | Capture >99% af planlagt tid uanset netværk | Autonom edge, store-and-forward 50 GB, nightly reboot, watchdog | KRITISK |
| Integrity | Integritet | Billeder uændrede fra linse til arkiv (juridisk bevis) | SHA-256 pre-XMP hash i sidecar JSON; SFTP SHA-256-verifikation | KRITISK |
| Synchronicity | Tidssynkron. | Kameraer på site optager inden for 1 sek. | NTP/chrony (~2 ms offset); multi-kamera simultane relæer + threads | KRITISK |
| Confidentiality | Fortrolighed | Tenant A kan aldrig tilgå Tenant B's data | customer_id row-level filter; JWT RBAC | HØJ |
| Accountability | Ansvarlighed | Alle handlinger sporbare til bruger + tid | Audit log; heartbeat-diagnostik pr. capture | HØJ |
| Continuity | Kontinuitet | Boot-to-capture < 120 sek. | gvfs deaktiveret; sysfs GPIO; nightly reboot 02:00 | HØJ |
| Resilience | Modstand | Overlever netværks-/strøm-/device-fejl | 50 GB circular buffer; store-and-forward; modem power-cycle | HØJ |
| Manageability | Håndterbarhed | Remote konfiguration uden fysisk adgang | Web UI: config, LAB mode, backup, SSH; CI/CD self-update | MIDDEL |
| Scalability | Skalerbarhed | Design til 500–1000 edges, 100+ sites | Multi-tenant RBAC; PostgreSQL | MIDDEL |
| Performance | Ydeevne | 1 billede/dag → 1/minut, konfigurerbart | FFmpeg timelapse; blur/brightness-filter; dag/nat-selektion | LAV |

## 3. Hardware, komponenter og tillidsgrænser

**Systemkomponenter:** Edge = Orange Pi 4 Pro (RK3588S, 128 GB NVMe, Armbian, Python, gphoto2, systemd). Headend prod = Mac Mini (macOS, FastAPI/uvicorn, PostgreSQL, nginx, HTTPS). Kamera = Nikon Z30 (USB/PTP via libgphoto2), relæ-strømstyret. Web UI = React + TypeScript + Tailwind + Recharts.

**GPIO (Orange Pi 4 Pro):** GPIO 356/Pin 7 = kamera-relæ (aktiv-lav, `/dev/cam0`); GPIO 357/Pin 16 = kamera 1-relæ (`/dev/cam1`); GPIO 361/Pin 11 = modem-relæ. Stabile udev USB-symlinks persistente på tværs af reboots.

**Tillidsgrænser (mål-tilstand):** Edge→Headend API over HTTPS m. JWT+HMAC; Edge→Headend SFTP (port 22222) m. SHA-256-verifikation, ED25519; Browser→Headend HTTPS; Edge→SSH-tunnel ED25519 autossh m. customer approval; Kamera→Edge USB/PTP (ingen netværkseksponering). Edge er untrusted by default.

**Miljø-lag som selvstændig tillidsgrænse (tilføjet 2026-07-06, periodisk tjek #83, Claude — fund, ikke tidligere flagget i denne fil):** Ud over ovenstående komponent-/netværkstillidsgrænser findes siden Peters miljøafklaring 2026-07-05 et andet, ortogonalt tillidslag: **`rd`/`staging`/`prod`** (se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`). Den fremtidige prod-fysiske-vært kører allerede i dag CrushFTP med live kundedata, uafhængigt af om TimeLapse Pro selv er deployet dertil — miljøgrænsen er derfor reelt en tillidsgrænse NU, ikke først ved cutover. Gældende politik (Peter, ordret, 2026-07-05): default-deny agent-adgang til staging/prod, kun R&D har stående agent-adgang (se `RISK_ASSESSMENT_v10.md` R19, `GO_LIVE_CHECKLIST_v10.md` M-01–M-08). En kontrolleret, tidsbegrænset, logget break-glass-undtagelse (separat Support-CA, kunde-samtykke, signeret ticket) er designet (`Claude_Support_Access_Model_2026-07-06.md`) men ikke bygget. Teknisk håndhævelse af selve default-deny (`AgentPrincipal`/miljøflag-model, M-05) er heller ikke kodet endnu — indtil da hviler grænsen på menneskelig disciplin, ikke en teknisk kontrol. Denne §3 nævnte ikke tidligere miljølaget overhovedet, selvom det er en reel, allerede gældende tillidsgrænse i SABSA-forstand (separat trust domain, ikke blot en applikations-flag) — tilføjet her for at holde dette dokuments tillidsgrænse-model i sync med RISK_ASSESSMENT/MILJOE_ARKITEKTUR. Bemærk desuden en kendt implementeringsfælde ved selve miljøflaget: `TIMELAPSE_ENV`-værdien `"rd"` kendes endnu ikke af de 3 kodesteder der læser den (`edge/agent.py`, `headend/main.py`, `headend/siem.py` — verificeret uændret ved kodelæsning 2026-07-06, periodisk tjek #83), se R19-detaljeafsnittet for fuld udredning.

## 4. Backup- og restore-arkitektur (pull)

Tre principper: ingen indkommende forbindelser til edge, alle backups samlet ét sted, fuld sporbarhed via web UI. Edge-enheder kan ikke nås udefra (NAT/firewall) — backup initieres fra edge og pushes til headend via eksisterende SFTP:

```
UI: Anmod backup → POST /api/admin/backup/trigger-edge/{device_id} (backup_requested=true)
Edge: opdager flag ved config-pull (≤5 min) → _check_backup() laver lokal .tar.gz i /tmp/
     → SFTP upload → /incoming/_backups/TL-XXX/ → POST /api/admin/backup/edge-complete
Headend: shutil.move → backup-target (eller NAS) → UI viser 'Backup komplet' + filnavn
```

Restore-test med dokumenteret RTO/RPO er stadig en åben blocker (jf. `RISK_ASSESSMENT_v10.md` R09, `GO_LIVE_CHECKLIST_v10.md` E-02).

## 5. CI/CD, sprints og teknisk gæld

CI/CD: automatiske tests kører ved hvert push; deploy kun hvis alle er grønne. Edge self-update via `update_requested`-flag fra headend-poller (ingen SSH). Sprint-historik og teknisk gæld er ført videre i `KRAVREGISTER_og_STATUS_v10.md` (§4 tidslinje) og `RISK_ASSESSMENT_v10.md`. Åbne arkitektur-punkter: intern CA/mTLS, disk-kryptering på edge, per-target update-status, JWT asymmetrisk (RS256/EdDSA) vs. nuværende HS256.
