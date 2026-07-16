# TimeLapse Pro - Verification, Risk & Evidence Register

**Dokument-ID:** TLP-VRER-001  
**Version:** 1.0  
**Dato:** 2026-07-16  
**Status:** MIGRERINGSKILDE OG RAPPORTFORMAT  
**Ejer:** Product Owner / Security & Architecture  
**Arbejdsmiljø:** R&D, med eksplicit promotion til staging og produktion

> PostgreSQL-tabellerne `grc_items`, `grc_links`, `grc_test_runs` og
> `grc_evidence` er fra 2026-07-16 den autoritative GRC-kilde. Dette dokument
> må ikke længere vedligeholdes som statusregister. Fremtidige versioner skal
> genereres fra GRC-databasen.

## 1. Formål og autoritet

Dette dokument er TimeLapse Pros eneste aktive statuskilde for:

- testkrav og testcases;
- manuelle UI-, API-, system-, Edge- og restore-tests;
- fund, defects, teknisk gæld og sikkerhedsrisici;
- remediation, acceptkriterier og rest-risiko;
- evidens, commits, CI-runs, change tickets og rapporter;
- go-live gates og control-mapping.

Kildedokumenter bevares for historik, forklaring eller procedure, men deres statusfelter er ikke autoritative efter registrering her. Ved konflikt gælder dette register, derefter `00_START_HER.md`, ADR'er og gældende arkitektur.

## 2. Governance og ændringsregler

1. Hvert krav, testcase og fund har et stabilt ID.
2. Et fund må kun lukkes med objektiv evidens og eksplicit acceptkriterium.
3. `PASS` kræver faktisk udførelse; kodeeksistens eller en grøn route er ikke nok.
4. Browser-PASS erstatter ikke API-, database-, filsystem-, certifikat-, restore- eller fysisk Edge-evidens.
5. Automatiserede tests må aldrig ændre operationel database direkte eller bruge skjulte fallback-credentials.
6. Destruktive tests kræver afgrænset QA-data, rollback og auditkontrol.
7. R&D-resultater må ikke automatisk promoveres til prod. Staging/prod kræver separat miljøevidens.
8. Nye fund oprettes først her og refereres derfra i risk, change og handover.

## 3. Status- og evidensmodel

### 3.1 Status

| Status | Betydning |
|---|---|
| NOT RUN | Identificeret, ikke udført |
| IN PROGRESS | Aktiv test/remediation |
| PASS | Udført og accepteret med evidens |
| FAIL | Reproducerbar afvigelse |
| BLOCKED | Dokumenteret ekstern afhængighed |
| N/A | Ikke relevant for dette lag/miljø |
| SUPERSEDED | Erstattet; historik bevares |

### 3.2 Fund-/risikostatus

| Status | Betydning |
|---|---|
| OPEN | Risiko/fund er aktivt |
| MITIGATING | Rettelse i gang |
| VERIFY | Rettet, men accepttest mangler |
| CLOSED | Acceptkriterium og evidens er opfyldt |
| ACCEPTED | Rest-risiko er formelt accepteret af rette ejer |

### 3.3 Obligatorisk evidens

| Evidenstype | Eksempel |
|---|---|
| CODE | Commit/tag/PR og relevante filer |
| AUTO | CI-run, pytest, lint, SAST, SBOM |
| UI | Browserresultat, viewport, rolle, før/efter-state |
| API | Requesttype, statuskode og schema; ingen secrets |
| OPS | Service-, log-, CMDB-, SIEM- eller backup-evidens |
| PHYSICAL | Kamera/Edge/NAS/staging-hardware |
| GOVERNANCE | Change ticket, approval, risk acceptance, DPIA |

## 4. System- og testbaseline

