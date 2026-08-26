# TimeLapse Pro - UI usecase-katalog

**Dato:** 2026-08-26  
**Formål:** Praktisk katalog til manuel gennemgang af alt klikbart i TimeLapse Pro UI, inkl. oprette, ændre, slette, opdatere, godkende og driftsnære handlinger.  
**Kilde:** Aktuel UI-navigation, `MENUGUIDE_BRUGER_v1.md`, `MENUGUIDE_ADMIN_v1.md`, `UI_TESTJOURNAL_v1.md` og live browsergennemgang 2026-08-26.  
**Status:** Arbejdsdokument til UAT, support, demo, regressionsprøver og senere automatisering.

> Dette dokument er ikke en erstatning for GRC-registeret eller CI. Det er den menneskelige "kan vi faktisk bruge systemet?"-liste.

## 1. Grundregel for brugervenlighed

På hver side skal brugeren kunne forstå de vigtigste ting uden at scrolle eller gætte.

Øverst på siden bør der, hvor relevant, stå:

| Sideklasse | Vigtig top-information |
|---|---|
| Dashboard | Samlet status, aktive alarmer, ventende security/OS/app-opdateringer, enheder online/stale/offline |
| Enhed/kamera | Navn, kunde/site, device-id, online/stale/offline, seneste heartbeat, seneste capture, upload/backlog, camera/relay/PTP status |
| Drift/SIEM | Værste status, aktive alarmer, tidsvindue, berørt enhed, hurtig vej til evidens |
| Updates/change tickets | Hvad afventer handling, risiko, miljø, device scope, artifact/signatur, rollback-status |
| Backup/retention/GDPR | Sidste succes, næste planlagte handling, datarisiko, irreversible handlinger tydeligt markeret |
| Config/admin | Hvilket lag redigeres, hvilken effektiv værdi gælder, hvad arves, og hvornår ændringen slår igennem |
| Credential/SSH/service | Trust-status, capability/rollekrav, udløb/revocation, audit og fail-closed årsag |

Hvis en side viser samme begreb som en anden side, skal ordene betyde det samme. Eksempel: `Online` må ikke betyde 90 minutter på Dashboard og 30 minutter i Drift uden at UI'et forklarer forskellen.

## 2. Testprincipper

| Klasse | Må køres direkte i produktion? | Krav |
|---|---:|---|
| Read-only navigation, filtre, faner og fold-ud | Ja | Ingen stateændring; browserfejl og synlige fejl noteres |
| Refresh/opdater-knapper | Ja | Må kun hente data igen |
| Opret/rediger med `QA-` testdata | Kun efter aftale | Før/efter-state, audit og oprydning |
| Sletning, retention og GDPR-sløring | Ja, i kontrolleret UAT | Få ældre/udvalgte testbilleder, før/efter-state, irreversibilitet forstået, audit kontrolleret |
| Update-godkendelse/deploy/rollback | Kun kontrolleret change | Artifact, signatur, scope, rollback, Edge health gate |
| LAB/service/relay/camera power | Kun kontrolleret Edge-test | Teknikersession, timeout, cleanup, relay OFF efter teardown |
| SSH/browserterminal/break-glass | Kun eksplicit autoriseret | Verified host identity, capability, MFA, audit, timeout |
| Credentials/nøgler | Kun separat security-change | Lifecycle, migration path, fail-closed test, ingen private keys i UI |

### 2.1 Destruktiv UAT er tilladt, men skal være lille og sporbar

Peter har godkendt at vi i testfasen må slette et eller nogle få gamle/ældre billeder for at prøve hele data-lifecycle-flowet. Det er vigtigt for at verificere, at UI, backend, audit og compliance-evidens faktisk hænger sammen.

Destruktive UAT-handlinger skal derfor køres sådan:

| Regel | Praktisk krav |
|---|---|
| Brug få billeder | Vælg 1-3 gamle billeder, helst fra en tydeligt dokumenteret test-/lavrisiko-periode |
| Dokumenter før-state | Capture-id, filename, device, kunde/site/kamera, uploadstatus, SFTP/API-status hvis synligt |
| Udfør kun én type ad gangen | Først manuel billedsletning, senere retention cleanup, senere GDPR-sløring |
| Verificer efter-state | UI viser ændring, DB/API-status stemmer, fil/adgang opfører sig som forventet |
| Kontroller audit | SIEM/auditlog viser bruger, tidspunkt, billede, årsag og resultat |
| Stop ved uklarhed | Hvis UI ikke viser præcis hvad der bliver slettet eller ændret, skal flowet stoppes og forbedres |

