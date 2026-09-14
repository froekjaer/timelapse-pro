# 16-Principle Governance Architecture & Impact Analysis (PR #240)

**Forfatter:** Claude Sonnet 5, 2026-09-14. **Status:** ANALYSE ALENE — intet implementeret, intet accepteret, ingen merge, ingen runtime-/netvaerks-/firewall-aendring, ingen GRC-migration koert, ingen §16-accept udfoert paa Peters vegne. Peter (og ChatGPT ved gennemgang) er beslutningsejer for enhver videre handling.

## 0. Repository/branch/SHA-tilstand ved gennemgang

Verificeret via `git fetch origin main` + `git fetch origin claude/capability-register-revision-2026-09-13` umiddelbart foer denne analyse blev paabegyndt:

| Reference | SHA |
|---|---|
| `origin/main` | `8452c5ef264d85823dce149a3bb371142d598569` |
| PR #240 branch (remote) | `814b52e854563898a824bbbdc9bd3d7f7bf07e5c` |
| Lokal worktree HEAD | `814b52e854563898a824bbbdc9bd3d7f7bf07e5c` |
| Peters citerede referencepunkt | `814b52e854563898a824bbbdc9bd3d7f7bf07e5c` |

**Ingen drift.** Alle fire matcher. PR #240's branch er en ren fast-forward af `origin/main` (bekraeftet `git merge-base HEAD origin/main` = `origin/main`s egen SHA). Denne analyse er skrevet OVEN PAA `814b52e8` som ny dokumentation, ikke en aendring af tidligere §5a/§5b/§16.3-indhold.

## 1. Autoritative eksisterende strukturer genfundet (search-before-create, §14/OP-001-praeceptivt)