| Baseline-ID | Område | Seneste resultat | Status | Evidens |
|---|---|---|---|---|
| BL-001 | Unit/contract CI | 588 passed, 4 auth-smoke skipped, 543 integration deselected | PASS | Lokal CI-identisk kørsel 2026-07-16 |
| BL-002 | GitHub CI/deploy | Python, shell, TypeScript, ESLint-ratchet, build og Mac deploy | PASS | GitHub runs til og med commit `ae8a9d8b` |
| BL-003 | UI lint | 166 errors + 20 warnings, baseline 186; ingen nye | PASS ratchet | `npm run lint:gate`; gæld består |
| BL-004 | Headend legacy main | Maks. 18.549 linjer og ingen nye direkte routes | PASS ratchet | `test_architecture_ratchet.py` |
| BL-005 | UI routes | 27 beskyttede routes renderet uden login-loop eller HTTP 500/502 | PASS read-only | In-app browser 2026-07-16 |
| BL-006 | Aktiv Edge | `TL-C87FF9587CA0`, Nikon Z30, R&D/test | ACTIVE | CMDB og browser |
| BL-007 | Integration harness | Hardcodede credentials og direkte DB-fallback fundet | FAIL | `tests/conftest.py`; se FIND-TEST-001 |

## 5. Testarkitektur og de 543 integrationstests

De 543 deselected tests er markerede integrationstests fordelt på 21 moduler. De er ikke fejlede, men heller ikke godkendt. De skal køres via følgende gates:

| Gate | Scope | Tilladt stateændring | Miljø | Status |
|---|---|---|---|---|
| IT-G1 | Statisk/lokal infrastruktur og read-only API | Ingen | Lokal/R&D | NOT RUN samlet |
| IT-G2 | Auth/RBAC/read-only live API | Session/logevents | R&D | BLOCKED af FIND-TEST-001 |
| IT-G3 | Reversible CRUD/config | Kun `QA-` data; cleanup påkrævet | R&D | BLOCKED af FIND-TEST-001 |
| IT-G4 | Kamera/Edge/LAB/update | Fysisk teststate og signerede artifacts | R&D Edge | IN PROGRESS |
| IT-G5 | GDPR/sletning/retention | Maks. 10 gamle billeder; audit+rollback hvor muligt | R&D | NOT RUN |
| IT-G6 | Backup/restore/bare metal | Kun scratch DB/mål; aldrig operationel restore | Isoleret | NOT RUN |
| IT-G7 | Staging/prod acceptance | Kun godkendt release/change | Staging/prod | BLOCKED af miljø |

### 5.1 Integrationsmoduler

| Suite-ID | Modul | Primært lag | Destruktivitet | Gate | Status |
|---|---|---|---|---|---|
| ITS-001 | `test_api_integration.py` | API/kamera | Read-only + LAB-parametre | G2/G4 | NOT RUN |
| ITS-002 | `test_auth_integration.py` | Auth/RBAC/MFA | Reversibel, rate-limit | G2/G3 | BLOCKED |
| ITS-003 | `test_backup_restore.py` | Backup/API/scripts | Potentielt destruktiv | G6 | NOT RUN |
| ITS-004 | `test_bare_metal_restore.py` | DR/system | Destruktiv uden isolation | G6 | NOT RUN |
| ITS-005 | `test_break_glass.py` | Security/operations | Privilegeret | G1/G7 | NOT RUN |
| ITS-006 | `test_camera_crud.py` | Kamera/RBAC | Reversibel QA-data | G3/G4 | NOT RUN |
| ITS-007 | `test_credential_rotation.py` | Keys/certs | Høj risiko | G1/G7 | NOT RUN |
| ITS-008 | `test_device_management.py` | CMDB/device | Reversibel QA-data | G3 | NOT RUN |
| ITS-009 | `test_e2e_workflows.py` | Capture/update/user | Blandet | G2-G5 | NOT RUN |
| ITS-010 | `test_eslint_compliance.py` | UI quality | Ingen | G1 | NOT RUN integration marker |
| ITS-011 | `test_fail2ban_security.py` | Host security | Kan blokere IP | G1 isoleret | NOT RUN |
| ITS-012 | `test_gdpr_redaction.py` | GDPR/image | Dataændrende | G5 | NOT RUN |
| ITS-013 | `test_mfa_ui_workflow.py` | MFA/WebAuthn | Kontoændrende | G3 | BLOCKED |
| ITS-014 | `test_mtls_security.py` | PKI/mTLS | Certifikatstate | G1/G7 | NOT RUN |
| ITS-015 | `test_nginx_8443_config.py` | Network/TLS | Read-only/statisk | G1 | NOT RUN |
| ITS-016 | `test_node_agent_launchd.py` | macOS service | Lokal service | G1 | NOT RUN |
| ITS-017 | `test_os_offline_update.py` | Edge update | Høj risiko | G4 | NOT RUN |
| ITS-018 | `test_retention_policy.py` | GDPR/retention | Blandet | G1/G5 | NOT RUN markeret suite |
| ITS-019 | `test_thumbnail_generation.py` | Images/jobs/RBAC | Reversibel | G2/G4 | NOT RUN |
| ITS-020 | `test_user_management_crud.py` | User/RBAC | Reversibel QA-data | G3 | BLOCKED |
| ITS-021 | `test_weekend_features_api.py` | Redaction/retention/jobs | Blandet | G2/G5 | NOT RUN |

