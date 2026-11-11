# Raw archaeology extract — current 003

## Dokumentation/BRUGERMANUAL_v10.md

1: # TimeLapse Pro — Brugermanual (v10, konsolideret)
5: **Målgruppe:** Kunde, site manager, projektleder og almindelig bruger
10: ## 1. Login
21: ## 2. Dashboard
34: ## 3. Se billeder
41: Thumbnails skal normalt være genereret af edge/headend. Hvis et thumbnail mangler, kan systemet postprocessere det i baggrunden (administrator kan starte postprocessing).
43: ## 4. Søgning og tags
63: AI-tags er hjælpemetadata, ikke juridisk sandhed. Ved vigtige rapporter bør billeder gennemgås manuelt.
65: ## 5. Billedkvalitet
75: Hvis et kamera gentagne gange giver dårlige billeder, skal en administrator bruge LAB-funktionen til at teste fokus, live preview og kamerakonfiguration.
77: ## 6. Timelapse-video
87: Status pr. 2026-06-23: videoeksport er et kendt krav, men ikke vurderet som fuldt production-ready i kravregisteret.
89: ## 7. Rapporter
100: Rapporter skal baseres på CMDB, update evidence, backup evidence, adgangslogs og kundens/siteets konfiguration.
102: ### 7.1 Compliance- og backup-status
106: ### 7.2 Retention Policy (GDPR G-02)
108: TimeLapse Pro har automatiseret retention policy for at overholde GDPR krav om begrænset opbevaring af persondata.
114:    - **Indstillinger**: Konfigurer hvor ofte automatisk cleanup skal køre (manuel/dagligt/ugentligt/månedligt).
131: ### 7.3 Site-Wide Look Matching (F-012)
143: 3. Hvis du ser "Mangler Site Reference":
172: | 60-74% | 🟡 Acceptabel | Synlig forskel, post-processing hjælper |
173: | < 60% | 🔴 Dårlig | Betydelig forskel, manuel korrektion nødvendig |
181: ## 8. Kendte begrænsninger
185: - MFA/WebAuthn er planlagt som krav før moden flerbrugerdrift.
188: ## 9. Hvad gør jeg ved fejl?
193: - der mangler billeder
200: Ved mulig datalækage eller forkert adgang skal det behandles som sikkerhedshændelse.

## Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md

1: # ChatGPT project instructions — TimeLapse Pro
18: This repo has repeatedly rebuilt, half-built, or forgotten the same capability across sessions — see `HANDOVER_LOG.md` 2026-08-16/17 for concrete, named examples (a security finding closed three separate times without its replacement ever being verified working; a break-glass account built without its key-delivery mechanism; a release manifest that silently dropped required files). Search before you build. After a change, verify the outcome — read back what you wrote, run the relevant tests, and for anything touching a security or trust boundary, confirm what depended on the changed thing still works.

## Dokumentation/CODEX_BUILD_ORDER_TRUST_DMZ_CONVERGENCE_2026-08.md

1: # Codex Build Order — Trust Service, Secure Service DMZ & Release Convergence
7: ## 1. First principle
13: ## 2. Repository / PR reconciliation before implementation
17: Required disposition:
31: ## 3. Complete WP-1 merge readiness
43: ## 4. WP-2 — TimeLapse Trust Service
65: ### Trust Service authority
82: ### Operational private key rule
89: ### Policy Decision Point
99: ### EdgeServiceGrant
114: A normal Headend session/JWT must not be accepted as an EdgeServiceGrant and must not be persisted on Edge for later technician access.
116: ### WP-2 contract tests
125: - missing required MFA denied
129: - technician without required capability denied
134: ## 5. Secure Service DMZ foundation
150: ### Hard rules
159: ### Network/config artifact
172: ## 6. SSH / support conduit migration
187: ## 7. Local TLS CSR lifecycle
199: Keep migration compatibility for existing image-injected keys until WP-4, but new canonical path must be CSR-based.
201: ## 8. WP-3 — Local Service Gateway
216: Normal field service must not require shell.
222: ## 9. WP-4 — Generator / provisioning split + DMZ production routing
235: Provisioning envelope must be signed, device-bound, purpose-limited, expiring/consumable and unusable after successful enrollment.
243: ## 10. Remaining convergence WPs
253: ## 11. Required treatment of all historical input
273: Each material finding must be classified as:
280: No material finding may remain as an unowned `TBD`, `TODO decision`, `open policy question` or ambiguous Proposed choice at RC1 baseline.
282: ## 12. Merge discipline
289: - documentation and runtime must not describe contradictory authorities
291: ## 13. Final output expected from Codex

