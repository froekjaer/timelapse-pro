# TimeLapse Pro — Document Archaeology Closure Ledger

**Dato:** 2026-09-17  
**Status:** WORKING CLOSURE LEDGER — discovery/evidence, ikke autoritativ GRC  
**Branch:** `chatgpt/capability-map-v0-20260916`  
**Relation:** Supplement til `DOCUMENT_ARCHAEOLOGY_INDEX_2026-09-16.md` og `KNOWLEDGE_ARCHAEOLOGY_REGISTER_2026-09-16.md`.

## 1. Formål

Dette dokument fastholder closure-evidence fra den branch-aware Knowledge Archaeology. Det eksisterende archaeology-index er fortsat coverage-indeks; denne ledger registrerer de afsluttende fresh checks, kendte gaps og de vigtigste historiske provenance-kæder, så dataindsamlingen senere kan lukkes uden at forveksle manglende originalkilder med manglende viden.

Ingen historisk status promoveres automatisk til current GRC-status. Supersession er ikke deletion.

## 2. Fresh branch-universum

Fresh pagineret branch-inventering 2026-09-17 viser **139 remote branches** i `froekjaer/timelapse-pro`:

- side 1: 100 branches, næste cursor `100`;
- side 2: 39 branches, næste cursor `139`;
- opslag efter cursor `139`: 0 branches.

Det tidligere tal **138** i `DOCUMENT_ARCHAEOLOGY_INDEX_2026-09-16.md` er derfor stale og skal ikke anvendes som closure-baseline.

Ny branch siden det tidligere snapshot omfatter `chatgpt/api-mtls-20260917`. Første tree/delta-pass viste ikke et nyt historisk dokumentunivers; branchens dokumentation er i høj grad allerede kendte blobs/provenances. Den skal stadig indgå i blob/provenance-regnskabet.

## 3. Closure pipeline og stopregel

Closure følger:

`branches inventoried → document paths discovered → unique blobs → READ/DEDUP/GAP → extracted → conflicts/supersession → proposed authoritative home`

Data collection må først erklæres lukket når:

1. alle 139 aktuelle remote branches er accounted for;
2. alle opdagede dokumentpaths er knyttet til blob SHA/provenance;
3. ingen unik dokumentblob står uklassificeret;
4. alle teknisk læsbare relevante tekstblobs er READ eller DEDUP;
5. binære/oversized/pre-Git-kilder er eksplicit GAP-klassificeret;
6. alle potentielt unikke knowledge gaps er vurderet;
7. current `main` er reconcilet mod archaeology-baselinen;
8. afsluttende fresh branch-check er udført.

**Vigtigt:** Closure betyder ikke nødvendigvis nul tekniske gaps. Closure kan ske med eksplicitte gaps, hvis ingen kendt ulæst kilde efterlader et uidentificeret requirement/capability-domæne.

## 4. GAP-taxonomi

| GAP-type | Betydning | Closure-effekt |
|---|---|---|
| `SOURCE_GAP` | Original/pre-Git kilde er kendt eller refereret, men original blob er ikke recoveret | Blokerer kun hvis unik viden ikke findes andetsteds |
| `BINARY_GAP` | DOCX/PDF/blob er inventorieret, men tekst er ikke faktisk ekstraheret og strict-read | Skal have sekundær evidens eller forblive unresolved |
| `TECHNICAL_GAP` | Kilden/blob findes, men connector/tooling kan ikke levere den læsbart, fx pga. størrelse | Registreres med teknisk årsag og evt. descendants |
| `COVERED_GAP` | Originalen mangler/kan ikke læses, men dokumenteret extraction eller senere direkte kilder bevarer requirement-intent/provenance | Evidence-quality gap, normalt ikke knowledge-loss blocker |
| `CRITICAL_KNOWLEDGE_GAP` | Kendt ulæst kilde kan indeholde et unikt requirement/capability-domæne uden anden evidens | Blokerer knowledge closure |

Status pr. 2026-09-17: der er endnu **ikke identificeret en dokumenteret `CRITICAL_KNOWLEDGE_GAP`**, men dette er ikke det samme som endelig closure. Blob/path reconciliation skal færdiggøres først.

## 5. Pre-Git og tidlig historie

Git-repositoriets første commit 2026-04-01 behandles som **første bevarede Git implementation baseline**, ikke som projektets begyndelse.

Tidlige kilder som `Startkrav.docx`, `ChatGpt-input.docx`, `Chat with Gemini.docx` og `Timelaps-chat.docx` er kendt gennem senere dokumenteret extraction/provenance. De må ikke markeres READ, medmindre originalt indhold faktisk recoveres og gennemlæses.

`AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` fra 2026-05-22 er strict-read og fungerer som vigtig sekundær bro til pre-Git-materialet. Dokumentet beskriver extraction fra 47 dokumenter og bevarer bl.a. update/provisioning/configuration/offline/security-intent fra de ældre kilder.

Evidence-strength skal derfor skelne mellem:

`original directly READ → documented historical extraction → later corroborating source/implementation → reference-only GAP`

## 6. Historisk provenance-kæde: requirements → observed implementation gaps

### 6.1 2026-05-22 — aggregated requirements

Det aggregerede kravregister formaliserer bl.a.:

- Headend-medieret production update frem for direkte Edge→GitHub;
- signeret/immutable artifact med exact source/hash/signer/SBOM;
- hierarchical update/config scope;
- per-target deployment status;
- staged rollout og rollback;
- Edge capture/store-forward-autonomi under netværks-/Headend-udfald;
- zero/near-zero-touch provisioning;
- device key/certificate lifecycle;
- backup/restore/RTO/RPO;
- all operational configuration manageable through governed UI/configuration rather than raw DB/code edits.

### 6.2 2026-05-23 — `SYSTEM_HEALTH_REGISTER.md`

Eksakt historisk kilde:

- path: `Dokumentation/SYSTEM_HEALTH_REGISTER.md`;
- blob SHA: `58bf9b155dd40e8aae67e470558b98e4da058f38`;
- commit: `443c5e0bd9f926f8838143d9fc51f7283fa9072c`;
- parent: `35e937db1fac960c5dba0552315ab1879189e2fe`;
- commit er GPG-verificeret;
- filen blev tilføjet som 273 nye linjer.

Dokumentet er en dateret health/implementation assessment, ikke current runtime truth. Det viser imidlertid direkte, hvordan kravene fra dagen før blev holdt op mod faktisk implementation.

Vigtige historiske findings:

- `HLTH-003`: Edge brugte stadig direkte `git fetch/pull origin main`, i konflikt med Headend-medieret/offline update-intent.
- `HLTH-004`: systemet verificerede signatur på et tag, men installerede derefter `origin/main`; signaturen var derfor ikke nødvendigvis bundet til den faktisk installerede revision.
- `HLTH-005`: UI approval viste environment/scope, men de valgte værdier blev ikke sendt til backend; operatorens forståede approval kunne afvige fra faktisk handling.
- `HLTH-007`: update scope manglede fuld `global|customer|site|camera|device` semantics; camera-scope skulle bindes til `DeviceAssignment`, så fysisk device-udskiftning ikke mister policyhistorik.
- `HLTH-008`: global `PendingUpdate.status` kunne ikke repræsentere sandheden for individuelle rollout-targets; separat `update_targets` blev foreslået.
- `HLTH-009`: policy/maintenance-window kunne være configured/returned uden at blive consumed/enforced af Edge.
- `HLTH-001/002`: exports og secrets i/omkring repo-worktree skabte konkret secret/data leakage-risk.
- `HLTH-010`: manglende production JWT secret kunne falde tilbage til process-generated secret, hvilket gjorde sikker drift afhængig af korrekt miljøkonfiguration.
- `HLTH-012/013/014`: lint/testmiljø/testkvalitet viste, at build/test-presence ikke i sig selv var stærk runtime evidence.

## 7. Invariants med historisk provenance

Følgende invariants er archaeology findings/candidates. De er ikke automatisk nye authoritative GRC-requirements, men skal vurderes under syntesen:

1. **Authorized object = executed object.** Det artifact/state der autoriseres og verificeres skal være identisk med det, der faktisk installeres/eksekveres.
2. **Operator approval binding.** Det mennesket ser og godkender skal være bundet til faktisk action, scope, target-set og relevante constraints.
3. **Aggregate state må ikke erstatte target truth.** Fleet/update-status skal bevare individuel target-state og failures.
4. **Configured ≠ consumed ≠ executed ≠ verified.** En parameter/policy er ikke operational evidence blot fordi den findes eller returneres.
5. **Logical assignment survives physical replacement.** Governance, konfiguration, historik og capture provenance skal følge logisk camera/site assignment ved hardwareudskiftning, mens hardware/private trust identity ikke ukritisk kopieres.
6. **Supersession ≠ deletion.** Et gammelt krav må ikke dø alene ved at forsvinde fra nyere dokumenter; change/supersession skal kunne forklares.
7. **Security enforcement at authority boundary.** UI hiding/labels er ikke adgangskontrol; restrictions skal håndhæves ved autoritativ enforcement boundary.
8. **Evidence scope is bounded.** Automated tests kan ikke alene attestere fysisk/runtime capability, som de ikke faktisk har exercised.
9. **Recovery/safety failure-domain separation.** En safety/recovery-mekanisme bør ikke afhænge af samme runtime/dependencies/failure domain som komponenten den skal redde.
10. **Capture-plane priority.** Scheduled capture må ikke være afhængig af eller unødigt forsinket af Headend, Internet, upload, heartbeat, inventory eller management communication.