Genfundet via tre parallelle, uafhaengige research-agenter, hver med eksplicit `git fetch origin main` + `git show origin/main:<path>` (ikke den delvist forældede lokale worktree — bekraeftet at `kind-shamir-29fe84`-worktreet er 255 commits bagud og selv MANGLER PR #240s egne filer, hvilket underbygger vigtigheden af den friskhedsdisciplin denne PR selv foreslaar).

### 1.1 `PAKKE_SPOR_REGISTER.md` (§14.6)
Fuldt laest, 223 linjer. Sektioner: "Aabne spor - fulde felter (§14.6)", "Rapporterede, ikke-verificerede lokale tilstande", "Reserverede/planlagte spor", "Backlog", "Hvordan du bruger dette register", "Faelles drift af registeret", "Ejerskab og aktivitet", "Partner- og kompetenceudvidelse", "Edge lokal shell-endpoint-sikkerhedsassessment", "Lifecycle-beslutning: ADR-004", "Edge shell-robusthed", "Governance-afslutning". **Ingen §16/§16a/§16b/§16c findes her endnu** — kun `(§14.6)` som reference til SAMARBEJDSMODEL. §16-forslaget i `CAPABILITY_REGISTER_FINAL_PROPOSAL` er korrekt positioneret som et FORSLAG til et nyt afsnit i SAMARBEJDSMODEL, ikke en duplikering af noget der allerede findes i PAKKE_SPOR_REGISTER.

### 1.2 OP-001 / operationelle loaders
`Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md` — vendoret verbatim fra `froekjaer/mission-framework` (commit `2db8c2ba`). Refereret fra `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` (manuel, da ChatGPT ikke autoloader repo-filer). **Step 5 (verbatim):** *"Search Before Create — Before creating a new: document; folder; repository structure; principle; protocol; term; architecture; template; identifier; verify that an equivalent or authoritative predecessor does not already exist. Creation is the final option, not the default first action."* Dette ER allerede den formelle, tvungne search-before-create-forpligtelse — §16.2 ("soeg efter problemet, ikke kun loesningens navn") er en PRAECISERING af OP-001 Step 5 for capability-specifikke aendringer, ikke en ny, konkurrerende regel.

### 1.3 `AGENTS.md` (delt med Kimi Code via samme fil)
5 nummererede punkter: (1) laes/foelg OP-001; (2) inspicer eksisterende filer/Git-tilstand mod HANDOVER_LOG, GRC-register, `Dokumentation/`-emnedokumenter, architecture-ratchet-testen, aabne PR'er/git-log; (3) search-before-create, stop naar autoritativ tilstand mangler; (4) post-aendrings-verifikation/tests; (5) kompakt preamble-status. Plus en "## Mandatory package / track reconciliation"-sektion der eksplicit citerer §14 og instruerer opdatering af `PAKKE_SPOR_REGISTER.md`. **`AGENTS.md` refererer allerede eksplicit til PAKKE_SPOR_REGISTER og search-before-create** — W1/W2-forslaget (nedenfor) er en UDVIDELSE af punkt 2/3, ikke en ny mekanisme.

### 1.4 Mission Framework-referencer i dette repo
`SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §15 ("Forslag til Mission Framework / Mission Platform — review-input", **Proposed, IKKE adopteret**), plus `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`/`CHATGPT-PROJECT-INSTRUCTIONS.md`, `mission-framework/README.md`, en raekke `Codex-Audit/*`-dokumenter, og en dedikeret `Dokumentation/Mission_Framework_Assessment/00_Collaborative_Intelligence_Evaluation_Protocol.md` (Proposed, 2026-07-22). "PROJECT_PRINCIPLES"/"human mandate" som eksakte termer: **nul hits** i `Dokumentation/` (de findes kun i selve det eksterne `mission-framework`-repo, ikke vendoret hertil endnu). "Decision authority"/"beslutningsmyndighed": kun i SAMARBEJDSMODEL §14/§15.

**Kritisk fund: SAMARBEJDSMODEL §15 er den naermeste eksisterende struktur for AI-autoritet/routing/mandat — men den er IKKE adopteret.** Den foreslaar allerede mandat/delegerings-/koordinations-/udfoerelses-/resultat-/genopretningslag og citerer Mission-Platform ADR-0002's "local decision authority over signed Action Requests." Dette er direkte relevant for Peters principper 14-16.

### 1.5 Korrektions-/provenance-konvention
**Eksisterer allerede som etableret PRAKSIS**, delvist som EKSPLICIT REGEL: HANDOVER_LOG's append-only, "KORREKTION"-maerkede entries (aldrig redigeret ind i original-entryen); PAKKE_SPOR_REGISTER's eksplicitte "Historisk korrektion: de tidligere X-tal er trukket tilbage som uafklaret population" moenster. Den naermeste EKSPLICITTE regel: SAMARBEJDSMODEL §14.4 ("Slet ikke audit trail, signerede artifacts i brug, rollbackkilder, idéer eller dokumenthistorik for at gøre listen pæn") og §14.6 ("aldrig 'vores version vinder' — flet begge sessioners oplysninger"), plus OP-001 Rule 6 ("Preserve historical evidence and continuity"). **Peters princip 13 er derfor allerede en normativ regel i dette repo — ikke en ny opfindelse — men den er spredt over tre kilder (§14.4, §14.6, OP-001 R6) uden ét samlet, navngivet sted.**

### 1.6 GRC-databasemodel (fuldt skema)
`grc_items` (BIGSERIAL, `item_type CHECK IN ('requirement','control','risk','test','finding','action')`, `external_id`, `title`, `description`, `status`, `priority`, `owner`, `due_at`, `source`, `scope JSONB`, `attributes JSONB`, `version`, audit-felter). `grc_links` (`source_item_id`/`target_item_id` — BEGGE NOT NULL FK til `grc_items.id`, `relationship` fri streng). `grc_test_runs` (FK til `grc_items`, `environment`, `result`, tidsstempler). `grc_evidence` (FK til `grc_items` ELLER `grc_test_runs`, `evidence_type`, `uri`, `sha256`, `retention_class`). `grc_documents`/`grc_document_revisions`/`grc_document_item_links` (versionerede, godkendte dokumenter genereret FRA grc_items). `grc_comments` (append-only).

**Bekraeftet, stadig aktuelt: duplikeret CHECK-constraint.** `headend/database.py:1368-1371` definerer sin EGEN `ck_grc_items_type`-constraint, uafhaengig af migrationsfilen — i dag identiske (6 vaerdier), men to steder der skal aendres sammen.

**Bekraeftet: ingen generisk CRUD for `grc_links`/`grc_evidence`.** Kun ét hardkodet link oprettes nogensinde (bootstrap-endpointet). `grc_evidence` har en create-endpoint, men INGEN GET/list-endpoint.

**Bekraeftet: `ITEM_TYPES = {"requirement","control","risk","test","finding","action"}`** i `headend/api/grc_register_api.py:25`. Aggregering er simple `COUNT`/`GROUP BY` — ingen procent-score.

### 1.7 Compliance Cockpit (`CompliancePage.tsx`, 1219 linjer)
**Ingen COMPLIANT/PARTIAL/NON_COMPLIANT-enum eksisterer noget sted.** `statusClass()`-kortet daekker kun operationelle tags (`pass, warning, fail, critical, high, medium, low, verified, implemented, open, blocked, rejected, in_progress, candidate_review, draft, approved, not_run`). `GrcItem.status` er en fri TypeScript `string`, ikke et union-type. Repo-bred soegning efter "compliant" (case-insensitive): 3 urelaterede hits, INGEN reelt compliance-status-begreb.

**Praecisering af en fejlagtig antagelse i mandatet:** strengen "Regler & Standarder" findes IKKE i repoet (nul hits). Den faktiske UI-tekst er **"Regler og standarder"** (dansk "og", ikke et og-tegn). Dette aendrer intet materielt, men er noteret for praecision.

Faner: register, reports, grc (risk), **regulatory** ("Regler og standarder"), approvals, controls, evidence. Scope-filtrering (`customer`/`site`/`camera`) findes kun som VISNING (targets-chips), ikke som forespoergsels-filter. Temporal/effective-date findes KUN paa `RegulatoryInstrument` (`effective_from`, `next_deadline`) — IKKE paa `GrcRegisterItem`/`GrcDocument`/`GrcComment`. `requirement_type` (binary/risk-based/hybrid): **nul hits**. `NOT_APPLICABLE`/`NOT ASSESSED`/`effective_date` (som eksakt term paa GRC-niveau): **nul hits**.

**Kritisk fund: `compliance_intelligence.py`'s statiske `INSTRUMENTS`-liste (~29 lovkrav, med `effective_from`/`next_deadline`) er FULDSTAENDIG UKOBLET fra det levende GRC-register.** Den mountes som sin egen router; intet i `grc_register_api.py` eller databasen refererer den. Det er et statisk, hardkodet Python-katalog, ikke en del af capability-/compliance-datamodellen.

### 1.8 Config-override-lagdeling (customer/site/device)
Bekraeftet, uaendret: 6-lags-kaede (hardkodet literal < ConfigDefaults/"Global Config" < device_config < customer < site < camera), implementeret i `headend/main.py::get_config()` (linje ~3560-3880). Separat, analog 4-lags-kaede for `bt_totp` specifikt. **Denne lagdeling er fuldstaendig ORTOGONAL til GRC-skemaet** — `grc_items.scope` (JSONB fri-form) er ikke koblet til denne hierarki-mekanisme.

### 1.9 AI/model/provider/routing/quota/budget
**Bekraeftet, to uafhaengige soegemetoder: INGEN IMPLEMENTERET, generisk AI-routing-/autonomi-MASKINE eksisterer i kode.** `git grep -iE "autonomy|participant|model_provider|ai_agent|quota|budget|routing"` i `headend/`: nul hits paa alle undtagen "routing" (kun én urelateret docstring). Filnavnet `headend/ai/ai_router.py` er MISVISENDE — det er en billedanalyse-pipeline-orkestrator (Ollama vision, tag-repository, GDPR, SIEM, CMDB), IKKE en AI-model-/udbyder-routing-/tillidsmekanisme. **Vigtig navnekollision at undgaa i videre arbejde: dette er ikke det samme som "AI routing" i Peters princip 15's forstand.**

**RETTELSE (fundet ved adversarial review, 2026-09-14, uafhaengigt genverificeret — filen findes):** ovenstaaende daekker kun IMPLEMENTERET kode. Et eksisterende DOKUMENTATIONS-NIVEAU forslag findes allerede: `Dokumentation/AI_KOMPETENCER_OG_OPGAVEROUTING.md` (2026-09-13, status "forslag til afproevning", forfattet af Codex efter Peters instruktion). Dette er IKKE implementeret arkitektur — dokumentet siger selv eksplicit: *"Dette er et designforslag, ikke en paastand om eksisterende funktionalitet"* og *"Ingen af disse loesninger er installeret eller tilkoblet Headend her."* Det er en TYND, lokal, forbruger-side reference/forslag, ikke en generisk platform. Indhold, bekraeftet ved fuld laesning: kompetencebaseret deltager-routing (§2's kompetencetabel for Codex/ChatGPT/Claude/Kimi/Z.ai/Gemini/DeepSeek/Grok/Copilot); budgetbevidsthed (§4.3, eksplicit haandhaevet loft, "kvalitets- eller sikkerhedskrav saenkes ikke tavst" ved utilstraekkeligt budget); én tydelig primaer udfoerer pr. opgave (§4.4, "Standardforslag: hoejst ét rettelsesforsoeg foer eskalering"); uafhaengig review baseret paa risiko, ikke automatisk (§4.5, "Auth, opdateringer, migration, backup/recovery og andre vaesentlige tillidsgraenser kraever uafhaengig kontrol"); og en EKSPLICIT AFVISNING af en implementeret lokal router til fordel for integration med den eksisterende `mission-metamodel` (§6, "Integrér med den eksisterende mission-metamodel, frem for en konkurrerende Mission Core. En router maa foreslaa en udfoerer, men maa ikke give sig selv adgang eller udvide mandatet").

**Arkitektonisk afvejning identificeret ved review (holdes DECISION REQUIRED, ikke afgjort her):** at insistere paa at al generisk routing/autonomi skal bygges OPSTROEMS foerst (§7/§2 nedenfor) risikerer en afhaengigheds-/dødvande-situation, da SAMARBEJDSMODEL §15 og Mission Platforms tilsvarende lag fortsat er Proposed/ufaerdige. `AI_KOMPETENCER_OG_OPGAVEROUTING.md`s egen anbefalede raekkefoelge (§5: "manuel, dokumenteret opgavefordeling -> lille kontrolleret maaling -> eventuel API-router") peger allerede paa at Mission Frameworks eget princip om vertikal laering ("Solar Eclipse... foerste referenceimplementering" — se dokumentets §6/§8) kan retfaerdiggoere et TYNDT, lokalt TimeLapse-PROTOTYPE-/forbrugsniveau, netop for at validere den generiske model empirisk, i stedet for at vente paa at den er faerdigdesignet i abstrakt form foerst. **Denne analyse tager IKKE stilling til om det er den rigtige vej — kun at begge veje (ren opstroems-foerst vs. tynd lokal validering) er reelle, gyldige arkitektoniske muligheder, og at valget er Peters, ikke noget denne analyse forudsaetter.**

### 1.10 UI_USECASE_CATALOG — linking
294 linjer, uaendret. **Bekraeftet, to uafhaengige soegemetoder: INGEN UC-*-ID refereres noget andet sted i repoet** (hverken GRC, tests, eller anden kode/dokumentation). Kataloget er et fritstaaende dokument uden nogen maskinel kobling til noget som helst.

### 1.11 MENUGUIDE-dokumenter
Organiseret strengt efter side/rute, udledt af UI-koden. Ingen UC-*-ID'er, ingen GRC-krav-ID'er — kun ren prosa-beskrivelse af `/compliance`-siden ét sted.

### 1.12 Architecture ratchet
`tests/architecture_baseline.json`: `{"headend_main_max_lines": 17550, "headend_main_max_direct_routes": 213}`. Mekanismen er en RENT MONOTON STOERRELSESLOFT paa `headend/main.py` (linjeantal + route-decorator-antal) — haandhaever INTET om arkitektonisk semantik, lagdeling, eller nogen anden fil. Kan ikke direkte genbruges til at haandhaeve §16's capability-invarianter; er kun relevant som PRAECEDENS for at "ratchets" som mekanisme allerede findes i repoet.

### 1.13 Deployment-sundhed/canary/flapping
**"canary", "health_gate", "flapping", "alerting": reelt nul hits** (ét "canary"-hit var en urelateret testkommentar). **"postflight" findes, men KUN for Headend-lokale brew-pakkeopdateringer** (certbot/ollama/ffmpeg) — ikke edge-enheder, ikke flaade-bred udrulning.

**RETTELSE (fundet ved adversarial review, 2026-09-14, uafhaengigt genverificeret og korrekt):** paastanden om at "restart_count" gav nul hits var forkert. `NRestarts`-DATAINDSAMLING eksisterer allerede som en aktiv, brugt primitiv: `edge/diagnostics/collector.py::_service_restarts()` (linje 290-302, `systemctl show timelapse-edge --property=NRestarts`, inkluderet i diagnostics-outputtet som `result["service_restarts"]`), `edge/service_operations.py::_service_state()` (linje 563, henter `NRestarts` som del af en generisk service-status-snapshot), og `edge/tools/bootstrap_cli.py:1467` (samme moenster). **Bekraeftet, praecis skelnen bevaret:** dette er REN INDSAMLING/RAPPORTERING paa forespoergsel — ingen af de tre steder sammenligner vaerdien mod en taerskel, eskalerer, eller alarmerer. `git grep "NRestarts" origin/main -- headend/` giver **nul hits** — Headend (flaadesiden) modtager/aggregerer aldrig denne vaerdi. Hullet er derfor IKKE "indsaml genstart-information fra bunden" — det er den passende overvaagnings-/forbruger-/eskaleringsmaskine og dens integration med den allerede-eksisterende indsamlingsprimitiv.

**Vigtigt, delvist REUSE-bart fund: `edge/update_lifecycle.py` implementerer allerede en reel post-restart-sundhedsport med timeout-baseret auto-rollback** for edge-app-opdateringer — tilstandsmaskine `awaiting_restart_health -> health_confirmed`, eller efter `health_timeout_s` (default 180s) automatisk `rolled_back_by_guard`. Dette er en FUNGERENDE "deployed-men-ikke-sund"-port — men afgraenset til ÉN enheds egen app-opdatering, ikke flaadesundhed, canary-kohorter, eller vedvarende service-flapping. **Ingen restart-loop-/crash-loop-DETEKTION (taerskel/alarm) findes noget sted** — hverken i `edge/agent.py` eller `headend/services/` — men den RAA datakilde (`NRestarts`) findes allerede og kan genbruges som input.

### 1.14 Temporal/effective-date
Kun `compliance_intelligence.py`'s ukoblede statiske katalog (se 1.7). Ingen GRC-krav-post har nogensinde en `effective_date`/`deadline`-kolonne.

### 1.15 Aeldre kravregistre
`Dokumentation/KRAVREGISTER_og_STATUS_v10.md` (275 linjer, 2026-07-07) — egen `CAP-*`/`ADM-*`-ID-skema, adskilt fra baade GRC-ID'er og UC-*-usecase-ID'er, refererer kun GRC beskrivende. Tre AELDRE, eksplicit arkiverede forgaengere findes under `Dokumentation/Gamle versioner/`. v10 er ~6 uger AELDRE end usecase-kataloget og har INGEN koblet relation til GRC, usecase-ID'er, eller `compliance_intelligence.py`.


## 2. Kortlaegning af Peters 16 principper til arkitekturlag

Ingen af de 16 principper antages at hoere hjemme i kun ét lag. Adskillelse: **normativ kilde** (hvor princippet i sin generelle form BOR forankres) vs. **TimeLapse-implementering** (den konkrete mekanisme i dette repo) vs. **Mission Platform** (generisk, tvaergaaende teknisk maskineri) vs. **Collaborative Intelligence** (samarbejdsmodel-laget).

| # | Princip (kort) | Normativ kilde | TimeLapse Pro | Mission Platform | Collaborative Intelligence |
|---|---|---|---|---|---|
| 1 | Capability preservation | Mission Framework (Provenance/Evidence-linje) | **EXTEND**: GRC `item_type='capability'` + §16.4/16.5 (allerede designet) | — | — |
| 2 | Mandatory governance wiring | Mission Framework (OP-001 Step 5 er allerede dette princip) | **EXTEND**: W1/W2 i AGENTS.md/CLAUDE.md/GEMINI.md/CHATGPT-instructions (punkt 2/3 udvides, ikke ny mekanisme) | — | — |
| 3 | End-to-end traceability | Mission Framework ("Provenance Matters"-linje) | **EXTEND**: GRC-link-design (skal rettes, se §1.6/§6 nedenfor) + usecase-kobling | — | — |
| 4 | Evidence before confidence | Mission Framework (allerede TRUST.md/"Evidence over Assumptions" — ikke vendoret som fil hertil endnu, kun anvendt via praksis) | REUSE af `grc_evidence.collected_at`/`uri`/`sha256`; §16.6/16.7 (allerede designet) praeciserer anvendelsen for capability-soegninger specifikt | — | — |
| 5 | Runtime outcome over process completion | Mission Framework/Collaborative Intelligence ("Reality before Models"-disciplin, allerede anvendt i dette repos OS-update-haendelseshistorik) | **REUSE + EXTEND**: `edge/update_lifecycle.py`s post-restart-sundhedsport ER allerede en fungerende instans af dette princip for ÉN kapabilitet (app-opdatering); §16.9 (allerede core, korrekt placeret per Peters afklaring) generaliserer det | — | — |
| 6 | Risk-/situationsbaseret drift (ingen universelle regler) | Mission Framework (beslutningsfilosofi) | Anvendes som en SKRIVEMAADE-begraensning paa §16c's formulering (allerede korrigeret af Peter vaek fra varighedsbaseret) — ingen selvstaendig datastruktur | — | — |
| 7 | Resilience/recovery by default | Mission Framework (kontinuitetsprincipper) | **REUSE**: Edge Management Reachability-invarianten (allerede godkendt, uaendret bevaret) + `update_lifecycle.py`s default-rollback | — | — |
| 8 | Monitoring proportional til impact | Mission Framework (risikobaseret, afloeser varighedsbaseret) | **NY (genuinely missing)**: intet flaade-/risikobaseret alarmeringslag eksisterer (§1.13) | Muligt fremtidigt generisk primitiv hvis andre projekter faar samme behov — IKKE nu | — |
| 9 | Compliance Cockpit er baseline | TimeLapse-produktbeslutning, forankret i Mission Framework-evidensprincipper | **EXTEND**: `CompliancePage.tsx`/GRC — konkret produktfunktion | Kandidat til fremtidig generisk "compliance cockpit"-Mission-Platform-komponent — IKKE nu | — |
| 10 | Komplet compliance-regnskab | Mission Framework ("Unknown is Better than Wrong") | **NY/EXTEND**: intet COMPLIANT/PARTIAL/NON_COMPLIANT/NOT_ASSESSED/NOT_APPLICABLE-vokabular eksisterer (§1.7) | — | — |
| 11 | Compliance er temporal/scoped | Mission Framework (evidens-tidsstempling) | **EXTEND**: kobl `compliance_intelligence.py` til levende GRC-poster ELLER tilfoej `effective_date`/scope-forespoergsel direkte paa `grc_items` | — | — |
| 12 | Aendringer trigger forklarlig impact-analyse | Mission Framework (evidensbaseret beslutningsstoette, ikke automatisk sandhed) | Minimal **EXTEND**: genbrug `grc_links` til at liste tilknyttede poster ved aendring | **Kandidat til generisk Mission-Platform-impact-analyse-motor** — dette er i sit fulde omfang en tvaergaaende orkestreringsopgave, ikke TimeLapse-specifik | — |
| 13 | Bevar evidens og uenighed (ingen historik-omskrivning) | Mission Framework (OP-001 Rule 6) + allerede-accepteret SAMARBEJDSMODEL §14.4/14.6 | **REUSE** — praksis eksisterer allerede og er demonstreret korrekt anvendt i denne PR selv (§5a's Pi-hole-korrektion) | — | — |
| 14 | Eksplicit, udviklende menneske/AI-autoritet | **Mission Framework/Collaborative Intelligence** (cross-project, IKKE TimeLapse-specifik) | Forbruger af en fremtidig autoritetsmodel — bygger IKKE sin egen | — | SAMARBEJDSMODEL §15 (Proposed, IKKE adopteret) er den naturlige hjemmebase — **skal formentlig faerdiggoeres her, ikke genopfindes** |
| 15 | Evidensbaseret AI-valg og laering (routing) | **Mission Platform** (Peters egen lagbeskrivelse naevner "participant registry, routing, quotas, budget, mandate, autonomy" — noejagtig SAMARBEJDSMODEL §15's ordforraad) | Forbruger, ikke bygger, af en GENERISK motor — men RETTET: `Dokumentation/AI_KOMPETENCER_OG_OPGAVEROUTING.md` er allerede et eksisterende, tyndt, lokalt DOKUMENTFORSLAG (ikke implementeret kode), se §1.9/§7 | **JA — dette er kernen af Mission Platform-laget per definition, for den GENERISKE motor** | Selektionsprincipperne (komplementaere kompetencer, laering af udfald) hoerer her; se §1.9 for afvejningen om en tynd lokal prototype foer opstroems er faerdig |
| 16 | Eksplicit ejerskab, undtagelser, overrides | Mission Framework ("Humans Remain Accountable", nu udvidet til situationel AI-autoritet) | **REUSE** (config-override-lagdeling, allerede implementeret, se §1.8) for customer/site/device-overrides; **EXTEND** for GRC-niveau ejerskab/mandat-felter (findes ikke i dag — se §6); §16.3 (allerede tilfoejet i forrige revision) daekker agent-selv-accept-bypasset konkret | Mandat-transfer-sporbarhed (autoritet flyttet fra ét AI/menneske til et andet) hoerer naturligt i Mission Platforms participant-registry naar den findes | — |

**Vigtigste strukturelle konklusion:** principperne 14 og 15 er de eneste to der IKKE boer implementeres som TimeLapse-specifik arkitektur — de er per Peters egen lagdefinition kernen af hhv. Collaborative Intelligence (menneske/AI-autoritetsmodel) og Mission Platform (AI-routing/tillid/autonomi). At bygge disse lokalt i TimeLapse ville skabe en konkurrerende, TimeLapse-laast version af noget der eksplicit er tiltaenkt som tvaergaaende. Dette flages som et af de klareste "IKKE her"-punkter i §J.20.


## 3. §16/§16a/§16b/§16c-placering

Nuvaerende udkast (i `CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` paa `814b52e8`) er allerede tekstuelt godt afstemt med Peters intention. Analysen nedenfor bekraefter placeringen og navngiver PRAECISE, ENDNU IKKE ANVENDTE formuleringsjusteringer for §16b/§16c som Peter selv har afklaret i dette mandat — disse er **anbefalinger til en fremtidig revision, ikke anvendt i denne analyse-only-fase**.

- **§16 core (16.1-16.9):** korrekt daekker capability-preservation + obligatorisk capability-bevidst aendrings-/dispositionsstyring. 16.9 (runtime-sundhed som fuldfoerelseskriterium) er KORREKT placeret som core, ikke §16c, per Peters eksplicitte instruks ("Observed post-change health is already a core requirement. Do not move that entirely into optional §16c"). §16.3 daekker allerede self-accept-bypasset (tilfoejet forrige revision).
- **§16a (drift-modstandsdygtige invarianter):** uaendret korrekt — daekker haandholdte lister/konstanter (release-artifact-sagen).
- **§16b (manuelle/operationelle handlinger) — ANBEFALET PRAECISERING, IKKE ANVENDT:** nuvaerende ordlyd ("automatiserede leveranceflow daekkes af 16.1; rene manuelle data-operationer forbliver i §16b") mangler eksplicit Peters nye "kun ved POTENTIEL MATERIEL PAAVIRKNING"-kvalifikator. Anbefalet tilfoejelse til en fremtidig revision: *"§16b's dokumentationskrav udloeses kun naar en manuel/ad hoc operationel handling har potentiel materiel paavirkning paa en capabilitys eksistens, data, eller recovery-egenskab (Travbyen-klassen)."* **RETTELSE (fundet ved adversarial review, 2026-09-14):** en tidligere version af denne anbefaling naevnte "triviel, reversibel, daglig drift" som eksempel paa hvad der IKKE udloeser §16b — men "reversibel" maa ALDRIG staa som en selvstaendig, uafhaengig undtagelse fra materiel-paavirkning-kriteriet. En handling kan vaere teknisk reversibel og STADIG have materiel paavirkning (Travbyen ER netop dette: en "reversibel" (rekonstruerbar) sletning, der alligevel var den reelle regressionssag, fordi capabilityen — synlige kameralokationer — faktisk gik tabt i mellemtiden). Ordinaer, lavrisiko, let-reversibel aktivitet KAN vaere et EKSEMPEL paa triviel drift, men reversibilitet maa aldrig i sig selv overtrumfe materiel-paavirkning-kriteriet. Dette forhindrer at §16b paalaegger fuld governance paa ubetydelige handlinger, som Peter eksplicit bad om at undgaa — uden at aabne en "det var jo reversibelt"-smuthul.
- **§16c (runtime-alarmering) — ANBEFALET PRAECISERING, IKKE ANVENDT:** nuvaerende ordlyd ("vedvarende fejlsignaler... skal rejse en synlig alarm") mangler eksplicit Peters "risiko-/impact-baseret, ikke varighedsbaseret"-afklaring. Anbefalet tilfoejelse: *"Udloesningskriteriet for §16c er FORVENTET KONSEKVENS/RISIKO ved fejlen, ikke fejlens varighed — en kortvarig fejl med potentielt kritisk konsekvens kraever oejeblikkelig detektion/alarm; en langvarig fejl med lav konsekvens kraever det ikke noedvendigvis paa samme maade. §16c maa IKKE kodificere en fast 'X minutter foer alarm'-taerskel som det styrende kriterium."*
- **Runtime-verifikation vs. loebende overvaagning — allerede korrekt adskilt i konceptet, boer gengives eksplicit i teksten:** §16.9 (fuldfoerelseskrav, core, obligatorisk) er en ANDEN ting end §16c (loebende, risikobaseret overvaagning/alarmering, valgfri udvidelse). Denne analyse bekraefter at denne adskillelse allerede findes konceptuelt (jf. z.ais note i §3 om test-fejlklasser) men anbefaler at §16's egen tekst eksplicit siger dette i én saetning, saa en fremtidig laeser ikke fejlagtigt tror 16.9 er en del af (og dermed valgfri via) §16c.

## 4. W1/W2 obligatorisk wiring-plan (bekraeftelse mod eksisterende struktur)

Det allerede foreslaaede W1 (`AGENTS.md`/soesterloaders punkt 3-udvidelse) og W2 (OP-001 Step 5-tilfoejelse) er **korrekt identificeret som de to steder alle agenter allerede tvinges igennem** (bekraeftet af research: `AGENTS.md` punkt 1 kraever laesning af OP-001; punkt 2/3 kraever allerede search-before-create/PAKKE_SPOR-tjek). W1/W2 er dermed en PRAECISERING af eksisterende, allerede-bindende punkter, ikke et nyt haandhaevelseslag. Dette er en **EXTEND**, ikke en NY struktur.

**Ét nyt, konkret fund fra denne analyse:** `CHATGPT-PROJECT-INSTRUCTIONS.md` er MANUEL (ChatGPT autoloader ikke repo-filer) — W1/W2's forslag om at opdatere "søster-loaders" skal derfor eksplicit huske at dette dokument kraever en MANUEL synkronisering hver gang, ikke en automatisk. Dette er en implementerings-detalje for en senere fase, ikke noget der aendrer selve arkitekturen.

## 5. GRC-datamodel-impact (minimum noedvendige relationer)

Kortlaegning af Peters efterspurgte begreber (25 konkrete raekker nedenfor — se korrektionsnote efter tabellen for den praecise optaelling) mod eksisterende GRC-skema. **REUSE/EXTEND/NEW klassificeret konservativt — NEW kun hvor intet genbrugeligt findes:**

| Begreb | Status | Begrundelse |
|---|---|---|
| Capability | **EXTEND** | Ny `item_type='capability'`-vaerdi paa eksisterende `grc_items` |
| Invariant | **EXTEND** | `grc_items.attributes` (JSONB, allerede fri-form) — ingen ny kolonne noedvendig |
| Usecase | **EXTEND (design-rettelse noedvendig)** | Enten en ny `grc_items`-raekke pr. usecase (kraever at usecase-ID'er faar en `grc_items.external_id`), ELLER en direkte reference i `attributes`. Det TIDLIGERE forslag om at linke usecases via `grc_evidence` er SKEMATISK UGYLDIGT (bekraeftet igen: `grc_links` kraever begge sider som `grc_items.id`; `grc_evidence` har sit eget PK-rum) — denne fejl SKAL rettes foer implementering, uanset hvilken af de to loesninger vaelges |
| Implementeringsreference | **REUSE** | `grc_items.source`/`attributes` daekker dette allerede |
| Krav/kontrol | **REUSE** | `item_type IN ('requirement','control')` findes allerede |
| Anvendelighed (applicability) | **NEW** | Findes reelt kun paa `compliance_intelligence.py`s ukoblede statiske katalog (`RegulatoryInstrument.applicability`, kun UI-visning) — ingen kolonne paa `grc_items` |
| Scope | **REUSE (delvist)** | `grc_items.scope JSONB` findes allerede, men er IKKE koblet til config-override-lagdelingen (customer/site/device) — kraever en bevidst beslutning om hvorvidt den skal vaere det |
| Compliance-status | **NEW** | Intet COMPLIANT/PARTIAL/NON_COMPLIANT/NOT_ASSESSED/NOT_APPLICABLE-vokabular eksisterer noget sted (bekraeftet, §1.7) |
| Evidens | **REUSE** | `grc_evidence` daekker dette allerede grundlaeggende |
| Evidens-provenance | **REUSE (delvist)** | `collected_by`/`collected_at`/`uri`/`sha256` findes; `source`/`method`-adskillelse (Peters "kilde, tid, omfang, metode") er delvist daekket — `method` mangler som eksplicit felt, kan formentlig ligge i `content JSONB` uden skemaaendring |
| Evidens-friskhed/udloeb | **EXTEND** | `retention_class` findes som fri streng, men INGEN haandhaevet udloebs-/friskhedslogik er fundet knyttet til den |
| Runtime-status | **NEW** | Intet felt paa `grc_items` repraesenterer "observeret koerende tilstand" adskilt fra dokumentstatus — `edge/update_lifecycle.py`s tilstandsmaskine er det naermeste, men er ikke GRC-koblet |
| Risiko | **REUSE** | `item_type='risk'` findes allerede |
| Risiko-ejer | **EXTEND** | `grc_items.owner` findes (fri streng, ikke rolletypet) — ingen skelnen mellem menneske-ejer og AI-ejer-med-dokumenteret-mandat |
| Beslutningsejer | **EXTEND** | Samme som ovenfor — `owner`-feltet er for gennemsigtigt/utypet til Peters princip 16's krav om sporbar mandat-overfoersel |
| Override | **NEW (paa GRC-niveau)** | Config-override-lagdelingen (customer/site/device) er REUSE for DEN mekanisme, men en GRC-registreret "bevidst accepteret undtagelse for capability X paa scope Y"-post findes ikke som egen struktur i dag |
| Effective date/betingelse | **NEW** | Bekraeftet nul hits paa `grc_items`; findes kun paa det ukoblede `compliance_intelligence.py`-katalog |
| Fremtidigt krav | **NEW** | Samme begraensning som ovenfor |
| Korrektion/supersession | **EXTEND** | Praksis findes (§1.5), men INGEN `grc_items.status='superseded'`/`superseded_by`-felt haandhaever det strukturelt — se Fejlklasse-valideringens Pi-hole-sag (§8) for hvorfor dette er en reel, ikke kun teoretisk, mangel |
| Remediation | **REUSE** | `grc_links` med `relationship='remediated_by'` bruges allerede (set i bootstrap-seed-data) |
| Lukning/genaabning | **EXTEND** | `status`-feltet findes, men ingen eksplicit "reopen paa ny evidens"-arbejdsgang/felt er fundet i API'et |
| AI/model/version-identitet | **NEW, men UPSTREAM** *(rettet, se nedenfor)* | Intet implementeret fundet (§1.9); et tyndt lokalt dokumentforslag findes (§1.9-rettelse), men selve identitets-DATAMODELLEN hoerer til den samme opstroems-struktur som autoritet/routing, ikke en isoleret TimeLapse-kolonne |
| AI opgave-egnethed/performance-evidens | **NEW, men UPSTREAM** *(rettet, se nedenfor)* | Intet implementeret fundet — konceptet (kompetencekort, maalt foerste-gangs-accept mv.) er allerede SKITSERET i `AI_KOMPETENCER_OG_OPGAVEROUTING.md` §3, men som et dokumentforslag, ikke en GRC-struktur; hoerer til Mission Platform (§7) |
| AI-autoritet/autonomi | **NEW, men UPSTREAM** | Hoerer til Mission Platform/Collaborative Intelligence, ikke en TimeLapse GRC-kolonne |
| Routing-beslutning/begrundelse | **NEW, men UPSTREAM** | Samme |

**KORREKTION (fundet ved adversarial review, 2026-09-14 — genoptalt fra selve tabellen, ikke justeret for at ramme de gamle totaler):** tabellen har **25 raekker, ikke 24** som tidligere anfoert. Genoptaelling af de faktiske klassifikationer ovenfor:
- **REUSE (7 raekker: 5 uden forbehold + 2 "delvist"):** Implementeringsreference, Krav/kontrol, Evidens, Risiko, Remediation (uden forbehold); Scope, Evidens-provenance (delvist).
- **EXTEND (8 raekker):** Capability, Invariant, Usecase, Evidens-friskhed/udloeb, Risiko-ejer, Beslutningsejer, Korrektion/supersession, Lukning/genaabning.
- **NEW, lokalt relevant (6 raekker — disse HOERER i TimeLapse):** Anvendelighed (applicability), Compliance-status, Runtime-status, Override (paa GRC-niveau), Effective date/betingelse, Fremtidigt krav. *(Runtime-status var tidligere fejlagtigt udeladt af denne opsummering, selvom den korrekt stod som NEW i tabellen — rettet. Effective-date og Fremtidigt-krav var tidligere fejlagtigt slaaet sammen til ét punkt — rettet til to separate.)*
- **NEW, men UPSTREAM (4 raekker):** AI/model/version-identitet, AI opgave-egnethed/performance-evidens, AI-autoritet/autonomi, Routing-beslutning/begrundelse. *(De to foerste var tidligere kun mærket "NEW" uden UPSTREAM-taggen i selve tabellen, selvom opsummeringsprosaen allerede antog at alle fire AI-relaterede punkter var UPSTREAM — denne uoverensstemmelse er nu rettet ved at give alle fire raekker samme, korrekte UPSTREAM-klassifikation, konsistent med §2 og §7's egen analyse, IKKE ved at aendre totalerne kunstigt.)*

7 + 8 + 6 + 4 = **25**, matcher det faktiske antal raekker.

**Nyttig eksisterende skema-praecedens for korrektion/supersession** (relevant for "Korrektion/supersession"-raekken ovenfor): `customer_risk_profiles`-tabellen (`headend/migrations/v21_customer_risk_profiles.sql`, `database.py:1065`) har allerede `CHECK (status IN ('submitted','validated','rejected','superseded'))` — dvs. `'superseded'` findes allerede som en gyldig statusvaerdi ANDETSTEDS i skemaet. Dette betyder IKKE at `grc_items` allerede understoetter korrektion/supersession — det goer den ikke, bekraeftet — men det er nyttig praecedens at genbruge MOeNSTERET (en `status`-vaerdi plus et `superseded_by`-lignende felt) fremfor at designe noget parallelt og inkonsistent, naar/hvis dette implementeres.

## 6. Compliance Cockpit — delta mellem nuvaerende og godkendt intention

Peter har udvidet Cockpittets tiltaenkte rolle betydeligt. Status pr. punkt (Peters liste G.1-23):

**Allerede daekket (REUSE):** drill-down til krav/kontrol/scope/evidens (bekraeftet UI-mekanisme findes); faner for register/reports/grc/regulatory/approvals/controls/evidence.

**Delvist daekket, kraever EXTEND:** scope-specifik status (findes kun som VISNING, ikke forespoergsel/filter); kilde-tekst for lovkrav (findes i `compliance_intelligence.py`s statiske katalog, men UKOBLET fra levende status); temporal/fremtidig tilstand (samme — kun paa det statiske katalog).

**Ikke fundet, kraever NEW:** krav-type (binaer/risikobaseret/hybrid — nul hits); eksplicit status for ALLE identificerede krav (intet COMPLIANT/PARTIAL/NON-COMPLIANT/UNKNOWN/NOT-APPLICABLE-vokabular eksisterer, kun ad hoc operationelle tags); evidensbaseret COMPLIANT-haandhaevelse (ingen mekanisme forhindrer i dag at et krav markeres "opfyldt" uden evidens, da der slet ikke findes et formelt "opfyldt"-begreb endnu); aggregering der ikke skjuler undtagelser (ingen aggregeringslogik overhovedet ud over simple COUNT'er — hverken god eller daarlig endnu, blot ikke-eksisterende); kommende krav/deadlines synlige FOER effective date paa en koblet, levende maade; impact-analyse ved aendring; AI-routing-/tillids-synlighed (hoerer til Mission Platform, ikke Cockpittet selv, men Cockpittet kunne blive VISNINGSSTEDET for det senere).

**Vigtigt arkitektonisk valg, IKKE afgjort her:** skal `compliance_intelligence.py`s statiske katalog (a) migreres ind i det levende GRC-skema (stoerre EXTEND, men loeser koblingsproblemet permanent), eller (b) forblive en separat reference-kilde med et eksplicit link tilfoejet fra `grc_items` (mindre indgribende, men bevarer to kilder til delvist overlappende sandhed)? **DECISION REQUIRED.**


## 7. AI-governance/routing/autonomi-impact

**UPSTREAM for GENERISK/IMPLEMENTERET maskineri; RETTET for dokumentationsniveau (se §1.9).** Bekraeftet nul IMPLEMENTERET struktur i kode. Peters princip 14 (menneske/AI-autoritet) og 15 (evidensbaseret AI-routing) beskriver noejagtigt det SAMARBEJDSMODEL §15 allerede (som Proposed, ikke adopteret) forsoeger at daekke, og det Peter selv definerer som "Mission Platform"-lagets kerne ("participant registry, routing, quotas, budget, mandate, autonomy"). **MEN** `AI_KOMPETENCER_OG_OPGAVEROUTING.md` (§1.9) viser at TimeLapse allerede har et TYNDT, LOKALT DOKUMENTATIONSFORSLAG for netop dette — kompetencebaseret routing, budget, én udfoerer, risikobaseret review — der selv eksplicit anbefaler at INTEGRERE med, ikke konkurrere med, den kommende opstroems-struktur.

At bygge en FULD, GENERISK routing-/autonomi-MOTOR lokalt i TimeLapse's GRC-skema ville stadig skabe en TimeLapse-laast kopi af noget der eksplicit er tvaergaaende — den konklusion staar. Men det tynde dokumentationsforslag, der ALLEREDE findes, er et andet, mindre indgribende sporgsmaal: skal det (a) forblive et rent dokument uden nogen GRC-kobling, (b) faa et minimalt REUSE-bart GRC-referencefelt der blot peger paa dets kompetencekort/beslutninger (uden at TimeLapse selv bygger routing-logik), eller (c) danne grundlag for en bevidst, lille, TimeLapse-lokal PROTOTYPE/valideringsimplementering foer det generiske lag er faerdigt opstroems (jf. den arkitektoniske afvejning i §1.9)?

**Anbefalet retning (DECISION REQUIRED, ikke udfoert, IKKE afgjort af denne analyse):** uanset (a)/(b)/(c) boer TimeLapse's GRC-skema hoejst faa et TYNDT REFERENCE-felt (`owner_type: human|ai`, `owner_authority_ref`) der peger UD til enten det eksisterende dokumentforslag eller en fremtidig faerdig opstroems-struktur — IKKE selv definere fulde autoritetsniveauer eller en generisk router. Klassifikation rettet fra rent "UPSTREAM" til: **UPSTREAM (for den generiske motor) + EXTEND-kandidat (for et tyndt referencefelt til det allerede-eksisterende lokale dokumentforslag) — begge dele DECISION REQUIRED.**

## 8. Customer/site/device override-impact

**REUSE for den eksisterende konfigurations-override-mekanisme** (§1.8, 6-lags-kaede, allerede robust implementeret og for nylig korrekt rettet, jf. `89b22231`). **NEW paa GRC-niveau**: en "governance-override" (fx "denne capability-invariant er bevidst ikke opfyldt for kunde X, begrundet saadan") findes ikke som struktur i dag — den nuvaerende config-override-mekanisme handler om FUNKTIONELLE parametre (sync-poll-interval, kvalitetstaerskler), ikke om GOVERNANCE-undtagelser. Disse boer formentlig forblive adskilte mekanismer (funktionel config vs. governance-undtagelse), koblet via `scope`-feltet, ikke sammenlagt.

## 9. Monitoring/runtime-sundheds-impact

Delt i to, som Peter selv bad om at holde adskilt:
- **Post-aendrings-verifikation (§16.9, core, obligatorisk for fuldfoerelse):** delvist **REUSE**-bar allerede — `edge/update_lifecycle.py`s post-restart-sundhedsport er en FUNGERENDE instans af dette princip, men kun for én capability (edge-app-opdatering). At udvide dette princip til ANDRE consequential capabilities (fx en fremtidig terminal-/GRC-/config-aendring) kraever **EXTEND**-arbejde pr. capability-type, ikke en generisk motor der findes i dag.
- **Loebende, risikobaseret overvaagning/alarmering (§16c, valgfri):** **REUSE (dataprimitiv) + NEW (forbrugs-/eskaleringslag).** `NRestarts`-indsamling eksisterer allerede (`edge/diagnostics/collector.py`, `edge/service_operations.py`) og kan genbruges som INPUT — men bekraeftet nul flaade-niveau flapping-/restart-loop-/health_gate-DETEKTION (ingen taerskel-/alarmlogik forbruger dataen i dag, og Headend modtager den slet ikke). Edge1-pydantic-haendelsens 13.039 genstarter over 19 timer uden alarm er det konkrete, evidensbaserede bevis for dette hul — ikke fordi tallet ikke KUNNE indsamles, men fordi intet nogensinde saa paa det eller videresendte det.

## 10. Temporal/fremtidig-compliance-impact

Se §6 (Compliance Cockpit) og GRC-model-tabellen (§5, "Effective date/betingelse", "Fremtidigt krav" — begge **NEW**). Det eneste eksisterende temporale lag (`compliance_intelligence.py`) er UKOBLET fra det levende system (§1.7/§1.14) — dette er den mest konkrete, allerede-identificerede tekniske gaeld i forhold til princip 11.

## 11. Audit/korrektion/supersession-impact

**REUSE af praksis (§1.5), EXTEND af struktur.** Praksissen (append-only, eksplicit KORREKTION-maerkning, bevar original) er allerede etableret og — vigtigt — DEMONSTRERET KORREKT ANVENDT i denne samme PR (§5a's Pi-hole-lukning). Det strukturelle hul: intet `grc_items.status='superseded'`/`superseded_by`-felt findes, saa denne disciplin haandhaeves i dag UDELUKKENDE af menneskelig/AI-laese-disciplin i Markdown-dokumenter, ikke af databasen. Se Fejlklasse-validering §H, Pi-hole-sagen, for hvorfor dette er en reel, ikke kun teoretisk, risiko.

## 12. Fejlklasse-validering (§H)

| Sag | Vurdering | Begrundelse |
|---|---|---|
| **Direct Edge terminal** | **PASS** (styrket af det fulde 16-princip-sat, ikke kun det tidligere §16-udkast alene) | Selv uden en direkte matchende usecase-post ville princip 3 ("manglende links er synlige governance-huller, ikke antagelser der stiltiende genopbygges") have tvunget en eksplicit disponering af fravaeret. §16.1.4's eksplicitte `git log --all`-krav ville uafhaengigt have fundet `d67ca26d`. Begge veje leder til samme fangst. |
| **SEC-016 (fjernelse uden erstatning)** | **PASS, betinget af registrering** | Princip 1's eksplicitte "maa ikke... fjerne eksisterende capabilities" daekker dette direkte — StaERKERE end den tidligere §16.1.1-only-formulering, MEN forudsaetter fortsat at en `CAP-*`-post for "commissioning/bootstrap-adgang" var registreret foerst. Uden registrering ville selv dette princip ikke automatisk have fanget det — hvilket igen illustrerer princip 3's pointe: registreringsomfanget selv er en governance-beslutning, ikke en selvfoelge. |
| **Release artifact drift** | **PASS** (forudsat §16a accepteret) | Uaendret fra tidligere analyse — dette ER netop §16a's maalgruppe. |
| **Travbyen** | **PASS** (med den PRAECISEREDE §16b, ikke anvendt endnu, se §3) | Materiel paavirkning (tabte device-/assignment-rækker, reel kundedata) opfylder klart "potentiel materiel paavirkning paa capability-data" — udloeser §16b uden at paalaegge fuld governance paa triviel drift, noejagtig Peters kriterium. |
| **Edge1 dependency/canary-fejl** | **PARTIAL — de to halvdele adskilt eksplicit, som bedt om** | (a) "Deployed vs. working"-skelnen: **PASS** — §16.9 (core, allerede korrekt placeret) kraever observeret sundhed for fuldfoerelse, ville have fanget den crash-loopende `timelapse-totp.service`. (b) "Detekter behov for overvaagning baseret paa impact, ikke varighed": **FAIL i dag paa FORBRUGS-/ESKALERINGSLAGET, ikke paa dataindsamlingen** — `NRestarts` indsamles allerede (rettet ovenfor, §1.13), men intet flaade-niveau risikobaseret alarmeringslag FORBRUGER den; selv en risikobaseret §16c KRAEVER en overvaagnings-/eskaleringsmekanisme der endnu ikke findes. §16c formulerer det korrekte PRINCIP men loeser ikke det manglende FORBRUGS-MASKINERI — hullet er mindre end tidligere antaget (raadata findes), men reelt. |
| **COMPLETE_TEST_CONTINUITY_PLAN** | **PASS** | Uaendret — §16.6/16.7's kildefrisheds-/to-metode-krav er praecis designet til denne fejlklasse, allerede demonstreret virkende i denne PRs egen historik. |
| **Pi-hole-korrektion** | **PASS paa DOKUMENT-niveau, PARTIAL paa SYSTEM-niveau** | Praksissen (§1.5/§11) forhindrede FAKTISK at den forkastede DHCP-hypotese blev praesenteret som gaeldende sandhed i DENNE PR (§5a demonstrerer det). MEN: dette skete fordi et menneske (Peter) og en AI-session fulgte disciplinen manuelt — der er INTET strukturelt/databasehaandhaevet `superseded`-felt der ville forhindre en FREMTIDIG, mindre omhyggelig soegning (fx en simpel grep efter "Pi-hole DHCP") i at finde den gamle, IKKE-markerede-som-forkert tekst foerst, hvis korrektionen laa laengere vaek i dokumentet eller i en anden fil. Dette er den klareste konkrete demonstration af GRC-model-hullet i §5/§11 ("korrektion/supersession: EXTEND"). |

## 13. Arkitektur-konfliktkontrol (§I)

| # | Konflikt | Nuvaerende tilstand | Godkendt princip | Kraevet beslutning/aendring |
|---|---|---|---|---|
| 1 | Fail-closed vs. degraderet-standard | Blandet i praksis: BT-PAN-TOTP er fail-closed ved untrusted host key (UC-SSH-003); andre stier degraderer sikkert | Princip 7: degraderet drift er STANDARD, override kraever dokumenteret begrundelse; princip 6: ingen universel regel | Ingen reel konflikt fundet — men INGEN samlet oversigt eksisterer over HVILKE capabilities der bevidst er fail-closed vs. degraderet-standard og HVORFOR. **DECISION REQUIRED:** skal dette dokumenteres eksplicit pr. capability-invariant (naturligt et `attributes`-felt) fremadrettet? |
| 2 | BT-PAN-only-antagelse vs. multi-netvaerk-naaelighed | **ALLEREDE LOEST** denne session (§5b, bevaret uaendret per instruks) | Edge Management Reachability-invarianten | Ingen yderligere handling — kun bekraeftelse af at intet i denne analyse modsiger den allerede godkendte tekst (verificeret: uaendret). |
| 3 | Kun-menneske-beslutningsejer vs. fremtidig AI-risikoejerskab | §16.3 (tilfoejet forrige revision) bruger allerede det rollenautrale ord "beslutningsejer", ikke "et menneske"/"Peter" eksplicit | Princip 14: nuvaerende baseline ER menneske-ansvarlighed, men arkitekturen skal TILLADE fremtidig AI-autoritet | **Ingen reel tekstlig konflikt fundet** — §16.3's ordlyd er allerede fremtidssikker. Den reelle mangel er strukturel (GRC har intet `owner_type`-felt, §5/§7), ikke tekstlig. |
| 4 | Fast AI-udbyder-routing vs. evidensbaseret naer-realtids-routing | Denne sessions FAKTISKE arbejdsmoenster i dag: manuel, Peter-medieret multi-AI-koordinering (Claude/Codex/Kimi/z.ai relayeret via chat) — ikke automatiseret routing | Princip 15 | **UPSTREAM, DECISION REQUIRED:** hoerer til Mission Platform (§7 ovenfor); ingen TimeLapse-loesning anbefales. |
| 5 | Compliance-procent/aggregering vs. komplet status-regnskab | Simple COUNT-aggregeringer findes (`by_type`, `open_findings`); INTET compliance-status-vokabular eksisterer der overhovedet KUNNE skjules endnu | Princip 10 | **NEW noedvendigt foer denne konflikt overhovedet kan opstaa i praksis** — statusvokabularet skal bygges FOERST (§5/§6), og aggregerings-sikkerhedsreglen ("aggregat maa ikke skjule kritiske undtagelser") skal designes SAMTIDIG, ikke eftermonteres. |
| 6 | Statiske compliance-frameworks vs. kontrakter/fremtidige krav | `compliance_intelligence.py`s statiske, ukoblede katalog | Princip 11 | **DECISION REQUIRED** (se §6): migrer til levende GRC, eller kobl med et link? |
| 7 | Ustabil historik vs. korrektion/supersession | Ingen konflikt — praksis matcher princippet allerede (§1.5/§11) | Princip 13 | REUSE, ingen handling noedvendig ud over den strukturelle EXTEND i §5/§11. |
| 8 | Fast evidens-gyldighed vs. type-/risikoafhaengig friskhed | `retention_class` findes som fri streng, ingen haandhaevet udloebslogik | Princip 4 (delvist) | **EXTEND noedvendig**, ikke akut — ingen observeret faktisk skadehaendelse endnu, men et logisk hul. |
| 9 | Rollebaserede tilladelser vs. situations-/risikobaseret AI-autonomi | `WRITE_ROLES = {"admin","super_admin"}` — fladt, binaert | Princip 14/16 | **UPSTREAM primaert** (Mission Platform-autonomimodel), med en tynd TimeLapse-API-EXTEND naar/hvis den model findes. Ingen TimeLapse-loesning anbefales foer da. |


## 14. Eksisterende strukturer der boer GENBRUGES (ikke duplikeres)

- `grc_items`/`grc_links`/`grc_test_runs`/`grc_evidence`/`grc_documents` — hele grundskemaet.
- `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`/`CHATGPT-PROJECT-INSTRUCTIONS.md` + OP-001 Step 5 — search-before-create er allerede der.
- `PAKKE_SPOR_REGISTER.md` §14.6 — sporregistrering.
- HANDOVER_LOG/PAKKE_SPOR_REGISTER's korrektions-/append-only-praksis.
- `edge/update_lifecycle.py`s post-restart-sundhedsport (princip om at genbruge, ikke genopfinde, for fremtidige capability-typer).
- Config-override 6-lags-kaeden (customer/site/device) for FUNKTIONELLE overrides.
- `UI_USECASE_CATALOG_2026-08-26.md` og `MENUGUIDE_*_v1.md` — bevares som menneskelaesbart lag, ikke erstattes.
- `tests/architecture_baseline.json`-moenstret (monoton ratchet) som PRAECEDENS for at "ratchets" er en accepteret mekanisme-klasse i dette repo — kan inspirere, men kraever ny logik for capability-invarianter specifikt.
- SAMARBEJDSMODEL §14.4/§14.6/§9 — allerede-accepterede regler §16 skal vaere additiv til, ikke erstatte.

## 15. Genuint manglende strukturer

- Compliance-status-vokabular (COMPLIANT/PARTIAL/NON_COMPLIANT/UNKNOWN-NOT_ASSESSED/NOT_APPLICABLE) — findes IKKE.
- Krav-type-klassifikation (binaer/risikobaseret/hybrid) — findes IKKE.
- `effective_date`/fremtidigt-krav-repraesentation koblet til levende GRC-poster — findes IKKE (kun ukoblet statisk katalog).
- Generisk `grc_links`/`grc_evidence`-CRUD-API/UI — findes IKKE (kun ét hardkodet link, ingen evidence-list-endpoint).
- Flaade-niveau risikobaseret overvaagning/alarmering (restart-loop/flapping-DETEKTION/eskalering) — findes IKKE, men RAADATAEN (`NRestarts`) findes allerede og er REUSE-bar som input.
- Struktureret `superseded`/`superseded_by`-felt for GRC-poster — findes IKKE (kun dokument-niveau-praksis).
- Usecase-til-capability-kobling — findes IKKE i nogen form (0 referencer nogen steder).
- AI-participant-/routing-/autonomi-registry — findes IKKE (bekraeftet fravaer, hoerer UPSTREAM).

## 16. Minimum sammenhaengende implementeringsraekkefoelge (IKKE udfoert — kun rapporteret som analyse)

Hvis/naar Peter (og ChatGPT) autoriserer implementering, er den logiske afhaengighedsraekkefoelge (ikke en tidsplan, kun rammer for rigtig raekkefoelge):

1. Ret link-design-fejlen (usecase-til-capability) FOER noget andet — enhver senere struktur der antager dette virker, ville ellers arve fejlen.
2. Tilfoej `item_type='capability'` (migration + `database.py`-duplikat + UI-hardkodning samtidig, alle tre steder identificeret i tidligere revision).
3. Byg compliance-status-vokabularet SAMTIDIG med aggregerings-sikkerhedsreglen (princip 10 kraever begge dele sammen, ikke sekventielt, for at undgaa en periode hvor aggregeringen findes uden komplethedsgaranti).
4. Kobl `compliance_intelligence.py` til levende GRC (efter Peters DECISION REQUIRED i §6).
5. Tilfoej `superseded`/`superseded_by`-felt til `grc_items` (loeser Pi-hole-klassens strukturelle hul).
6. W1/W2-wiring (relativt uafhaengig, kan foeres parallelt, men KUN sammen med §16-accept, aldrig alene — jf. Peters "wiring er en del af acceptpakken, ikke en senere forbedring").
7. Flaade-niveau overvaagning/alarmering (§16c-maskineri) — stoerst, mest usikker afhaengighed, formentlig sidst.
8. AI-routing/autonomi — eksplicit UDENFOR denne raekkefoelge, afventer Mission Platform/Collaborative Intelligence-arbejde.

## 17. Migrations-/bagudkompatibilitetsbekymringer

- Ny `item_type` CHECK-vaerdi er additiv og ikke-brydende FORUDSAT `database.py`s duplikerede constraint opdateres SAMTIDIG (ellers fejler ORM-initialiserede miljoeer stille, som allerede identificeret).
- Enhver aendring til `grc_links`' brug (fx polymorf targeting for evidence) er en SKEMA-AeNDRING, ikke kun en ny vaerdi — kraever reel migration, ikke kun en Python-settilfoejelse.
- Compliance-status-vokabular paa et felt der i dag er fri `string` (`GrcRegisterItem.status`) kraever en beslutning om MIGRATIONSSTRATEGI for eksisterende data (skal de ~6 typers eksisterende `status`-vaerdier (draft/open/blocked/etc.) migreres ind i det nye vokabular, eller leve side om side med det som to forskellige felter?). **DECISION REQUIRED.**
- `compliance_intelligence.py`-migrering (hvis valgt) paavirker en router der allerede er mountet og i brug — kraever en overgangsplan, ikke en big-bang-udskiftning.

## 18. Beslutninger der fortsat genuint kraeves fra Peter (og ChatGPT ved review)

1. Accepter §16 core (16.1-16.9) som formuleret?
2. Accepter de PRAECISEREDE §16b/§16c-formuleringer fra §3 ovenfor (endnu ikke anvendt i selve proposal-dokumentet)?
3. Skal `compliance_intelligence.py` migreres ind i levende GRC, eller forblive separat med et link (§6)?
4. Skal compliance-status-migrationsstrategien (§17) genbruge det eksisterende `status`-felt eller tilfoeje et nyt, parallelt felt?
5. Skal GRC's `scope`-felt kobles til den eksisterende customer/site/device-config-lagdeling, eller forblive uafhaengig (§8)?
6. Skal AI-autoritet/routing (princip 14/15) formelt henvises til SAMARBEJDSMODEL §15/Mission Platform for FAERDIGGOERELSE der, foer noget som helst TimeLapse-specifikt bygges (staerk anbefaling fra denne analyse, men beslutningen er Peters)?
7. Skal en pr.-capability "fail-closed vs. degraderet-standard"-dokumentation (§13, konflikt 1) tilfoejes som et formelt `attributes`-felt naar capability-item'er faktisk oprettes?
8. Rekonfirmation: W1/W2-wiring forbliver en OBLIGATORISK del af enhver fremtidig §16-accept, ikke en separat, senere, valgfri forbedring — denne analyse har ikke fundet noget der modsiger dette, men beder Peter om eksplicit at genbekraefte princippet efter denne udvidede analyse.

## 19. Ting der IKKE boer implementeres i TimeLapse (hoerer opstroems)

- **En FULD, GENERISK AI-provider-/model-routing-MOTOR med evidensbaseret tillid** (princip 15) — hoerer i Mission Platform. TimeLapse boer forbruge en faerdig model, ikke bygge sin egen parallelle GENERISKE motor. **Praecisering:** dette udelukker ikke det allerede-eksisterende, tynde, lokale dokumentforslag (`AI_KOMPETENCER_OG_OPGAVEROUTING.md`, §1.9) eller en evt. bevidst, lille, lokal PROTOTYPE til at validere den generiske model — kun en konkurrerende, TimeLapse-laast FULD motor.
- **Menneske/AI-autoritets-/mandatmodellen i sin generelle form** (princip 14) — hoerer i Mission Framework/Collaborative Intelligence via SAMARBEJDSMODEL §15, som allerede er det rigtige, endnu-ikke-faerdige hjemsted.
- **En generisk, tvaerprojekt impact-analyse-motor** (princip 12, fulde omfang) — TimeLapse kan genbruge `grc_links` til en MINIMAL lokal version, men den fulde "aendring i ét projekt trigger analyse paa tvaers af scopes/projekter"-vision hoerer i Mission Platform.
- **Et generisk "Compliance Cockpit"-produkt til genbrug paa tvaers af andre projekter** — den KONKRETE `CompliancePage.tsx`/GRC-implementering er korrekt TimeLapse-specifik produktarbejde nu, men hvis samme behov opstaar i et andet projekt senere, boer den underliggende model (ikke UI'et) overvejes udtrukket til Mission Platform DA, ikke foer.

## 20. Klassifikations-legende brugt gennemgaaende

- **REUSE** — eksisterende struktur daekker behovet uaendret.
- **EXTEND** — eksisterende struktur er den rigtige base, men kraever en konkret, navngiven tilfoejelse.
- **NEW** — ingen genbrugelig struktur fundet; ny konstruktion noedvendig I TimeLapse.
- **UPSTREAM** — hoerer arkitektonisk til Mission Framework/Mission Platform/Collaborative Intelligence, ikke TimeLapse.
- **DECISION REQUIRED** — flere gyldige veje findes; kraever Peters (og ChatGPTs) eksplicitte valg foer noget kan klassificeres endeligt.

---

**Denne rapport implementerer intet.** Ingen GRC-migration er koert, ingen Compliance Cockpit-adfaerd er aendret, ingen AI-routing er aendret, ingen autonomi er aendret, ingen runtime/firewall/netvaerk er aendret, ingen overvaagning er implementeret, §16 (eller §16a/16b/16c) er ikke accepteret, W1/W2 er ikke udfoert, og PR #240/#239 er ikke merged. De to §16b/§16c-formuleringsjusteringer i §3 er ANBEFALINGER til en fremtidig revision, ikke anvendt her.
