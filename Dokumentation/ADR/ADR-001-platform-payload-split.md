# ADR-001: Platform/Payload-snit for edge-arkitekturen

- **Status:** **Accepted 2026-07-16** (Peter, efter enig anbefaling fra Claude + Codex). Bindende for både menneske- og AI-sessioner (jf. `ADR/README.md` og `00_START_HER.md`). Afvig kun via en ny ADR der superseder denne.
- **Dato:** 2026-07-15 · **Revideret:** 2026-07-16 (Codex' 6 amendments + AI-domænesnit indarbejdet — se §Amendments og §Revisionslog) · **Accepteret:** 2026-07-16
- **Beslutningstagere:** Peter (produkt-/driftsejer), Claude, Codex
- **Kontekst-referencer:** `Arkitektur/Modularisering_Platform_Payload_Plan.md`, `Arkitektur/TimeLapse_Arkitektur_og_Dataflow.mermaid.md`, `Claude_QA_Arkitektur_Review_2026-07-15.md` §4, `Codex_REVIEW_Claude_Arkitektur_Risk_Test_2026-07-15.md`, `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md` (K1–K6), `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`.

---

## Kontekst

To kræfter tvinger en beslutning frem nu:

1. **Teknisk gæld & fejlklasser.** `headend/main.py` er vokset til ~18.400 linjer, og samme fejlklasse (routere monteret uden auth) er dukket op tre gange (SEC-001, R15, R22). Uden et arkitektursnit fortsætter monoliten med at vokse, og hver ny session optimerer for "feature færdig i dag".
2. **Produktambition.** Produktet skal kunne løftes fra et rent timelapse-produkt til en generisk edge-platform, der også kan drive små vandværker, vindmøller, solceller m.m., med sikker remote access via edgen til bagvedliggende (OT-)backendsystemer.

Edge-laget er allerede delvist modulært (`edge/hal/`, `edge/config/`, `edge/tunnel/`, `edge/update/`, signeret config-hierarki, signerede OTA-artifacts), så snittet formaliserer en retning koden allerede halvt følger. Claude og Codex er nået frem til samme konklusion uafhængigt.

Beslutningen skal træffes **før** yderligere kodeflytning (P2-01), så refaktorering sker mod et aftalt mål frem for ad hoc.

---

## Beslutning

Vi indfører et eksplicit **Platform/Payload-snit** som den styrende arkitekturramme for edge-laget (og det tilsvarende domæne-snit på headend).

### 1. To lag med klart ejerskab

- **Platform-kerne (non-funktionel, genbrugelig, ét udviklingsspor):** identitet & enrollment, config/policy-hierarki, update/OTA, telemetri & observability (SIEM/CMDB/ITIM), remote access (tunnel + JIT/AccessTicket), HAL, sikkerhed & RBAC/GRC, storage/backup.
- **Payload (funktionel, udskiftelig, parallelt udviklingsspor):** domæne-drivere, domæne-QA, databehandling/AI, domæne-datamodel og domæne-UI-flader. I dag: kamera/timelapse (gphoto2/Nikon + billed-QA + AI-tagging). Fremtidige verticals: vandværk, vindmølle, solcelle.

**Afgrænsningstest:** et modul der ville se identisk ud for et vandværk som for et kamera er **platform**; ellers er det **payload**.

### 2. Koblingen er én kontrakt: `PayloadDriver` + capability manifest

Platform og payload kobles udelukkende gennem en versioneret kontrakt (normativ skitse — detaljer forfines i ADR-002):

```text
PayloadDriver (livscyklus, kaldt af platformen):
  configure(policy)            # signeret config fra platformens hierarki
  tick(now)                    # periodisk domænearbejde (capture/poll)
  collect_telemetry() -> dict  # standardiseret metrik → platformens SIEM/CMDB
  handle_command(cmd)          # fra remote access, gennem allowlist

Capability manifest (deklareres af payload, HÅNDHÆVES af platformen):
  - påkrævede hardware-capabilities (kamera / Modbus / GPIO ...)
  - resource quota (CPU, RAM, disk, netdata)
  - fil- & netværks-allowlist (least privilege)
  - egen service-identitet (payload-credential ≠ platform-credential)
  - health/rollback-kontrakt + versioneret payload-API (SemVer)
  - dataklassifikation (billeder vs. procesdata → GDPR/retention)
```

En payload leveres som **signeret pakke** med samme trust-model som de eksisterende OTA-artifacts, og loades bag manifest'ets quota + allowlist. En fejl i én payload må ikke kunne kompromittere kernen eller andre payloads.

### 3. Repo-model: monorepo nu, migrerbar til pakke senere

Vi starter som **monorepo (model A)** med skarpe pakkegrænser: `contracts/` (PayloadDriver + manifest-schema), `platform/`, `payloads/<navn>/`. Grænserne holdes så rene, at et senere skift til **model B** (platform publiceret som versioneret pakke via GitHub Packages, payloads som separate repos) er billigt, hvis/ når isolationsbehovet opstår.

### 4. Kontrakt-versionering = SemVer

`contracts/` versioneres semantisk. En breaking change i `PayloadDriver`/manifest = major bump = en bevidst, koordineret ændring på tværs af begge spor.

### 5. Navngivning: neutral fremad, additiv bagud

Nye platform-tabeller/-API bruger domæneneutrale ord (fx `asset`/`node` frem for `camera`). **Eksisterende `camera`/`capture`-kontrakter omdøbes IKKE bredt** — alt er additivt (ingen skema-brud før live-verifikation), i tråd med projektets grundprincip og Codex' review.

### 6. Sikkerhed indbygget, ikke bagpå

Capability manifest = least privilege fra dag 1. Remote access til en payload eller dens OT-backend går **altid** gennem platformens JIT/tunnel-model (break-glass/AccessTicket, R19) — aldrig ved at åbne indgående porte på OT-nettet. Tunnelen behandles som en bidirektionel management-conduit (Codex' skærpelse) med destinations-allowlist, kortlivede certifikater, session recording og kill switch.

### 7. Governance bliver bindende

Kontrollerne K1–K6 fra `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md` vedtages som arbejdsregler: automatisk route-auth-sweep (K1), ingen nye endpoints i `main.py` (K2), ratchet-gates i CI (K3), step-up på følsomme handlinger (K4), commit før deploy (K5), ADR-proces (K6).

---

## Amendments 2026-07-16 (efter Codex-review — accepteret af Claude, indarbejdet i beslutningen)

Codex' uafhængige review (HANDOVER 2026-07-16) rettede reelle svagheder i førsteudkastet. Alle seks amendments accepteres og er nu normativ del af ADR-001:

1. **Isolation er en enforcement-grænse, ikke bare en deklaration.** En in-process Python-`PayloadDriver` + manifest giver IKKE i sig selv CPU/RAM/disk/net/credential-isolation eller fault containment. Når ADR'en lover isolation, skal payloaden køre i en **separat OS-sandboxet proces/service** (eller tilsvarende enforcement boundary). Manifestet er *deklaration*; **platform-policy er autoritativ enforcement**.
2. **Control plane og data plane er separate, versionerede kontrakter.** Lifecycle/config/command/health (control) må ikke blandes med store billeder, video eller fremtidige OT-telemetristrømme (data). To kontrakter, hver sin SemVer.
3. **Fail-closed privilegie-tildeling.** Payloaden *deklarerer* behov men *tildeler* aldrig selv privilegier. Platformen validerer manifestet mod en **signeret allowlist/policy**, afviser ukendte capabilities **fail-closed**, og **logger** beslutningen.
4. **Failure contracts skal beskrives:** timeout, backpressure, crash/restart, degraded mode, resource exhaustion, kompatibilitetsmatrix (platform↔payload-versioner) og rollback ved defekt/inkompatibel payload.
5. **Konkrete trust boundaries/zoner/conduits.** Remote support og leverandøradgang kun via JIT/AccessTicket, kortlivede identiteter, destinations-allowlist, session-audit, revocation og kill switch (skærper §6 fra "indbygget" til normativt krav).
6. **Additiv, gate-styret migration** så den generiske platformvision ikke forsinker TimeLapse Pro production-readiness (jf. Codex' scope-punkt og §7 nedenfor).

**AI-domænesnit (Codex, accepteret):** kameraanalyse, billedtagging, Edge QA og Site Look tilhører **TimeLapse-payloaden**; AI til SIEM/CMDB/drift tilhører **platformen**. Ollama/Gemini/provider-adaptere kan være **fælles teknisk infrastruktur**, men prompt, dataklassifikation, adgang, retention og resultatejerskab ligger altid i det **kaldende domæne**. (Dette løser hvor "AI" hører hjemme: det er splittet efter formål, ikke ét modul.)

Med disse amendments blev ADR'en bekræftet af Codex og **accepteret af Peter 2026-07-16**.

## Alternativer overvejet

- **Status quo (fortsæt monolit).** Afvist: gælden vokser, fejlklasser gentages, og verticals ville kræve gaffelkopiering af hele kodebasen.
- **Fuld microservices/multi-repo nu.** Afvist: for tungt og for tidligt; ville forsinke TimeLapse Pro's production-readiness (Codex' scope-punkt) og indføre distribueret kompleksitet, før grænserne overhovedet har sat sig.
- **Plugin via dynamisk import uden manifest.** Afvist: giver ingen isolation eller least-privilege — en payload ville arve platformens fulde rettigheder, hvilket er uacceptabelt for OT-verticals og CRA/IEC 62443.
- **Valgt: monorepo + kontrakt + capability manifest, designet migrerbart.** Bedste balance mellem lav friktion nu og reel isolation/portabilitet senere.

---

## Konsekvenser

**Positive**
- Refaktoreringen af monoliten (P2-01) får et mål: udtræk sker mod `platform/`-moduler, ikke ad hoc — så gæld-nedbrydning og modularisering er samme arbejde og betaler sig hjem uanset verticals.
- Ny vertical kan bygges kun mod platform-API'et uden at røre kernen (bevises i plan-fase 4).
- Sikker remote access til backend/OT bliver en platform-egenskab, ikke noget hver vertical genopfinder.
- Klart parallelt ejerskab: kerne-spor og payload-spor kan udvikles samtidigt (CODEOWNERS, path-filtreret CI).

**Negative / omkostninger**
- Kontrakten (`contracts/`) er nu det dyre at ændre; kræver SemVer-disciplin og forhåndsinvestering.
- Et ekstra abstraktionslag (PayloadDriver) mellem platform og domænelogik.
- Kræver governance-modenhed (ADR'er, ratchet-gates) for ikke at skride.

**Neutrale**
- Ingen kodeflytning sker som følge af selve ADR'en; den sætter kun retningen. Første tekniske skridt (kontrakt-spike, wrap af kameralogik) besluttes/eksekveres separat.

---

## Standardmapping

- **SABSA:** styrker *Extensibility* og *Manageability*; payload-isolation understøtter *Integrity* og *Availability* (fejl indkapsles).
- **IEC 62443:** capability manifest = least privilege (SR 2.1); payload-isolation + conduit-kontrol = zone/conduit-model; tunnel som eksplicit management-conduit med enforcement point.
- **CRA:** secure-by-design (indbygget least privilege), signerede payload-pakker, SBOM pr. modul, uafhængig sårbarhedshåndtering pr. payload.
- **NIS2:** segmentering og adgangsstyring; klar afgrænsning mellem produktfunktion og privilegerede værktøjer.
- **GDPR:** dataklassifikation i manifest'et (billeddata vs. procesdata) driver retention/DPIA pr. payload — relevant fordi verticals har vidt forskellige dataklasser.

---

## Afgrænsning (ikke besluttet her)

- **Payload-pakkeformat, signerings- og loader-detaljer** (inkl. proces-sandbox-mekanisme fra amendment 1 og control/data-plane-kontrakterne fra amendment 2) → ADR-002.
- **Federation / flere prod-headends** (trust root, release-promotion, tenant ownership, revocation, SBOM/VEX-distribution) → senere ADR, når der er >1 prod-headend.
- **Multi-vendor trust-økosystem** (tredjeparts-leverandører der leverer signerede payloads/opdateringer + tidsbegrænset support): leverandøridentitet & certifikatlivscyklus, delegated signing med scope, kundegodkendelse, SBOM/VEX/licens, vulnerability disclosure, support-JIT, tenant-isolation, staging/promotion, revocation, liability og audit-evidens → **separat fremtidig ADR**. Grundprincip fastlagt her: **ingen leverandør arver platformens eller kundens fulde rettigheder.**
- **Konkret modul-udtræksrækkefølge og sprint-plan** → P2-01 + `Modularisering_Platform_Payload_Plan.md` §5 (ikke normativt i denne ADR).

**Langsigtet vision (kontekst, ikke besluttet her):** Peters mål er at kunne open-source en sikker platform for mindre OT-installationer (vandværk, solceller, vindinstallationer m.m.), der kombinerer beskyttelse og effektiv drift. Visionen udvikles gennem ADR'er og threat modelling — **ikke** gennem for tidlig generalisering af produktkoden. Open source reducerer ikke i sig selv risiko; secure-by-design og et dokumenteret trust-økosystem er forudsætninger.

---

## Opfølgning ved accept

1. Sæt status til `Accepted`, opdatér registeret i `ADR/README.md`, og tilføj en henvisning i `CLAUDE.md`/agent-instruktionerne, så alle sessioner er underlagt snittet.
2. GitHub-setup (lavt niveau, høj værdi): `CODEOWNERS` med `platform/` + `payloads/`, path-filtrerede CI-jobs, PR-skabelon der kræver ADR-reference ved arkitekturændringer.
3. Kontrakt-spike (plan-fase 1): definér `contracts/PayloadDriver` + manifest-schema og wrap den nuværende kameralogik bag den — dækket af `test_lab_tick_state_machine.py` — for at bevise at kontrakten passer på det vi allerede har, før noget flyttes.
4. Skriv ADR-002 (payload-pakkeformat + signering + proces-sandbox + control/data-plane-kontrakter) parallelt.

---

## Revisionslog

| Dato | Ændring | Af |
|---|---|---|
| 2026-07-15 | Førsteudkast (Proposed): platform/payload-snit, `PayloadDriver`+manifest, monorepo-model A, SemVer, additiv navngivning, K1–K6. | Claude |
| 2026-07-16 | Amendments indarbejdet efter Codex' uafhængige review: (1) proces-isolation som enforcement-grænse, (2) control/data-plane som separate kontrakter, (3) fail-closed capability-validering mod signeret allowlist, (4) failure contracts, (5) normativ JIT/conduit-kontrol, (6) additiv gate-styret migration; + AI-domænesnit; + multi-vendor trust som fremtidig ADR; + open-source OT-vision som kontekst. | Claude (efter Codex-review) |
| 2026-07-16 | Codex bekræftede at alle amendments var korrekt indarbejdet og anbefalede accept. **Status → Accepted af Peter.** Binding skrevet ind i `00_START_HER.md`. | Peter (beslutning) |