## Dokumentation/COMPLIANCE_REGULATORY_INTELLIGENCE_ARCHITECTURE_v1.md

1: # Compliance Regulatory Intelligence & Audit - målarkitektur
7: ## Formål
9: Compliance-menuen skal kunne vedligeholde et versionsstyret globalt register over lovgivning, standarder og best practice samt gennemføre reproducerbare audits mod hele det valgte og anvendelige kravkatalog. Systemet må aldrig forveksle et TimeLapse-specifikt udsnit med en fuld standardaudit.
11: ## Principper
14: 2. Metadata, originaltekst, normaliseret krav og TimeLapse-mapping er separate lag.
21: ## Informationsmodel
26: - `Requirement`: stabil requirement ID, hierarchy, normative level, effective dates og source locator.
29: - `RequirementMapping`: requirement -> control/test/evidence/policy/owner med mapping confidence og review.
34: ## Kildeconnectors
44: ## Auditflow
48: 3. Udfyld applicability questionnaire og godkend profil.
55: ## Audittyper
57: - `readiness`: alle krav gennemgås, men ikke en certificeringspåstand.
63: ## Global baseline og profiler
65: Den fælles kontrolgraf bør mindst kunne mappes til EU/DK, NIST og NERC. Jurisdiktionsprofiler tilføjes efter marked: USA (NERC CIP/NIST), UK (NIS Regulations/PSTI/UK GDPR), Canada, Australien og andre kun efter konkret salgs-/produktplan. En global liste er discovery; et audit kræver valgt jurisdiction/sector/effective version.
67: ## Implementeringsfaser
72: - **Fase 3:** requirement/control/evidence graph og applicability profiler.
76: ## Fase 0-begrænsning

## Dokumentation/CONVERGENCE_SOURCE_TO_DECISION_TRACEABILITY_2026-08.md

