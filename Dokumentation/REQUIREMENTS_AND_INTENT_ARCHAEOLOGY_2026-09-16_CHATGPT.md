# TimeLapse Pro — Requirements & Intent Archaeology

**Dato:** 2026-09-16  
**Forfatter:** ChatGPT i samarbejde med Peter Frøkjær  
**Status:** Working archaeology / provenance map — ikke et nyt konkurrerende kravregister  
**Branch:** `chatgpt/capability-map-v0-20260916`  
**Baseline for direkte repo-læsning:** `main @ 8452c5ef264d85823dce149a3bb371142d598569`

## 1. Formål

Dette dokument forsøger at bevare **hele projektets intention**, ikke kun de krav der tilfældigvis står i det nyeste kravregister.

Det omfatter:

- eksplicitte produktkrav;
- brugerønsker og UX-forventninger;
- drifts- og recoverybehov;
- sikkerheds- og compliancekrav;
- arkitekturprincipper;
- fotofaglige mål;
- AI-/analyseønsker;
- update/provisioning/backup-intentioner;
- historiske idéer der senere er ændret;
- konflikter og superseded retninger;
- evidensbaserede læringer fra faktiske fejl i systemet.

Målet er ikke at gøre alt historisk materiale bindende. Målet er, at **intet væsentligt går tabt uden at vi kan se, hvad der blev ændret og hvorfor**.

## 2. Klassifikation

Denne arkæologi bruger følgende labels:

- **CURRENT** — nuværende, bevidst gældende intention/krav.
- **CURRENT / VERIFY** — intentionen er stadig relevant, men implementation/runtime skal verificeres.
- **OPEN** — ønsket/kravet er fortsat relevant og ikke lukket.
- **CHANGED** — intentionen består, men den konkrete løsning er ændret.
- **SUPERSEDED** — en tidligere løsning eller regel er bevidst erstattet.
- **HISTORICAL** — vigtig som provenance/idé, men ikke gældende krav.
- **PROPOSED** — designidé eller kandidatprincip som aldrig blev formelt bindende.
- **CONFLICT / DECISION NEEDED** — samtidige eller efterfølgende kilder er ikke entydigt forenelige.

Implementeringsstatus og governance-status holdes adskilt. Et krav kan være CURRENT selv om implementationen mangler; kode kan eksistere uden at capability'en er runtime-verificeret.

## 3. Kildehierarki og coverage

### 3.1 Direkte læst i denne runde

Følgende centrale kilder er læst direkte mod den verificerede baseline:

- `00_START_HER.md`
- `KRAVREGISTER_og_STATUS_v10.md`
- `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md`
- `DOKUMENTPAKKE_OVERSIGT_v10.md`
- `Timelapse_pro_full_documentation_v10.md`
- `TimeLapse_Roadmap_v10.md`
- `SABSA_Architecture_v10.md`
- `RISK_ASSESSMENT_v10.md`
- `GO_LIVE_CHECKLIST_v10.md`
- `Update_Flow_v10.md`
- `BRUGERMANUAL_v10.md`
- `MENUGUIDE_BRUGER_v1.md`
- `MENUGUIDE_ADMIN_v1.md`
- `UI_USECASE_CATALOG_2026-08-26.md`
- `TimeLapse_Configuration_Guide_v10.md`
- `TimeLapse_Edge_Runbook_v10.md`
- `RBAC_Remote_Operational_v10.md`
- `BACKUP_RESTORE_TEST_PROCEDURE_v1.md`
- `TIMELAPSE_BILLEDKVALITET_OG_VIDEOARKITEKTUR_v1.md`
- `Claude_AI_Tagging_Redesign_2026-06-23.md`
- `FAIR_RISK_INPUT_MODEL_v1.md`
- `COMPLIANCE_REGULATORY_INTELLIGENCE_ARCHITECTURE_v1.md`
- `AI_KOMPETENCER_OG_OPGAVEROUTING.md`
- `PRIORITIZED_BACKLOG.md`
- `SYSTEM_HEALTH_REGISTER.md`
- `ADR/ADR-001-platform-payload-split.md`
- `ADR/ADR-004-development-and-recovery-shell-access.md`
- `Arkitektur/CORE_DESIGN_PRINCIPLES_ANALYSE_2026-09-13_CLAUDE.md`
- `Claude_Support_Access_Model_2026-07-06.md`
- aktuelle og historiske dele af `HANDOVER_LOG.md`.

### 3.2 Indirekte bevaret gennem dokumenteret konsolidering