Status `CONTROLLED UAT` betyder: skal prøves, men kun med ovenstående ramme.

## 3. Roller og testbrugere

| Rolle | Skal kunne | Må ikke kunne |
|---|---|---|
| Viewer | Se egne kunder/sites/captures, tags, compliance-read-only, hjælp | Adminmenu, users, keys, updates approval, terminal, sletning |
| Operator | Viewer plus begrænsede driftsopgaver efter capability | Credential/admin/security-governance |
| Admin | Drift, config, updates, backup, CMDB, SIEM, lokale access-flows | Super-admin-only brugeradministration |
| Super Admin | Alle administrative flows | Egen/primary admin-beskyttelse må stadig håndhæves |
| Technician | Service Operations gennem ServiceSession | Direkte GPIO, direkte hardwarelogik i UI/CLI |
| Break Glass | Kun nødsituation med audit og udløb | Normal daglig drift |

## 4. Usecase-format

Hver usecase kan senere kopieres til GRC eller Playwright.

| Felt | Betydning |
|---|---|
| ID | Stabil reference |
| Start | Menu/side |
| Handling | Hvad brugeren gør |
| Forventet resultat | Hvad UI/API/drift skal vise |
| Top-info check | Hvad der skal være synligt uden unødig scrolling |
| Sikkerhed/audit | Hvilke kontroller der skal være opfyldt |
| Status | `READY`, `NEEDS TESTDATA`, `CONTROLLED UAT`, `BLOCKED` eller `READ-ONLY PASS` |

## 5. Dashboard og navigation

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-DASH-001 | Enheder `/` | Åbn Dashboard | Kunder, sites og enheder vises uden fejl | Fleet-status, captures, kvalitet, upload, pending updates | Ingen | READ-ONLY PASS |
| UC-DASH-002 | Enheder `/` | Fold kunde/site ind og ud | Layout holder, tællere følger visning | Kunde/site online-tæller er tydelig | Ingen | READY |
| UC-DASH-003 | Enheder `/` | Klik aktiv enhed | Enhedsside åbner | Navn, site, device-id og status øverst | Tenant-scope | READ-ONLY PASS |
| UC-DASH-004 | Enheder `/` | Klik kamera-config ikon | Kamerasiden åbner | Kamera/site/device synligt | Admin-only hvis redigering | READ-ONLY PASS |
| UC-DASH-005 | Enheder `/` | Klik pending update indikator | Updates åbner med relevant kø/status | Antal security/OS/app tydeligt | Admin gating | READ-ONLY PASS |
| UC-DASH-006 | Enheder `/` | Klik Ny kunde | Formular åbner uden at oprette | Obligatoriske felter tydelige | Super-admin gating | READY |
| UC-DASH-007 | Alle sider | Åbn/luk navigation | Alle menuer vises, også på smal skærm | Aktuel side markeret | Ingen | READY |
| UC-DASH-008 | Alle sider | Klik kontekstuel hjælp | Rigtigt hjælpekapitel åbner | Hjælp er tilgængelig øverst | Ingen | READY |

## 6. Login, session og RBAC

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-AUTH-001 | `/login` | Log ind med gyldig bruger | Dashboard åbner | Bruger/rolle synlig i navigation | Session-cookie sikker | READY |
| UC-AUTH-002 | `/login` | Forkert password gentagne gange | Generisk fejl, rate limit, SIEM-event | Fejl uden credential-læk | Auth-audit | NEEDS TESTDATA |
| UC-AUTH-003 | Navigation | Log ud | Session invalideres og login vises | Ingen brugerdata efter logout | Session revoke | READY |
| UC-AUTH-004 | Viewer | Åbn admin-route direkte | Ingen adgang | Forklarende besked | RBAC server-side | NEEDS TESTDATA |
| UC-AUTH-005 | Admin-følsom handling | Kræv MFA/step-up | Handling blokeres uden MFA | Krav står før handling | MFA audit | NEEDS TESTDATA |

