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
- `GAP` — kan endnu ikke læses/verificeres teknisk.

## 6. Læst / aktivt behandlet — første ledger

| Kilde / dokument | Provenance | Status | Noter |
|---|---|---|---|
| `00_START_HER.md` | current `main` snapshot | READ / EXTRACTED | Master-index; GRC authority, dokumenthierarki, tidligere Peter-instruktion om fuld dokumentgennemgang. |
| `KRAVREGISTER_og_STATUS_v10.md` | current `main` snapshot | READ IN PROGRESS / EXTRACTED | Historisk konsolideret kravbaseline; statusmarkeringer behandles som daterede claims, ikke current runtime truth. |
| `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` | current `main` snapshot | READ / EXTRACTED | Update/change/provisioning/backup requirements; inkluderer ældre dokumenter og chat-kilder. |
| `COMPLIANCE_REGULATORY_INTELLIGENCE_ARCHITECTURE_v1.md` | current `main` snapshot | READ / EXTRACTED | Regulatory intelligence, applicability, evidence snapshots, audit model og phased target architecture. |
| `UI_USECASE_CATALOG_2026-08-26.md` | tidligere archaeology source | READ / EXTRACTED | Human UAT/regression baseline; ikke erstatning for GRC. |
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

## 10. Completion statement

**IKKE KOMPLET.**

Der må ikke skrives “alle dokumenter gennemlæst” før coverage-regnskabet kan underbygge det. Ved afslutning skal indekset mindst vise antal branches, dokumentpaths, unikke blobs, READ, DEDUP, GAP og unresolved conflicts samt tidspunkt/SHA for afsluttende fresh verification.
