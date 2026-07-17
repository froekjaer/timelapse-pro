# TimeLapse Pro - UI-testjournal

**Version:** 1.0  
**Oprettet:** 2026-07-16  
**Miljø:** R&D Headend `https://timelapse.froekjaer.dk`  
**Aktiv Edge:** `TL-C87FF9587CA0`  
**Testbruger:** `codex`, rolle `super_admin`  
**Formål:** Sporbar browserbaseret funktions-, integrations-, responsiv- og brugervenlighedstest af hele UI'et.

> **Reference/arbejdsjournal.** Autoritativ testcase-, run-, finding- og
> evidensstatus ligger i PostgreSQL GRC-registeret og vises i Compliance ->
> GRC register. Journalen er narrativ evidens, ikke statuskilde.

## 1. Statusdefinitioner

| Status | Betydning |
|---|---|
| PASS | Testet i browser med forventet resultat og relevant før/efter-state |
| FAIL | Reproducerbar afvigelse; issue/rettelse skal angives |
| BLOCKED | Kan ikke gennemføres før en dokumenteret afhængighed er opfyldt |
| NOT RUN | Testcase er identificeret, men endnu ikke kørt |
| N/A UI | Teknisk integrationstest uden meningsfuld UI-handling |

En grøn route/render-test er ikke det samme som en grøn funktions-/skrivetest. Destruktive handlinger kræver afgrænset testdata, audit-evidens og rollback.

## 2. Forholdet til de 543 fravalgte tests

CI kører `pytest -m "not integration"`. Ved seneste kørsel blev 543 tests derfor deselected. De ligger primært i 21 integrationsmoduler og omfatter både UI-understøttede flows og tekniske kontroller.

| Gruppe | Eksempler | Browser kan dække | Separat teknisk test kræves |
|---|---|---:|---:|
| Auth og brugeradministration | login, logout, RBAC, MFA, CRUD | Ja | Ja |
| Kamera og billeder | captures, thumbnails, LAB-parametre | Ja | Ja |
| Update governance | kandidater, approve, Edge pull, rollback | Ja | Ja |
| Backup/restore | jobstart, status, download | Delvist | Ja, isoleret restore |
| Infrastruktur | mTLS, fail2ban, Nginx, launchd | Nej/delvist | Ja |
| Edge/offline OS | signatur, bundle, installation, rollback | Delvist | Ja, fysisk Edge |
| GDPR/retention | visning, redaktion, sletning, audit | Ja | Ja |

Browserjournalen dokumenterer brugeroplevelsen. Pytest/API-, database-, filsystem-, certifikat- og fysisk Edge-evidens dokumenteres i samme testcase, men må ikke erstattes af et visuelt PASS.

## 3. Testmiljø og sikkerhedsregler

- Brug kun R&D/testmiljø, medmindre testcase udtrykkeligt er godkendt til staging/prod.
- Ingen direkte internet-, GitHub- eller apt-installation fra Edge.
- Ingen automatisk billedsletning. Højst 10 gamle billeder må anvendes til kontrolleret sletning; årsag og auditlog skal verificeres.
- Oprettede testbrugere, tickets og konfigurationer skal have genkendeligt `QA-` prefix og ryddes kontrolleret.
- Reelle billeder anvendes til AI-, thumbnail- og billedkvalitetstest.
- Browserkonsol, HTTP 4xx/5xx, SIEM-event og relevant backend/Edge-status indgår i evidensen.

## 4. Route- og responsiv baseline

Tidligere Codex-browserpass 2026-07-16 åbnede alle beskyttede routes på desktop, 390x844 mobil og 800x1024 tablet. Ingen aktuel HTTP 500/503 eller login-loop blev observeret. Device- og CMDB-overflow blev rettet og genverificeret. Denne baseline genkøres efter større navigation/layoutændringer.

