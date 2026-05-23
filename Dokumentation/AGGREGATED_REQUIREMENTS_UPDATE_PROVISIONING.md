# TimeLapse Pro - aggregeret kravregister for update, change, provisioning og drift

**Status:** Arbejdsversion 0.1  
**Dato:** 2026-05-22  
**Formål:** Samle krav fra alle dokumenter i `Dokumentation/`, inklusive ældre versioner og chat-/arbejdsdokumenter, uden at reducere detaljegrad.  
**Scope i denne version:** Update/change/deployment, signeret godkendelse, Edge/Headend provisioning, backup/headend-resiliens og relaterede compliancekrav.  

## Læseprincipper

- Nyeste/gældende dokumenter vægtes højest, men ældre dokumenter må ikke ignoreres. Ældre krav markeres som historiske, konflikter eller kandidater, hvis de ikke findes i nyeste materiale.
- Krav med sikkerheds-, compliance- eller driftskonsekvens bevares, selv hvis de kun findes i chat-dumps eller tidlige roadmap-versioner.
- Konflikter afgøres ikke tavst. De listes i afsnittet "Konflikter og beslutninger".
- Formatet er Markdown for hurtig iteration. Det kan senere omsættes til Word, Excel/CSV, JSON Schema eller ticket-format.

## Kildegrundlag

Første pass har udtrukket tekst fra 47 filer i `Dokumentation/`, inklusive:

- `RISK_ASSESSMENT_v6.md` og `TimeLapse_SABSA_Risk_Assessment_v6.md.docx`
- `TimeLapse_Security_Compliance_v2.docx`, `timelapse_full_security.docx`, `timelapse_security.docx`
- `TimeLapse_SABSA_Architecture*.docx`
- `TimeLapse_Roadmap_v1.docx` til `TimeLapse_Roadmap_v4.docx`
- `TimeLapse_Edge_Runbook_v2.docx` til `TimeLapse_Edge_Runbook_v7.docx`
- `TimeLapse_RBAC_Remote_Operational_v1.docx`
- `TimeLapse_System_Inventory_v1.docx`
- `Headend_Installationsguide_Mac_Mini.md`
- `Startkrav.docx`
- `ChatGpt-input.docx`, `Chat with Gemini.docx`, `Timelaps-chat.docx`
- `Orange Pi PC Plus User Manual_v3.2.pdf`
- fail2ban, certbot og security-notes konfigurationsfiler

Maskinelt arbejdsindeks:

- `/Users/peter/Documents/Codex/2026-05-22/brug-github-til-at-gennemg-mine/timelapse_documentation_index.json`
- `/Users/peter/Documents/Codex/2026-05-22/brug-github-til-at-gennemg-mine/extracted_docs/`

## Overordnet målmodel

TimeLapse Pro skal understøtte en livscyklus fra R&D/LAB til produktion:

1. Udvikling og test på R&D/LAB-udstyr.
2. Kvalitetssikring via automatiske tests, signering og menneskelæsbart change ticket.
3. Godkendelse efter policy: automatisk eller manuel, på globalt, kunde-, site-, kamera- eller device-niveau.
4. Staged deployment til test/staging og derefter promotion til produktion.
5. Headend-mediated distribution til edges, så edges ikke kræver direkte GitHub/Internet.
6. Healthcheck, rollback og audit for både app-, OS- og tredjepartsopdateringer.
7. Dokumenteret provisioning af nye edges og headends, inklusive kold/varm backup og restore.

## Kravregister

### UPD-001 - Update-systemet skal være policy-drevet og hierarkisk

**Krav:** Systemet skal kunne afgøre auto/manual update-policy ud fra et hierarki: global default -> kunde -> site -> kamera/device -> runtime override.

**Detaljer:**

- Policy skal kunne sættes forskelligt for `app_security`, `app_updates`, `os_security` og `os_updates`.
- Mere restriktiv policy skal kunne vinde over en mere åben nedarvet policy.
- Manual approval skal kunne kræves for udvalgte kunder, sites, kameraer eller devices.
- Auto-deploy skal kunne tillades, hvis kunden/site/kameraet er konfigureret til det.
- Runtime/LAB-tilstand må kunne blokere eller udskyde opdatering.