`KRAVREGISTER_og_STATUS_v10.md` siger eksplicit, at det konsoliderer tidligere kravregistre samt essensen af `Startkrav.docx` og `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md`.

`AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` dokumenterer, at dets første pass udtrak tekst fra 47 filer, herunder:

- `Startkrav.docx`;
- `ChatGpt-input.docx`;
- `Chat with Gemini.docx`;
- `Timelaps-chat.docx`;
- Roadmap v1–v4;
- Edge Runbook v2–v7;
- SABSA Architecture-versioner;
- Security/Compliance-dokumenter;
- RBAC/Remote-operational;
- System Inventory;
- Headend-installationsguide;
- hardwaremanualer og security-notes.

`RISK_ASSESSMENT_v10.md` dokumenterer desuden 79 lokale dokumenter / 54.470 tekstlinjer i det tidligere analysekorpus, og `DOKUMENTPAKKE_OVERSIGT_v10.md` angiver ca. 79–110 filer gennemgået over flere sessioner.

**Begrænsning:** de binære `.docx` chat-dumps kan ikke tekstlæses direkte gennem den nuværende GitHub-connector. Deres indhold er derfor i denne version repræsenteret via de tidligere dokumenterede tekstudtræk og konsolideringer. Dette må ikke beskrives som en ny, direkte reread af hver binær fil.

## 4. Overordnet produktintention

### 4.1 Kerneopgave — CURRENT

TimeLapse Pro skal levere **pålidelige, autentificerede, tidssynkrone timelapse-optagelser fra ubemandede lokationer**, med central styring, multi-tenant isolation og dokumenterbar dataintegritet.

Produktet er ikke bare et kamera-script. Det er en kombination af:

- autonome Edge-enheder;
- centrale Headend-funktioner;
- fysisk kamera-/relay-styring;
- sikker dataoverførsel og buffering;
- UI til kunder og drift;
- billedkvalitet/video/AI;
- update/provisioning;
- CMDB/GRC/audit/compliance;
- lokal og central recovery.

### 4.2 Nøglekvaliteter — CURRENT / VERIFY

Historisk SABSA-intention:

- planlagt capture >99% uanset netværk;
- site-kameraer synkroniseret inden for ca. 1 sekund;
- billeder uændrede fra linse til arkiv;
- boot-to-capture-mål <120 sek.;
- netværks-/strøm-/device-fejl må ikke ødelægge missionen;
- central management uden fysisk besøg, men lokal recovery skal eksistere;
- designbarhed mod 500–1000 edges / 100+ sites;
- capturefrekvens fra ca. 1/dag til 1/minut skal kunne konfigureres.

Disse er vigtige **mål/invariants**, ikke automatisk aktuelle SLA'er. De skal verificeres og enten bekræftes, justeres eller markeres historiske i den senere Golden Capability acceptance.

## 5. Capture, kamera og fysisk site

### 5.1 Autonom capture — CURRENT

- Edge tager billeder automatisk efter lokalt anvendelig schedule.
- Headend-/internetudfald må ikke i sig selv stoppe capture.
- Capture skal fortsætte under relevante update-/kommunikationsudfald.
- Kamera-/capture-loop skal komme tilbage efter reboot eller tydeligt alarmere hvis det ikke gør.

### 5.2 Multi-kamera/site-synkronitet — CURRENT / VERIFY

- Flere kameraer på samme site skal kunne optage tæt synkront.
- Historisk mål: inden for 1 sekund.
- NTP/chrony/GPS er midler; selve capability'en er korrekt tidslig sammenhæng mellem captures.

### 5.3 Kamera-strøm og HAL — CURRENT

- Kamera/modem/relæ må styres gennem kontrolleret hardwarelag/service operations.
- Relay skal ende i sikkert state efter session/teardown/failure.
- GPIO/device-specific mapping skal være canonical og ikke afhænge af farlige defaults.
- Hardware-abstraktion skal understøtte flere targets.

### 5.4 Kamera-lokation != fysisk Edge — CURRENT

- Den logiske kamera-/lokationshistorik skal overleve udskiftning af fysisk Edge.
- Captures skal bindes til logisk kamera/site, ikke kun fysisk device-id.

### 5.5 Kamera QA / drift detection — CURRENT

- Blur, eksponering, histogram, fokus, WB, direkte sol/refleksion, linseobstruktion mv. skal kunne vurderes.
- Et enkelt dårligt billede må ikke ukritisk drive autonom kameraregulering.
- Fokus/WB behandles særskilt fra eksponering.
- Ved autonom EV-regulering ønskes tidsserie, hysterese, rate limits og anti-windup.
- Fokusændring er kontrolleret testjob med recovery, ikke almindelig capture-sideeffekt.