## 7. Enheder, billeder og kamera

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-DEV-001 | Enhedsside | Åbn Billeder | Seneste billeder vises | Seneste capture og uploadstatus øverst | Capture access audit ved åbning/download | READY |
| UC-DEV-002 | Enhedsside | Åbn Tidslinje | Kalender og dagliste vises | Antal billeder og valgt periode | Tenant-scope | READY |
| UC-DEV-003 | Enhedsside | Åbn Statistik | Health/capture/camera stats vises | CPU, disk, backlog, camera status | Ingen | READY |
| UC-DEV-004 | Enhedsside | Åbn Konfiguration | Identitet og arvet config vises | Effektiv config og lag | Admin for save | READY |
| UC-DEV-005 | Enhedsside | Rediger enhedsidentitet til eksisterende site/kamera | Binding opdateres relationelt | Ny kunde/site/kamera synlig | Audit, ingen løs fritekstbinding | NEEDS TESTDATA |
| UC-DEV-006 | Enhedsside | Opret ny kamera-lokation via dropdown | Ny lokation oprettes og bindes | Location vs device forklares | Audit og rollback/oprydning | NEEDS TESTDATA |
| UC-DEV-007 | Billede | Åbn thumbnail/lightbox | Billede, metadata og tags vises | QA/upload/tid/device synligt | Capture access audit | READY |
| UC-DEV-008 | Billede | Rediger tags på udvalgte billeder | Tags ændres og vises efter refresh | Valgte antal billeder synligt | Audit, tenant-scope | NEEDS TESTDATA |
| UC-DEV-009 | Billede | Slet afgrænset gammelt/testbillede | Kræver årsag, audit, billedet fjernes | Irreversibel advarsel øverst i modal | 1-3 udvalgte billeder, audit og efterkontrol | CONTROLLED UAT |
| UC-CAM-001 | Kameraside | Åbn kamera-config | Identitet, AI-kontekst, driftanalyse, BT PAN sektioner vises | Kamera/site/device og status øverst | Admin gating | READY |
| UC-CAM-002 | Kameraside | Rediger AI-kontekst | Gemmes og bruges i senere analyse | Hvad påvirkes står ved feltet | Audit | NEEDS TESTDATA |
| UC-CAM-003 | Kameraside | Rediger retention/parametre | Effektiv værdi ændres på korrekt lag | Arv/override tydeligt | Audit og config-version | NEEDS TESTDATA |
| UC-CAM-004 | Kameraside | Vis QR/TOTP | Kode vises kun her og kun kortvarigt | Sensitiv adgang markeret | Admin+tenant; må ikke logges | NEEDS TESTDATA |
| UC-CAM-005 | Kameraside | Omassign til anden lokation | Billeder følger lokation, hardware kan skiftes | Konsekvens forklares før save | Audit | NEEDS TESTDATA |

## 8. Tags, søgning og AI på billeder

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-TAG-001 | Tag søgning | Klik populært tag | Resultater filtreres | Aktivt filter øverst | Tenant-scope | READY |
| UC-TAG-002 | Tag søgning | Brug dato/kunde/site/kamerafilter | Kun matchende billeder vises | Filterresume synligt | Ingen | READY |
| UC-TAG-003 | Tag søgning | QA søgning | QA-filtre og resultater vises | Pass/fail/deviation synligt | Ingen | READY |
| UC-TAG-004 | Tag søgning | AI fritekstsøgning | Forespørgsel giver forståelig respons/resultater | Query og confidence synlig | AI read-only | READY |
| UC-TAG-005 | AI Styring | Tag Review - godkend/afvis tag | Tag flyttes ud af kø | Antal afventende synligt | Audit | NEEDS TESTDATA |
| UC-TAG-006 | AI Styring | Tag Oprydning - kør analyse | Grupper vises og kan reviewes | Jobstatus øverst | Ingen auto-apply uden accept | NEEDS TESTDATA |
| UC-TAG-007 | AI Styring | Statistik | Tagliste og kategori vises | Totaler og top-tags | Ingen | READY |