**Kilder:** `RISK_ASSESSMENT_v6.md` R06; `TimeLapse_Roadmap_v3.docx`; `TimeLapse_Roadmap_v4.docx`; `Timelaps-chat.docx` omkring hierarkisk config; eksisterende `GlobalConfigPage.tsx` og `get_update_policy`.

**Implementeringsstatus:** Delvist. Backend har `PendingUpdate` og policy default, UI har `UpdatesPage`, men hierarchy/policy er ikke fuldt realiseret i UI eller DB.

### UPD-002 - Update-scope skal understøtte global, kunde, site, kamera og device

**Krav:** En opdatering skal kunne målrettes globalt, til en kunde, et site, et kamera eller en konkret fysisk edge/device.

**Detaljer:**

- Eksisterende `scope` dækker `global|customer|site|device`, men kamera/logisk camera bør også kunne være scope.
- Kamera-scope skal respektere Camera/DeviceAssignment-modellen, så et fysisk device kan udskiftes uden at miste policyhistorik.
- UI skal vise effektivt scope og hvilke devices/kameraer der rammes.

**Kilder:** `RISK_ASSESSMENT_v6.md` om staged rollout global->customer->site->device; `TimeLapse_Roadmap_v3.docx`; `TimeLapse_RBAC_Remote_Operational_v1.docx`; `TimeLapse_SABSA_Risk_Assessment_v6.md.docx`.

**Implementeringsstatus:** Delvist. `PendingUpdate.scope` findes, men UI er reduceret til global/device i approval modal, og kamera-scope mangler.

### UPD-003 - App updates må ikke forudsætte direkte GitHub-adgang fra Edge

**Krav:** Edge-enheder skal kunne opdateres uden direkte internetadgang eller direkte GitHub-adgang. Headend skal være update authority/proxy.

**Detaljer:**

- Edge må kun initiere forbindelser mod Headend/API/SFTP eller godkendt Headend-distributionskanal.
- Headend skal hente, verificere og pakke app-release/artifact.
- Edge skal hente artifact fra Headend, ikke `git fetch origin main` direkte.
- R&D/LAB kan have mere direkte mekanismer, men prod-design må ikke bygge på dem.

**Kilder:** Brugerafklaring 2026-05-22; `Timelaps-chat.docx` linjer om ingen public SSH til edge og edge self-update; `Startkrav.docx` om edge pull-model fra headend; `RISK_ASSESSMENT_v6.md` om edge autonomi og lukket netværk.

**Implementeringsstatus:** Ikke opfyldt. `deploy/edge_update.sh` og `edge/agent.py` har direkte `git fetch/pull origin main`-paths.

### UPD-004 - Headend skal producere verificerede update artifacts

**Krav:** Headend skal producere eller cache et verificeret artifact pr. app-release, egnet til offline/Headend-mediated Edge-update.

**Detaljer:**

- Artifact kan være Git bundle, tarball, signed package eller anden maskinlæsbar pakke.
- Artifact skal have manifest med mindst: release id, target commit, source branch/tag, build timestamp, hash, signer, test-resultat, SBOM-reference og rollback target.
- Artifact skal være immutable efter godkendelse.
- Artifact skal kunne distribueres til edge via API eller SFTP uden at edge kender GitHub.

**Kilder:** `RISK_ASSESSMENT_v6.md` R06; `TimeLapse_Roadmap_v4.docx` om patching/deploy/SBOM; brugerkrav om Headend-mediated Edge; CRA/security compliance dokumenter.

**Implementeringsstatus:** Mangler.

### UPD-005 - Update artifacts og change tickets skal være signerede

**Krav:** Alle app-release artifacts og tilhørende change tickets skal signeres kryptografisk.

**Detaljer:**