| ID | Route/menu | Desktop | Tablet | Mobil | Funktionel status | Bemærkning |
|---|---|---|---|---|---|---|
| UI-001 | Dashboard `/` | PASS | PASS | PASS | PASS read-only | Navigation og statuskort |
| UI-002 | Device `/devices/TL-C87FF9587CA0` | PASS | PASS | PASS | PASS partial | Billeder, tidslinje, statistik, config-faner |
| UI-003 | Kamera `/cameras/TL-C87FF9587CA0` | PASS | PASS | PASS | NOT RUN write | Profil/binding/parametre |
| UI-004 | LAB `/devices/TL-C87FF9587CA0/lab` | PASS | PASS | PASS | NOT RUN full | Fysisk Nikon Z30-flow kræves |
| UI-005 | Timelapse `/devices/TL-C87FF9587CA0/timelapse` | PASS | PASS | PASS | PASS partial | Lightbox og include/exclude testet |
| UI-006 | Tags `/tags` | PASS | PASS | PASS | PASS partial | Søgning med ægte tag testet |
| UI-007 | Indstillinger `/settings` | PASS | PASS | PASS | NOT RUN write | Save/rollback mangler |
| UI-008 | Global config `/global-config` | PASS | PASS | PASS | NOT RUN write | Arv/override kræver matrix |
| UI-009 | Backup `/backup` | PASS | PASS | PASS | NOT RUN jobs | Headend DR, Edge restore/ISO |
| UI-010 | System Administration `/system-admin` | PASS | PASS | PASS | PASS read-only | Skrivehandlinger mangler |
| UI-011 | Notifikationer `/notifications` | PASS | PASS | PASS | NOT RUN write | Mail/integrationstest mangler |
| UI-012 | Brugere `/users` | PASS | PASS | PASS | PASS partial | Viewer-afvisning og QA-brugeroprettelse testet; rediger/deaktiver/slet mangler |
| UI-013 | Nøgler `/key-management` | PASS | PASS | PASS | NOT RUN destructive | Rotation/revocation isoleres |
| UI-014 | SSH `/ssh-tunnel` | PASS | PASS | PASS | NOT RUN live | Tunnelstart/stop kræver Edge |
| UI-015 | Opdateringer `/updates` | PASS | PASS | PASS | PASS E2E app | Se UI-201..UI-209 |
| UI-016 | Change tickets `/change-tickets` | PASS | PASS | PASS | NOT RUN workflow | Ticket/evidence/export |
| UI-017 | Compliance `/compliance` | PASS | PASS | PASS | PASS read-only | Faner testet; rapport/audit mangler |
| UI-018 | Retention `/retention` | PASS | PASS | PASS | NOT RUN write | Ingen automatisk billedsletning |
| UI-019 | GDPR redaction `/redaction` | PASS | PASS | PASS | NOT RUN destructive | Afgrænset ægte billede kræves |
| UI-020 | CMDB `/cmdb` | PASS | PASS | PASS | PASS read-only | Version/SBOM/detail responsive |
| UI-021 | CMDB detail | PASS | PASS | PASS | PASS read-only | Aktiv Edge og Headend |
| UI-022 | SIEM `/siem` | PASS | PASS | PASS | PASS partial | Faner, periode, pause/live testet |
| UI-023 | Import `/import` | PASS | PASS | PASS | NOT RUN write | Afgrænset importfil kræves |
| UI-024 | AI `/ai` | PASS | PASS | PASS | PASS navigation | Modelkørsel og prompt-save mangler |
| UI-025 | Open WebUI `/openwebui` | PASS | PASS | PASS | PASS partial | Runtime start/stop/timeout mangler |
| UI-026 | Post-processing `/post-processing` | PASS | PASS | PASS | NOT RUN jobs | Thumbnail/AI-job med ægte billeder |
| UI-027 | Drift `/observability` | PASS | PASS | PASS | PASS read-only | Log/detail/actions mangler |

## 5. Funktionelle testcases

### 5.1 Authentication og brugere

| ID | Test | Forventet | Status | Pytest-reference | Evidens/resultat |
|---|---|---|---|---|---|
| UI-101 | Gyldigt login/logout | Sikker cookie; logout invaliderer session | PASS | `test_auth_integration.py` | Browser-login/logout samt isoleret API-test 2026-07-17 |
| UI-102 | Forkert login og rate limit | Generisk fejl; throttling; SIEM-event | NOT RUN | `test_auth_integration.py` | |
| UI-103 | Viewer/operator/admin RBAC | Korrekte menuer og 403 på forbudte handlinger | PASS partial | `test_auth_integration.py` | 31/31 kørte auth/tenant-tests bestod; viewer-backend afviste brugeroprettelse og anden tenant. UI-regression af rollebaseret navigation afventer deploy. |
| UI-104 | Opret `QA-` bruger | Bruger vises; auditlog oprettes | PASS partial | `test_user_management_crud.py` | `QA-viewer-20260717` oprettet via ægte UI; audit-verifikation og oprydning mangler. |
| UI-105 | Rediger rolle/email/aktiv | Ændring slår igennem og auditeres | NOT RUN | `test_user_management_crud.py` | |
| UI-106 | Passwordvalidering | Politik vises og håndhæves server-side | NOT RUN | `test_user_management_crud.py` | |
| UI-107 | MFA enrollment | QR, TOTP, recovery og audit virker | NOT RUN | `test_mfa_ui_workflow.py` | Kræver afgrænset QA-bruger |
| UI-108 | WebAuthn | Register/login/remove credential | BLOCKED | `test_auth_integration.py` | Kræver kompatibel authenticator |
| UI-109 | Deaktivér/slet QA-bruger | Login blokeres; self/primary admin beskyttes | NOT RUN | `test_user_management_crud.py` | |