## 6. UI verification register

Dette afsnit overtager alle aktive cases fra `UI_TESTJOURNAL_v1.md`.

### 6.1 Route og responsiv rendering

| Test-ID | Område | Desktop | Tablet | Mobil | Funktionel status | Seneste evidens |
|---|---|---|---|---|---|---|
| UI-001 | Dashboard | PASS | PASS | PASS | PASS read-only | Browser routepass 2026-07-16 |
| UI-002 | Device/billeder/tidslinje/statistik/config | PASS | PASS | PASS | PASS partial | 85 ægte frames; tabs/lightbox |
| UI-003 | Kamera/profil/binding | PASS render | PASS | PASS | NOT RUN write | H1-semantic afvigelse observeret |
| UI-004 | Nikon Z30 LAB | PASS render | PASS | PASS | NOT RUN full | Fysisk kamera kræves |
| UI-005 | Timelapse video | PASS | PASS | PASS | PASS partial | Include/exclude/lightbox |
| UI-006 | Tagsøgning | PASS | PASS | PASS | PASS partial | Ægte tag og resultatlimit |
| UI-007 | Settings/global config | PASS | PASS | PASS | NOT RUN write | Arv/override mangler |
| UI-008 | Backup/Edge ISO/DR | PASS | PASS | PASS | NOT RUN jobs | |
| UI-009 | System admin/notifications | PASS | PASS | PASS | PASS read-only | |
| UI-010 | Users/keys/SSH | PASS | PASS | PASS | NOT RUN write | |
| UI-011 | Updates/change tickets | PASS | PASS | PASS | PASS app E2E | lab.14/lab.15 |
| UI-012 | Compliance/retention/redaction | PASS | PASS | PASS | PASS read-only | Writeflows mangler |
| UI-013 | CMDB/detail | PASS | PASS | PASS | PASS read-only | Overflow rettet |
| UI-014 | SIEM/drift | PASS | PASS | PASS | PASS partial | Tabs/periode/live-pause |
| UI-015 | Import/AI/OpenWebUI/postprocess | PASS | PASS | PASS | PASS navigation | Jobs/model-save mangler |

### 6.2 Kritiske funktionsflows

| Test-ID | Flow | Acceptkriterium | Status | Evidens / næste handling |
|---|---|---|---|---|
| UI-AUTH-01 | Login/logout/cookie | Gyldigt login; logout invalid; sane cookie | NOT RUN | ITS-002 |
| UI-AUTH-02 | RBAC 4 roller | Menusynlighed + server-side 403 | NOT RUN | Opret isolerede QA-identiteter |
| UI-AUTH-03 | User CRUD | `QA-` bruger, audit, cleanup | BLOCKED | FIND-TEST-001 |
| UI-AUTH-04 | MFA/WebAuthn | Enrollment, recovery, step-up, audit | BLOCKED | FIND-TEST-001 og authenticator |
| UI-CAM-01 | Capture/thumbnail | Ingen synkron generation; baggrundsrepair | NOT RUN | Ægte billeder |
| UI-CAM-02 | LAB state | UI efter Edge-kvittering | NOT RUN | Nikon Z30 |
| UI-CAM-03 | Preview/full/stream | Visning i LAB; reel stream | NOT RUN | Reverse tunnel |
| UI-CAM-04 | Fokus/parametre | Save/readback, ingen Unknown | NOT RUN | Nikon Z30 |
| UI-UPD-01 | Dirty artifact | Afvis registrering/binding | PASS | `40cbef1b` |
| UI-UPD-02 | Signed tag/candidate | GPG, clean snapshot, SHA, candidate | PASS | lab.14/lab.15 |
| UI-UPD-03 | Approval UX | Modal viser ID/release/miljø/scope | PASS | #104 open/cancel |
| UI-UPD-04 | Edge app E2E | poll/trust/backup/install/receipt/report | PASS | #105 og #108 test-deployed |
| UI-UPD-05 | Supersession | Kun nye pending; historik i Erstattet | PASS | 62 gamle kandidater superseded |
| UI-UPD-06 | OS offline | Headend artifact; ingen Edge-internet | NOT RUN | #91 |
| UI-UPD-07 | Rollback | Backup + known-good receipt/version | NOT RUN | R&D Edge |
| UI-UPD-08 | Ollama/Headend app | Identitet, backup, install, postflight, CMDB | NOT RUN | |
| UI-BKP-01 | Backup create/verify | Checksums, image mirror, audit | NOT RUN | PROC-BKP-01 |
| UI-BKP-02 | Scratch restore | Ingen operationel DB; RTO/RPO | NOT RUN | PROC-BKP-01 |
| UI-GDPR-01 | Access audit | View/download logs user+image | NOT RUN | |
| UI-GDPR-02 | Delete/redact | Reason/audit; max 10 old images | NOT RUN | G5 |
| UI-AI-01 | Model/prompt save | DB, UI, provenance, rollback | NOT RUN | |
| UI-AI-02 | Real-image tagging | Precision/recall/quality with real images | NOT RUN | |
| UI-OPS-01 | Logs/alerts/mail | Search, tenant/RBAC, notification | NOT RUN | |
| UI-COMP-01 | Full-standard audit | Complete selected standard, evidence/export | NOT RUN | |