- Commit/tag-signatur alene er ikke nok; change ticket og artifact-manifest skal også signeres.
- Signatur skal kunne verificeres maskinelt på Headend og, hvor muligt, på Edge.
- Signeret ticket skal kunne eksporteres til kunde eller kundens ticketing-system.
- Signering af brugeraccept skal knyttes til logged-in user, rolle, tidspunkt, IP/user-agent og eventuel MFA/WebAuthn kontekst.

**Kilder:** Brugerkrav 2026-05-22; `security-notes.md` om GPG signing; `TimeLapse_Security_Compliance_v2.docx` om change management, audit og CRA; `RISK_ASSESSMENT_v6.md` om Authenticity/Accountability.

**Implementeringsstatus:** Delvist på Git-commit niveau. Mangler ticket-/manifest-signering og user approval signature.

### UPD-006 - Change ticket skal være både menneske- og maskinlæsbart

**Krav:** For hver update skal der genereres et change ticket i et format der både kan læses af mennesker og parse's af systemet.

**Detaljer:**

- Formatkandidater: JSON med canonical signing, YAML, XML, Markdown med embedded JSON block, eller JSON + renderet Markdown/PDF.
- Ticket skal mindst indeholde:
  - change id
  - update type (`app_security`, `app_updates`, `os_security`, `os_updates`)
  - severity og risikoklassifikation
  - scope og berørte kunder/sites/kameraer/devices
  - nuværende version og target version
  - release notes
  - security impact
  - testresultater
  - rollback-plan
  - maintenance window
  - reboot requirement
  - expected downtime
  - SBOM/diff/reference
  - godkendelseskrav
  - signaturer
  - eksportstatus til kunde/ticketing

**Kilder:** Brugerkrav 2026-05-22; `TimeLapse_Security_Compliance_v2.docx` om formaliseret change management; `TimeLapse_Roadmap_v4.docx` om SBOM og deploy-historik; `RISK_ASSESSMENT_v6.md`.

**Implementeringsstatus:** Mangler.

### UPD-007 - UI skal understøtte review og godkendelse af change ticket

**Krav:** UI skal vise alle relevante change-ticket felter før godkendelse, og godkendelseshandlingen skal være eksplicit og auditérbar.

**Detaljer:**

- UI må ikke nøjes med en "Godkend" knap uden detaljer.
- Bruger skal kunne se scope, severity, update-type, release notes, teststatus, rollback-plan, reboot/downtime og signaturstatus.
- UI skal kunne kræve MFA/WebAuthn ved højrisikoændringer.
- UI skal kunne eksportere eller downloade ticket til kundeaccept.
- UI skal kunne registrere ekstern kundeticket-reference.

**Kilder:** Brugerkrav; `TimeLapse_RBAC_Remote_Operational_v1.docx` om customer approval og audit; `TimeLapse_Security_Compliance_v2.docx`; eksisterende `UpdatesPage.tsx`.

**Implementeringsstatus:** Delvist. `UpdatesPage.tsx` viser basale oplysninger og approve/reject, men mangler ticketvisning, signatur, kundeaccept og MFA-gating.

### UPD-008 - Rollout skal være staged og kontrolleret

**Krav:** Update rollout skal kunne ske i faser: R&D/LAB -> staging/test -> pilot -> production.

**Detaljer:**

- En update skal kunne godkendes til test først og derefter promoveres til production.
- Promotion må kræve separat signeret approval.
- Scope skal kunne begrænses i hver fase.
- Systemet skal vise deployed/failed counts og status pr. device.
- Production rollout må kunne pauses/stoppe ved fejlgrænse.

**Kilder:** `RISK_ASSESSMENT_v6.md` R06; `TimeLapse_Roadmap_v4.docx`; brugerkrav om R&D/LAB og senere prod deploy; eksisterende `promote_update`.

**Implementeringsstatus:** Delvist. `promote_update` findes, men mangler robust status pr. target og gating.

### UPD-009 - Rollback skal være automatisk ved fejlet update

**Krav:** Edge og Headend skal automatisk rollbacke ved fejlet update efter definerede health criteria.