### 5.2 Kamera, billeder og LAB

| ID | Test | Forventet | Status | Pytest-reference | Evidens/resultat |
|---|---|---|---|---|---|
| UI-121 | Captures og pagination | Ægte billeder vises uden synkron thumbnail-generering | PASS partial | `test_api_integration.py`, `test_e2e_workflows.py` | 85 frames/lightbox testet 2026-07-16 |
| UI-122 | Manglende thumbnail | Baggrundsjob opretter fil; refresh viser den | NOT RUN | `test_thumbnail_generation.py` | Kendt fejl skal genprøves |
| UI-123 | Billedadgang audit | Visning/download registrerer bruger og billede | NOT RUN | capture access tests | |
| UI-124 | LAB start/stop real state | UI må først vise aktiv efter Edge-kvittering | NOT RUN | LAB contract tests | Nikon Z30 fysisk test |
| UI-125 | Preview/full capture | Resultat vises i LAB; metadata gemmes | NOT RUN | `test_api_integration.py` | |
| UI-126 | Live stream | Reel stream, ikke serie af stills | NOT RUN | LAB runtime tests | Reverse SSH kræves |
| UI-127 | Fokus/parameterændring | Nikon-værdier gemmes og læses tilbage | NOT RUN | camera tests | |
| UI-128 | Edge AI quality/autoadjust | Anbefaling, guardrails og audit vises | NOT RUN | Edge AI tests | Ægte billeder kræves |

### 5.3 Update-flow

| ID | Test | Forventet | Status | Evidens/resultat |
|---|---|---|---|---|
| UI-201 | Dirty worktree artifact | Registrering/binding afvises fail-closed | PASS | Rettet i `40cbef1b`; dirty artifact bevaret som evidens |
| UI-202 | Signeret Git-tag | Clean snapshot, GPG, SHA og kandidater | PASS | `v2.8.1-lab.14` og `.15` registreret via UI |
| UI-203 | Godkendelsesmodal | ID, release, miljø og scope er synlige | PASS | `#104` åbnet/annulleret uden stateændring |
| UI-204 | Edge app E2E | poll, trust, backup, install, receipt, report | PASS | `#105` lab.14 og `#108` lab.15 deployet til aktiv Edge i test |
| UI-205 | Aktiv status øverst | Kun aktuelle flows vises med live trin | PASS | Sticky status viste `#108`; stale `#33` blev fundet og filtreret i efterfølgende fix |
| UI-206 | Supersession | Ældre pending kandidater flyttes til Erstattet | PASS | 62 gamle kandidater; kun tre aktuelle app-kandidater tilbage |
| UI-207 | Test til prod-klar | Kræver eksplicit testaccept; ingen auto-prod | PASS | `#105/#108` forblev test efter deploy |
| UI-208 | Edge OS offline update | Signeret bundle fra Headend; ingen Edge-internet | PASS | `#91`: 9/9 deb-filer, signatur/trust/backup/install/receipt gennemført fra Headend uden Edge-internet |
| UI-209 | Rollback | Backup verificeres; gammel receipt/version gendannes | NOT RUN | Skal udføres kontrolleret på R&D Edge |
| UI-210 | Headend app/Ollama | Lab-test, backup, install, postflight og CMDB-version | NOT RUN | Ollama skal identificeres præcist først |

### 5.4 Backup, GDPR, drift og compliance

| ID | Test | Forventet | Status | Pytest-reference | Evidens/resultat |
|---|---|---|---|---|---|
| UI-301 | Headend backup/verify | Job, checksum, restore-evidens og fejlvisning | NOT RUN | `test_backup_restore.py` | |
| UI-302 | Edge backup/restore | Backup vises; isoleret restore valideres | NOT RUN | backup tests | |
| UI-303 | Edge ISO build/download/delete | Signeret image, katalog, sikker sletning | NOT RUN | image build tests | |
| UI-304 | Retention-save | Arv/override og audit; ingen automatisk fotosletning | NOT RUN | `test_retention_policy.py` | |
| UI-305 | Specifik billedsletning | Årsag kræves; audit; max 10 gamle testbilleder | NOT RUN | deletion tests | |
| UI-306 | GDPR redaction | Original beskyttes; redigeret output/audit | NOT RUN | `test_gdpr_redaction.py` | |
| UI-307 | Logkonsol | Filtre, pagination, tenant/RBAC og download | NOT RUN | SIEM/log tests | |
| UI-308 | Mailalarm | Regel, testmail, rate limit og audit | NOT RUN | notification tests | |
| UI-309 | Compliance audit/rapport | Fuld valgt standard, evidens og eksport | NOT RUN | compliance tests | |
| UI-310 | CMDB version/SBOM | Installeret og seneste version er entydige | PASS partial | Aktiv Edge/app verificeret; Ollama/OS mangler |