## 6. Billeddata, integritet og lifecycle

### 6.1 Integritet/provenance — CURRENT

- Billedets identitet, device/camera/site, tidspunkt og metadata skal være sporbare gennem hele kæden.
- SHA-256 har historisk været en central kontrol for image/artifact integrity.
- Original og derivater skal kunne skelnes.
- En status om upload/processing må ikke være stærkere end evidensen for den faktiske fil/runtime.

### 6.2 Originalbilleder — CURRENT, ændret fra tidlig retentionmodel

**Tidlig model:** automatisk retention pr. kamera og automatisk cleanup blev implementeret/beskrevet i juli.

**Senere/current designretning:** projekt-/capturedata slettes ikke automatisk som normal retentionmekanisme; eksplicit disposition/deletion kræver årsag, actor og audit. Core Design Principles-analysen viser, at main siden 2026-07-15 har håndhævet dette via en no-op automatic cleanup og eksplicit deletion service.

**Klassifikation:** CHANGED. Historisk retention-UI/-krav skal bevares som provenance, men må ikke ukritisk læses som nuværende auto-delete-intention.

### 6.3 Store-and-forward — CURRENT

- Lokal buffer skal overleve netværksudfald.
- Backlog skal være synlig og drænes kontrolleret efter reconnect.
- Buffer-full/backpressure skal have defineret adfærd.
- Ingen update må slette capture-buffer eller lokale secrets.

### 6.4 Billedadgang og destruktive handlinger — CURRENT

- Download/adgang til fuldopløsningsbilleder auditeres.
- Destruktiv UAT er tilladt i testfasen på lille, dokumenteret scope (fx 1–3 gamle testbilleder) med før/efter-state og audit.
- Hvis UI ikke klart viser hvad der slettes/ændres, skal flowet stoppes.

## 7. Billedkvalitet, timelapse-video og fotografisk intention

### 7.1 Overordnet — CURRENT

TimeLapse Pro skal kunne producere **fotografisk stabile og konsistente lange forløb**, ikke bare concatenere billeder.

### 7.2 Principper — CURRENT / TARGET

- stabil geometri før kosmetik;
- eksponering analyseres som tidsserie;
- beskyt highlights;
- undgå jagende white balance;
- fokusproblemer diagnosticeres separat;
- originaler er immutable;
- efterbehandling sker på kopier;
- output skal kunne reproduceres fra rendermanifest;
- mulighed for høj-kvalitets master og separate leveranceprofiler.

### 7.3 Render/evidence — TARGET / OPEN

- scene-aware deflicker frem for blind udjævning;
- ECC/subpixel alignment med grænser/alarm ved større kameraforskydning;
- eksplicit farvestyring Rec.709/sRGB;
- overlay baseret på rigtige `captured_at` timestamps;
- render manifest med frame-hashes, capture-times, tool/filter versioner, parametre og outputhash;
- persistent job-state og kontrolleret retention af afledte videoer;
- proof/preview før dyr render.

### 7.4 Ingen falsk dokumentation — CURRENT

Optical-flow/interpolation bør ikke være standard for dokumentarisk output, fordi syntetiske mellemframes kan opfinde artefakter. Hvis funktionen findes, skal den være tydeligt mærket kreativ eksport.

### 7.5 Site-Wide Look Matching — CURRENT / VERIFY

- site-wide golden reference;
- per-camera LUTs;
- capture hints;
- kameraer på samme site bør kunne klippes sammen uden tydelige farve-/eksponeringsspring.

## 8. AI, søgning og billedanalyse

### 8.1 AI-tags er assistance, ikke sandhed — CURRENT

- AI-tags er søge-/hjælpemetadata og må ikke behandles som juridisk sandhed.
- Vigtige rapporter kræver menneskelig vurdering efter behov.

### 8.2 Tagging philosophy — CURRENT / VERIFY

- åbent vokabular frem for tvunget checklist;
- ingen `no_crane`/`no_worker`-agtige fraværstags;
- ingen kvote der tvinger modellen til at opfinde tags;
- kontekst pr. kunde/site/kamera/lokal tid;
- baseline for hvad kameraet normalt ser;
- anomalier/hændelser og billedkvalitet vurderes eksplicit;
- vokabular fungerer som normalisering/review-lag bagefter.

### 8.3 AI-strategi pr. kunde/site — CURRENT DESIGN

Historisk design understøtter:

- `cloud_only`;
- `local_only`;
- `local_then_cloud`;
- `technical_only`.

