# Codex_Timelapse_pro_full_documentation_v1

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Version:** 1.0  
**Status:** Samlet merged dokument baseret på Codex' 7 dokumenter, makkerens/Claude-dokumenterne og `ADMIN_MANUAL_2026-06-23.md`.

## 0. Dokumentets formål

Dette dokument samler TimeLapse Pro's aktuelle dokumentation i ét autoritativt arbejdsdokument.

Det indeholder:

1. Konsolidering af Codex- og makker-dokumentsæt.
2. Konklusion og go/no-go for lab, første site og Internet-facing produktion.
3. Krav, ønsker, bygget status, mangler og roadmap.
4. Risk assessment og virtuel penetrationstest.
5. Bruger- og administratormanual.
6. Port- og website-/backend-arkitektur for `www.timelapse-pro.dk` og `backend.timelapse-pro.dk`.
7. Standardindeks for SABSA, COBIT, ISO 27000/27001, IEC 62443, NIS2, CRA og GDPR.
8. Leverandør-/partnerdokumenter og kundedokumenter, der skal bruges per standard.

## 1. Kildeindeks

### 1.1 Codex-kildesæt

| Dokument | Anvendelse |
|---|---|
| `Codex_DOKUMENTPAKKE_OVERSIGT_2026-06-23.md` | Codex' kildegrundlag, konflikter og samlet status |
| `Codex_RISK_ASSESSMENT_v7_2026-06-23.md` | Codex risk assessment, SABSA/standardmapping og virtuel pentest |
| `Codex_KRAVREGISTER_og_STATUS_2026-06-23.md` | Codex kravregister, bygget status, mangler og roadmap |
| `Codex_GO_LIVE_CHECKLIST_2026-06-23.md` | Codex go-live gate |
| `Codex_PORT_AUDIT_og_WEBSITE_2026-06-23.md` | Codex port- og domænemodel |
| `Codex_BRUGERMANUAL_2026-06-23.md` | Codex brugerflow |
| `Codex_ADMINISTRATORMANUAL_2026-06-23.md` | Codex admin-/driftsflow |

### 1.2 Makker-/Claude-kildesæt

| Dokument | Anvendelse |
|---|---|
| `Claude_RISK_ASSESSMENT_v7_2026-06-23.md` | Detaljeret risk assessment, tidligere findings, standardvurdering |
| `Claude_KRAVREGISTER_og_STATUS_2026-06-23.md` | Detaljeret kravregister med implementeringsgrad |
| `Claude_GO_LIVE_CHECKLIST_2026-06-23.md` | Detaljeret Internet-go-live checklist |
| `Claude_PORT_AUDIT_og_WEBSITE_2026-06-23.md` | Detaljeret Cloudflare/portmigrationsplan |
| `Claude_BRUGERMANUAL_2026-06-23.md` | Kundevendt brugerflow og begrænsninger |
| `Claude_ADMIN_MANUAL_2026-06-23.md` | Praktisk adminmanual med kommandoer |
| `ADMIN_MANUAL_2026-06-23.md` | Identisk dublet af `Claude_ADMIN_MANUAL_2026-06-23.md`; ikke behandlet som selvstændig kilde |

### 1.3 Kildebegrænsninger

Den tidligere dokumentgennemgang udtrak 54.470 tekstlinjer fra 79 lokale dokumentationsfiler. `.gdoc`/`.gslides` var lokale Google Drive-pointere og blev ikke hentet i denne kørsel. To ældre `.docx` timeoutede ved lokal tekstkonvertering. PDF-hardwaremanualer blev identificeret, men ikke tekstudtrukket lokalt.

## 2. Executive Summary

### 2.1 Overordnet konklusion

TimeLapse Pro er **lab/pre-production-klar**, men **ikke klar til Internet-facing produktion** pr. 2026-06-23.

Systemet har nu et stærkt teknisk fundament:

- Aktiv Edge `TL-C87FF9587CA0` med Orange Pi 4 Pro og Nikon Z30.
- Mac Mini Headend med FastAPI, PostgreSQL, nginx, Ollama, CMDB, updates, GRC og LAB.
- Capture/upload virker i lab.
- RBAC, CMDB-auth og Key Management er forbedret.
- App artifact update er E2E-testet på aktiv Edge uden direkte GitHub/Internet.
- Global Config med arv: global -> kunde -> site -> kamera.
- Kamera-lokation og fysisk Edge er adskilt via DeviceAssignment.
- Edge image build og public website draft findes.

De vigtigste produktionsblockere er:

1. Mac Headend bruger stadig nginx på public `*:80` og `*:443` i lab.
2. Backup + restore-test er ikke dokumenteret som production evidence.
3. GDPR-grundlag mangler: DPIA, retention, DPA, subprocessor-liste og adgangslog.
4. Node-agent/CMDB freshness er ikke stabilt nok.
5. Stale/legacy credentials skal ryddes eller migreres.
6. MFA/WebAuthn skal håndhæves for admin/high-risk operations.
7. OS offline update E2E mangler på aktiv Edge.
8. Nikon Z30 LAB/fokus/video-streaming er endnu ikke production-hærdet.

### 2.2 Go/No-Go

| Mål | Vurdering | Kommentar |
|---|---|---|
| Fortsat R&D/LAB | Go | Systemet kan trygt fortsætte i lab |
| Kontrolleret testsite | Betinget go | Kræver backup/restore, Nikon LAB og node-agent |
| Første rigtige kundesite | No-go lige nu | GDPR, retention, DPA og driftsbeviser mangler |
| Internet-facing production | No-go | Portmodel, MFA, backup, credentials og compliance skal lukkes |
| `www.timelapse-pro.dk` statisk website | Go | Må hostes separat fra Headend |
| `backend.timelapse-pro.dk` | No-go | Skal bag Cloudflare Tunnel/proxy og non-standard origin |

## 3. Samlet systembeskrivelse

### 3.1 Arkitektur

```text
Orange Pi 4 Pro Edge
  Nikon Z30
  gphoto2 / GPIO relay
  timelapse-edge service
  local buffer
       |
       | HTTPS API / SFTP / reverse SSH debug
       v
Mac Mini Headend
  FastAPI / uvicorn
  PostgreSQL
  React UI
  CMDB / GRC / Updates / LAB
  Ollama / AI tooling
  Storage: /Volumes/data-fast
  Backup: /Volumes/Backup
       |
       | nginx / Cloudflare Tunnel target
       v
Browser UI / public website
```

### 3.2 Hovedkomponenter

| Komponent | Status | Nøglekrav |
|---|---|---|
| Edge capture | Implementeret | Autonom drift, store-and-forward, relay power |
| Nikon Z30 | Delvist | Remote focus, focus slice og video skal færdiggøres |
| Headend API | Implementeret | Auth, RBAC, CMDB, uploads, updates |
| React UI | Implementeret/delvist | Galleri, admin, updates, LAB, GRC |
| CMDB | Delvist | Frisk node-agent inventory og installed/latest versions |
| GRC | Delvist | Click-through, evidence freshness, rapportgenerator |
| Update-flow | Delvist/godt i lab | OS E2E, per-target status, customer approval |
| Backup | Delvist | Restore-test og RTO/RPO mangler |
| Public website | Draft implementeret | Hostes separat på `www.timelapse-pro.dk` |

## 4. Kravregister og status

### 4.1 Capture og billedhåndtering

