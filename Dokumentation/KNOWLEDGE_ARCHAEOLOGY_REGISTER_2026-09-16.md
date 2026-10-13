# TimeLapse Pro — Knowledge Archaeology Register

**Dato:** 2026-09-16  
**Status:** DISCOVERY — working register, ikke autoritativ GRC-import  
**Branch:** `chatgpt/capability-map-v0-20260916`  

## 1. Formål

Dette register opsamler krav, ønsker, beslutninger, rationale, lessons learned, usecases, acceptance criteria, risici og åbne spørgsmål fra hele TimeLapse Pro-projektets dokumentation og historik.

Målet er at bevare projektets tanker uden at gøre ethvert historisk udsagn normativt.

Hvert fund skal derfor have:

- kilde og om muligt dato/version;
- type;
- historisk/aktuel/usikker status;
- mulig konflikt eller supersession;
- foreslået autoritativt hjem;
- relation til capability/GRC/usecase/ADR hvor kendt.

## 2. Dispositionstyper

- `GRC_REQUIREMENT`
- `GRC_CAPABILITY`
- `GRC_RISK`
- `GRC_CONTROL`
- `GRC_TEST_EVIDENCE`
- `GRC_FINDING`
- `USECASE`
- `ADR_DECISION`
- `OPERATIONAL_RULE`
- `PRODUCT_DOC`
- `HISTORICAL_KNOWLEDGE`
- `FUTURE_IDEA`
- `OPEN_QUESTION`

**Regel:** Discovery-materiale må ikke automatisk promoveres til gældende krav. Konflikter og senere ændringer skal bevares eksplicit.

## 3. Kildeinventar — Wave A

Første gennemgang omfatter allerede identificerede stærke kilder:

1. `UI_USECASE_CATALOG_2026-08-26.md` — menneskelig UAT/regressionsbaseline.
2. `KRAVREGISTER_og_STATUS_v10.md` — historisk kravbaseline; ikke aktuel runtime-status.
3. `MENUGUIDE_BRUGER_v1.md` og `MENUGUIDE_ADMIN_v1.md` — funktionalitet udledt fra UI-kode.
4. GRC PostgreSQL `grc_items` — autoritativt for tests, testkørsler, risici, findings, remediations og evidens.
5. `tests/architecture_baseline.json` og kontrakt/regressionstests — maskinlæsbar regressionsbeskyttelse.
6. SABSA Architecture v2/v3.
7. SABSA Risk Assessment v1/v2.
8. System Architecture & Configuration Guide v3.
9. HANDOVER_LOG, PAKKE_SPOR_REGISTER, ADR/SAMARBEJDSMODEL og nyere archaeology/review-rapporter.
10. Git-historik, issues, PR'er og diskussioner — senere waves.
11. Gemte projektsamtaler/summeringer — senere waves; udsagn herfra skal kilde- og tidsmærkes og må ikke antages aktuelle.

## 4. Første udtræk — produktmission og business attributes

### KA-0001 — Ubemandet autonom timelapse
- **Type:** GRC_REQUIREMENT + GRC_CAPABILITY
- **Kilde:** SABSA Architecture v2/v3; Configuration Guide.
- **Udsagn:** Systemet skal levere pålidelige timelapse-optagelser fra fysisk svært tilgængelige/ubemandede lokationer med minimal menneskelig indgriben.
- **Relation:** CAP-01, CAP-05, CAP-06, CAP-13.
- **Status:** CURRENT INTENT; skal verificeres mod nyere GRC.

### KA-0002 — Capture uafhængig af netværk
- **Type:** GRC_REQUIREMENT
- **Kilde:** SABSA Business Attribute Availability + Configuration Guide.
- **Udsagn:** Planlagt capture skal fortsætte når Headend/netværk ikke er tilgængeligt.
- **Relation:** CAP-01.
- **Status:** CURRENT INTENT.

### KA-0003 — Data-integritet fra linse til arkiv
- **Type:** GRC_REQUIREMENT + GRC_CONTROL
- **Kilde:** SABSA Architecture v2/v3.
- **Udsagn:** Billedidentitet/integritet skal kunne dokumenteres gennem capture- og arkivkæden; historisk foreslået/implementeret med SHA-256 og strukturerede filnavne.
- **Relation:** CAP-04.
- **Status:** CURRENT INTENT; konkrete mekanismer skal vurderes mod nuværende source.