Valget skal kunne afspejle kvalitet, privacy, pris og databehandlerforhold. `local_only` kan være et compliance-/privacyvalg; `local_then_cloud` en cost/quality-balance.

### 8.4 AI resource governance — OPEN

- AI-budget, quotas, modelvalg og resourceforbrug skal være synligt og kontrolleret.
- Lokal AI må ikke gøre Headend ustabil; derfor findes fx Normal/Pause/Low-memory modes.
- Fail-closed low-memory-mode må ikke skjult falde tilbage til stor model.

## 9. UI og menneskelig anvendelighed

### 9.1 “Kan vi faktisk bruge systemet?” — CURRENT

`UI_USECASE_CATALOG_2026-08-26.md` er den praktiske menneskelige baseline for UAT og senere automation.

### 9.2 Første skærmbillede — CURRENT

Hvor relevant skal brugeren uden unødig scroll kunne se:

- samlet/worst status;
- aktive alarmer;
- device/site/customer identity;
- latest heartbeat/capture;
- backlog/upload;
- update-state;
- risici/handlinger der kræver opmærksomhed.

### 9.3 Statusord skal betyde det samme — CURRENT

`online`, `stale`, `offline`, `deployed`, `healthy` mv. må ikke have forskellige skjulte definitioner på forskellige sider. OBS-UI-001 dokumenterede konkret uenighed mellem Dashboard og Drift.

### 9.4 UNKNOWN er en rigtig tilstand — CURRENT

- “ingen data endnu” må ikke ligne “failed”.
- UI skal vise utilstrækkelig evidence ærligt frem for falsk grøn status.

### 9.5 Hjælp/forståelighed — CURRENT

Peter ønskede gennemgang af alle UI-sider/menuer/undermenuer, så ikke-selvforklarende parametre har kort kontekstuel hover-hjælp. Dette blev omsat til `InfoTooltip` på tværs af UI.

### 9.6 Farlige handlinger — CURRENT

- farlige/destruktive handlinger visuelt og semantisk adskilt fra read-only;
- konsekvens før handling;
- passende confirmation;
- audit bagefter.

### 9.7 Terminal/recovery UX — CURRENT

En adgangsvej er ikke “virkende” blot fordi en shell teknisk kan modtage tegn. Peter har eksplicit afvist løsninger hvor PTY/transcript/sikkerhedskontrol gjorde terminalen praktisk ubrugelig. Ctrl-C, Tab, history arrows, Home/End, resize, reconnect mv. er capability-egenskaber, ikke kosmetik.

## 10. Konfiguration

### 10.1 Hierarki — CURRENT

Fem lag findes i den historiske målmodel:

`Global → Kunde → Site → Kamera → Runtime/LAB`

Central permanent config beskrives normalt som fire lag; Runtime/LAB er et temporært femte lag.

### 10.2 Effective config/provenance — CURRENT

- bruger skal kunne se arvet værdi, override, effektiv værdi og vindende lag;
- ændringer skal være audit/versioneret;
- laveste nødvendige override foretrækkes for ikke at blokere senere globale ændringer.

### 10.3 “Ingen rå DB for normale parametre” — CURRENT INTENT

Tidligt krav: timing/operationelle parametre skal administreres gennem UI/configmodel; normal drift bør ikke kræve manuelle databaseændringer eller kodeændringer.

### 10.4 Saved != applied — CURRENT

Central status skal kunne skelne mellem “gemt/udsendt” og faktisk anvendt runtime-state på Edge.

## 11. Edge ↔ Headend kommunikation og offline drift

### 11.1 Edge-autonomi — CURRENT

- Edge skal kunne fortsætte relevante missionfunktioner uden Headend/internet.
- Lokal config/cache, lokal DB/buffer og lokal recovery er grundkrav.

### 11.2 Polling-model — CHANGED

**Historisk:** separate heartbeat/config/SIEM-loops.  
**Current:** konsolideret sync-poll er den senere implementeringsretning.

Intentionen er fortsat: config, heartbeat, telemetry, events og update-state skal være sporbare og robuste. Den konkrete polling-topologi er CHANGED.

### 11.3 Last-seen ≠ healthy — CURRENT LEARNING

Handover-historien viser flere tilfælde hvor config-poll/last_seen fortsatte mens capture/diagnostics/service reelt var døde. Derfor må kommunikationsaktivitet ikke alene definere Edge health.

## 12. Lokal og remote management / recovery

### 12.1 Lokal recovery — CURRENT