## 9. Timelapse-video og post-processing

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-VID-001 | Enhed -> Timelapse Video | Vælg periode og hent billeder | Previewliste tæller billeder | Periode, antal og filter synligt | Read-only indtil render | READY |
| UC-VID-002 | Timelapse Video | Juster FPS, opløsning, format, dag/nat | Valg afspejles i preview/renderplan | Outputopsummering øverst | Ingen | READY |
| UC-VID-003 | Timelapse Video | Start render-job | Job startes og kan følges | Jobstatus og forventet output | Audit, CPU/disk hensyn | NEEDS TESTDATA |
| UC-VID-004 | Post-processing | Opdater status | Batchjobs og tællere opdateres | Aktuel jobstatus øverst | Ingen | READY |
| UC-VID-005 | Post-processing | Start thumbnail/AI job | Job starter, tæller fremdrift | Antal berørte billeder øverst | Ingen originaler ændres | NEEDS TESTDATA |

## 10. Global config, system admin og notifikationer

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-CONF-001 | Global Config | Vælg global/kunde/site/kamera-lag | Matrix viser arv og effektiv værdi | Valgt lag + effektiv kontekst øverst | Admin gating | READY |
| UC-CONF-002 | Global Config | Gem override | Underliggende lag arver korrekt | Diff/ændret felt synligt før save | Audit og config-version | NEEDS TESTDATA |
| UC-CONF-003 | Global Config | Nulstil til arv | Felt fjernes fra lavere lag | Arv-kilde tydelig | Audit | NEEDS TESTDATA |
| UC-CONF-004 | System Admin | Vælg device | Enhedens systemparametre læses via admin-safe endpoint | Device-id/status øverst | Admin gating | READY |
| UC-CONF-005 | System Admin | Ændr ikke-farlig parameter i test | Gem og bekræft config_version | Hvornår Edge får ændringen | Audit | NEEDS TESTDATA |
| UC-CONF-006 | System Admin | Ændr GPIO/relay parameter | Skal kræve tydelig advarsel og kontrolleret change | GPIO mapping og risiko øverst | Kun med test-Edge/fysisk recovery-plan | CONTROLLED UAT |
| UC-CONF-007 | Notifications | Gem email/SMS/Teams config | Config gemmes og testkanal kan køres | Aktiv/inaktiv kanal øverst | Secrets må ikke vises efter save | NEEDS TESTDATA |
| UC-CONF-008 | Notifications | Send testbesked | Besked modtages, audit/log oprettes | Kanal og modtager synlig før send | Sender data eksternt | NEEDS TESTDATA |

## 11. Backup, restore, provisioning og retention

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-BKP-001 | Backup -> Headend DR | Opdater status | Seneste backup, checksum, target vises | Sidste succes og restore-readiness øverst | Ingen | READY |
| UC-BKP-002 | Backup -> Headend DR | Start backup | Backup job, checksum og log vises | Scope: DB/config/images tydeligt | Audit; storagekapacitet | NEEDS TESTDATA |
| UC-BKP-003 | Backup -> Headend DR | Download backup | Kun autoriseret bruger får fil | Filnavn, størrelse, hash | Sensitive download | NEEDS TESTDATA |
| UC-BKP-004 | Backup -> Edge restore | Anmod Edge backup | Edge uploader backup via authenticated channel | Seneste Edge backup øverst | Ingen reprovisioning | NEEDS TESTDATA |
| UC-BKP-005 | Backup -> Edge ISO | Klargør ny Edge | Envelope/bootstrap oprettes kontrolleret | One-time/expiry synligt | Ingen private keys i image/envelope | NEEDS TESTDATA |
| UC-BKP-006 | Backup -> Headend generator | Klargør ny headend | Installationspakke genereres | Miljø, domæne, port, tokenstatus | Signatur/expiry | NEEDS TESTDATA |
| UC-RET-001 | Retention | Se status/indstillinger/log | Status og log vises | Aktiv/inaktiv og næste kørsel øverst | Ingen | READY |
| UC-RET-002 | Retention | Gem retention policy | Policy ændres, audit oprettes | Berørte scope og dage synligt | GDPR governance | NEEDS TESTDATA |
| UC-RET-003 | Retention | Start cleanup | Kun uploaded/safe-to-delete billeder slettes FIFO | Antal kandidater og årsag før start | Først dry-run/preview; derefter få udvalgte billeder | CONTROLLED UAT |
| UC-RED-001 | GDPR Sløring | Vælg billede | Detektioner vises | Antal fund og status øverst | Capture access audit | READY |
| UC-RED-002 | GDPR Sløring | Godkend sløring | Redigeret output gemmes, original beskyttes | Original/redigeret status tydelig | GDPR audit | NEEDS TESTDATA |
| UC-RED-003 | GDPR Sløring | Afvis false positive | Status gemmes med årsag | Årsag og reviewer | GDPR audit | NEEDS TESTDATA |

