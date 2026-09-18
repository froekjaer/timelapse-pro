# TimeLapse Pro — Document Archaeology Closure Ledger

**Dato:** 2026-09-17  
**Status:** WORKING CLOSURE LEDGER — discovery/evidence, ikke autoritativ GRC  
**Branch:** `chatgpt/capability-map-v0-20260916`  
**Relation:** Supplement til `DOCUMENT_ARCHAEOLOGY_INDEX_2026-09-16.md` og `KNOWLEDGE_ARCHAEOLOGY_REGISTER_2026-09-16.md`.

## 1. Formål og stopregel

Closure følger:

`branches inventoried → document paths discovered → unique blobs → READ/DEDUP/GAP → extracted → conflicts/supersession → proposed authoritative home`

Data collection må først erklæres lukket når alle aktuelle remote branches er accounted for, alle opdagede dokumentpaths er knyttet til blob SHA/provenance, ingen unik dokumentblob står uklassificeret, alle teknisk læsbare relevante tekstblobs er READ/DEDUP, binære/oversized kilder er eksplicit GAP-klassificeret, potentielt unikke knowledge gaps er vurderet, current `main` er reconcilet, og et sidste fresh branch-check er udført.

Closure betyder ikke nødvendigvis nul tekniske gaps. Closure kan ske med eksplicitte gaps, hvis ingen kendt ulæst kilde efterlader et uidentificeret requirement/capability-domæne.

Ingen historisk status promoveres automatisk til current GRC-status. **Supersession er ikke deletion.**

## 2. Fresh branch-universum

Fresh pagineret branch-inventering 2026-09-17 viser **139 remote branches** i `froekjaer/timelapse-pro`: 100 + 39; opslag efter cursor 139 gav 0. Det tidligere tal 138 i archaeology-indexet er stale.

Ny branch siden det tidligere snapshot omfatter `chatgpt/api-mtls-20260917`. Første tree/delta-pass viste ikke et nyt historisk dokumentunivers; branchens dokumentation er i høj grad kendte blobs/provenances. Den skal stadig indgå i endeligt blob/provenance-regnskab.

## 3. GAP-taxonomi

| GAP-type | Betydning | Closure-effekt |
|---|---|---|
| `SOURCE_GAP` | Refereret original kilde/blob kan ikke recoveres | Blokerer kun hvis unik viden ikke findes andetsteds |
| `BINARY_GAP` | DOCX/PDF/blob er inventorieret/recoveret, men tekst er ikke faktisk ekstraheret og strict-read | Skal have sekundær evidens eller forblive unresolved |
| `TECHNICAL_GAP` | Kilden findes, men connector/tooling kan ikke levere den læsbart, fx pga. størrelse | Registreres med teknisk årsag og evt. descendants |
| `COVERED_GAP` | Originalen kan ikke strict-reades, men dokumenteret extraction eller senere direkte kilder bevarer requirement-intent/provenance | Evidence-quality gap, normalt ikke knowledge-loss blocker |
| `CRITICAL_KNOWLEDGE_GAP` | Kendt ulæst kilde kan indeholde et unikt requirement/capability-domæne uden anden evidens | Blokerer knowledge closure |

Status: der er endnu **ikke identificeret en dokumenteret `CRITICAL_KNOWLEDGE_GAP`**, men blob/path reconciliation skal færdiggøres før endelig closure.

## 4. Pre-Git projektstart vs Git provenance

Git-repositoriets første commit 2026-04-01 er **første bevarede Git implementation baseline**, ikke projektets begyndelse. Tidlige projektkilder kan være skabt før Git og senere indført i repository history.

### 4.1 Vigtig recovery 2026-09-17

Et recursive tree-pass på `feature-camera-hardware-cmdb` (`Dokumentation` tree `c8e5776704b812452785a4d82965294db0014987`, `truncated=false`) recoverede de eksakte repository paths og blob SHA'er for de tidligere formodede pre-Git originals:

| Kilde | Eksakt path på historisk branch | Blob SHA | Size | Status |
|---|---|---|---:|---|
| Startkrav | `Dokumentation/Empiri og kilder/Startkrav.docx` | `f3533f333652792ea3779a6e349f090a339ae61c` | 17,312 | `BINARY_GAP`, original blob recoveret |
| ChatGPT input | `Dokumentation/Empiri og kilder/ChatGpt-input.docx` | `f77615324fa67fc2f1a8038d4260e6f40fd7d09f` | 120,503 | `BINARY_GAP`, original blob recoveret |
| Gemini chat | `Dokumentation/Empiri og kilder/Chat with Gemini.docx` | `36d2f83db622b5f96c1abf75e25e263263cb8feb` | 81,727 | `BINARY_GAP`, original blob recoveret |
| Timelaps chat | `Dokumentation/Empiri og kilder/Timelaps-chat.docx` | `844a4e692373553ca6f1a6adb01fc5bbfd2727f7` | 503,401 | `BINARY_GAP`, original blob recoveret |

Dette korrigerer den tidligere foreløbige `SOURCE_GAP`-klassifikation: originalerne er **ikke tabt fra Git-history**. De er binære og endnu ikke strict-read.

`Startkrav.docx` blev derefter hentet via GitHub connector med den eksakte path og `encoding=base64`. Connectoren returnerede DOCX/ZIP-data, men output blev trunkeret af response-budgettet. Det beviser blob/path recovery, men er **ikke** text extraction og må ikke markeres READ.

Konsekvens: pre-Git provenance-risikoen er reduceret fra “original source not recovered” til “original binary recovered, extraction pending/limited by connector”.

### 4.2 Historisk Dokumentation-tree og Gamle versioner

Samme non-truncated recursive tree identificerede `Dokumentation/Gamle versioner` som tree:

`241d43a0cf6c93bde88e2883e2bf3fb62c1aeb38`

Det erstatter den tidligere fejlagtige/ufuldstændige tree-SHA-antagelse og giver et reproducerbart historisk inventory-anchor.

Tree'et bekræfter desuden eksakte binary families og SHA'er, bl.a.:

- Configuration Guide: `04cf2284...`, `e87b88f...`, `e6951210...`;
- Edge Runbook v2–v7: `882abf04...`, `c0d1cdf6...`, `db28089e...`, `4e65f6a2...`, `aaecbeb2...`, `77e7d5aa...`;
- Roadmap v1–v4: `deba2e21...`, `47cf4328...`, `4948047f...`, `5b85539e...`;
- SABSA Architecture original/v3–v9: `d0e64a24...`, `aca63339...`, `20b235d3...`, `62a63c2a...`, `272f65ad...`, `4564ce71...`, `d0ebd551...`, `7cdda53c...`;
- SABSA Risk original/v2–v6: `8509188e...`, `2e3060d8...`, `5faf3cf1...`, `8aabddcc...`, `496a3719...`, `1b054703...`;
- RBAC Remote Operational v1: `afc39dfe...`;
- Security/Compliance v2: `8b5506ef...` (samme blob som `timelapse_full_security.docx`, dermed dedupe provenance);
- System Inventory v1: `02f8adae...`;
- `timelapse_security.docx`: `6ffe0c55...`.

Disse er inventorierede originals, ikke `SOURCE_GAP`. De forbliver `BINARY_GAP`/`BINARY_PENDING_EXTRACTION` indtil tekst er faktisk ekstraheret eller de dispositioneres som `COVERED_GAP` med dokumenteret secondary extraction.

## 5. Historical extraction bridge

`AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` fra 2026-05-22 er strict-read og beskriver extraction fra 47 dokumenter, herunder Startkrav, chats, Roadmaps, Edge Runbooks, SABSA/Risk, RBAC, Security/Compliance og System Inventory.

Det giver secondary evidence for kravfamilier som Headend-medieret production update, signeret/immutable artifact, hierarchical update/config scope, per-target state, staged rollout/rollback, Edge capture/store-forward autonomy, zero/near-zero-touch provisioning, certificate lifecycle, backup/restore/RTO/RPO og governed operational configuration.

Evidence-strength:

`original directly READ → documented historical extraction → later corroborating source/implementation → reference-only GAP`

Recovered-but-unextracted DOCX ligger mellem første og andet niveau: original blob/provenance er kendt, men content evidence kommer indtil videre fra documented extraction.

## 6. Requirements → observed implementation gaps

Den eksakte historiske `Dokumentation/SYSTEM_HEALTH_REGISTER.md` blev oprettet 2026-05-23:

- blob `58bf9b155dd40e8aae67e470558b98e4da058f38`;
- commit `443c5e0bd9f926f8838143d9fc51f7283fa9072c`;
- parent `35e937db1fac960c5dba0552315ab1879189e2fe`;
- GPG-verificeret commit;
- 273 tilføjede linjer.

Den daterede assessment viser bl.a.:

- Edge direct GitHub update i konflikt med Headend-mediated intent;
- tag-signatur ikke bundet til faktisk installeret `origin/main`;
- UI approval-valg ikke sendt til backend;
- manglende fuld `global|customer|site|camera|device` scope;
- behov for `DeviceAssignment`-binding så fysisk device replacement ikke mister policyhistorik;
- manglende per-target deployment truth;
- configured/returned policy uden sikker consumed/enforced semantics;
- konkrete secret/data leakage-risici;
- test/build-presence uden stærk runtime evidence.

Dette giver en direkte provenance-chain:

`early need → 2026-05-22 formalized requirement → 2026-05-23 observed implementation gap → remediation intent → later implementation/evolution`.

## 7. Candidate invariants med historisk provenance

Disse er archaeology findings, ikke automatisk authoritative GRC requirements:

1. **Authorized object = executed object.**
2. **Operator approval binding:** visible approval skal bindes til faktisk action/scope/targets/constraints.
3. **Aggregate state må ikke erstatte target truth.**
4. **Declared/configured ≠ consumed ≠ executed ≠ runtime reconciled ≠ outcome verified ≠ evidence retained.**
5. **Logical assignment survives physical replacement**, mens private hardware trust identity ikke kopieres ukritisk.
6. **Supersession ≠ deletion**; disappearance er ikke documented change.
7. **Security enforcement at authority boundary**, ikke kun UI.
8. **Evidence scope is bounded**; automated test kan ikke attestere fysisk/runtime capability den ikke exercised.
9. **Recovery/safety failure-domain separation.**
10. **Capture-plane priority:** scheduled capture må ikke afhænge af Headend/Internet/upload/heartbeat/inventory/management.
11. **Configured parameter semantics must match runtime consumption**; ellers er surface falsk.
12. **Production trust must fail closed**; missing trust anchor må ikke stiltiende blive TOFU.

## 8. Camera direction og migration

- Nikon er strategisk/default retning for nye installationer.
- Fungerende understøttede legacy Canon-kameraer er fortsat migration/backward-compatibility intent.
- En defekt legacy Edge skal kunne erstattes af TimeLapse Pro Edge uden tvunget udskiftning af et fungerende understøttet kamera.
- Camera compatibility evidence: `declared compatible → lab verified → physical production verified → currently supported`.

## 9. Current-main reconciliation

PR #243 blev oprettet mod en ældre `main`-base. Fresh delta-pass 2026-09-17 viste primært governance/capability documentation, loader/preamble og tests; intet nyt historisk requirement-domæne blev identificeret.

Nyere governance understøtter separationen:

`decision/architecture accepted ≠ implemented ≠ verified`

og:

`Capability/invariants → Usecases → implementation/history → automated verification → runtime/physical evidence`.

Archaeology skal fodre eksisterende authoritative homes; den må ikke blive et konkurrerende GRC-register.

## 10. Kendte tekniske/binary gaps

### 10.1 Oversized historical markdown

`Dokumentation/Gamle versioner/2026-06-03-Timelapse - Risk og plan videre.md`, blob `b8b44eeb02c15b365d84e90b208cbb447d2ceef8`, size 1,158,581 bytes, kan ikke direct-read gennem nuværende connector pga. response-size-begrænsning.