**Detaljer:**

- App update rollback skal bruge kendt tidligere version/artifact.
- Healthcheck skal mindst kontrollere service-active, heartbeat, API-kommunikation og eventuelt capture-loop.
- Rollback-resultat skal rapporteres til Headend.
- Hvis rollback fejler, skal der oprettes kritisk alarm og manuel intervention.
- Rollback skal være testet som en del af release acceptance.

**Kilder:** `RISK_ASSESSMENT_v6.md` Resilience/R06; `TimeLapse_Roadmap_v3.docx` og `v4` om `git reset --hard`/rollback; `deploy/edge_update.sh`; `edge/agent.py`.

**Implementeringsstatus:** Delvist. `edge_update.sh` har service health rollback, men ikke Headend artifact model, heartbeat-baseret rollback eller ticket binding. `edge/agent.py` har rollback stub.

### UPD-010 - Maintenance window og reboot-policy skal være konfigurerbar

**Krav:** Update execution skal respektere maintenance window og reboot-policy på relevant scope.

**Detaljer:**

- Policy skal kunne definere tilladt tidsvindue.
- Reboot må kun ske automatisk hvis policy tillader det.
- OS-kernel/security updates skal kunne markeres som reboot-required.
- Capture schedule skal indgå i beslutningen, så opdatering ikke afbryder vigtige optagelser.

**Kilder:** `RISK_ASSESSMENT_v6.md` R06; brugerkrav; `TimeLapse_RBAC_Remote_Operational_v1.docx` om vedligeholdelsesvindue ved nøgle/secrets rotation.

**Implementeringsstatus:** Delvist/mangler. Default `maintenance_window` findes i policy response, men enforcement er ikke tydelig.

### UPD-011 - OS security og OS functional updates skal håndteres særskilt

**Krav:** OS security updates og funktionelle OS updates skal klassificeres, godkendes og deployes separat.

**Detaljer:**

- `os_security` skal kunne have højere default prioritet end `os_updates`.
- OS security kan være auto på nogle scopes, manual på andre.
- Funktionelle OS updates bør typisk være manual eller staged.
- apt/package-list og reboot-required skal indgå i ticket.
- OS update resultater skal rapporteres og auditeres.

**Kilder:** Brugerkrav; `TimeLapse_Security_Compliance_v2.docx` om OS-sikkerhedsopdateringer og supportperiode; `headend/main.py` `/api/updates/available`; `edge/agent.py`.

**Implementeringsstatus:** Delvist. Edge indsamler apt info og backend opretter `PendingUpdate`, men ticket, package details og robust result audit mangler.

### UPD-012 - Tredjepartsapplikationer og dependencies skal indgå i update governance

**Krav:** Update-systemet skal håndtere ikke kun Timelapse-app og OS, men også afhængigheder og nødvendige tredjepartsapplikationer.

**Detaljer:**

- Python dependencies, Node/npm dependencies, gphoto2, nginx, PostgreSQL, Ollama/Gemini-integration, certbot, fail2ban og systemd units bør kunne spores.
- SBOM skal genereres og opdateres ved release.
- Vulnerability status bør kunne knyttes til change ticket.

**Kilder:** Brugerkrav; `TimeLapse_Security_Compliance_v2.docx` CRA/SBOM; `Headend_Installationsguide_Mac_Mini.md`; `TimeLapse_System_Inventory_v1.docx`.

**Implementeringsstatus:** Mangler samlet model. Inventory findes delvist.

### UPD-013 - Change og update audit trail skal være komplet

**Krav:** Alle update-relaterede handlinger skal logges med tilstrækkelig evidens.

**Detaljer:**

- Oprettelse, ticket generation, artifact creation, approval, rejection, promotion, deployment start, deployment success/failure, rollback request/result og export til kunde skal auditeres.
- Audit skal inkludere actor, rolle, tenant/customer context, timestamp, IP/user-agent, MFA/WebAuthn status og signature/hash.
- Audit skal være tenant-isoleret og egnet til kundedokumentation.