| ID | Krav | Status | Mangler |
|---|---|---|---|
| CAP-001 | Automatisk capture på Edge | Implementeret | Langtidstest på Nikon Z30 |
| CAP-002 | Store-and-forward ved netværksudfald | Implementeret | Evidence pr. site |
| CAP-003 | Thumbnail ved upload | Delvist/implementeret | Robust backfill/postprocessing |
| CAP-004 | Billedkvalitet: blur, lys, eksponering | Delvist | Edge CV pipeline og threshold tuning |
| CAP-005 | AI-analyse og tagging | Delvist | Cloud/Gemini ontologi, confidence, review |
| CAP-006 | Vejr-/lys-/genskinsmetadata | Delvist | Søgbar metadata-model |
| CAP-007 | Timelapse-video eksport | Mangler/delvist | FFmpeg/UI workflow og quality filters |
| CAP-008 | Retention pr. kamera | Mangler | GDPR blocker |
| CAP-009 | Download/adgangslog pr. billede | Mangler | GDPR/ISO/NIS2 |
| CAP-010 | Sidecar metadata/hash | Delvist/implementeret | Integrity evidence pr. billede |

### 4.2 UI og brugerfunktioner

| ID | Krav | Status | Mangler |
|---|---|---|---|
| UI-001 | Kundegalleri med thumbnails | Implementeret | Performance QA ved store backlogs |
| UI-002 | Lightbox/full image | Implementeret | Access-log pr. visning/download |
| UI-003 | Tag-søgning | Implementeret/delvist | Kvalitetssikret tag ontology |
| UI-004 | Danske labels, engelske backend-tags | Implementeret | Kunde-redigerbar oversættelsestabel |
| UI-005 | RBAC kundelogin | Implementeret/delvist | MFA/WebAuthn enforcement |
| UI-006 | Compliance rapporter | Delvist | Standardrapporter og evidence links |
| UI-007 | Sløring/redaction workflow | Mangler | GDPR privacy by design |

### 4.3 Admin, CMDB og GRC

| ID | Krav | Status | Mangler |
|---|---|---|---|
| ADM-001 | CMDB device/software inventory | Delvist | Node-agent freshness, latest version |
| ADM-002 | GRC dashboard | Delvist | Quantitative risk og click-through |
| ADM-003 | Key Management | Implementeret/delvist | Stale cleanup, CA/mTLS |
| ADM-004 | Backup UI | Delvist | Restore-test og edge backup UX |
| ADM-005 | Edge image build/download | Implementeret | Production signing/evidence |
| ADM-006 | LAB mode | Delvist | Nikon focus/video og state correctness |
| ADM-007 | Postprocessing admin job | Delvist | Missing thumbnails skal oprettes robust |
| ADM-008 | Global Config | Implementeret | Flere parametre og UX-polish |

### 4.4 Update-flow

| ID | Krav | Status | Mangler |
|---|---|---|---|
| UPD-001 | Edge må ikke bruge direkte Internet/GitHub/apt i prod | Implementeret som princip | Legacy paths lab-only |
| UPD-002 | App artifacts signeres og deployes fra Headend | E2E testet i lab | Production signing policy |
| UPD-003 | OS security og functional bundles | Delvist | OS E2E på aktiv Edge |
| UPD-004 | Lab -> staging -> production | Delvist | Gating og kundeaccept |
| UPD-005 | Change tickets | Delvist | Signeret approval, MFA-context, external ticket ID |
| UPD-006 | Per-target update status | Delvist/mangler | UI-flowstatus pr. Edge |
| UPD-007 | SBOM pr. release/artifact | Delvist | Automatisk binding til change ticket |
| UPD-008 | Rollback og pre-update backup | Delvist | Restore/evidence og failure gates |

### 4.5 Security og compliance

| ID | Krav | Status | Mangler |
|---|---|---|---|
| SEC-001 | RBAC | Implementeret | Review og endpoint coverage evidence |
| SEC-002 | MFA/WebAuthn | Delvist/mangler | Enforcement |
| SEC-003 | HMAC device auth | Delvist | Alle aktive/stale credentials |
| SEC-004 | Intern CA/mTLS | Mangler | IEC 62443/CRA hardening |
| SEC-005 | SFTP chroot | Implementeret/delvist | Aktuel chroot-evidence i GRC |
| SEC-006 | Secrets ikke i Git | Implementeret | Rotation og Keychain/secret manager |
| SEC-007 | Backup/restore | Delvist/mangler | Restore-test |
| SEC-008 | GDPR DPIA/retention/DPA | Mangler | Kundeproduktion blocker |
| SEC-009 | Incident response | Mangler | GDPR 72t, NIS2 incident process |