1: # TimeLapse Pro — Convergence Source-to-Decision Traceability
9: ## Open PR Disposition
13: | PR #5 — Core Design Principles | Platform/payload split, explicit disposition, retention principle | Reconcile and retain. Conflict around automatic retention is resolved in favor of retain-until-explicit-disposition and implemented in WP-6. | WP-6; locked decisions §2, §14, §19 |
14: | PR #6 — Architecture Governance | Governance lifecycle and document state management | Reconcile into baseline. No open policy questions remain for convergence; use Accepted/Implemented/Verified states as execution tracking. | WP-0/WP-6/WP-8; locked decisions §1, §19 |
15: | PR #8 — OS catalog refresh | Useful update/catalog work with hardcoded OS assumptions | Preserve useful implementation, but production merge waits for WP-4 removal of hardcoded OS assumptions. | WP-4; build order §9 |
16: | PR #9 — Broad Edge/runtime PR | Camera recovery, dependency closure, permission fixes, data/export fixes, browser SSH terminal, shared break-glass/service flow | Split. Cherry-pick only convergence-compatible fixes. Hold browser terminal, shared break-glass normal-service and normal technician shell until WP-2/WP-3 policy and gateway are implemented. | WP-2/WP-3/WP-6 split; locked decisions §10, §11, §19 |
17: | PR #10 — Edge trust/service work order | Historical review brief and assessment input | Superseded as execution authority. Preserve assessment evidence and handover references. | WP-0 evidence; locked decisions §19 |
18: | PR #11 — Edge Reference Architecture | Proposed Edge reference architecture and ADR proposals | Reconcile useful architecture text into locked baseline. Proposed/TBD wording is superseded by locked decisions. | WP-2/WP-5; locked decisions §3-§13 |
19: | PR #12 — Release Convergence Plan | Release convergence plan, locked decisions and Codex build order | Merge-ready documentation source. Absorb into implementation baseline; avoid duplicate contradictory authority after PR #13 merges. | WP-0/WP-1/WP-2; PR #13 |
20: | PR #13 — WP-1 | Canonical Edge lifecycle and credential inventory implementation | Canonical WP-1 implementation. Merge after CI and v29 rehearsal. | `edge_lifecycle_records`, `edge_credential_inventory`, v29 |
22: ## Historical Finding Disposition
26: | July independent 3P assessment | Need explicit platform architecture, trust boundaries and assurance traceability | Implemented / in progress | Platform/payload split and Trust Service/DMZ boundaries are locked. Traceability is maintained here and in WP handovers. | Locked decisions §2-§4; WP-2 |
27: | August Edge Trust & Service assessment | Edge identity, credential lifecycle, technician service model and controlled local access were inconsistent | Implemented / in progress | WP-1 implements canonical lifecycle and credential authority. WP-2 implements PDP and EdgeServiceGrant. WP-3 implements Local Service Gateway. | PR #13; WP-2/WP-3 |
28: | SABSA/risk assessments | Trust decisions and business attributes must map to controls/evidence | Implemented / in progress | Trust decisions centralize in TimeLapse Trust Service. Every PDP decision must return Allow/Deny plus reason. | WP-2 PDP tests |
29: | ADR-001/002/003 and ADR proposals | Edge identity, service lifecycle and controlled local service access needed accepted ADR direction | Superseded by locked decision until accepted ADRs are finalized | Locked decisions are execution authority. ADR text may be reconciled later without changing implementation semantics. | Locked decisions §5-§12 |
30: | RBAC / remote operations design | Role checks were endpoint-local and not capability/resource/context based | Implemented in WP-2 | Existing `require_role` becomes compatibility adapter around central PDP. Unknown action/resource/context denies by default. | WP-2 PDP |
31: | Edge generator reviews | Image generation mixed release artifact, provisioning envelope and credential issuance | Deferred beyond WP-2 | Target is generic signed image plus signed provisioning envelope. Full split is WP-4. | Locked decisions §12; WP-4 |
32: | PKI/local trust work | Local TLS leaf private keys were centrally generated/injected in legacy flow | Deferred with compatibility | New canonical path is Edge-generated key + CSR signed by Trust Service. Existing image-injected keys are migration compatibility. | WP-2/WP-4 |
33: | Retention/storage/SIEM findings | Project evidence must not be deleted by pressure, age or unknown state | Deferred to WP-6 | Retain-until-explicit-disposition is locked. Storage alarms are monitoring, not deletion authority. | Locked decisions §14; WP-6 |
34: | Claude review findings | Hidden config, SFTP known_hosts, OS assumptions, camera/GDPR/data lifecycle issues | Mixed: implemented / deferred | Security-critical compatibility fixes may be cherry-picked. Broad runtime/data lifecycle changes wait for their WP. | PR #9 split; WP-4/WP-6 |
35: | Codex assessment findings | Edge trust/service conformance gaps | Implemented / in progress | WP-1 closes lifecycle/credential foundation; WP-2 starts Trust Service, PDP, EdgeServiceGrant and Secure Service DMZ foundation. | PR #13; WP-2 |
38: ## PR #9 Split Disposition
42: | Camera recovery fix | Candidate focused cherry-pick if still needed after WP-1/CI baseline | Separate bugfix PR |
43: | gphoto dependency closure | Candidate focused cherry-pick if tests show gap | Separate dependency PR |
46: | data lifecycle/export fixes | Hold until retain-until-explicit-disposition model is implemented | WP-6 |
47: | browser SSH terminal | Do not merge as normal service capability | WP-3 after EdgeServiceGrant/Local Service Gateway |
48: | shared break-glass key service flow | Do not merge as normal technician identity | WP-2/WP-3 controlled break-glass policy |
50: ## No Open Decisions

## Dokumentation/Claude-2026-08-15.md