## 7. Technical verification register

| Test-ID | Kontrol | Status | Evidens / restarbejde |
|---|---|---|---|
| TV-001 | Python syntax all tracked files | PASS | GitHub CI |
| TV-002 | Shell syntax all tracked files | PASS | GitHub CI |
| TV-003 | Unit/contract suite | PASS | BL-001 |
| TV-004 | UI TypeScript/build | PASS | GitHub CI |
| TV-005 | ESLint no-regression | PASS ratchet | 186 eksisterende fund skal reduceres |
| TV-006 | Route auth sweep | PASS contract | Vedligehold allowlist |
| TV-007 | Architecture ratchet | PASS | `main.py` må ikke vokse |
| TV-008 | mTLS/CA/revocation/expiry | NOT RUN live | ITS-014 |
| TV-009 | Nginx/TLS/ports | PASS R&D partial | Prod/staging acceptance mangler |
| TV-010 | fail2ban/rate-limit | NOT RUN samlet | ITS-011/002 |
| TV-011 | Backup restore | NOT RUN | PROC-BKP-01 |
| TV-012 | License/SBOM | PASS report partial | Runtime/prod inventory recheck |
| TV-013 | Edge commissioning doctor | NOT RUN deployed lab.15 | Fysisk accept |

## 8. Procedure register

### PROC-BKP-01 - Headend backup og scratch restore

**Kilde:** `BACKUP_RESTORE_TEST_PROCEDURE_v1.md` (indhold overtaget; kilden er procedure-reference).  
**Sikkerhedsregel:** Restore må aldrig pege mod operationel `timelapse_db`.

1. Vælg backup-ID og registrer checksum, timestamp, source host og omfang.
2. Udpak i ny scratch-mappe uden overskrivning.
3. Verificer manifest og checksum før restore.
4. Opret unik scratch PostgreSQL-database.
5. Restore database til scratch; valider schema, kritiske tabeller og row counts.
6. Verificer config-arkivets forventede filer, permissions og fravær af eksponerede secrets.
7. Verificer billed-mirror med filantal, stikprøvehash og læsbarhed; billeder må ikke slettes.
8. Kør applikations-/healthcheck mod isoleret restore, hvis muligt.
9. Registrer RTO, opnået RPO, afvigelser og cleanup.
10. Drop kun scratch-database og scratch-filer efter evidens er gemt.

**Status:** NOT RUN mod seneste reelle backup.  
**Accept:** Restore kan gennemføres reproducerbart uden adgang til eller ændring af operationel DB.

## 9. Integrated finding and risk register