## 8. Camera direction og migration

Archaeology skal bevare følgende distinction:

- Nikon er strategisk/default retning for nye installationer.
- Fungerende understøttede legacy Canon-kameraer er ikke automatisk obsolete.
- En defekt legacy Edge skal kunne erstattes af TimeLapse Pro Edge uden tvunget udskiftning af et fungerende understøttet kamera.
- Camera compatibility skal evidensklassificeres: `declared compatible → lab verified → physical production verified → currently supported`.

Dette er både camera-abstraction og lifecycle/migration-intent.

## 9. Current-main reconciliation

Archaeology PR #243 blev oprettet mod en ældre `main`-base. Fresh check 2026-09-17 viste, at `main` siden var flyttet frem.

Delta-pass fra den tidligere archaeology-base til fresh `main` viste primært governance/capability documentation, loader/preamble og tests; der blev ikke identificeret et nyt historisk requirement-domæne i dette delta.

Nyere capability/governance-materiale understøtter separationen:

`decision/architecture accepted ≠ implemented ≠ verified`

og kæden:

`Capability/invariants → Usecases → implementation/history → automated verification → runtime/physical evidence`.

Archaeology-resultatet skal derfor fodre eksisterende authoritative homes; det må ikke blive et konkurrerende GRC-register.

## 10. Kendte tekniske/source gaps

### 10.1 `Startkrav.docx` og øvrige pre-Git originals

Originalerne er endnu ikke direct-read. `Startkrav.docx` blev forsøgt hentet via en antaget historisk path, men pathen returnerede 404. Det beviser ikke, at dokumentet aldrig var i historikken; exact historical path/tree recovery skal være grundlaget for endelig disposition.

Krav fra `Startkrav.docx` og relaterede tidlige kilder findes delvist som documented secondary extraction i 2026-05-22-registeret. Indtil original recovery er udtømt klassificeres de som `SOURCE_GAP`, med mulighed for `COVERED_GAP` pr. requirement.

### 10.2 Oversized historical markdown

`Dokumentation/Gamle versioner/2026-06-03-Timelapse - Risk og plan videre.md`, kendt blob SHA `b8b44eeb02c15b365d84e90b208cbb447d2ceef8`, er ca. 1.16 MB og har ikke kunnet direct-read gennem den aktuelle connector pga. response-size-begrænsning.

Status: `TECHNICAL_GAP / OVERSIZE_SOURCE`. Senere extraction/descendants kan bruges som sekundær evidens, men originalen må ikke markeres READ.

### 10.3 Historical DOCX families

Flere kendte historiske DOCX-versioner — bl.a. Configuration Guide, SABSA Architecture/Risk, Edge Runbook og Roadmap-familier — må stå `BINARY_GAP`/`BINARY_PENDING_EXTRACTION`, indtil teksten faktisk er ekstraheret og strict-read eller en eksplicit covered-gap disposition er dokumenteret.

## 11. Closure assessment — foreløbig

Archaeology har efterhånden vist et stabilt mønster: senere fundne historiske kilder giver hovedsageligt bedre provenance, rationale og conflict chains til allerede identificerede requirement/capability-familier frem for helt nye domæner.

Der er pr. denne ledger ikke evidens nok til at erklære **100 %** eller `DATA COLLECTION CLOSED`. Der mangler især:

- endelig branch→path→blob reconciliation for alle 139 branches;
- endelig unique-blob count;
- disposition af resterende binary/pre-Git/oversize sources;
- dokumenteret vurdering af om nogen af disse er `CRITICAL_KNOWLEDGE_GAP`;
- sidste fresh branch/main reconciliation ved closure-tidspunktet.

Når disse punkter er opfyldt, kan dataindsamlingen lukkes med eksplicitte tekniske/source gaps, hvis antallet af `CRITICAL_KNOWLEDGE_GAP` er nul.

## 12. Næste fase efter closure

Efter closure skal knowledge ikke blot kopieres til GRC. Syntesen skal følge:

`Knowledge Register → dedupe → requirement/change/conflict chains → current intent determination → authoritative GRC/capability/ADR/usecase/history placement → implementation mapping → verification → runtime evidence`.

Golden Capabilities fryses først efter denne syntese og efter at historiske krav har fået mulighed for at udfordre nyere dokumentation.