### KA-0004 — Site-synkroniserede captures
- **Type:** GRC_REQUIREMENT
- **Kilde:** SABSA Architecture v3.
- **Udsagn:** Kameraer på samme site skulle optage inden for 1 sekund af hinanden via koordineret schedule og synkroniseret tid.
- **Relation:** CAP-03 + CAP-01.
- **Status:** HISTORICAL REQUIREMENT CANDIDATE — vigtigt at verificere om dette stadig er gældende.

### KA-0005 — Tenant-isolation
- **Type:** GRC_REQUIREMENT + GRC_RISK + GRC_CONTROL
- **Kilde:** SABSA Architecture/Risk Assessment.
- **Udsagn:** Kunde/Tenant A må ikke kunne tilgå Tenant B's data; isolation skal håndhæves gennem relevante backend-, auth-, storage- og transfergrænser.
- **Relation:** CAP-14.
- **Status:** CURRENT INTENT.

### KA-0006 — Boot-to-capture
- **Type:** GRC_REQUIREMENT + GRC_TEST_EVIDENCE
- **Kilde:** SABSA Architecture v2/v3.
- **Udsagn:** Historisk mål: automatisk recovery efter strømudfald og boot-to-capture <120 sekunder.
- **Relation:** CAP-13.
- **Status:** HISTORICAL ACCEPTANCE TARGET — skal verificeres før promotion.

### KA-0007 — Dage/uger uden netværk
- **Type:** GRC_REQUIREMENT
- **Kilde:** SABSA Architecture.
- **Udsagn:** Systemet skal kunne fungere uden netværk i dage/uger ved hjælp af lokal buffer, cached config og store-and-forward.
- **Relation:** CAP-05/CAP-06.
- **Status:** CURRENT INTENT; konkret retention/kapacitet skal verificeres.

### KA-0008 — Skalerbarhed
- **Type:** GRC_REQUIREMENT
- **Kilde:** SABSA Architecture v2/v3.
- **Udsagn:** Historiske mål spænder fra 1–100+ enheder til 20+ kunder/100+ enheder uden arkitekturændring.
- **Relation:** Headend/fleet capability; mulig manglende Golden Capability.
- **Status:** CONFLICT/EVOLUTION — bevar begge formuleringer; normaliser senere.

## 5. Første udtræk — arkitektur- og designbeslutninger

### KA-0010 — gPhoto2 til DSLR-kontrol
- **Type:** ADR_DECISION
- **Kilde:** Configuration Guide AD-03.
- **Rationale:** DSLR-kontrol inkl. settings/RAW/EXIF; Motion/fswebcam vurderet som webcam-orienteret.
- **Status:** HISTORICAL DECISION; verificer nuværende multi-camera-driverarkitektur.

### KA-0011 — OpenCV Laplacian til billedkvalitet
- **Type:** ADR_DECISION
- **Kilde:** Configuration Guide AD-04/§8.1.
- **Rationale:** tilstrækkelig failure detection, lav kompleksitet, ingen proprietær NPU-driverafhængighed.
- **Status:** HISTORICAL DECISION; senere AI-sidecars kan supplere uden nødvendigvis at supersede QA-mekanismen.

### KA-0012 — overlayFS for filesystem resilience
- **Type:** ADR_DECISION + GRC_CONTROL
- **Kilde:** Configuration Guide AD-05; SABSA risk T-O07.
- **Udsagn:** Selektiv read-only OS/root med writable dataområde blev valgt som ønsket resilience-design.
- **Status:** HISTORICALLY PLANNED / IMPLEMENTATION MUST BE REVERIFIED.

### KA-0013 — Reverse SSH fremfor Cloudflare WARP
- **Type:** ADR_DECISION
- **Kilde:** Configuration Guide AD-06/§9.4.
- **Rationale:** ingen tredjepartsafhængighed, NAT/CGNAT-egnet, standard OpenSSH/auditability.
- **Status:** HISTORICAL DECISION; senere Cloudflare proxy-diskussion for Headend webtrafik er et separat spørgsmål og må ikke fejlagtigt behandles som samme beslutning.

### KA-0014 — Pull-model for config
- **Type:** ADR_DECISION + GRC_CONTROL
- **Kilde:** Configuration Guide AD-07.
- **Rationale:** Edge initierer; ingen inbound config-port; cached config giver degraded drift.
- **Relation:** CAP-07/CAP-08.
- **Status:** CURRENT ARCHITECTURAL INTENT, subject to source verification.

### KA-0015 — SQLite Edge / PostgreSQL Headend
- **Type:** ADR_DECISION
- **Kilde:** Configuration Guide AD-09.
- **Rationale:** lokal enkelhed/WAL/single-device vs central concurrency/multi-tenant.
- **Status:** CURRENT/HISTORICAL — verificer nuværende implementation.