- må ikke afhænge af Headend eller internet;
- må ikke afhænge af én managementtransport;
- BT-PAN, LAN og routed/customer networks kan anvendes hvor deployment-policy tillader det;
- authentication/authorization skal være uafhængig af netværksvejen.

### 12.2 General-purpose/root shell — CHANGED → CURRENT DEVELOPMENT CAPABILITY

**Tidlig/proposed retning:** restricted shell / “No General-purpose Shell” / typed operations.  
**Nuværende beslutning:** under development/stabilization vejer recoverability/diagnosability højere. Root/general-purpose shell bevares, med additive controls der ikke gør recovery skrøbelig.

- local-first session audit;
- fail-closed enable-policy;
- ingen central/network dependency for selve recoverykanalen;
- fremtidig begrænsning vurderes ud fra faktisk modenhed/evidence, ikke dato.

### 12.3 Remote access — CURRENT

- reverse tunnel frem for generel inbound Edge-administration;
- host identity/trust verificeres;
- browserterminal kræver trusted/verified host;
- central remote access må ikke være eneste recoveryvej.

### 12.4 Customer-controlled/support access — CHANGED

**Tidligt:** ingen agentadgang til staging/prod.  
**Senere modning:** default-deny + kontrolleret, tidsbegrænset, logget break-glass-support, aktiveret af Peter og med relevant kundesamtykke/ticket.

Dette er et godt eksempel på “intention bevaret, mekanisme modnet”: ingen stående adgang består som invariant.

## 13. Updates, dependencies og release governance

### 13.1 Headend er production update authority — CURRENT

- Edge må ikke kræve direkte GitHub/Internet/apt i production.
- Direkte git-pull kan kun være lab/nødspor, tydeligt policybegrænset.

### 13.2 Artifact — CURRENT

Artifact bør bindes til:

- release/target revision;
- source ref;
- build timestamp;
- hash;
- signer;
- tests;
- SBOM;
- rollback target.

Artifact skal være immutable efter godkendelse.

### 13.3 Change ticket — CURRENT

- både menneske- og maskinlæselig;
- scope, severity, versions, release notes, security impact, tests, rollback, maintenance/reboot, SBOM, approvals, signatures;
- approval skal være sporbar til actor/role/time/context;
- customer/external ticket reference kan være relevant.

### 13.4 Staged rollout — CURRENT

`R&D/LAB → staging/test → pilot → production`, med mulighed for pause/stop ved fejl og separat promotion.

### 13.5 Update må ikke afbryde missionen unødigt — CURRENT

- capture schedule skal indgå i maintenance/reboot-beslutning;
- eksisterende version fortsætter hvis artifact ikke kan hentes/verificeres;
- pre-update backup;
- rollback/recovery ved failure.

### 13.6 “deployed” != “working” — CURRENT LEARNING

Edge1-hændelsen og ældre Ollama-hændelse viser samme mønster: package/deployment-state er ikke bevis for fungerende runtime. Postflight skal kontrollere relevante outcomes (service, API, tunnel/capture hvor relevant) og monitorering skal opdage vedvarende failure efter deployment.

### 13.7 Dependencies er første-klasses updateobjekter — CURRENT

Python/npm/gphoto2/nginx/Postgres/Ollama/certbot/fail2ban/systemd mv. skal kunne spores, risikovurderes og bindes til SBOM/change/evidence, ikke behandles som usynlig “underliggende drift”.

## 14. Provisioning, Builder og reproducerbarhed

### 14.1 Zero/near-zero touch — CURRENT

- bootstrap package;
- one-time/time-limited token;
- identity;
- Headend URL/CA/config;
- automatisk effektiv config efter enrollment.

### 14.2 Identity — CHANGED

**Tidligt:** MAC-derived ID kunne bruges som identitet.  
**Current:** MAC kan være bootstrap convenience, ikke production trust anchor. Nøgler/certs/revocation er den ønskede trust-retning.

### 14.3 Multi-target HAL — CURRENT

Historisk mål om OP4Pro, OP-PC+, RPi4/RPi5, Jetson m.fl. og HAL-abstraktion bevares. Faktisk support skal vurderes pr. target og må ikke udledes af at en klasse/file findes.

### 14.4 Reproducibility/provenance — CURRENT LEARNING

Builder/audit viser, at `source_commit` eller VERSION ikke må hævde reproducerbar artifact-state hvis artifactets faktiske bytes indeholder andet. Build → artifact → installed runtime skal have verificerbar provenance.

## 15. Backup, restore og disaster recovery

### 15.1 Backup er ikke nok — CURRENT

Et backup-job er kun en antagelse indtil restore er testet.

### 15.2 Headend restore — CURRENT / OPEN