**Kilder:** SABSA Accountability i `RISK_ASSESSMENT_v6.md`; `TimeLapse_RBAC_Remote_Operational_v1.docx`; `TimeLapse_Security_Compliance_v2.docx`.

**Implementeringsstatus:** Delvist. `approved_by/approved_at` findes, men ikke fuld audit/ticket chain.

### UPD-014 - Update-status skal spores pr. target

**Krav:** En update med flere targets skal have status pr. device/kamera, ikke kun global status på `PendingUpdate`.

**Detaljer:**

- Per-target status skal kunne være pending, approved, downloading, deploying, healthcheck, deployed, failed, rolled_back, skipped.
- `deployed_count` og `failed_count` skal udledes fra per-target records.
- UI skal kunne vise hvilke devices der mangler, fejlede eller rullede tilbage.

**Kilder:** `PendingUpdate` har `deployed_count/failed_count`; R06 staged rollout; brugerkrav.

**Implementeringsstatus:** Mangler per-target tabel/model.

### UPD-015 - Edge skal bevare autonom drift under update og netværksudfald

**Krav:** Edge må fortsætte capture/store-and-forward under Headend- eller netværksudfald og må ikke efterlades i halvopdateret tilstand.

**Detaljer:**

- Edge skal have lokal config cache og lokal DB/circular buffer.
- Update skal være atomisk eller have tydelig staging/activation.
- Hvis update artifact ikke kan downloades/verificeres, skal Edge fortsætte på eksisterende version.
- Update må ikke slette capture buffer eller lokale secrets.

**Kilder:** `Startkrav.docx`; `RISK_ASSESSMENT_v6.md`; `TimeLapse_Edge_Runbook_v7.docx`; `TimeLapse_System_Inventory_v1.docx`.

**Implementeringsstatus:** Delvist.

### PROV-001 - Ny Edge provisioning skal være zero-touch eller near-zero-touch

**Krav:** En ny edge skal kunne startes på rå OS med minimal manuel handling og registrere sig mod Headend.

**Detaljer:**

- Headend skal generere bootstrap package med `bootstrap.yaml`, device id, headend URL, bootstrap token, CA cert og eventuelle initiale nøgler.
- Edge skal kunne hente effektiv konfiguration fra Headend efter bootstrap.
- Bootstrap token skal være engangsbrug eller tidsbegrænset.
- Device identity må ikke alene hvile på let-spoofbar MAC-adresse i production.

**Kilder:** `Startkrav.docx`; `TimeLapse_Roadmap_v3.docx/v4`; `RISK_ASSESSMENT_v6.md`; `TimeLapse_RBAC_Remote_Operational_v1.docx`; brugerkrav om rå OS/autoconfig.

**Implementeringsstatus:** Delvist. `/api/bootstrap` findes, men production-grade package/provisioning lifecycle er ufærdig.

### PROV-002 - Headend skal kunne generere OS-tilretning og app-installation for Edge

**Krav:** Provisioning skal kunne installere/konfigurere nødvendige OS-pakker, services og Timelapse-komponenter på edge.

**Detaljer:**

- OS hardening, package install, Python venv, systemd service, watchdog, gphoto2, GPIO, modem/network tools og logging skal kunne beskrives som provisioneringsprofil.
- Provisioning skal være idempotent.
- Resultat skal rapporteres til Headend som provisioning status.
- Production provisioning bør ikke kræve rå databasekald eller manuel filkopiering.

**Kilder:** Brugerkrav 2026-05-22; `TimeLapse_Edge_Runbook_v7.docx`; `TimeLapse_Pro_Configuration_Guide_v3.docx`; `TimeLapse_System_Inventory_v1.docx`; Orange Pi manual.

**Implementeringsstatus:** Mangler samlet orchestreret provisioning. Runbooks findes.

### PROV-003 - Provisioning skal generere og rotere device-nøgler

**Krav:** Headend skal håndtere device-nøgler, client certs og SSH tunnel-nøgler med lifecycle og revokering.