### KA-0016 — Nightly reboot som stabilitetsmekanisme
- **Type:** ADR_DECISION + OPERATIONAL_RULE
- **Kilde:** Configuration Guide AD-10; SABSA.
- **Rationale:** USB/gPhoto2 hang, memory/zombie cleanup.
- **Status:** HISTORICAL — skal vurderes kritisk mod nyere watchdog/health/recovery-arkitektur; må ikke antages ønsket permanent design.

### KA-0017 — Suspend-to-RAM mellem captures
- **Type:** FUTURE_IDEA / HISTORICAL_REQUIREMENT_CANDIDATE
- **Kilde:** Configuration Guide AD-11.
- **Udsagn:** Power-saving mål med krav om bench validation før deployment.
- **Status:** PLANNED/HISTORICAL; ikke promotion uden nyere evidens.

## 6. Første udtræk — åbne ønsker og produktkrav

### KA-0020 — Timelapse video generation
- **Type:** FUTURE_IDEA + GRC_REQUIREMENT_CANDIDATE
- **Kilde:** Configuration Guide FR-18.
- **Udsagn:** Headend skal kunne komponere timelapse-video fra datointerval, historisk med FFmpeg som anbefalet værktøj.
- **Status:** CONFIRMED OPEN ITEM i historisk dokument; nuværende status ukendt.

### KA-0021 — UX for ikke-IT-brugere
- **Type:** GRC_REQUIREMENT_CANDIDATE + USECASE
- **Kilde:** Configuration Guide FR-20/BR-06.
- **Udsagn:** Site managers/kunder uden IT-baggrund skal kunne bruge UI; klare statusindikatorer, thumbnail gallery, simpel config-editor og alert inbox blev efterspurgt.
- **Relation:** CAP-16.
- **Status:** CURRENT PRODUCT INTENT candidate; nyere UI-katalog skal være stærkere evidence.

### KA-0022 — Drift i -25°C til +60°C
- **Type:** GRC_REQUIREMENT_CANDIDATE + GRC_RISK
- **Kilde:** Configuration Guide NFR-01.
- **Udsagn:** Historisk miljømål -25°C..+60°C kræver passende SSD/enclosure/thermal design.
- **Status:** OPEN/HISTORICAL — hardware-BOM skal verificeres.

### KA-0023 — IP65 enclosure minimum
- **Type:** GRC_REQUIREMENT_CANDIDATE
- **Kilde:** Configuration Guide NFR-12.
- **Udsagn:** Fanless aluminium, thermal path, cable management, camera window, drip loops, IP65 minimum.
- **Status:** OPEN/HISTORICAL.

### KA-0024 — Alert delivery channel
- **Type:** FUTURE_IDEA + GRC_REQUIREMENT_CANDIDATE
- **Kilde:** Configuration Guide FR-19.
- **Udsagn:** Offline/health alerts skulle have ekstern delivery; email/SMS/webhook var kandidater.
- **Status:** OPEN DECISION historisk; nyere monitoring-arkitektur skal undersøges.

### KA-0025 — SLA/pricing/business model
- **Type:** PRODUCT_DOC + OPEN_QUESTION
- **Kilde:** Configuration Guide BR-01.
- **Udsagn:** Hardware købes af kunde; software/headend/monitoring/support leveres som service; SLA/pricing var ikke fastlagt.
- **Status:** BUSINESS OPEN ITEM; sandsynligvis uden for teknisk GRC medmindre SLA skaber konkrete requirements.

## 7. Første udtræk — risici der kan afsløre skjulte krav

### KA-0030 — Config må ikke overskrive forkert Edge-state
- **Type:** GRC_RISK + GRC_CONTROL + GRC_REQUIREMENT_CANDIDATE
- **Kilde:** Risk Assessment T-O01.
- **Udsagn:** Per-device config/versioning skal forhindre utilsigtet config-overskrivning.
- **Relation:** CAP-08.

### KA-0031 — GPIO/HAL portability
- **Type:** GRC_RISK + HISTORICAL_KNOWLEDGE
- **Kilde:** Risk Assessment T-O02.
- **Udsagn:** BCM/BOARD antagelser var inkompatible med RK3588S; historisk løsning var direkte sysfs GPIO.
- **Status:** HISTORICAL SOLUTION; nyere HAL-arkitektur kan have supersedet den konkrete løsning, men problemet/kravet skal bevares.

