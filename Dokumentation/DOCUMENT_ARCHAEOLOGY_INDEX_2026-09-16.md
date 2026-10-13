# TimeLapse Pro — Document Archaeology Index

**Dato:** 2026-09-16  
**Status:** WORKING INDEX — coverage ledger, ikke autoritativ kravstatus  
**Branch:** `chatgpt/capability-map-v0-20260916`  

## 1. Formål

Dette indeks dokumenterer den fulde, branch-aware gennemgang af TimeLapse Pro-projektets dokumentation. Målet er at kunne bevise læsedækning og opdage krav, ønsker, beslutninger, rationale, risici, usecases og lessons learned, også når de kun eksisterer på historiske eller aldrig-mergede branches.

Indekset er et dækningsregnskab. Det er ikke et konkurrerende kravregister og promoverer ikke automatisk historiske udsagn til GRC.

## 2. Coverage-regel

En dokumentversion identificeres primært ved Git blob SHA, ikke kun filnavn.

- Byte-identiske kopier på flere branches læses én gang, men alle provenances registreres.
- En ændret blob læses som en selvstændig dokumentversion.
- Slettede/historiske dokumenter skal med, når de kan identificeres fra Git-historikken.
- Binære eller teknisk utilgængelige dokumenter må ikke markeres læst; de registreres som GAP indtil indholdet faktisk er gennemgået.
- Branch-navn eller gammel status er ikke i sig selv bevis for, at indhold er superseded eller irrelevant.

## 3. Aktuelt branch-universum

Frisk branch-inventering 2026-09-16 viser **138 branches** i `froekjaer/timelapse-pro`.

Coverage skal omfatte alle 138, inklusive `main`, `docs/*`, `feature/*`, `security/*`, `fix/*`, `codex/*`, `claude/*`, `kimi/*`, `agent/*`, assessment-, ops-, refactor- og investigation-branches.

**Status:** BRANCH INVENTORY COMPLETE FOR CURRENT REMOTE VIEW.  
**Bemærkning:** Branch-universet kan ændre sig under arbejdet; afsluttende coverage skal derfor fresh-verificere branch-listen igen.

## 4. Coverage pipeline

`branches → document paths → unique blobs → read → extract → classify → conflict/supersession analysis → proposed authoritative home`

Completion må først erklæres når:

1. alle branches er inventorieret;
2. alle dokumentpaths på hver branch er registreret;
3. identiske blobs er deduplikeret med provenance bevaret;
4. alle læsbare unikke dokumentblobs er gennemlæst;
5. utilgængelige blobs/formater er eksplicit registreret som GAP;
6. relevante udsagn er udtrukket til Knowledge Archaeology Register eller et specialiseret archaeology-register;
7. nyere/modstridende kilder er undersøgt;
8. disposition er foreslået uden tavs promotion;
9. branch-listen og coverage fresh-verificeres ved afslutning.

## 5. Statuskoder

- `INVENTORIED` — fil/blob/provenance identificeret, endnu ikke nødvendigvis læst.
- `READ` — dokumentversion faktisk gennemlæst.
- `EXTRACTED` — relevante krav/ønsker/beslutninger mv. udtrukket.
- `DEDUP` — blob er identisk med allerede læst version; provenance registreres.
- `CONFLICT` — modstridende eller udviklet krav/beslutning fundet.
- `SUPERSEDED_CANDIDATE` — nyere materiale ser ud til at erstatte udsagnet, men relation skal bevises.
- `NO_REQUIREMENT_CONTENT` — læst, men ingen relevant projektviden fundet.
- `BINARY_PENDING_EXTRACTION` — binær dokumentversion er inventorieret, men må ikke markeres READ før tekst faktisk er udtrukket og gennemgået.
- `GAP` — kan endnu ikke læses/verificeres teknisk.

## 6. Læst / aktivt behandlet — første ledger