**Detaljer:**

- Intern CA anbefales frem for individuelle self-signed certs.
- Device client certs bør have udløb og rotation.
- SSH keys skal kunne genereres, installeres, begrænses og revokeres.
- Kompromitteret edge skal kunne isoleres ved at tilbagekalde cert/nøgle.

**Kilder:** `RISK_ASSESSMENT_v6.md` PKI-afsnit; `TimeLapse_RBAC_Remote_Operational_v1.docx`; `TimeLapse_Security_Compliance_v2.docx`.

**Implementeringsstatus:** Delvist/planlagt.

### PROV-004 - Kold og varm backup Headend skal indgå i provisioningmodellen

**Krav:** Systemet skal kunne etablere og genskabe Headend fra backup, inklusive varm/kold standby-scenarier.

**Detaljer:**

- Backup Headend skal kunne få nødvendige certs, DB backup, artifact store, configuration, keys og UI/backend services.
- Failover/restore skal have dokumenteret RTO/RPO.
- Edge skal kunne kende primær og eventuel fallback Headend, uden at bryde trust/pinning.
- Kold backup skal kunne provisioneres fra rå OS.

**Kilder:** Brugerkrav; `RISK_ASSESSMENT_v6.md` R09; `TimeLapse_Roadmap_v4.docx` om DR; `TimeLapse_Security_Compliance_v2.docx`; `Headend_Installationsguide_Mac_Mini.md`.

**Implementeringsstatus:** Delvist. Backup findes i UI/runbooks, men standby/failover architecture mangler.

### PROV-005 - Backup og restore skal testes og dokumenteres

**Krav:** Backup må ikke kun eksistere; restore skal testes og kunne dokumenteres.

**Detaljer:**

- Automatisk off-site backup er et åbent punkt i gældende risikovurdering.
- Backup-testprocedure mangler og skal etableres.
- Restore-test skal kunne generere audit/resultat.
- Kunde-/tenantdata skal bevares adskilt og krypteres.

**Kilder:** `RISK_ASSESSMENT_v6.md` R09; `TimeLapse_Edge_Runbook_v7.docx`; `TimeLapse_System_Inventory_v1.docx`; `TimeLapse_Security_Compliance_v2.docx`.

**Implementeringsstatus:** Delvist.

### SEC-001 - Compliance-targets skal være eksplicitte i design og tickets

**Krav:** Update/provisioning-systemet skal understøtte krav fra ISO 27001:2022, NIS2, CRA og IEC 62443.

**Detaljer:**

- CRA kræver security updates, supportperiode, vulnerability handling og SBOM.
- NIS2 kræver supply-chain/security governance og dokumenterbar risikostyring.
- IEC 62443 kræver secure update, identity, audit, least privilege og secure deployment.
- ISO 27001 kræver change management, access control, logging, backup og supplier/dependency governance.

**Kilder:** `TimeLapse_Security_Compliance_v2.docx`; `timelapse_full_security.docx`; `RISK_ASSESSMENT_v6.md`.

**Implementeringsstatus:** Delvist dokumenteret; ikke fuldt operationaliseret.

### SEC-002 - Secrets og runtime caches må ikke committes

**Krav:** Secrets, runtime caches, exports og backup artifacts må ikke indgå i Git.

**Detaljer:**

- `secrets/`, service accounts, exported DB data, `.bak` og generated snapshots skal håndteres uden for Git.
- Edge runtime cache som `edge/sftp_cache.yaml` skal ignoreres og have stramme permissions.
- Change tickets må referere til secrets som masked values eller secret IDs, aldrig rå secrets.

**Kilder:** Praktisk fund 2026-05-22; `RISK_ASSESSMENT_v6.md` R05; `TimeLapse_Security_Compliance_v2.docx`; `.gitignore`.

**Implementeringsstatus:** Delvist. Der er signeret commit for `edge/sftp_cache.yaml` ignore og future `chmod(0600)`.

### SEC-003 - Tests skal være gate før deploy