### KA-0032 — SFTP credentials må ikke ligge i klartekst
- **Type:** GRC_RISK + GRC_REQUIREMENT_CANDIDATE
- **Kilde:** Risk Assessment T-O05.
- **Status:** Historisk aktiv høj risiko; nuværende credential-model skal verificeres.

### KA-0033 — Version-controlled deployment/provenance
- **Type:** GRC_REQUIREMENT + GRC_RISK
- **Kilde:** Risk Assessment T-O08 + nyere #242-læring.
- **Udsagn:** Runtime på Edge skal kunne forbindes til versionsstyret/reproducerbart artifact; direkte patches uden provenance er en risiko.
- **Relation:** CAP-11/CAP-13.
- **Status:** CURRENT INTENT; nyere audit viser at problemet har udviklet sig fra 'main.py ikke i git' til artifact/source provenance.

### KA-0034 — NTP/clock health
- **Type:** GRC_REQUIREMENT + GRC_RISK + GRC_CONTROL
- **Kilde:** Risk Assessment T-TS01/T-TS02.
- **Udsagn:** Time sync skal verificeres; historisk alarmmål >2s og capture sync-mål <1s.
- **Relation:** CAP-03/CAP-12.
- **Status:** REQUIREMENT CANDIDATE; thresholds skal genbekræftes.

### KA-0035 — Modem self-recovery
- **Type:** GRC_REQUIREMENT_CANDIDATE + GRC_CONTROL
- **Kilde:** Risk Assessment T-N02.
- **Udsagn:** Ved vedvarende connectivity failure skal modem kunne power-cycles/recoveres automatisk.
- **Relation:** CAP-07/CAP-13.
- **Status:** HISTORICAL/CURRENT candidate.

### KA-0036 — Bufferkapacitet ved langvarigt netværksudfald
- **Type:** GRC_REQUIREMENT + GRC_RISK
- **Kilde:** Risk Assessment T-N01.
- **Udsagn:** Historisk 50 GB lokal buffer og store-and-forward ved >24h outage.
- **Relation:** CAP-05/CAP-06.
- **Status:** CAPABILITY current; konkret 50 GB threshold historical until reverified.

## 8. Kendte evolutioner / konflikter der SKAL bevares

1. **GPIO:** direkte sysfs var tidligere en løsning på Orange Pi inkompatibilitet; nyere HAL/service-operation arkitektur må vurderes som mulig supersession, ikke omskrive historien.
2. **Remote access:** Reverse SSH vs Cloudflare WARP handlede om Edge remote access. Senere Cloudflare proxy for Headend webtrafik er et andet scope.
3. **Authentication:** ældre MVP-dokumenter tillod statisk password; senere design har TOTP/MFA/break-glass. Den gamle tekst skal mærkes historical/superseded, ikke slettes.
4. **Monitoring:** ældre dokumentation beskrev watchdog/heartbeat som implementeret; Edge1-hændelsen viser at 'implementeret telemetry/restart' ikke er det samme som operational outcome monitoring.
5. **Deployment:** ældre risiko var direkte patches uden git; nyere provenance-audit viser et bredere artifact/runtime identity-problem.
6. **Management path:** ældre beskrivelser fokuserede på reverse SSH; nyere krav kræver også lokal Edge-hosted recovery over flere tilladte transports.
7. **Status:** gamle `LØST`/`IMPLEMENTERET` markeringer er historiske snapshots og må aldrig automatisk importeres som nuværende GRC-status.

## 9. Discovery backlog

Næste waves:

- **Wave B:** fuldt kravregister + UI usecase catalog + menuguides; dedupliker alle krav/usecases.
- **Wave C:** alle nyere Markdown/HANDOVER/ADR/governance/archaeology-rapporter.
- **Wave D:** GitHub issues/PR'er/commit-historik for krav og rationale som kun findes i udviklingshistorien.
- **Wave E:** gemte projektchats/summeringer; udtræk Peter-ønsker, forkastede alternativer, lessons learned og 'det skal også kunne'-krav.
- **Wave F:** source/tests/GRC reconciliation og promotion/disposition.

## 10. Promotion gate til GRC

Et discovery-item promoveres først til GRC når:

1. udsagnet er klassificeret korrekt;
2. kilden er registreret;
3. nyere modstridende beslutninger er søgt;
4. scope og status er kendt eller eksplicit UNKNOWN;
5. relation til eksisterende GRC-item er undersøgt for dublet;
6. hvis requirement: acceptance/evidence-behov er beskrevet;
7. historisk status bevares ved supersession frem for overskrivning.