Status: `TECHNICAL_GAP / OVERSIZE_SOURCE`. Senere extraction/descendants kan være secondary evidence; originalen må ikke markeres READ.

### 10.2 Recovered historical DOCX

De tidlige DOCX-originals og version families er nu path/SHA-recoveret. Deres primære status er derfor `BINARY_GAP`, ikke `SOURCE_GAP`. Hvor 2026-05-22 extraction eller senere strict-read descendants bevarer samme requirement-intent, kan enkelte requirements dispositioneres som `COVERED_GAP`; det ændrer ikke originalblobens READ-status.

### 10.3 Hardware manuals og pointer formats

Store hardware-PDF'er og Google pointer-filer (`.gslides`/eventuelle `.gdoc`) skal klassificeres særskilt. Vendor/manual reference-materiale er ikke automatisk product requirement authority. De skal kun kunne blokere knowledge closure, hvis de er eneste kendte evidens for et product requirement/capability-domæne.

## 11. Closure assessment — foreløbig

Vigtig ændring denne run: de fire centrale tidlige originals (`Startkrav`, `ChatGpt-input`, `Chat with Gemini`, `Timelaps-chat`) er **recovered as exact historical blobs**. Den tidligere source-loss-hypotese er derfor korrigeret. Det reducerer den væsentligste pre-Git uncertainty til binary extraction/evidence quality.

Der er stadig ikke evidens nok til `DATA COLLECTION CLOSED`. Der mangler især:

- endelig branch→path→blob reconciliation for alle 139 branches;
- endelig unique-document-blob count;
- endelig disposition af recovered binary/oversize sources;
- dokumenteret vurdering af om nogen er `CRITICAL_KNOWLEDGE_GAP`;
- sidste fresh branch/main reconciliation ved closure-tidspunktet.

Hvis disse checks ender med `CRITICAL_KNOWLEDGE_GAP = 0`, kan dataindsamlingen lukkes med eksplicitte `BINARY_GAP`/`TECHNICAL_GAP`/`COVERED_GAP` uden at foregive, at original tekst er læst.

## 12. Næste fase efter closure

`Knowledge Register → dedupe → requirement/change/conflict chains → current intent determination → authoritative GRC/capability/ADR/usecase/history placement → implementation mapping → verification → runtime evidence`

Golden Capabilities fryses først efter syntese og efter at historiske krav har fået mulighed for at udfordre nyere dokumentation.


## 13. Strict-read closure delta — System Health Register

Den historiske `Dokumentation/SYSTEM_HEALTH_REGISTER.md` ved commit `443c5e0bd9f926f8838143d9fc51f7283fa9072c`, blob `58bf9b155dd40e8aae67e470558b98e4da058f38`, er nu hentet i tre ikke-overlappende line ranges (1–120, 121–240, 241–320) og dermed **strict-complete READ**. Tidligere connector-truncation er lukket for denne kilde.

Registeret indeholder HLTH-001..HLTH-015. De tidligere kendte HLTH-001..014 er bekræftet direkte; den afsluttende del tilføjer især:

- HLTH-014: tekst-/presence-tests er smoke checks, ikke stærk API/datamodel/integration-evidens; anbefaler TestClient-, migration- og Edge API contract-tests.
- HLTH-015: README var stadig Vite-template og gav derfor ikke korrekt TimeLapse Pro build/run/security/onboarding-overblik.
- Første foreslåede remediation-pakke kobler Git/secrets hygiene, approval-binding i UI/API, API statusfelter og eksplicit legacy/LAB-only disposition af direkte Edge Git update.
- Åbne beslutninger viser, at registeret er en dateret health assessment og remediation-plan, ikke bevis for senere lukning.

Archaeology-konsekvens: `SYSTEM_HEALTH_REGISTER.md` flyttes fra partial/truncated evidence til `READ / EXTRACTED`. Ingen ny `CRITICAL_KNOWLEDGE_GAP` blev identificeret ved strict completion.

Yderligere invariant: **presence/text tests må ikke bruges som evidens for faktisk integration eller runtime outcome; testens attestationsscope følger den adfærd, testen faktisk exercises.**