**Krav:** Der skal være et test/staging-gate før deployment til Edge og production Headend.

**Detaljer:**

- Python syntax/unit tests for edge og headend.
- API tests for update/provisioning endpoints.
- Frontend build/typecheck.
- Integration test for Edge->Headend update policy, artifact download, report og rollback.
- Testresultater skal indgå i change ticket.

**Kilder:** `Timelaps-chat.docx` om testplan og automatisk testscript; `TimeLapse_Roadmap_v3.docx/v4`; compliance docs.

**Implementeringsstatus:** Delvist. CI findes, men update/provisioning gates er ikke komplette.

### CFG-001 - Alle konfigurationsparametre skal kunne administreres fra UI

**Krav:** Det skal "aldrig" være nødvendigt at ændre rå database eller kode for timing/operationelle parametre.

**Detaljer:**

- Central admin UI skal vise og ændre alle config-parametre.
- Effective/merged config pr. kamera skal kunne vises.
- LAB mode ændringer skal kunne gemmes for aktuelt kamera og uploades til Headend.
- Nedarvning skal følge Default -> Kunde -> Site -> Kamera.

**Kilder:** `Timelaps-chat.docx` omkring hierarkisk config og LAB mode; `GlobalConfigPage.tsx`; `Startkrav.docx`.

**Implementeringsstatus:** Delvist.

## Konflikter og beslutninger

### CON-001 - Edge direct GitHub pull vs. Headend-mediated update

**Observation:** Ældre roadmap/runbooks beskriver `git pull` på Edge, Git deploy keys og Edge self-update direkte fra origin. Nyere brugerkrav og production constraints siger, at Edge ikke nødvendigvis har Internet og skal opdateres via Headend.

**Foreløbig beslutning:** Production design skal være Headend-mediated. Direkte GitHub kan kun være R&D/LAB nødfunktion, tydeligt markeret og disabled by policy i prod.

**Kilder:** `TimeLapse_Roadmap_v3.docx`, `TimeLapse_Edge_Runbook_v4-v7.docx`, brugerkrav 2026-05-22.

### CON-002 - SQLite vs. PostgreSQL Headend

**Observation:** Ældre dokumenter omtaler Raspberry Pi 5 og SQLite på Headend; nyere Mac Mini installation bruger PostgreSQL.

**Foreløbig beslutning:** R&D/LAB kan have historiske SQLite/Pi spor, men production Headend bør være Mac Mini/PostgreSQL som aktuel installationsguide. Backup/failover skal tage højde for PostgreSQL.

**Kilder:** `TimeLapse_Security_Compliance_v2.docx`, `Headend_Installationsguide_Mac_Mini.md`, `TimeLapse_System_Inventory_v1.docx`.

### CON-003 - MAC-baseret identity vs. cert/key-baseret identity

**Observation:** Startkrav og tidlige docs bruger MAC-afledt device_id. Nyere risikovurdering peger på intern CA, client certs og revokering.

**Foreløbig beslutning:** MAC-afledt ID kan være bootstrap convenience, ikke production trust anchor. Production identity skal være cert/key-baseret.

**Kilder:** `Startkrav.docx`, `RISK_ASSESSMENT_v6.md`, `TimeLapse_RBAC_Remote_Operational_v1.docx`.

### CON-004 - Single PendingUpdate status vs. per-target deployment state

**Observation:** Nuværende DB har status på selve update-recorden, men staged rollout kræver status pr. target.

**Foreløbig beslutning:** Behold `PendingUpdate` som change/update header, tilføj per-target statusmodel.

**Kilder:** eksisterende `PendingUpdate`; R06; brugerkrav.

### CON-005 - Change ticket format

**Observation:** Bruger nævner XML/JSON/andet; kravet er maskin- og menneskelæsbart samt signeret.

**Foreløbig anbefaling:** Canonical JSON som signeret system-of-record plus renderet Markdown/PDF til menneskelæsning. XML kan eksporteres senere hvis kundeticketing kræver det.