1: # Claude — Gennemgang af TimeLapse Pro mod Mission Framework (2026-08-15)
5: **Metode:** Fuld gennemlæsning af `froekjaer/mission-framework` (GitHub), efterfulgt af uafhængig verifikation af kendte issues fra `ISSUES.md` og `PRIORITIZED_BACKLOG.md` (sidst opdateret hhv. 2026-06-14 og 2026-07-09) mod den faktiske kode på commit `365d5289` — 376 commits senere. Fire agenter arbejdede parallelt: (1) distillation af mission-framework-principper, (2) sikkerhedsgennemgang, (3) dataflow/arkitektur-gennemgang, (4) kodekvalitetsgennemgang. Dette er selv en anvendelse af framework'ets **Independent Outcome Verification**-princip: dokumenters påstande blev ikke taget for pålydende, men efterprøvet mod kode.
7: **Provenance-note (jf. TRUST.md/EVIDENCE_MODEL.md):** Denne rapport er AI-genereret evidens, ikke en autoritativ konklusion. Den skal vurderes på sin evidens og efterprøves af et menneske, ikke behandles som fakta i kraft af at være produceret. Ingen go-live-beslutning bør hvile på denne rapport alene.
11: ## 1. Hvad "acceptabelt" betyder ifølge Mission Framework
17: Governance-modellen (review-kit) er konkret: **Critical- og Major-fund blokerer**, medmindre en navngivet, ansvarlig person eksplicit accepterer restrisikoen skriftligt. "Positive observationer opvejer ikke blokerende fund." Ingen AI-selvcertificering — et menneske skal være regnskabspligtig for go-live-beslutningen. Review-outcomes: Approved / **Approved with Conditions** / Changes Required / Rejected / Unable to Conclude.
23: ## 2. Sikkerhed — status på kendte kritiske issues (ISSUES.md §A, §F)
27: | A-01 CMDB uden authentication | ✅ Fixet | Alle CMDB-routes kræver rolle+MFA (`headend/cmdb.py:105-134`), commits `b5cfc343`, `b0e224c1` |
28: | A-02 Break-glass verificerer ikke caller-identitet | 🟡 Delvist | Auth krævet nu, men `admin_username` tages stadig fra request body, ikke session — audit-trail (`last_used_by`, `rotation_reason`) kan forfalskes af enhver autentificeret CMDB-admin |
29: | A-03 `/../../inventory/`-route-hack | ✅ Fixet | Normal route `/api/inventory/{device_id}` med device-token-auth (`headend/main.py:11683`) |
30: | A-04 `disable-mfa` uden rolletjek | ✅ Fixet | Kræver super_admin + fresh password + TOTP step-up (`headend/main.py:1450-1485`) |
31: | A-05 GPG-check bypasses ved manglende signed tags | 🟡 Delvist | Selve bypass-koden (`deploy/edge_update.sh:29-40`, `return 0`) er uændret, men hele legacy git-update-stien er nu bag opt-in kill switch `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1` (default slået fra) |
32: | A-06 `claudetest`-superbruger | ✅ Fixet | Ingen spor i kode eller git-historik |
33: | F-02 Dupliceret `DELETE /api/admin/users/{user_id}` | ✅ Fixet | Kun én route tilbage, med self-delete-guard (`main.py:2138-2153`) |
35: ### Nye fund fra frisk gennemgang
41: | 3 | Lav/Observation | `headend/services/ssh_host_trust_migration.py:44-56` | Den netop mergede (PR #28, 2026-08-15) legacy known_hosts-migration matcher tillid på tunnel-**port**, ikke enheds-ID. Fail-closed og byte-eksakt nøglematch, så praktisk risiko lav, men bør på sigt gøres enheds-bundet. |
46: **Samlet sikkerhedsvurdering:** Alle seks tidligere kritiske huller er lukket eller substantielt afbødet. To reelle, ikke-blokerende fund består (A-02 identitetsbinding, A-05 dormant bypass). Ét nyt Middel-fund (usaniteret filnavn) bør rettes hurtigt — mønsteret til fixen findes allerede i samme fil.
50: ## 3. Dataflow / arkitektur
54: | B-01 config_version dækker kun device-laget | ✅ Fixet | Hash beregnes nu over hele det merged `cfg`-dict (`main.py:4233-4237`) |
55: | B-02 Rapport-data (`camera_params`, `wifi_data`) sendes ubrugt til edge | 🟡 Åben | `camera_profile` læses nu af edge, men `camera_params`/`wifi_data` har fortsat **nul** læse-referencer i `edge/` — stadig ~115 KB ubrugt data pr. poll |
56: | B-03 "Send kun ved ændring" (304/If-None-Match) | 🔴 Åben | Ingen conditional headers i `edge/upload/headend_client.py:_get`, ingen ETag-logik i `get_config` |
57: | B-04 Settings-ændringer bumper ikke config_version | 🟡 Delvist løst som sideeffekt af B-01 | Periodisk fuld poll (~5 min) fanger ændringen alligevel; UI-toggle for slot-settings findes nu (`SystemAdminPage.tsx:859-863`) |
58: | C-01 Upload-slot slået fra (`upload_slot_enforced=false`) | 🔴 Åben (by design) | Mekanismen virker, men er stadig off by default. Den oprindelige blokering (B-01) er løst — intet teknisk til hinder for at slå den til |
59: | C-02 Backup omgår slot-mekanismen | 🔴 Åben | `edge/agent.py:1269, 1760, 1974` kalder `upload_edge_backup` uden slot-check |
60: | C-03 Slot skal udvides til downloads | 🔴 Åben | Ingen slot/quota-logik i `download_artifact_file` |
62: ### Nye strukturelle fund
64: - **Dokumentation matcher ikke kode:** `docs/edge-polling-data-usage.md` estimerer config-poll til ~336 KB/dag; den faktiske belastning er **~35 MB/dag** (faktor ~100 forkert) — matcher det oprindelige ISSUES.md-estimat, som dokumentet tilsyneladende aldrig blev afstemt med. Dette er en direkte krænkelse af framework'ets "Evidence over Assumptions"-princip.
72: ## 4. Kodekvalitet
76: | D-01 Thumbnail-genoprettelse kører ikke | ✅ Fixet | `_thumbnail_auto_loop` genererer og verificerer reelt (`main.py:13106-13181`) |
77: | D-02 AI-tag genoprettelse kører ikke | ✅ Fixet | `queue_capture_for_analysis` + Gemini-batch-sti (`main.py:12162-12181, 12452-12518`) |
78: | F-02 Dupliceret DELETE-route | ✅ Fixet | |
79: | F-03 Kryptisk engine-init | 🔴 Åben | `main.py:364`, uændret |
80: | F-04 `session_policy` mangler i model | ✅ Fixet | `database.py:1029` |
81: | F-05 `ensure_utc` defineret 3x | 🟡 Delvist | Nu kun 2x (`main.py:100`, `database.py:1410`) |
82: | F-06 SQLite default-fallback | ✅ Fixet | Default er nu Postgres, med fail-closed guard mod pytest-mod-prod |
83: | F-07 `sha256_pre_xmp` dobbelt-deklareret | 🔴 Åben | `main.py:748` og `:774` |
84: | F-08 `on_event("startup")` "duplikeret" | Ikke en bug | 4 unikt navngivne startup-handlers, distinkt formål — men `on_event` er deprecated i FastAPI, bør migreres til `lifespan` |
86: ### Struktur
88: - **Test coverage:** 110 testfiler, ~940 testfunktioner, reel CI (`.github/workflows/ci.yml`), 809/1353 tests collected (544 bevidst deselected som integration). Substantielt, ikke overfladisk — men flere "testsuiter" dækker features der kun er delvist implementeret (fx `test_os_offline_update.py`: 0/16 passing), hvilket backlog'en dog selv ærligt markerer som 🟡, ikke ✅.
89: - **Frontend ESLint:** Ratchet-gate holder linjen, men reel oprydning sker ikke — 185 problemer, stort set uændret fra ~222 for måneder siden.
92: - To funktionelt relevante TODO'er: `headend/cmdb.py:982,1032` — password-rotation propageres ikke faktisk til edge via SSH endnu.
96: ## 5. Den systemiske pointe: Engineering Continuity
100: Dette er præcis den type brist Mission Framework advarer imod under **Engineering Continuity**: "intet menneske, AI-model, eller session skal være eneste bærer af missionskritisk viden" — men her er problemet snarere, at der findes *for mange* parallelle, indbyrdes uafstemte kilder (`ISSUES.md`, `PRIORITIZED_BACKLOG.md`, `docs/`, `Dokumentation/`), uden en entydig autoritativ status. `RISK_ASSESSMENT_v10.md`, `GO_LIVE_CHECKLIST_v10.md` og `KRAVREGISTER_og_STATUS_v10.md` i `Dokumentation/` er ikke selv blevet efterprøvet mod koden i denne gennemgang — givet mønstret ovenfor anbefales samme kode-mod-dokument-metode anvendt på dem, før de bruges som beslutningsgrundlag for go-live.
104: ## 6. Samlet vurdering og betingelser
112: 3. **Eksplicit, skriftlig beslutning** fra en navngiven ansvarlig: skal upload-slot-enforcement og config-bloat (B-02/B-03/C-01/C-02) løses før go-live, eller accepteres restrisikoen (mobildataforbrug, manglende fair-brug mellem enheder)?
118: *Denne rapport er genereret af Claude (Sonnet 5) ved AI-assisteret kodegennemgang. Materiel AI-involvering er hermed synliggjort jf. framework'ets Provenance-krav. Konklusioner bør efterprøves af et menneske før de lægges til grund for en go-live-beslutning.*

## Dokumentation/Claude_AI_Tagging_Redesign_2026-06-23.md

1: # TimeLapse Pro — Redesign af AI-tag-generering
10: ## 1. Problemet
14: ### Rodårsag
19: 2. Prompten krævede *"Find between 15 and 35 tags total"* — en kvote, der pressede modellen til at fylde op, og fravær er en nem måde at fylde op på.
22: ### Tre andre begrænsninger ift. målet
30: ## 2. Den nye tilgang
37: 4. **Dedikeret hændelses-/anomaliblok.** Eksplicit liste modellen aktivt skal kigge efter: brand/røg/ild, oversvømmelse, ambulance/brandbil/politi, ulykke, ukendt køretøj, uvedkommende, personer/køretøjer om natten, efterladt udstyr, dyr. Den bruger konteksten til at vurdere hvad der er *usædvanligt for netop dette kamera*.
47: ## 3. Lokal Ollama — pris og privacy
56: | `technical_only` | Kun OpenCV, ingen AI-tags | Maks privacy / ingen omkostning |
58: Den nye prompt-filosofi er nu anvendt på **begge** motorer. Ollama-prompten er en bevidst **slankere** variant (samme regler — åbent vokabular, ingen fravær, kontekst, anomali/kvalitet — men kortere og med færre tags), fordi de lokale modeller (fx `llava-phi3`) er små og klarer lange instruktioner dårligere. Kontekstblokken fodres til Ollama på præcis samme måde som til Gemini.
62: **Forudsætning for at Ollama virker i drift:** Ollama skal køre på headend (`:11434`) med en vision-model trukket (`ollama pull llava-phi3` el. lign.), og `local_model` i `ai_config` skal pege på den. `local_then_cloud` kræver desuden gyldige Gemini-credentials til eskalering. Det er værd at køre en LAB-sammenligning af lokal vs. cloud-tag-kvalitet på et repræsentativt udsnit, før en kunde sættes på `local_only`.
66: ## 4. Hvad er ændret i koden
81: ## 5. Sådan tages baseline i brug
86: ## KONTEKST (baggrundsviden — beskriv stadig kun hvad du faktisk ser)
94:   usædvanligt og bør markeres som en hændelse.
105: Gode baselines beskriver: synsfeltet, faste/forventede objekter, hvad der er normalt på forskellige tider, og hvad der **ikke** skal udløse falsk anomali (fx trafik på en vej i baggrunden, naboens kran).
109: ## 6. Anbefalede næste skridt
111: 1. **UI-felt til baseline** i kamera-redigering (React) — bagenden er klar; mangler kun et tekstfelt der sender `baseline_description`/`context_notes`. (Lille opgave.)

## Dokumentation/Claude_Intern_CA_mTLS_Design_2026-07-05.md

1: # TimeLapse Pro — Intern CA / mTLS til Device-identitet — Design-notat
6: **Beslægtet:** `RISK_ASSESSMENT_v10.md` §13–14 (PKI-skelet, Key Management UI-krav), R05/R07/R08,
13: > opfølgningsspørgsmål (§10)** — designet er derfor færdigt og blocker-frit. Ingen kode er rørt
18: ## 1. Hvorfor (problem og formål)
30: Det der **mangler**, og som R05/R07/R08 peger på, er en **stærk, asymmetrisk device-identitet**:
47: ## 2. SABSA-forankring (kort)
51: | **Kontekstuelt** (forretning) | Kundens tillid til at *kun deres egne* kameraer/edges kan levere billeder ind i deres site — device-identitet er en del af multi-tenant-løftet (jf. R16-lækagesagen, som var en *autorisations*-fejl, ikke en *autentificerings*-fejl, men samme tillidskæde). |
66: ## 3. Nuværende tilstand (grundlag for designet — verificeret ved kodelæsning i dag)
74: | Enforcement-status | `headend/main.py:2503,2585-2655` | Tælles og vises (R15), men **ikke globalt påtvunget** |
84: ## 4. Foreslået PKI-hierarki
93: ### 4.2 Root CA-placering — BESLUTTET, med forbehold (2026-07-05, Peter)
114: `SERVICES_OG_DRIFT_kilde_til_sandhed.md`). Genereringen bør ske via et script Peter selv kører i
121: ikke skelnede): Root CA'ens private nøgle skal aldrig røre et system der er online/routinemæssigt
126: fundamentalt (de skal dog re-udstedes — acceptabel kost, sjældent scenarie).
128: ### 4.1 Certifikatprofil (forslag)
134: | SAN | `URI:timelapse:device:<device_id>` (undgår DNS-navne-krav for interne device-IDs) | — |
136: | Levetid | **10 år, default — konfigurerbar, se §4.3** (ændret 2026-07-05, erstatter §13.2's oprindelige 6 måneder) | 2 år |
137: | Revokering | CRL — se §7. **Skal altid stoppe kommunikation øjeblikkeligt, uanset levetids-konfiguration (§4.3)** | — |
139: ### 4.3 Certifikat-levetid — politik og konfiguration (BESLUTTET 2026-07-05, Peter)
143: certifikat påvirker driften. Revoket certifikater skal selvfølgelig stoppe kommunikationen til den
146: Dette er tre separate beslutninger, som bør holdes adskilt i design og kode:
148: 1. **Default levetid: 10 år** (ikke 6 måneder som i v6-skelettet, §13.2) — markant længere end den
158:    — dvs. om Headend skal afvise forbindelser fra et device med et cert, der er teknisk udløbet men
164: (CRL) skal ALTID stoppe kommunikation til det pågældende device øjeblikkeligt, uanset
167: "dette device er ikke længere tillid" — en aktiv sikkerhedsbeslutning, der aldrig bør være
168: konfigurerbart bort. Dette skal håndhæves i koden som to adskilte tjek, ikke ét kombineret
171: **Implikation for §7 (CRL-friskhed):** fordi certifikater nu lever op til 10 år (ikke 6 måneder),
180: ## 5. Integration med eksisterende auth (ikke et enten/eller)
182: **BESLUTTET 2026-07-05 (Peter, svar på §10 spørgsmål 3):** "Enig, men alt fremtidige skal på
186: (`Frøkjær`) skal RETROFITTES til mTLS som en del af denne udrulning, netop for at bevise
203:    secret og skal have et klientcertifikat tilføjt UDEN at miste eksisterende data/historik.
207:    ingen fremtidig "nedgrader HMAC til valgfri"-beslutning er planlagt.
213: ## 6. Arkitekturvalg — BESLUTTET 2026-07-05 (Peter): Model B
221: | **A: Cloudflare Access mTLS / service tokens** | `cloudflared` valideres device-certs ved tunnel-indgangen (Cloudflare Access "mTLS"-policy eller service tokens), Cloudflare terminerer stadig public TLS | Ingen ændring af A-01–A-04 (GO_LIVE_CHECKLIST) — Cloudflare-arkitekturen fra go-live-planen bevares fuldt ud | Cloudflare bliver en *nødvendig* del af tillidskæden for device-identitet, ikke kun transport; kræver Cloudflare Access-plan-niveau der understøtter dette (skal bekræftes — Codex/Peter har adgang til Cloudflare-dashboardet, jeg har det ikke) |
222: | **B: Ende-til-ende mTLS til nginx/Headend selv** | `cloudflared` proxy'er TCP transparent (eller device'er forbinder uden om Cloudflare for API-trafik), nginx/Headend selv validerer klientcert (`ssl_client_certificate` i nginx, eller FastAPI/Starlette-mellemlag) | Fuld ende-til-ende kryptografisk kæde, uafhængig af Cloudflare | Kræver formentlig en separat indgang uden om den planlagte Cloudflare Tunnel for device-trafik (modstrider evt. A-01–A-04-designet, som netop vil lukke alt direkte porteksponering) — **skal afklares mod GO_LIVE_CHECKLIST §A før dette vælges** |
228: så det er den konkrete blocker for at gå fra design til kode.
231: Peter har samtidig bekræftet at Cloudflare Tunnel bevidst skal undgås for prod (se
244: A-01–A-04/A-13s Tunnel-/443-krav er allerede rettet i `GO_LIVE_CHECKLIST_v10.md`. Peter bruger
251: ## 7. Nøglelivscyklus
256: | **Rotation** | Effektiv levetid fra config-hierarkiet (default 10 år, §4.3), eller manuel fra Key Mgmt UI | Device genererer ny CSR før udløb (analogt til JWT-refresh-mønster), Headend re-signerer — ingen nedetid hvis rotation sker med margin. Given den lange default-levetid er dette job mindre tidskritisk end oprindeligt antaget (var 6 måneder), men bør stadig bygges nu, samme stil som `_backup_auto_loop`/`_baseline_recompute_loop` |
258: | **Revokering** | Fysisk kompromitteret device (R05), device udfaset | Cert tilføjes til CRL, **eller** OCSP-responder markerer den spærret. Stopper ALTID kommunikation øjeblikkeligt — ikke konfigurerbart (§4.3). Se afvejning nedenfor. |
269: ## 8. Key Management UI — udvidelse af eksisterende §14-krav
279: - **Provisioneringspakke (§14):** `_build_bootstrap_yaml` (`headend/main.py:9438`) skal udvides til
286: ## 9. Implementeringsplan (faser, ikke datoer — §6-beslutning truffet, ingen fase startet endnu)
301:    devices kommer på mTLS — bør ske umiddelbart efter trin 3-4 er kodet, FØR trin 8 (Key Mgmt UI)
314: kræver enten §6-beslutningen fra Peter, eller ændringer i selve bootstrap-protokollen som bør
320: ## 10. Åbne spørgsmål til Peter (opsummeret) — status 2026-07-05, ALLE BESVARET
327:    (`_resolve_config_hierarchy()`), IKKE de oprindelige 6 måneder fra v6/§13.2. Desuden
332:    konfigurere om forældet certifikat påvirker driften. Revoket certifikater skal selvfølgelig
335:    mellemstation som oprindeligt foreslået). ALLE fremtidige devices skal på mTLS fra bootstrap.
336:    Det EKSISTERENDE R&D-device (`Frøkjær`) skal desuden **retrofittes til mTLS** som en konkret
338:    Peter: "Enig, men alt fremtidige skal på mTLS, og jeg vil gerne have den aktuelle opsætning
353: ## 11. Dokumenthistorik
360: | 2026-07-05 (designspørgsmål besvaret) | Claude: Peter besvarede §10 spørgsmål 2-3 (spørgsmål 1+4 allerede afsluttet). Ny §4.3 tilføjet — cert-levetid 10 år default, konfigurerbar pr. global/kunde/site/kamera via eksisterende `_resolve_config_hierarchy()`, adskilt fra en separat udløbs-grace-politik, og adskilt fra revokering (som ALTID stopper kommunikation, ikke konfigurerbart). §5 opdateret — HMAC bevares permanent (ikke kun fase 1), alle fremtidige devices på mTLS, OG det eksisterende R&D-device skal retrofittes til mTLS som verifikation. §4.1, §7, §9 (nyt trin 5: retrofit) og §10 opdateret i tråd hermed. Design er nu færdigt — ingen åbne spørgsmål tilbage; kodefasen kan påbegyndes som ny, afgrænset opgave. Ingen kode rørt i denne runde. |