## 12. CMDB, SBOM og drift

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-CMDB-001 | CMDB | Åbn liste | Enheder, miljø, OS/app, update status vises | Risikofilter og sidste set | Ingen | READY |
| UC-CMDB-002 | CMDB detail | Åbn device | Hardware, OS/software, storage, netværk vises | Risk, site, status, last_seen øverst | Ingen | READ-ONLY PASS |
| UC-CMDB-003 | CMDB detail | Vis SBOM | Installeret vs aktuel version vises farvekodet | Version gaps øverst | Ingen secrets | READY |
| UC-CMDB-004 | CMDB detail | Vis historik | Ændringer vises kronologisk | Seneste ændring øverst | Ingen | READY |
| UC-CMDB-005 | CMDB detail | Skift miljølabel test/lab/prod | Miljø ændres kontrolleret | Konsekvens før save | Audit, release policy | NEEDS TESTDATA |
| UC-CMDB-006 | CMDB detail | Break-glass checkout | Password vises kun til autoriseret bruger | Udløb, device, reason og audit synligt | Sensitive, MFA/step-up | CONTROLLED UAT |
| UC-CMDB-007 | CMDB detail | Opret break-glass konto | Konto lifecycle oprettes | Scope og expiry øverst | Audit, Edge sync | NEEDS TESTDATA |
| UC-DRIFT-001 | Drift | Åbn overview | Health tiles og aktive alarmer vises | Værste status øverst | Ingen | READY |
| UC-DRIFT-002 | Drift | Klik log-genvej | SIEM åbner med filter | Kilde/filter synlig | Ingen | READY |
| UC-DRIFT-003 | Drift | Klik Edge tile | Trend/metric vises eller CMDB deep-link | Device og metric øverst | Ingen | READY |
| UC-DRIFT-004 | Drift | Billedadgang-log | Filtrer bruger/device/fil | Filter og antal hits | GDPR audit | READY |
| UC-SIEM-001 | SIEM | Skift periode/live | Events og totaler opdateres | Tidsvindue øverst | Ingen | READY |
| UC-SIEM-002 | SIEM | Filter severity/type/device/source | Liste og grafer filtreres | Aktive filtre synligt | Ingen | READY |
| UC-SIEM-003 | SIEM | Klik event | Detaljepanel viser normalized fields | Severity, device, time øverst | Ingen secrets i log | READY |
| UC-SIEM-004 | SIEM | AI SIEM analyse | Read-only anbefaling vises | Datagrundlag og tidsvindue | Ingen auto-remediation | NEEDS TESTDATA |

## 13. Updates, change tickets og releases

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-UPD-001 | Updates | Åbn statusfaner | Afventer/godkendt/blokeret/deployet m.fl. virker | Aktiv kø og risk øverst | Ingen | READY |
| UC-UPD-002 | Updates | Review pending update | Device, type, severity, artifact og blocker vises | Hvorfor handling kræves | Ingen | READY |
| UC-UPD-003 | Updates | Godkend app-update | Change ticket/artifact kontrolleres, Edge puller senere | Commit, signatur, rollback | Governance audit | NEEDS TESTDATA |
| UC-UPD-004 | Updates | Afvis update | Status bliver rejected med grund | Grund synlig | Audit | NEEDS TESTDATA |
| UC-UPD-005 | Updates | OS offline bundle | Kun signeret bundle accepteres | Bundle hash/signatur | Ingen Edge-internet | NEEDS TESTDATA |
| UC-UPD-006 | Updates | Rollback | Tidligere artifact gendannes og health gate køres | Rollback target synligt | Audit og recovery | NEEDS TESTDATA |
| UC-CHG-001 | Change tickets | Åbn ticketliste | Signerede tickets vises | Status og seneste ændring | Ingen | READY |
| UC-CHG-002 | Change tickets | Opret ticket fra PendingUpdate ID | Ticket binder update | Update ID og scope øverst | Audit | NEEDS TESTDATA |
| UC-CHG-003 | Change tickets | Godkend/afvis ticket | Beslutning signeres | Beslutning og ansvarlig synlig | Signatur og audit | NEEDS TESTDATA |
| UC-CHG-004 | Change tickets | Kontroller duplicate tickets | Dubletter bør ikke forvirre bruger | Canonical/erstattet synlig | Datahygiejne | READY |