- database restore i scratch;
- config restore;
- image mirror sanity og åbning af faktiske billeder;
- dokumenteret resultat/RTO;
- separat bare-metal-scenarie;
- offsite-scenarie;
- RPO for interval mellem mirrors/backups.

### 15.3 Edge backup — CURRENT

Historisk pull-model: ingen generel inbound connection til Edge; Headend anmoder, Edge laver backup og pushes ud via godkendt kanal.

### 15.4 Warm/cold Headend — TARGET / OPEN

- genskabelse fra rå OS;
- DB/config/artifacts/keys/services;
- trust/pinning ved primær/fallback;
- dokumenteret RTO/RPO.

## 16. Health, observability og alarmer

### 16.1 Outcome frem for proces — CURRENT

- process active, last_seen, deploy success og restart count er signaler, ikke outcome i sig selv.
- health skal måle de kritiske capabilities der faktisk forventes at virke.

### 16.2 Monitoring proportional to impact — CURRENT

Alarmbehov afgøres af konsekvens/risk, ikke kun hvor længe fejlen har eksisteret.

### 16.3 Restart loops — OPEN

Hvis systemd/watchdog konstant genstarter en fejlet service, må det ikke maskere failure. NRestarts/tilsvarende telemetry skal have en passende consumer/threshold/klassifikation, med hensyn til services hvor restart er forventet normaladfærd.

### 16.4 Notifications — CURRENT

Email/SMS/Teams findes som kanaler; en ændring skal testes med faktisk testbesked. “Configured” er ikke bevis for at alarmen kan leveres.

## 17. Security, identity og tenant isolation

### 17.1 Tenant isolation — CURRENT

- customer/site/device scope server-side;
- request body må ikke kunne vælge fremmed tenant;
- cross-tenant image/data leak er en capability failure.

### 17.2 MFA/step-up — CURRENT, implementation evolved

Historisk RS256/short-JWT/WebAuthn design og senere TOTP/policy-implementation har ændret detaljer. Den vedvarende intention er stærkere authentication for admin/high-risk handlinger og mulighed for step-up.

### 17.3 Secrets — CURRENT

- ingen secrets i Git;
- ingen rå secrets i exports/chat/notebook-dumps;
- private Edge SSH keys ejes på Edge i senere design; Headend public-key-only;
- stale/revoked credentials skal håndteres gennem lifecycle.

### 17.4 mTLS/internal CA — OPEN/TARGET

Design har eksisteret længe; faktisk implementation/status skal verificeres mod nyere source før det behandles som aktiv control.

### 17.5 Edge disk encryption — OPEN/TARGET

Historisk højt prioriteret ved fysisk kompromitteret Edge, men må vurderes mod recovery/operational constraints før implementation.

## 18. Compliance/GRC/regulatory intelligence

### 18.1 Compliance Cockpit — CURRENT

Systemet skal kunne vise og arbejde med gældende lovgivning, standarder, kontrakter og intern governance uden at kalde et TimeLapse-subset for en komplet standardaudit.

### 18.2 Applicability first — CURRENT

Applicability skal afgøres efter fx jurisdiction, sector, company/product role, product class, AI use case og contract før compliance-status.

### 18.3 Statusser må ikke blandes — CURRENT

`implemented`, `tested`, `independently_assessed`, `certified` er forskellige påstande.

### 18.4 Reproducible audit — TARGET/CURRENT PRINCIPLE

Audit bindes til:

- catalog/version/hash;
- scope;
- applicability profile;
- evidence snapshot;
- assessor;
- timestamp.

Alle applicable controls skal have eksplicit status; N/A kræver begrundelse.

### 18.5 External regulatory change — CURRENT PRINCIPLE

`fetch → hash → diff → review → approved baseline`; ingen ekstern ændring bliver automatisk gældende bare fordi en connector finder den. Headend skal kunne fortsætte offline med seneste godkendte snapshot.

## 19. Risk/business context

### 19.1 FAIR-ready, ikke falsk præcision — CURRENT

CMDB/SIEM risk score er operationel prioritet, ikke automatisk FAIR eller forventet DKK-tab.

### 19.2 Customer business input — TARGET/CURRENT MODEL

Versioneret/valideret input kan omfatte:

- service-/projektværdi;
- downtime cost;
- recreation cost;
- contractual penalties;
- business dependency;
- CIA impact;
- RTO/MTD;
- personal data level;
- assumptions/context.

Historik bevares, og egentlig FAIR-beregning må først aktiveres når frequency/vulnerability/loss-input er tilstrækkeligt valideret.