## Foreslået datamodel - arbejdsskitse

### `change_tickets`

- `id`
- `ticket_id`
- `update_id`
- `format_version`
- `title`
- `summary`
- `classification`
- `change_type`
- `severity`
- `risk_score`
- `compliance_refs`
- `scope`
- `scope_id`
- `target_selector`
- `current_versions`
- `target_versions`
- `release_notes`
- `security_impact`
- `sbom_ref`
- `artifact_refs`
- `test_summary`
- `rollback_plan`
- `maintenance_window`
- `reboot_policy`
- `created_at`
- `created_by`
- `canonical_json`
- `signature`
- `signature_key_id`

### `change_approvals`

- `id`
- `ticket_id`
- `approved_by`
- `approved_role`
- `approved_at`
- `decision`
- `comment`
- `external_ticket_ref`
- `mfa_context`
- `ip_address`
- `user_agent`
- `canonical_decision_json`
- `signature`

### `update_targets`

- `id`
- `update_id`
- `ticket_id`
- `target_type`
- `target_id`
- `device_id`
- `camera_id`
- `status`
- `attempt_count`
- `started_at`
- `finished_at`
- `current_version`
- `target_version`
- `rollback_version`
- `last_error`
- `healthcheck_result`

### `update_artifacts`

- `id`
- `update_id`
- `artifact_type`
- `path_or_url`
- `sha256`
- `size_bytes`
- `target_commit`
- `source_ref`
- `created_at`
- `created_by`
- `signature`
- `sbom_path_or_url`

## Foreslået change ticket JSON - første udkast

```json
{
  "schema": "dk.froekjaer.timelapse.change-ticket.v1",
  "ticket_id": "TLP-CHG-2026-000001",
  "title": "TimeLapse Pro app update",
  "change_type": "app_updates",
  "severity": "medium",
  "environment": "test",
  "scope": {
    "level": "site",
    "id": "SITE-123",
    "targets": ["TL-C87FF9587CA0"]
  },
  "versions": {
    "current": {"TL-C87FF9587CA0": "63a6455"},
    "target": "40dfe3f39112..."
  },
  "artifact": {
    "type": "git-bundle",
    "sha256": "hex",
    "target_commit": "40-char sha",
    "source_ref": "main"
  },
  "risk": {
    "summary": "App update with automatic rollback",
    "business_impact": "Capture may pause during service restart",
    "expected_downtime_seconds": 60
  },
  "controls": {
    "maintenance_window": "02:00-04:00",
    "reboot_allowed": false,
    "rollback": "automatic",
    "healthcheck": ["systemd active", "heartbeat", "config pull"]
  },
  "tests": {
    "ci_run": "url-or-id",
    "status": "passed",
    "suites": ["backend", "edge", "frontend", "integration"]
  },
  "compliance": ["ISO27001 A.8.32", "IEC62443 secure update", "NIS2 Art.21", "CRA security updates"],
  "approval": {
    "required": true,
    "approver_role": ["admin", "super_admin", "customer_approver"],
    "external_ticket_ref": null
  },
  "signatures": []
}
```

## Næste analyseopgaver

1. Udtræk alle unikke krav fra chat-dumps uden at blande fejlrettelseslogs og midlertidige kommandoer ind som permanente krav.
2. Markér krav som `current`, `historical`, `conflict`, `implemented`, `partial`, `missing`.
3. Sammenhold kravregisteret med faktisk kode i:
   - `headend/main.py`
   - `headend/database.py`
   - `edge/agent.py`
   - `deploy/edge_update.sh`
   - `deploy/headend_poller.sh`
   - `timelapse-ui/src/pages/UpdatesPage.tsx`
   - `timelapse-ui/src/pages/GlobalConfigPage.tsx`
4. Beslut ticket-format og signeringsmekanisme.
5. Designe per-target deployment state.
6. Designe Headend-mediated artifact store.
7. Designe provisioning flow for:
   - R&D/LAB Edge
   - production Edge
   - production Headend
   - warm/cold backup Headend