## 5. Risk assessment og virtuel penetrationstest

### 5.1 Samlet risikoregister

| ID | Risiko | Score | Status | Behandling |
|---|---|---:|---|---|
| R01 | SFTP data-læk/lateral movement | 4 | Lav/delvist | Gem chroot evidence |
| R02 | Uautoriseret admin UI | 8 | Medium | MFA/WebAuthn |
| R03 | Hardwaretab bryder historik | 3 | Lav | DeviceAssignment bevares |
| R04 | Manglende remote adgang | 4 | Lav | Debug-only tunnel |
| R05 | Kompromitteret fysisk Edge | 12 | Høj | mTLS, disk encryption, credential rotation |
| R06 | Fejlet update i stor skala | 8 | Medium | OS E2E, per-target rollout |
| R07 | Nøglekompromittering | 8 | Medium | Stale cleanup, key lifecycle |
| R08 | MITM/API manipulation | 8 | Medium | CA-pinning/mTLS |
| R09 | Backup/restore fejler | 12 | Høj | Restore-test og offsite |
| R10 | SSH tunnel misbrug | 4 | Lav | Audit og restricted access |
| R11 | AI hallucinerer tags | 9 | Medium | Cloud ontology, confidence, review |
| R12 | GDPR non-compliance | 16 | Kritisk | DPIA, retention, DPA, access logs |
| R13 | Headend på public 80/443 | 12 | Høj | Cloudflare Tunnel og loopback origin |
| R14 | CMDB inventory stale | 9 | Medium | Node-agent og freshness gating |
| R15 | Nikon Z30 drift/fokus | 9 | Medium | LAB, profiling, accepted equivalents |

### 5.2 Virtuel pentest findings

| Finding | Prioritet | Status | Handling |
|---|---|---|---|
| Mac Headend/nginx bruger `*:80` og `*:443` | P0 | Åben | Flyt bag Cloudflare Tunnel |
| `/api/cmdb/` anonym adgang | P0 | Løst | Bevar auth regression test |
| Backup/restore ikke bevist | P0 | Åben | Restore-test |
| GDPR-grundlag mangler | P0 | Åben | DPIA/DPA/retention |
| Stale credentials | P1 | Åben | Migrer/revoker |
| MFA/WebAuthn ikke enforced | P1 | Åben | Admin/high-risk enforcement |
| OS update E2E mangler | P1 | Åben | Test offline artifact på aktiv Edge |
| OpenWebUI rolle uklar | P2 | Åben | Lab-only eller RBAC-prod service |
| Frontend lint gæld | P2 | Åben | CI gate |
| LocalStorage/token posture | P2 | Åben | Auth cookie model og XSS review |

## 6. Internet-, port- og website-arkitektur

### 6.1 Produktionsregel

TimeLapse Pro må ikke kræve inbound TCP `80`, `443`, `21`, `22` eller `8080` på Mac Headend-origin.

Undtagelse: `www.timelapse-pro.dk` må naturligt bruge public 80/443 hos Cloudflare/hostingplatform. Kravet handler om Mac Headend-origin og TimeLapse backend.

### 6.2 Target model

```text
www.timelapse-pro.dk
  Statisk website, Cloudflare Pages eller tilsvarende
  Login links -> backend.timelapse-pro.dk

backend.timelapse-pro.dk
  Cloudflare Tunnel/WAF/Access
  -> Mac Headend origin 127.0.0.1:18443
  -> nginx -> React UI / FastAPI 127.0.0.1:8000
```