## 20. Platform/payload og langsigtet produktretning

### 20.1 Platform/Payload split — CURRENT / Accepted ADR-001

Platformen ejer generiske non-functional capabilities: identity, config/policy, update, telemetry, remote access, HAL, security/GRC, storage/backup.

Payload ejer domænelogik: kamera/timelapse, image QA, domain AI, domain UI/data.

### 20.2 Isolation — CURRENT DESIGN PRINCIPLE

Manifest/declaration er ikke isolation i sig selv. Reelle privileges/resources/fault boundaries skal håndhæves af platform-policy/enforcement boundary.

### 20.3 Control plane ≠ data plane — CURRENT DESIGN PRINCIPLE

De skal have separate versionerede kontrakter.

### 20.4 Langsigtet vertical-vision — CURRENT CONTEXT, ikke akut krav

Platformen ønskes på sigt genbrugelig til fx mindre vandværker, vind/sol og andre edge/OT-installationer. TimeLapse Pro production-readiness må ikke ofres for for tidlig generalisering.

## 21. AI-samarbejde, udviklingsproces og governance

Disse er ikke produkt-features, men de er nu en del af projektets operative intention og skal bevares som governance-kontekst.

### 21.1 Evidence before confidence — CURRENT

En status eller agentpåstand er ikke bevis. Faktiske bytes/runtime/outcome prioriteres.

### 21.2 Capability preservation — CURRENT

Konsekventielle ændringer skal identificere berørte capabilities/invariants før disposition og verificere dem efter ændring.

### 21.3 Human/AI authority — CURRENT

Mandat skal være eksplicit og kan være permanent, midlertidigt eller betinget. AI-autonomi kan udvikle sig med evidence/risk, men må ikke antages eller overføres mellem modeller/vendors.

### 21.4 AI routing — CURRENT DIRECTION

Vælg udfører efter dokumenteret egnethed, nødvendige tools/dataadgang, risk og samlet ressourceforbrug — ikke favoritbrand. Independent review er risk-based og skal være reelt uafhængigt i metode/kontekst, ikke bare et andet logo.

### 21.5 Resource/quota availability — OBSERVATION

Abonnement/agent/model er forskellige ting; quota/tilgængelighed er en reel operationel constraint og bør indgå i routing/continuity frem for at gøre én bestemt agent til permanent blocking dependency.

### 21.6 Cross-repository / website propagation — CURRENT

Konsekventielle governance-/architecture-/capability-beslutninger vurderes for impact på authoritative og derived artifacts, andre repos og publicerede websites. Completion kræver update+verification eller registreret gap med owner/disposition.

## 22. Evolution / conflict ledger

| Emne | Tidligere tanke/løsning | Senere/current retning | Klassifikation |
|---|---|---|---|
| Edge update | direkte `git pull`/origin | Headend-mediated signed artifact; direct only lab/emergency | SUPERSEDED for prod |
| OS update | direkte apt/upgrade | Headend-signed offline bundle, no-download | SUPERSEDED for prod |
| Headend | RPi/SQLite | Mac Mini/PostgreSQL | CHANGED |
| Kamera | Canon-centric | Nikon Z30 current, abstraction retained | CHANGED |
| Device trust | MAC-derived identity | MAC bootstrap convenience; key/cert trust | CHANGED |
| JWT/auth | RS256 short-token target, memory-only browser | later implementation differed (HS256/TOTP etc.) | CHANGED / VERIFY |
| Cloudflare | Tunnel / 18443 / direct 80/443 variants | direct 8443 on staging/prod due CrushFTP; DNS-01; optional proxy | SUPERSEDED |
| Edge polling | separate config/heartbeat/SIEM loops | consolidated sync poll | SUPERSEDED implementation |
| Retention | automatic per-camera cleanup | explicit disposition/no automatic project-data deletion | CHANGED materially |
| Local service | elaborate Local Service Gateway, no shell | simpler TOTP/Service Operations + root shell retained in dev | CHANGED / Proposed model not binding |
| Remote support | no agent staging/prod ever | default deny + Peter-controlled time-bound audited exception | CHANGED, invariant preserved |
| SSH key ownership | Headend-generated private Edge key | Edge owns operational private key; Headend public-key-only | SUPERSEDED |
| Browser/terminal audit | full transcript attempted | transcript dropped when it broke terminal; start/end audit preserved | CHANGED by usability evidence |
| Health | heartbeat/last_seen/deployed as convenient status | actual runtime/capture/service outcome required | CHANGED by incidents |
| AI tagging | closed vocabulary/list pressure | open contextual vocabulary + normalization/review | CHANGED |
| AI processing | cloud-centric | configurable cloud/local/hybrid/technical | EXPANDED |
| Video | simple FFmpeg export | evidence/balanced/web/master/creative distinction, reproducible processing | EXPANDED |
| Platform scope | TimeLapse-specific monolith | Accepted Platform/Payload split + future vertical reuse | EXPANDED |