| Kilde / dokument | Provenance | Status | Noter |
|---|---|---|---|
| `00_START_HER.md` | current `main` snapshot | READ / EXTRACTED | Master-index; GRC authority, dokumenthierarki, tidligere Peter-instruktion om fuld dokumentgennemgang. |
| `KRAVREGISTER_og_STATUS_v10.md` | current `main` snapshot | READ / EXTRACTED | Historisk konsolideret kravbaseline; statusmarkeringer behandles som daterede claims, ikke current runtime truth. |
| `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` | current `main` snapshot | READ / EXTRACTED | Update/change/provisioning/backup requirements; inkluderer ældre dokumenter og chat-kilder. |
| `COMPLIANCE_REGULATORY_INTELLIGENCE_ARCHITECTURE_v1.md` | current `main` snapshot | READ / EXTRACTED | Regulatory intelligence, applicability, evidence snapshots, audit model og phased target architecture. |
| `UI_USECASE_CATALOG_2026-08-26.md` | tidligere archaeology source | READ / EXTRACTED | Human UAT/regressionsbaseline; ikke erstatning for GRC. |
| `MENUGUIDE_BRUGER_v1.md` | tidligere archaeology source | READ / EXTRACTED | UI-derived functional evidence. |
| `MENUGUIDE_ADMIN_v1.md` | tidligere archaeology source | READ / EXTRACTED | UI-derived functional evidence. |
| SABSA Architecture v2/v3 | uploaded/project source | READ / EXTRACTED | Mission/business attributes, availability, integrity, synchronicity, continuity, resilience, manageability, scalability. |
| SABSA Risk Assessment v1/v2 | uploaded/project source | READ / EXTRACTED | Historical risks/controls reveal hidden requirements; historical statuses not current truth. |
| System Architecture / Configuration Guide v3 | uploaded/project source | READ / EXTRACTED | Historical ADRs, open requirements, product/business wishes. |
| Documentation Archaeology report | project source | READ / EXTRACTED | Identified UI catalog, stale kravregister semantics, GRC authority and architecture tests. |
| Capability Regression Archaeology report | project source | READ / EXTRACTED | Capability-preservation evidence and historical regression context. |

## 7. Aktuelle dokumentfamilier der skal læses fuldt

Dette er en arbejdsqueue, ikke en udtømmende slutliste:

- autoritative/current `*_v10.md` dokumenter;
- `ADR/` og `Arkitektur/`;
- security/compliance/risk/pentest materiale;
- update/change/provisioning/deployment/build/image dokumentation;
- Edge/Headend runtime, recovery, terminal, connectivity og technician access;
- camera/capture/image quality/video/AI/tagging/redaction/retention;
- UI/usecases/manualer/help/tooltips;
- backup/restore/DR/storage;
- CMDB/ITIM/observability/SIEM/health/alerting;
- GRC/regulatory/compliance intelligence;
- governance/collaboration/handover/PAKKE_SPOR/review/archaeology;
- old versions, chat dumps and historical requirement sources;
- branch-only documentation and deleted historical documents.

## 8. Branch-aware pass

For hver af de 138 branches skal følgende registreres:

| Felt | Betydning |
|---|---|
| branch | branch-navn |
| branch head | commit ved inventory-tidspunkt |
| path | dokumentsti |
| blob SHA | unik content-identitet |
| seen on | øvrige branches med samme blob |
| read status | INVENTORIED/READ/DEDUP/GAP |
| extraction ref | KA-ID eller andet archaeology-register |
| conflict ref | relation til nyere/ældre version |
| notes | kontekst og disposition |

Den detaljerede blob/provenance-matrix udbygges løbende. Den må gerne blive maskinelt genereret senere; dette dokument er den menneskelige coverage-oversigt.

## 9. Foreløbige capability-familier som dokumentarkæologien skal teste

De oprindelige 16 Golden Capabilities behandles som foreløbige. Arkæologien har allerede indikationer på yderligere selvstændige capability-familier, som ikke må tabes:

- camera abstraction / multi-camera-family support — **Nikon er strategisk/default retning for nye installationer; understøttede eksisterende Canon-kameraer forbliver current migration/backward-compatibility intent, så en defekt legacy Edge kan erstattes af TimeLapse Pro Edge uden tvunget kameraskift**;
- image quality / photographic consistency;
- timelapse video production;
- AI analysis/tagging/search;
- fleet/scalability management;
- provisioning and reproducible Edge builds;
- backup/restore/disaster recovery;
- regulatory intelligence / GRC / reproducible audit;
- alert delivery and operational notification;
- physical/environmental robustness;
- historical import / virtual-device continuity.

De tilføjes ikke automatisk som Golden Capabilities. Hele dokumentmængden skal først have mulighed for at bekræfte, afkræfte eller omforme dem.

## 10. Branch archaeology wave — Codex Audit / Compliance Readiness

Branch `feature-camera-hardware-cmdb` er nu aktivt traverseret. Følgende unikke tekstblobs er strict-complete læst i denne wave:

| Dokument | Blob SHA | Status | Archaeology-note |
|---|---|---|---|
| `Claude_Support_Access_Model_2026-07-06.md` | `e2fc185bc73459ac3322aaef316d6543e5bfadbc` | READ / EXTRACTED | Default-deny support exception; separate Support-CA; AccessTicket lifecycle; dokumentet udvikler sig fra design-only til model/schema-only implementation. |
| `Codex-Audit/03_ARCHITECTURE_DATAFLOWS.md` | `99970008081d7e334c2f1a3cc816b9cf5e696386` | READ / EXTRACTED | Dated architecture assessment; live evidence and migration/convergence gaps preserved. |
| `Codex-Audit/04_CODE_REVIEW_FINDINGS.md` | `3be8113a7676451fe7d5b923974864806b456555` | READ / EXTRACTED | Dated code findings; do not import old severity as current status without re-verification. |
| `Codex-Audit/05_SECURITY_RISK_SABSA_PENTEST.md` | `75f5bf9d082ca826f909da50771a982d7ce058b1` | READ / EXTRACTED | Non-destructive virtual pentest; explicit convergence risk and legacy-path concerns. |
| `Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md` | `6e8fb970689b16f2b5a7d46626a7061fa34eee65` | READ / EXTRACTED | Technical readiness assessment, explicitly not legal advice/certification. |
| `Codex-Audit/07_ACCEPTANCE_GATE_AND_ROADMAP.md` | `6788352b98d0906c3f0a9707509601a0768c93e8` | READ / EXTRACTED | Historical release gates; useful capability-preservation evidence. |
| `Codex-Audit/08_EVIDENCE_LOG.md` | `7ddaac0022ef317b140abaac6331ee279b4d5be5` | READ / EXTRACTED | Establishes exact audit baseline, 52-test scope and explicit not-performed limitations. |
| `Compliance-Readiness-Pack/00_INDEX.md` | `e9333198e81332a7cbcf5b8dae693d33fcbe96d6` | READ / EXTRACTED | Readiness/evidence layer, not certification. |
| `Compliance-Readiness-Pack/01_CUSTOMER_SITE_DPIA_PACK.md` | `462def015811dd20a2abb5bd632c9fe8b9fe2050` | READ / EXTRACTED | Site-specific privacy/retention template; proposed defaults are not universal legal requirements. |
| `Compliance-Readiness-Pack/02_DATA_PROCESSING_ROLE_MATRIX.md` | `fabcad58fc52d80b87b45ef8b093e31ce48926f1` | READ / EXTRACTED | Contract/onboarding working matrix; roles explicitly agreement-dependent. |
| `Compliance-Readiness-Pack/03_VULNERABILITY_UPDATE_SLA.md` | `7734482aa36ef77457cf0092616dc01fd295ecc0` | READ / EXTRACTED | Operational policy template; response/remediation times are proposed policy until adopted. |
| `Compliance-Readiness-Pack/04_SBOM_RELEASE_EVIDENCE_CHECKLIST.md` | `9e785e9e02d2ac2279d1d2d750d9985c6f28a5fb` | READ / EXTRACTED | Strong release-evidence and no-regression checklist. |
| `Compliance-Readiness-Pack/05_ISO_NIS2_CER_SUPPLIER_ASSURANCE.md` | `ad5f90ba08e239c054c86462568c3cbd8bc2da21` | READ / EXTRACTED | Customer-facing readiness summary; certification claims explicitly prohibited. |
| `Compliance-Readiness-Pack/06_AI_SYSTEM_INVENTORY.md` | `e9730653fdf9f69012b996470880540c0863bf6a` | READ / EXTRACTED | AI baseline: observe/classify/recommend; human control; no bypass of PDP/session/capabilities. |
| `Compliance-Readiness-Pack/07_COMPLIANCE_ACCEPTANCE_GATE.md` | `c9d16f880a35a189020789965882c2de96f7ad4e` | READ / EXTRACTED | Pilot/production/market gates; dated readiness policy, not current compliance proof. |

`Codex-Audit/00_INDEX.md`, `01_EXECUTIVE_READINESS.md` og `02_MISSION_FRAMEWORK_ALIGNMENT.md` var strict-complete læst i den umiddelbart foregående wave og forbliver registreret som READ/EXTRACTED i arbejdsgrundlaget.

### Tværgående fund fra denne wave