## 14. Credentials, SSH, lokal adgang og technician

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-KEY-001 | Nøgler | Åbn Credentials/CMDB/Compliance faner | Inventory og lifecycle vises | Aktive/revoked/legacy gaps øverst | Ingen private keys | READY |
| UC-KEY-002 | Nøgler | Migrer legacy preview | Viser hvad der ændres før commit | Antal credentials og risks | Ingen sideeffekt i preview | NEEDS TESTDATA |
| UC-KEY-003 | Nøgler | Udsted credential | Credential oprettes med scope/expiry | Scope, owner, expiry | Audit, least privilege | NEEDS TESTDATA |
| UC-KEY-004 | Nøgler | Revoker/roter credential | Gammel afvises, ny aktiv | Active successor synlig | Fail-closed | NEEDS TESTDATA |
| UC-SSH-001 | SSH Tunnels | Se tunnelkommando | Korrekt `ssh -p ... -i ... orangepi@localhost` vises | Device, port, key path | Ingen private key material | READY |
| UC-SSH-002 | SSH Tunnels | Åbn browserterminal | Kun trusted host + capability + MFA | Trust/capability/timeout øverst | Full audit og revoke close | NEEDS TESTDATA |
| UC-SSH-003 | SSH Tunnels | Untrusted host key | Terminal nægtes fail-closed | Årsag og evidence synlig | Ingen known_hosts bypass | READY |
| UC-SSH-004 | SSH Tunnels | Deaktivér commissioning key | Kræver verified personlig service-login | Hvad deaktiveres og fallback | Audit | CONTROLLED UAT |
| UC-LOCAL-001 | Lokal adgang | Åbn oversigt | Resolver-lag og SID vises uden koder | Ikke-provisionerede markeres | Ingen secret i overview | READY |
| UC-LOCAL-002 | Lokal adgang -> Kamera | Vis QR/kode | Kun valgt kamera viser secret/kode | Device/site og udløb | Secret må ikke logges | NEEDS TESTDATA |
| UC-TECH-001 | Edge Technician UI | Start ServiceSession | Principal, grant, capability, expiry vises | Service Session status øverst | EdgeServiceGrant/PDP | NEEDS EDGE |
| UC-TECH-002 | Edge Technician UI/CLI | Acquire camera power lease | Relay ON kun via lease/HAL | Relay, camera detect, PTP status | Audit og timeout | NEEDS EDGE |
| UC-TECH-003 | Edge Technician UI/CLI | Revoke/expiry | Session invalidates, live view stopper, relay OFF | Cleanup-status øverst | Contract test | NEEDS EDGE |

## 15. Import, Open WebUI og AI Ops

| ID | Start | Handling | Forventet resultat | Top-info check | Sikkerhed/audit | Status |
|---|---|---|---|---|---|---|
| UC-IMP-001 | Import | Vælg eksisterende kunde/site | Kamera-destination filtreres korrekt | Destination summary | Ingen | READY |
| UC-IMP-002 | Import | Opret virtuel kamera-import | Virtuel device oprettes og billeder registreres | Antal filer og destination | Audit, testdata | NEEDS TESTDATA |
| UC-IMP-003 | Import | ZIP upload | Fil modtages, valideres og importeres | Filnavn/størrelse før upload | Upload confirmation | NEEDS TESTDATA |
| UC-IMP-004 | Import | Serversti import | Kun tilladt path importeres | Path og antal filer | Path allowlist | NEEDS TESTDATA |
| UC-WEBUI-001 | Open WebUI | Se status | Service og adgangskrav vises | MFA/status øverst | Ingen | READY |
| UC-WEBUI-002 | Open WebUI | Start tidsbegrænset session | Open WebUI åbner med udløb | Udløb og bruger | MFA, admin, audit | NEEDS TESTDATA |
| UC-AIOPS-001 | AI Styring | Kør AI Ops read-only analyse | Forslag vises uden remediation | Snapshot og modelstatus | No auto-change | NEEDS TESTDATA |
| UC-AIOPS-002 | AI Styring | Pause/lav-memory/normal drift | Ollama runtime ændres tidsbegrænset | Aktiv runtime og udløb | Audit | NEEDS TESTDATA |