## 6. Ikke-UI integrationstests

Disse køres separat med pytest/systemevidens og må ikke markeres PASS alene via browser:

- `test_mtls_security.py`: certifikatkæde, revocation og expiry-policy.
- `test_fail2ban_security.py`: logbaseret blokering og unban.
- `test_nginx_8443_config.py`: Nginx/TLS/port-konfiguration.
- `test_node_agent_launchd.py`: macOS launchd persistence og privilege.
- `test_os_offline_update.py`: offline bundle, signatur, dpkg og rollback.
- `test_backup_restore.py` og `test_bare_metal_restore.py`: faktisk restore i isoleret mål.
- `test_break_glass.py`: nødadgang med audit og efterfølgende rotation.
- De API-/databaseassertions i de øvrige integrationsmoduler, som ikke har en synlig UI-repræsentation.

## 7. Fund og ændringslog

| Dato | Fund | Alvor | Rettelse/status |
|---|---|---|---|
| 2026-07-16 | Dirty worktree kunne signeres som release | Kritisk | Fail-closed artifact trust implementeret |
| 2026-07-16 | Grøn deploy kunne vise cached gammel UI | Høj | Commit-versionerede assets og Nginx revalidation |
| 2026-07-16 | Godkendelsespanel var svært at opdage | Medium | Modal og sticky aktiv flowstatus |
| 2026-07-16 | 62 gamle kandidater så stadig godkendelige ud | Høj | Eksplicit `superseded` state og Erstattet-filter |
| 2026-07-16 | Gammel `#33` fyldte aktiv status | Medium | Aktivitet begrænset til nylige/startede flows |
| 2026-07-17 | Signeret `lab.16` Edge app E2E | Høj | `#111` gennemførte approval, poll, trust, backup, install og receipt på `TL-C87FF9587CA0` |
| 2026-07-17 | Edge artifact oprettede fejlagtigt Headend-kandidat | Høj | `#112` blokeret med årsag; fremtidige signed-tag Edge-kandidater ekskluderer Headenden |
| 2026-07-17 | Inaktiv gammel Edge fik release-kandidat | Medium | `#110` afvist; fravalg bevaret i update-auditsporet |
| 2026-07-17 | Viewer så skrivekontroller og kunne åbne brugeroprettelsesdialog | Høj | Backend afviste korrekt med 403; route guards og rollebaseret skjulning implementeret, afventer live regression efter deploy |
| 2026-07-17 | Dashboard brugte navnefelter og viste en korrekt bundet enhed som “uden kunde/site” | Medium | Device-API eksponerer nu stabile `customer_id`/`site_id`; dashboard grupperer på id med legacy fallback |
| 2026-07-17 | Topniveau-pytest kunne arve operational `DATABASE_URL` | Kritisk test-sikkerhed | `tests/conftest.py` tvinger nu `timelapse_test` før Headend-import; isoleret test-Headend på port 8011 anvendt |
| 2026-07-17 | `test_device_management.py` forventer gammel `{devices: [...]}` kontrakt | Medium testgæld | 11 testfejl klassificeret som forældede assertions, 4 bestod og 5 blev fravalgt; modernisering er næste testarbejde |

## 8. Exit-kriterier

UI-QA er først komplet, når:

1. Alle routecases har desktop/tablet/mobil PASS efter seneste væsentlige layoutændring.
2. Alle P0/P1 skriveflows er PASS eller dokumenteret BLOCKED med ejer og afhængighed.
3. Ingen uforklaret HTTP 500/502/503, konsolfejl eller login-loop forekommer.
4. RBAC og tenant-isolation er verificeret med mindst viewer, operator, admin og super_admin.
5. Update, backup/restore, GDPR, LAB og AI er testet med ægte R&D-data og evidens.
6. Ikke-UI integrationstests er kørt separat; browser-PASS bruges ikke som erstatning.
7. Fund er rettet, regressionstestet, committed til `main`, CI-grønne og registreret i `HANDOVER_LOG.md`.