| Finding-ID | Kilde-ID | Fund/risiko | CIA/impact | Prioritet | Status | Verifikation/remediation |
|---|---|---|---|---|---|---|
| FIND-TEST-001 | VPEN-013 / Incident 2026-07-15 | Integration harness har hardcodede credentials og direkte operationel DB-fallback | Integritet, assurance | P0 | OPEN | Fjern DB-fallback; env/secret QA creds; destructive gate |
| FIND-UPD-001 | Ny 2026-07-16 | Dirty worktree kunne signeres som release | Supply-chain integrity | P0 | CLOSED | UI-UPD-01 |
| FIND-UPD-002 | Ny 2026-07-16 | Grøn deploy kunne fastholde gammel cached UI | Integrity/availability | P1 | CLOSED | Commit-versionerede assets + Nginx revalidation |
| FIND-UPD-003 | Ny 2026-07-16 | Gamle app-kandidater fremstod godkendelige | Change integrity | P1 | CLOSED | Supersession; UI-UPD-05 |
| FIND-UPD-004 | HLTH-008 | Multi-target rollout kræver live 2+ device accept | Integrity/availability | P1 | VERIFY | Site-scope live test mangler |
| FIND-SEC-001 | R24 | Translation/statistics auth-regression | Availability/customer UX | P1 | OPEN | Viewer read; admin write; regressionstest |
| FIND-SEC-002 | R25 | Disable-MFA mangler fuld step-up assurance | Confidentiality/access | P1 | OPEN/VERIFY | Kode/teststatus reevalueres live |
| FIND-ARCH-001 | R26/P2-01 | Legacy `main.py` vedligeholdelsesrisiko | Integrity/changeability | P1 | MITIGATING | Ratchet + modular extraction |
| FIND-BKP-001 | R09/E-01/E-02 | Seneste reelle backup/restore-evidens mangler | Availability/integrity | P0 go-live | OPEN | PROC-BKP-01 |
| FIND-PKI-001 | R05 | Edge mTLS/CA/revocation live assurance mangler | Confidentiality/integrity | P0 go-live | OPEN | TV-008 |
| FIND-GDPR-001 | R12 | DPIA/retention/subprocessor/site acceptance | Legal/privacy | P0 go-live | OPEN | UI-GDPR + governance |
| FIND-NET-001 | VPEN-001/A-series | Prod 8443/port ownership/cert/firewall ikke accepteret | External attack surface | P0 go-live | OPEN | Staging/prod port audit |
| FIND-CRED-001 | C-10/D-06 | Stale device credentials | Unauthorized access | P1 | OPEN | Revoke/migrate med continuity evidence |
| FIND-OBS-001 | F-series | Freshness, node-agent og alerts delvist verificeret | Availability/detection | P1 | OPEN | UI-OPS-01 + live checks |
| FIND-UI-001 | UI routepass | Kamera-route mangler level-1 heading | Accessibility/UX | P3 | OPEN | Semantisk UI-fix og browserretest |

## 10. Control mapping

| Control-familie | Registerevidens | Hovedgaps |
|---|---|---|
| SABSA | Business attributes, risk IDs, environment gates, evidence chain | Kvantitativ business impact og owner acceptance |
| COBIT | BAI06 change, DSS01 operations, DSS04 continuity, MEA assurance | KPI/KRI og formel control owner |
| ISO 27001:2022 | A.5 policies, A.8 assets/change/logging/vulnerability, A.5.30 continuity | Restore, supplier/cloud and periodic review evidence |
| IEC 62443 | Zones/conduits, least privilege, signed offline Edge update, audit | SL-target, cert lifecycle and staging acceptance |
| CRA | Secure-by-design, vulnerability handling, SBOM, secure updates | Product classification, reporting operations, support period |
| NIS2 | Risk measures, incident handling, supply chain, continuity | Legal applicability and management approval |
| GDPR | Access audit, deletion reasons, retention, redaction, DPIA | Site DPIA, notices, DPA/subprocessors and live deletion tests |
| AI Act | Model/prompt provenance, human review, real-image testing | Classification, data governance, monitoring and transparency |

## 11. Go-live verification gates