### 6.3 Target portprofil

| Funktion | Target port | Binding |
|---|---:|---|
| Backend origin HTTPS | 18443 | `127.0.0.1` |
| Backend origin HTTP, hvis TLS termineres eksternt | 18080 | `127.0.0.1` |
| FastAPI intern | 8000 eller 18000 | `127.0.0.1` |
| OpenWebUI intern | 18081 | `127.0.0.1` |
| SFTP ingress | 12222 | privat/tunnel |
| SIEM/syslog | 15514 | loopback/privat |
| Ollama | 11434 | `127.0.0.1` |

### 6.4 Public website

Codex har oprettet et statisk website i:

- `website/index.html`
- `website/styles.css`
- `website/script.js`
- `website/assets/`

Website skal hostes separat fra Headend, fx Cloudflare Pages.

## 7. Bruger- og administratormanual

### 7.1 Brugermanual

Kundens normale flow:

1. Gå til login via `www.timelapse-pro.dk` eller direkte `backend.timelapse-pro.dk`.
2. Log ind med rollebaseret adgang.
3. Se dashboard med kameraer, seneste billeder, status, upload og alarmer.
4. Gå til site/kamera.
5. Se thumbnails og fulde billeder.
6. Filtrer på dato, tags, kvalitet, lysforhold og timelapse-egnethed.
7. Eksporter rapporter/video når funktionerne er aktiveret.
8. Kontakt admin ved offline/stale kamera, manglende thumbnails, forkerte tags eller adgangsfejl.

### 7.2 Administratormanual

Daglige checks:

```bash
curl http://127.0.0.1:8000/api/health
launchctl print gui/$(id -u)/dk.froekjaer.timelapse-headend | grep -E "state =|pid ="
tail -200 ~/Library/Logs/timelapse-headend.log
pg_isready -U timelapse
df -h /Volumes/data-fast /Volumes/Backup
```

Genstart Headend:

```bash
launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend
```

Edge drift:

```bash
ssh orangepi@192.168.86.134
journalctl -u timelapse-edge -n 200
systemctl is-active timelapse-edge
```

Backup/restore:

1. Trigger backup via Admin UI.
2. Verificer backupfil og checksum.
3. Stop Headend før restore.
4. Restore database og captures til testplacering.
5. Start Headend og valider health.
6. Gem resultater som GRC evidence.

Update-flow:

1. CMDB inventory.
2. Headend reconcile.
3. Artifact build/sign.
4. Change ticket.
5. Approval til lab/staging/prod.
6. Edge poll.
7. Artifact download og verification.
8. Pre-update backup.
9. Install.
10. Report deployed/failed/blocked.

Nikon Z30 LAB:

1. Start LAB mode.
2. Verificer relay og kamera.
3. Kør preview og full capture.
4. Test autofocus/focus slice/focus quality.
5. Gem config på korrekt config-lag.
6. Stop LAB mode.

## 8. Standardindeks

### 8.1 SABSA Index

| SABSA lag/attribute | TimeLapse Pro evidens | Status | Mangler |
|---|---|---|---|
| Contextual | Business objective: dokumentation over tid og kundeevidens | Delvist | Business impact pr. kunde/site |
| Conceptual | Headend as authority, Edge as autonomous reporter | God | Formaliseret policy model |
| Logical | RBAC, CMDB, GRC, update artifacts, backup, AI metadata | Delvist | Evidence chain fuldendt |
| Physical | Mac Mini, Orange Pi 4 Pro, Nikon Z30, storage, tunnel | Delvist | Portmodel og startup preflight |
| Component | FastAPI, React, PostgreSQL, nginx, Ollama, gphoto2 | God i lab | Node-agent og OpenWebUI rolle |
| Operational | Runbooks, update-flow, backup, incident response | Delvist | Restore og incident drills |
| Availability | Capture/upload virker | Gul | Preflight, monitoring |
| Integrity | Signed artifacts delvist | Gul | OS E2E, image/hash evidence |
| Confidentiality | RBAC/SFTP chroot | Gul | MFA, mTLS, GDPR |
| Accountability | Change tickets/audit | Gul | Signed approvals |
| Authenticity | HMAC | Gul | CA/mTLS og stale cleanup |
| Privacy | Tenant isolation | Gul/rød | DPIA, retention, access log |