- Desired/declared state skal adskilles fra applied state, observed runtime state, verified outcome og retained evidence.
- Rollback er først en operationel capability når kendt-god runtime er genetableret og verificeret; backup/filer alene er ikke rollback-evidence.
- Security properties klassificeres efter faktisk håndhævet mekanisme, ikke navnet på flow/felt/dokument.
- Automation må ikke skabe en alternativ execution path, der omgår assurance gates i referenceflowet.
- Privileged exception access skal være non-standing, explicit authorized, scope-bound, time-bound, revocable og attributable.
- Device identity og privileged support identity skal holdes i separate trust domains.
- Release evidence skal bindes til exact artifact/source/SBOM/deployed revision og efterfølges af post-deploy outcome verification.
- Compliance/readiness-templates og kundevendte claims må aldrig promoveres til verified compliance uden relevant site-, kontrakt-, runtime- og evt. licenseret/certificeret evidence.

## 11. Historical consolidation / implementation verification wave

Følgende yderligere historiske blobs er strict-complete læst og klassificeret i archaeology-arbejdsgrundlaget:

| Dokument / evidence | Blob SHA | Status | Archaeology-note |
|---|---|---|---|
| `Codex_ADMINISTRATORMANUAL_2026-06-23.md` (historisk variant) | `8180cb5a4214f1a3c85f26a409c0f1344371f5aa` | READ / EXTRACTED | Logical camera vs physical device; config inheritance; Nikon primary; governed update authority. |
| `Codex_BRUGERMANUAL_2026-06-23.md` (historisk variant) | `f65eda7566a390f4069a17b554c9b570f3f074c8` | READ / EXTRACTED | Customer UX, stale/offline semantics, canonical tags, AI as helper metadata, video not production-ready. |
| `Codex_DOKUMENTPAKKE_OVERSIGT_2026-06-23.md` (historisk variant) | `23c0b5c83007e4e00c827f29fdd7ff40040291f0` | READ / EXTRACTED | Historical coverage checkpoint: 79 files / 54,470 extracted lines; explicit DOCX/PDF/GDrive limitations. |
| `Codex_Timelapse_pro_full_documentation_v1.md` | `a4f4047fc6a537f5d178c672bb3446d1e5c6dc99` | READ / EXTRACTED | Parallel 'authoritative' consolidation; authority claim itself is not sufficient provenance. |
| `Claude_Timelapse_pro_full_documentation_v1.md` | `ee01c3ae231d4fa973129006512387f532470459` | READ / EXTRACTED | Distinct parallel consolidation; contains claim/evidence tensions that must not silently promote to current product claims. |
| `Headend_Installationsguide_Mac_Mini.md` | `59e60189214315121447df370dcb49a9093663e1` | READ / EXTRACTED | Known historical implementation generation; concrete platform paths/services are not current invariants by themselves. |

### Verified implementation/history corrections

- WP-3 Unified Technician Platform was not merely proposed: merged implementation evidence exists, and current `main` retains `edge/service_operations.py` plus `edge/service_platform.py`. Archaeology classification is therefore `IMPLEMENTED + MERGED + PRESENT`, while remote Headend-to-Edge dispatch remains a separate capability question.
- Camera direction is now explicitly classified as **Nikon strategic/default for new deployments** plus **Canon current migration/backward compatibility**. A supported legacy Canon camera must be retainable when a failed legacy Edge is replaced with TimeLapse Pro Edge. This is compatible with the longstanding logical-camera/physical-device separation and later Canon+Nikon implementation evidence.
- Commit-history evidence on 2026-07-12 implements site-wide look matching with Nikon Picture Controls and Canon Picture Styles; 2026-09-02 CMDB camera-hardware reporting includes Canon EOS vendor-extension paths plus generic PTP fields for Nikon/other cameras. Canon support is therefore not to be marked retired solely because Nikon became primary.

## 12. Explicit unresolved extraction gaps

These remain unresolved and MUST NOT be counted READ:

- `Dokumentation/Gamle versioner/2026-06-03-Timelapse - Risk og plan videre.md` — historical text blob approx. 1.16 MB; normal connector retrieval has exceeded response limits. Status: `GAP / OVERSIZE_PENDING_EXTRACTION`.
- Historical `.docx` generations (including Configuration Guide, Edge Runbook, SABSA Architecture/Risk and update-flow variants) — status remains `BINARY_PENDING_EXTRACTION` until actual document text is extracted and reviewed.
- Historical hardware-manual PDFs — inventoried where known, but not READ merely from filename/metadata.

## 13. Completion statement

**IKKE KOMPLET.**

Der må ikke skrives “alle dokumenter gennemlæst” før coverage-regnskabet kan underbygge det. Ved afslutning skal indekset mindst vise antal branches, dokumentpaths, unikke blobs, READ, DEDUP, `BINARY_PENDING_EXTRACTION`, GAP og unresolved conflicts samt tidspunkt/SHA for afsluttende fresh verification.