| Gate-ID | Krav | Status | Blokerende fund |
|---|---|---|---|
| GL-01 | Internet-port, TLS, DNS, firewall og CrushFTP coexistence accepteret | BLOCKED | FIND-NET-001 |
| GL-02 | Auth/RBAC/MFA/rate-limit integrationstest grøn | BLOCKED | FIND-TEST-001, FIND-SEC-002 |
| GL-03 | CA/mTLS/revocation/expiry testet end-to-end | BLOCKED | FIND-PKI-001 |
| GL-04 | Backup + scratch restore med RTO/RPO evidens | BLOCKED | FIND-BKP-001 |
| GL-05 | Signed update/rollback for app, OS og Headend | PARTIAL | UI-UPD-06/07/08 |
| GL-06 | GDPR/DPIA/retention/access/deletion | BLOCKED | FIND-GDPR-001 |
| GL-07 | Monitoring, SIEM, alert og disk/NAS | PARTIAL | FIND-OBS-001 |
| GL-08 | Staging parity og promotion evidence | BLOCKED | Staging ikke etableret |
| GL-09 | CI, SBOM, license og vulnerability process | PARTIAL | Integration/live assurance |
| GL-10 | Residual risks accepted by accountable owner | BLOCKED | Open P0/P1 findings |

## 12. Evidence ledger

| Evidence-ID | Dato | Scope | Resultat | Reference |
|---|---|---|---|---|
| EV-20260716-01 | 2026-07-16 | Full unit/contract gate | PASS 588/4 skipped/543 deselected | Local CI-identical command |
| EV-20260716-02 | 2026-07-16 | UI routepass 27 routes | PASS read-only | In-app browser |
| EV-20260716-03 | 2026-07-16 | App update lab.14 | PASS Edge test deploy | #105, tag `v2.8.1-lab.14` |
| EV-20260716-04 | 2026-07-16 | App update lab.15 + supersession | PASS | #108, tag `v2.8.1-lab.15`, 62 superseded |
| EV-20260716-05 | 2026-07-16 | Approval modal | PASS open/cancel, no state change | #104 browser QA |
| EV-20260716-06 | 2026-07-16 | Integration harness audit | FAIL safety | `tests/conftest.py` direct DB fallback |

## 13. Source migration and document status

| Kildedokument | Ny status | Overtaget til |
|---|---|---|
| `MASTER_TEST_CHECKLIST_v1.md` | SUPERSEDED som aktiv status; reference | §§4-7, 9-11 |
| `UI_TESTJOURNAL_v1.md` | SUPERSEDED som aktiv status; reference | §6 og §12 |
| `BACKUP_RESTORE_TEST_PROCEDURE_v1.md` | PROCEDURE REFERENCE | PROC-BKP-01 |
| `RISK_ASSESSMENT_v10.md` | HISTORISK BASELINE | §9-11; detaljer fortsat kilde |
| `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md` | DELTA SOURCE | §9-11 |
| `SYSTEM_HEALTH_REGISTER.md` | HISTORISK FINDING SOURCE | §9 |
| `GO_LIVE_CHECKLIST_v10.md` | REQUIREMENT SOURCE | §11 |
| `Claude_QA_Arkitektur_Review_2026-07-15.md` | REVIEW EVIDENCE | §9 |
| `Codex_REVIEW_Claude_Arkitektur_Risk_Test_2026-07-15.md` | REVIEW EVIDENCE | §9-10 |
| `Gamle versioner/*QA*`, `*TEST*`, `*PENTEST*` | HISTORISK EVIDENS | Ikke aktiv status |

## 14. Næste handlinger

| Prioritet | Handling | Relateret ID | Status |
|---|---|---|---|
| P0 | Ret integration harness og credentialmodel | FIND-TEST-001 | IN PROGRESS |
| P0 | Kør auth/RBAC read-only integrationsgate | IT-G2 | BLOCKED |
| P0 | Kør backup + scratch restore | PROC-BKP-01 | NOT RUN |
| P0 | Test Edge OS offline update #91 | UI-UPD-06 | NOT RUN |
| P1 | Browserinventar og alle knapper/funktioner | §6 | IN PROGRESS |
| P1 | Test rollback af signerede Edge app artifact | UI-UPD-07 | NOT RUN |
| P1 | Identificer og test Ollama update | UI-UPD-08 | NOT RUN |
| P1 | Kør mTLS/revocation/expiry | TV-008 | NOT RUN |
| P1 | Kør GDPR access/delete/redaction | UI-GDPR | NOT RUN |

## 15. Dokumenthistorik

| Version | Dato | Ændring |
|---|---|---|
| 1.0 | 2026-07-16 | Første kanoniske konsolidering af master test checklist, UI-journal, backup restore, risk, health, go-live og QA-review. |