### 8.2 COBIT Index

| COBIT objective | TimeLapse Pro mapping | Status | Dokument/evidence |
|---|---|---|---|
| EDM03 Risk Optimization | GRC dashboard, risk register, go-live gate | Delvist | Risk assessment, GRC evidence |
| EDM04 Resource Optimization | AI local/cloud decision, Edge/Headend resources | Delvist | AI strategy mangler governance |
| APO12 Managed Risk | Risk treatment plan | Delvist | Mangler ejere/deadlines |
| APO13 Managed Security | RBAC, HMAC, signed updates | Delvist | MFA/mTLS/secrets |
| APO14 Managed Data | Captures, metadata, retention | Delvist | Retention/access log |
| BAI06 Managed IT Changes | Change tickets, artifacts, promotion | Delvist | Signed approval/customer approval |
| BAI09 Managed Assets | CMDB | Delvist | Node-agent freshness |
| DSS01 Managed Operations | Admin manual, health checks | Delvist | Monitoring/alerting |
| DSS04 Managed Continuity | Backup/restore | Mangler/delvist | Restore-test |
| DSS05 Managed Security Services | Auth, SFTP, logs, fail2ban | Delvist | SIEM coverage |
| MEA01 Performance Monitoring | Dashboard/CMDB/GRC | Delvist | Quantitative KPIs |
| MEA03 Compliance | Standard reports | Delvist | Report generator/evidence |

### 8.3 ISO 27000 / ISO 27001 Index

| Område | Mapping | Status | Nødvendige dokumenter |
|---|---|---|---|
| Asset management | CMDB, device inventory, SBOM | Delvist | Asset register, SBOM report |
| Access control | RBAC, roles, auth | Delvist | Access policy, MFA policy |
| Cryptography | TLS, HMAC, GPG | Delvist | Crypto/key management policy |
| Operations security | Logs, backup, updates | Delvist | Operations runbook |
| Change management | Change tickets/artifacts | Delvist | Change management procedure |
| Supplier security | Gemini/Google, Cloudflare, hardware suppliers | Mangler | Supplier register, DPA/SCC |
| Incident management | Not fully documented | Mangler | Incident response plan |
| Business continuity | Backup/restore | Mangler/delvist | BCP/DR plan, restore evidence |
| Compliance | GRC reports | Delvist | ISO control statement/evidence pack |

### 8.4 IEC 62443 Index

| IEC 62443 tema | Mapping | Status | Handling |
|---|---|---|---|
| Zones and conduits | Public, proxy, Headend, AI, Edge, camera bus | Delvist | Tegn og godkend zone-model |
| Identification/authentication | RBAC, HMAC | Delvist | mTLS/device certs |
| Use control | Roles, admin functions | Delvist | MFA/high-risk enforcement |
| System integrity | Signed artifacts, hashes | Delvist | OS E2E, boot hardening |
| Data confidentiality | TLS, chroot, tenant isolation | Delvist | Encryption at rest, retention |
| Restricted data flow | Edge pull, no direct Internet | God/delvist | Enforce lab-only legacy paths |
| Timely response | SIEM/logs | Delvist | Incident runbook |
| Resource availability | Buffer, backup | Delvist | Restore tests and monitoring |

### 8.5 NIS2 Index