## 23. Candidate additions/refinements to the Golden Capability Map

The initial 16-capability map is deliberately small. Archaeology shows several areas that may deserve explicit top-level capability or a named sub-capability before the map becomes stable:

1. **Site synchronization / trustworthy time** — likely strengthen CAP-03 rather than new top-level.
2. **Image quality & photographic consistency** — currently spread across capture/UI; may deserve own Golden Capability.
3. **Timelapse render/export reproducibility** — likely separate from ordinary Headend UI.
4. **AI analysis/search/anomaly** — significant product value not explicit in current 16.
5. **Provisioning / reproducible build** — currently hidden inside update/recovery; #242 shows it deserves explicit treatment.
6. **Backup / restore / disaster recovery** — too consequential to remain implicit in CAP-13/15.
7. **Compliance/GRC evidence** — product capability, not only governance.
8. **Notification / alarm delivery** — possibly sub-capability of health/monitoring.
9. **Historical import / virtual devices** — product functionality with important preservation invariant.
10. **Scalability / multi-headend / customer-owned governance** — likely future capability, not necessarily Golden today.

These are candidates, not automatically promoted. Promotion should depend on whether loss of the capability would mean Peter considers TimeLapse Pro materially diminished.

## 24. High-value acceptance scenarios recovered from history

The following scenarios repeatedly expose the difference between “code exists” and “product works”:

1. **Offline capture:** disconnect Headend/network; scheduled captures continue; buffer/backlog visible; reconnect drains correctly.
2. **Reboot-to-mission:** reboot Edge; management and capture return; next scheduled capture succeeds.
3. **Timestamp chain:** physical capture time → Edge record → Headend DB → UI → video overlay retain same semantic instant.
4. **Device replacement:** replace Edge while retaining logical camera/site history.
5. **Update failure:** deploy controlled bad candidate; health fails; rollback/recovery + truthful status + alarm.
6. **Dependency failure:** installed package/version differs from healthy runtime; status must not say “working”.
7. **Local recovery with Headend down:** technician gets practical terminal/recovery via permitted local path.
8. **Network path change:** same valid recovery session survives legitimate BT-PAN/WiFi/Ethernet transition while auth/audit remains intact.
9. **Restore:** restore DB/config/images into scratch/new host and prove the recovered data opens/works.
10. **Tenant isolation:** user from tenant A cannot retrieve tenant B image/API data even by direct route manipulation.
11. **Image evidence:** original remains unchanged after QA/render/redaction workflow; derivative provenance is clear.
12. **Video reproducibility:** same manifest/toolchain yields functionally identical output and correct capture timestamps.
13. **Alert delivery:** induce a controlled critical condition; correct channel receives alarm; evidence persists.
14. **UI truthfulness:** Dashboard/Drift/CMDB show consistent status for same underlying state, including UNKNOWN/no-data.
15. **Direct Edge terminal:** Ctrl-C, Tab, history, Home/End, resize, reconnect, logout/expiry, no Headend/internet.

## 25. Gaps in this archaeology

- Binære chat/docx-kilder are not directly re-parsed in this pass; their earlier extracted/consolidated content is included by provenance.
- Google Drive pointer files referenced in old corpus were not independently fetched in this pass.
- Very old archived documents are represented mainly through the v10 consolidation and explicit conflict tables unless a later issue required reopening the original.
- Runtime truth is not inferred from historical “✅ Implementeret” labels; current capability verification is a separate phase.
- Some historical requirements were already internally inconsistent at the time (e.g. retention, auth storage, ports, update paths). This document intentionally preserves the conflict rather than silently selecting an old winner.

## 26. Recommended use

Use this archaeology as the **input catalogue** for `CAPABILITY_MAP_2026-09-16_CHATGPT.md`:

1. decide which intentions are true Golden Capabilities;
2. attach stable invariants;
3. link usecases;
4. map current implementation;
5. map automated evidence;
6. map physical/runtime evidence;
7. classify current gaps honestly;
8. preserve superseded/history references rather than deleting them.

The archaeology itself should remain descriptive/provenance-oriented. GRC remains authoritative for active findings/tests/risks/evidence; accepted ADRs/governance remain authoritative for decisions.