## 16. Brugervenlighedstjek pr. side

Ved gennemgang skal vi notere disse ting særskilt fra "virker/virker ikke":

| Check | Spørgsmål |
|---|---|
| Første skærmbillede | Ved jeg hvor jeg er, hvad status er, og hvad der kræver min handling? |
| Vigtige tal | Er counts/risiko/update/last_seen øverst og forståelige? |
| Sprog | Er teksten dansk, kort og handlingsorienteret? |
| Farver | Er grøn/gul/rød konsistent og ikke pynt? |
| Tom tilstand | Forklarer siden hvad der mangler, og hvad næste sikre handling er? |
| Fejltilstand | Viser siden en menneskelig fejltekst, ikke bare 401/500? |
| Loading | Kan brugeren se om systemet arbejder? |
| Sideeffekt | Er farlige knapper tydeligt adskilt fra read-only knapper? |
| Secrets | Vises kun nødvendige filstier/fingerprints, aldrig private keys/tokens/passwords? |
| Audit | Er det tydeligt når en handling bliver logget/signeres? |
| Mobil/tablet | Kan alt læses uden vandret scroll, især CMDB/SBOM og Updates? |

## 17. Kendte observationspunkter fra 2026-08-26

| ID | Observation | Anbefaling |
|---|---|---|
| OBS-UI-001 | Dashboard viser `TL-043EB9E72EFD` som Online, mens Drift melder `ingen heartbeat >30 min`. | Indfør ensartet statusmodel: `online`, `stale`, `offline`, evt. `api-seen` vs `telemetry-seen`. |
| OBS-UI-002 | AI Styring viser `Ollama-servicen svarer ikke`. | Bevar som driftssignal, men vis gerne tydelig "påvirker kun lokale AI-funktioner" øverst. |
| OBS-UI-003 | `/mgmt/technician` på Headend viser næsten tom shell. | Beslut om ruten skal skjules/redirecte til Edge-lokal Technician UI eller have en forklarende side. |
| OBS-UI-004 | Mange sider har farlige handlinger tæt på read-only kontroller. | Brug tydeligere action-zoner: "Vis", "Planlæg", "Udfør farlig handling". |
| OBS-UI-005 | SIEM/Change tickets har mange ens klikbare rækker. | Gør første række/detalje og filterchips mere visuelt tydelige; undgå at hele lange tekstblokke føles som knapper. |

## 18. Foreslået gennemgangsorden

1. Read-only smoke: alle menuer, faner, filtre, fold-ud, detailvisninger.
2. UX-læsbarhed: første skærmbillede på hver side, farver, statusord, tomme tilstande.
3. Testdata CRUD: `QA-` kunde/site/kamera/bruger/ticket/import.
4. Governance flows: update approval, change ticket, signed artifact, rollback.
5. Security flows: RBAC, MFA, credentials, SSH/browserterminal, break-glass.
6. Data lifecycle: backup, restore rehearsal, retention dry-run, GDPR-redaction på testbillede.
7. Edge technician: ServiceSession, leases, camera diagnostics, cleanup efter revoke/expiry.
8. Regression automation: de usecases der er stabile, omsættes til Playwright/API-contract tests.

## 19. Exit-kriterier for "alt klikbart virker"

En komplet UI acceptance kræver:

- Alle read-only navigationer og faner loader uden synlige fejl eller browser-konsolfejl.
- Alle oprette/redigere/slette flows er testet med `QA-` data og ryddet op.
- Alle farlige handlinger kræver tydelig accept, viser konsekvens og efterlader audit.
- RBAC er testet med mindst viewer, operator, admin og super_admin.
- Secrets vises aldrig på oversigter og aldrig i logs.
- Updates/credentials/terminal/backup/retention har fail-closed negative tests.
- Edge hardwarehandlinger går gennem Service Operations/HAL og efterlader relay OFF efter session teardown.
- Første skærmbillede på hver side viser det brugeren skal vide først.
- Kendte observationspunkter er enten rettet eller dokumenteret som bevidste valg.