| NIS2 område | Mapping | Status | Dokumenter |
|---|---|---|---|
| Risk management | Risk register/GRC | Delvist | Risk treatment plan |
| Incident handling | Draft/manual only | Mangler | Incident response procedure |
| Business continuity | Backup/restore | Mangler/delvist | BCP/DR plan |
| Supply chain | Cloudflare/Gemini/hardware | Mangler | Supplier risk register |
| Security in systems | RBAC, HMAC, signed updates | Delvist | Security architecture |
| Vulnerability handling | Not formalized | Mangler | Vulnerability disclosure/CVE process |
| Access policies | RBAC | Delvist | MFA/admin policy |
| Cryptography | TLS/HMAC/GPG | Delvist | Key lifecycle policy |

### 8.6 CRA Index

| CRA kravtype | Mapping | Status | Handling |
|---|---|---|---|
| Secure by design/default | Headend authority, RBAC, signed updates | Delvist | MFA/mTLS/port hardening |
| Vulnerability handling | SAST signals, update flow | Delvist/mangler | PSIRT/vulnerability process |
| Security updates | Artifact model, offline OS bundles | Delvist | OS E2E, customer notification |
| SBOM | Model fields, image build SBOM | Delvist | Automated SBOM publishing |
| Technical documentation | This doc set | Delvist | Release evidence package |
| Lifecycle support | Not declared | Mangler | Support period policy |
| No direct device Internet update | Implemented as principle | God | Enforce and test |
| Secure installation | Edge image/provisioning | Delvist | Hardening checklist |

### 8.7 GDPR Index

| GDPR artikel/område | Mapping | Status | Dokumenter/handling |
|---|---|---|---|
| Art. 5 data minimization/storage limitation | Retention needed | Mangler | Retention policy |
| Art. 6 lawful basis | Customer/project basis | Mangler | Customer DPIA/legal basis |
| Art. 13/14 information | Signage/privacy notice | Mangler | Privacy notice/sign text |
| Art. 25 privacy by design/default | RBAC/tenant isolation | Delvist | Redaction, retention defaults |
| Art. 28 processor agreement | TimeLapse as processor | Mangler | DPA |
| Art. 30 records | Processing records | Mangler | RoPA template |
| Art. 32 security | RBAC, TLS, SFTP | Delvist | MFA, backups, access logs |
| Art. 33/34 breach notification | Incident process | Mangler | 72h breach procedure |
| Art. 35 DPIA | Site camera monitoring | Mangler | DPIA per site |
| Data subject rights | Images may include persons | Mangler | DSAR/redaction process |

## 9. Leverandør-/partnerdokumenter

Disse dokumenter bør udarbejdes og vedligeholdes som leverandør-/partnerpakke.

### 9.1 På tværs af standarder

| Dokument | Relevant for | Indhold |
|---|---|---|
| Supplier Security Overview | ISO, NIS2, CRA, IEC 62443 | Arkitektur, hosting, controls, update model |
| Security Architecture | SABSA, IEC 62443 | Zones/conduits, identity, data flow, trust boundaries |
| Secure Update Policy | CRA, IEC 62443, ISO | Lab/staging/prod, signed artifacts, rollback |
| SBOM Package | CRA, ISO, NIS2 | App, OS bundles, Edge images, dependencies |
| Vulnerability Disclosure Policy | CRA, NIS2, ISO | Intake, triage, severity, SLA, advisories |
| Support Lifecycle Policy | CRA | Supported versions, patch windows, EOL |
| Backup and DR Statement | ISO, NIS2 | Backup scope, RTO/RPO, restore evidence |
| Incident Notification Procedure | NIS2, GDPR, ISO | Roles, timeline, customer notification |
| Subprocessor Register | GDPR, ISO, NIS2 | Cloudflare, Google/Gemini, hosting, email |
| Data Processing Addendum | GDPR | Processor terms, security measures, subprocessors |
| Penetration Test Summary | ISO, NIS2, CRA | Scope, findings, remediation |
| Port and Network Requirements | IEC 62443, ISO | Required ports, forbidden ports, tunnel model |

### 9.2 Partner onboarding checklist

1. Klassificer partner: hosting, AI, hardware, support, integration eller kunde-ejet Headend.
2. Indhent security contact og incident contact.
3. Indhent eller udarbejd DPA/subprocessor terms.
4. Vurder dataadgang: billeder, metadata, logs, secrets, support.
5. Vurder hosting/region og data transfer.
6. Aftal vulnerability/incident SLA.
7. Gem evidence i GRC.

## 10. Kundedokumenter

Disse dokumenter bør udleveres eller tilpasses per kunde/site.

### 10.1 Kundepakke per standard

| Dokument | Relevant standard | Indhold |
|---|---|---|
| Kundeaftale / Service Description | SABSA, ISO, NIS2 | Hvad leveres, ansvar, SLA, support |
| Databehandleraftale | GDPR | Roller, behandlingsformål, sikkerhedsforanstaltninger |
| DPIA-skabelon pr. site | GDPR | Kameraformål, risici, afværgeforanstaltninger |
| Retention Policy pr. kamera | GDPR, ISO | Hvor længe billeder, tags og logs gemmes |
| Privacy Notice / skiltetekst | GDPR | Information til registrerede på byggepladsen |
| Kundeaccept for auto-updates | ISO, CRA, NIS2 | OS security, OS functional, app security, app updates |
| Change Request / Ticket format | COBIT, ISO, CRA | Risiko, test, rollback, approval |
| Incident Notification Procedure | GDPR, NIS2 | Kontakt, tidslinje, eskalering |
| Access Control Matrix | ISO, GDPR | Roller, brugere, adgangsniveauer |
| Backup/Restore Statement | ISO, NIS2 | RTO/RPO, restore-test, ansvar |
| Port/Network Requirements | IEC 62443 | Kunde-firewall, tunnel, SFTP, no inbound Edge |
| Compliance Evidence Report | SABSA, ISO, IEC, CRA, GDPR | CMDB, SBOM, updates, backups, logs |

### 10.2 Kundeaccept for update-politik

Kunden bør kunne vælge per kunde/site/kamera:

| Update-type | Mulige policies |
|---|---|
| OS security | Auto, scheduled auto, manual approval |
| OS functional | Manual approval, staged approval |
| App security | Auto eller manual afhængigt af SLA |
| App functional | Manual/staged |
| Timelapse Pro release | Lab -> staging -> prod med change ticket |

På sigt bør change requests kunne sendes via mail eller API til kundens ticketing-system.

## 11. Roadmap

| Fase | Indhold | Prioritet |
|---|---|---|
| Pre-Internet gate | Cloudflare Tunnel, portmodel, backup/restore, node-agent, GDPR minimum | P0 |
| Site readiness | Nikon Z30 LAB, video, focus, OS update E2E | P1 |
| Customer readiness | MFA, DPA, DPIA, retention, reports | P1 |
| Security hardening | mTLS/internal CA, disk encryption, SAST/lint | P1/P2 |
| Scale readiness | Multi-headend, customer-owned headends, partner packages | P2 |
| Compliance automation | Standard reports, evidence freshness, quantitative risk | P2 |

## 12. Final conclusion

TimeLapse Pro er på vej fra et teknisk timelapse-system til en GRC-understøttet dokumentationsplatform. Både Codex- og makker-dokumenterne peger på samme hovedretning:

- Edge skal være autonom, men ikke update authority.
- Headend skal være source of truth for config, CMDB, updates, artifacts og evidence.
- Public website og backend skal adskilles.
- Internet-facing production kræver portmigrering, backup/restore, GDPR-grundlag, MFA/credentials og frisk CMDB evidence.
- Nikon Z30 er den rigtige kameraretning, men LAB/fokus/video skal gøres færdigt før første rigtige site.

Codex' anbefaling er at beholde status som lab/pre-production, færdiggøre P0-listen og derefter køre en frisk end-to-end QA med evidens, før `backend.timelapse-pro.dk` sættes live.

