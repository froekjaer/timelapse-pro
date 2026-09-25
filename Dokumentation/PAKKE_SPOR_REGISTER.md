# Pakke-/spor-register — åbne branches og PR'er på tværs af AI-sessioner

> **Fælles reviewrunde (historisk):** [Reviewpakke v1.0](PAKKE_GOVERNANCE_REVIEWPAKKE_2026-09.md) — fastlåst baseline, beslutningspunkter og fælles svarskabelon brugt frem til Peters accept af ADR-003 + §14 (2026-09-13). Se §Governance-afslutning nedenfor for den aktuelt gældende status.

**Formål:** supplement til `HANDOVER_LOG.md`. Handover-loggen er kronologisk og god til
"hvad skete der i denne opgave"; dette register er et **stående overblik** over hvilke
pakker (branches/PR'er) der er åbne *lige nu*, så ingen session — Claude, Codex, Kimi
eller Peter — starter et nyt spor uden at vide at et overlappende spor allerede findes,
og ingen glemt branch rådner uden at nogen bemærker det.

**Proces:** se `ADR/ADR-003-pakke-hygiejne-mod-legacy-branches.md` for reglen dette
register understøtter. Kort version: før du merger eller opdaterer en pakke, tjek denne
liste for overlap; efter merge, ret listen til.

**Sidst opdateret:** 2026-09-13 (Claude, efter Peters forespørgsel om #214/BEHIND-status; Kimi: tilføjet målt branch-sweep, se §Backlog; Claude igen: #159/#163/#214/#229 migreret til §14.6 fulde felter, rapporterede stashes/worktrees tilføjet, intern modsigelse om accept-status rettet; Claude igen (F2): stash-observation opdateret fra 3 til 5 efter Kimis nyere rapport; **Kimi senest (reconciliation-mandat 2026-09-13):** #229 lukket uden merge, #214 rebased til `bde560eb` (CLEAN, CI grøn), semantisk restanalyse af #163 og #159 udført — se de enkelte spor; **Claude (2026-09-14):** #239 (edge-terminal xterm.js) og #240 (Capability Register-forslag) registreret som fulde §14.6-spor efter et P1-fund i #240s egen adversarial review paapegede at de manglede)

---

## Åbne spor — fulde felter (§14.6)

Disse spor ændrer kode, sikkerhed eller den fælles governance-tekst og er derfor
**fulde spor** efter §14.6 — ikke lette spor. #229 er lukket 2026-09-13 (se nederst
i sektionen) og er ikke længere et åbent spor. Base/head-SHA'er er hentet frisk
2026-09-13T10:58Z; #214's SHA er opdateret efter rebase 2026-09-13T~15:10Z. SHA'er ældes med
tiden — se PR'en for den aktuelt gældende SHA, ikke kun tallet her.

### #258 — `chatgpt/apple-intelligence-provider-20260924`

- **Mandat/session:** ChatGPT, fortsat under Peters eksplicitte mandat til at arbejde videre 2026-09-25.
- **Formål/scope:** Generisk AI-provider-arkitektur med Apple Foundation Models som lokal provider uden at fjerne Ollama/Gemini; fysisk LAB-benchmark og menneskereviewet ground truth. Seneste delspor bringer benchmark-konteksten tættere på produktion ved read-only autoritativ vocabulary og samme Gemini settings/environment-path som Headend.
- **Berørte domæner/kontrakter:** `headend/ai/apple_foundation_service.py`, `headend/ai/integration.py`, `headend/ai/provider_config.py`, `headend/ai/tag_vocabulary.py`, `headend/tools/compare_ai_providers.py`, AI strategy/UI, provider provenance, benchmark/GRC-dokumentation.
- **Base/head:** PR #258, draft mod `main`. Verificeret 2026-09-25: base `b901d486733d69733bad2f21dfa42354573b6aba`, head `c2a712f59e127a0f0678ac6ea34e23abe7bfeffc`, GitHub rapporterer mergeable=true. SHA'er er snapshots og skal genhentes før merge.
- **Overlap/restdisposition:** Ingen eksisterende post i dette register dækkede #258. Sporet overlapper funktionelt med eksisterende Image AI/Ollama/Gemini-integration, men ændringerne ligger på én samlet PR og må ikke splittes ud som parallel provider-implementation uden ny overlap-analyse. Provider-output forbliver observation, ikke autoritativ sandhed.
- **Seneste verificerede aktivitet/evidens:** TRAVBYEN-001 er menneskereviewet for privacy. Fysisk benchmark v3 på head `90f26484` brugte live approved DB-vocabulary (`effective_source=database`, 37 kategorier / 664 tags, ingen fallback). Apple fandt personforekomst korrekt; Ollama missede den. GitHub Actions run `36113897612` på samme head er completed/success. Det er case-evidence, ikke provider-ranking.
- **Næste handling:** TRAVBYEN-001 benchmark v3 og CI er accepteret. Udvid nu til 10–20 repræsentative, menneskereviewede captures med live database vocabulary; tilføj derefter Gemini via autoritativ Headend-konfiguration. Ingen provider-defaults/prompttuning før repræsentativt ground truth.
- **Blokeringsansvarlig:** Teknisk acceptance: ChatGPT/næste AI-session. Fysisk Headend-run og merge-beslutning: Peter.
- **Opfølgning:** Før merge, efter fysisk benchmark v3 og når reviewed corpus udvides.

### #214 — `claude/globalconfig-parallel-load`

- **Mandat/session:** Claude (oprindelig forfatter). Rebase udført af Kimi 2026-09-13 under Peters mandat.
- **Formål/scope:** Fjern unødig sekventiel netværkstur i `GlobalConfigPage.tsx::loadBase()` — samme waterfall-mønster som #213 (UsersPage).
- **Berørte domæner/kontrakter:** `timelapse-ui/src/pages/GlobalConfigPage.tsx` (frontend). Ingen kendt overlap med andre åbne spor.
- **Base/head:** PR #214, head **`bde560eb0c0922e631d997edfb8284f6af4464e1`** (rebased af Kimi 2026-09-13T~15:10Z på main `ebd98fff`, force-with-lease), base `main`. Efter rebase: `mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`.
- **Overlap/restdisposition:** Ingen overlappende pakke rører samme fil (verificeret ved diff mod main). Intet restkrav udestår.
- **Seneste verificerede aktivitet/evidens:** Rebase 2026-09-13 uden konflikter; lokal `npm run build` (tsc + vite) bestået efter rebase; CI efter push: Python Syntax Check SUCCESS, Web UI Build Check SUCCESS. Ændringen verificeret læst: `api('/api/admin/users')` flyttet ind i det eksisterende `Promise.all` med bevaret `.catch(() => [])` — samme fejlsemantik, blot parallel.
- **Næste handling:** Klar til Peters merge-beslutning. Ingen yderligere teknisk blokering.
- **Blokeringsansvarlig:** Ingen aktiv blokering — afventer Peters merge-godkendelse.
- **Opfølgning:** Ved merge.

### #163 — `codex/edge-post-restart-health-handshake`

- **Mandat/session:** Ingen aktiv udfører bekræftet. Oprindeligt Codex (branch oprettet 2026-08-30). Claude har leveret en PR-kommentar med konfliktanalyse, ikke kodeintegration.
- **Formål/scope:** Post-restart health-stabilitetsvindue for app-updates + Headend-sweeper der markerer hængende post-restart-handshakes som `failed`/`blocked`.
- **Berørte domæner/kontrakter:** `edge/agent.py`, `edge/update_lifecycle.py`, `edge/scripts/watchdog.sh`, `headend/main.py`, `headend/services/post_restart_health.py`.
- **Base/head:** PR #163, head `4c0cfba268da35af3b213a1a628ffb5d40cfdfa3`, base `main`. Ved hentning 2026-09-13T10:58Z: `mergeStateStatus=DIRTY`, `mergeable=CONFLICTING`.
- **Overlap/restdisposition:** Main har selvstændigt videreudviklet samme kodeområde under andre navne (`mark_pending_app_update_health_confirmed`/`awaiting_restart_health` i `edge/update_lifecycle.py`, verificeret ved `git merge-tree`). **Semantisk restanalyse udført af Kimi 2026-09-13** (i eksisterende clean worktree `timelapse-pro-edge-health-handshake`, head `4c0cfba2`): Branchens kerne er (a) **stabilitetsvindue** — `record_pending_app_update_health_probe(stability_s)` kræver at edge rapporterer sundhed *kontinuerligt i et konfigurerbart antal sekunder* efter restart, ikke kun én bekræftelse; (b) **Headend-sweeper** `sweep_stale_post_restart_update_handshakes()` i ny fil `headend/services/post_restart_health.py` der markerer hængende handshakes `failed`/`blocked` efter timeout (1800s). **Ingen af delene findes på main** (verificeret: filen findes ikke; `grep` efter `stability_s`/`consecutive`/sweep-logik i main's `edge/update_lifecycle.py` og `headend/` giver intet). Main's eksisterende `mark_pending_app_update_health_confirmed` er et engangs-flag, ikke et stabilitetsvindue. **Reelt konfliktområde ved integration:** `edge/agent.py` (main refaktoreret), `headend/main.py` (main modulariseret), `headend/tests/test_update_lifecycle.py`, HANDOVER_LOG. **Korrekt integration kræver:** genimplementering af stabilitetsvindue + sweeper mod aktuel main-struktur (ikke blot rebase), herunder at sweeperen registreres i main's nuværende service-/routeropbygning, samt gentest.
- **Seneste verificerede aktivitet/evidens:** PR-kommentar med konfliktanalyse, 2026-09-13. Kimi semantisk restanalyse 2026-09-13 (se Overlap/restdisposition). Ingen ny commit på branchen siden 2026-08-30.
- **Næste handling:** Peters beslutning om ønsket funktionalitet; derefter genimplementering (ikke blot rebase) mod aktuel main + gentest, før merge/deploy. Sporet som R03 i `Pakke_Governance_Review_2026-09/DISPOSITION.md`.
- **Blokeringsansvarlig:** Udfører ikke bekræftet — afventer eksplicit overdragelse (§14.5). Ingen automatisk tildeling til seneste forfatter.
- **Opfølgning:** Før første merge/deploy fra sporet.

### #159 — `codex/fix-capture-time-and-edge2-evidence`

- **Mandat/session:** Ingen aktiv udfører bekræftet. Oprindeligt Codex (branch oprettet 2026-08-29). Claude har leveret en PR-kommentar med konfliktanalyse, ikke kodeintegration.
- **Formål/scope:** Eksplicitte lokal-/UTC-/tidszonefelter fra capture-liste- og timeline-API'et, så thumbnail-tidsstempler ikke afhænger af browserens tidszonegæt.
- **Berørte domæner/kontrakter:** `headend/main.py`, `headend/capture_api_helpers.py` (ny, ren tilføjelse — ingen konflikt), `timelapse-ui/src/pages/DevicePage.tsx`, `timelapse-ui/src/components/CaptureThumbnailCard.tsx`, `timelapse-ui/src/lib/captureTime.ts`, `timelapse-ui/src/types/index.ts`.
- **Base/head:** PR #159, head `eaa0289267f67edd734a7aa28ea18380d4afd0e8`, base `main`. Ved hentning 2026-09-13T10:58Z: `mergeStateStatus=DIRTY`, `mergeable=CONFLICTING`.
- **Overlap/restdisposition:** `DevicePage.tsx`/`CaptureThumbnailCard.tsx` er ændret uafhængigt på main af senere lightbox-/prefetch-arbejde. **Semantisk restanalyse udført af Kimi 2026-09-13:** Branchens kerne — felterne `captured_at_local` / `captured_at_utc` / `captured_at_timezone` i capture-liste- og timeline-API'et — findes **ikke** i main's API-svar (verificeret: 0 forekomster i `headend/main.py` på main; kun `headend/importer.py:229` har en lignende `_to_local`-linje i import-stien, ikke i API-svaret). `headend/capture_api_helpers.py` og `timelapse-ui/src/lib/captureTime.ts` findes ikke på main. Merge-test mod main: auto-merge lykkes for `requirements.txt`, `CaptureThumbnailCard.tsx`, `DevicePage.tsx`, `types/index.ts`; **konflikt kun i `headend/main.py`** (modularisering) og HANDOVER_LOG (kronologisk, triviel). **Korrekt integration kræver:** genplacering af API-felterne i main's modulariserede struktur (formentlig capture-relateret modul), ikke blot konfliktløsning, plus gentest af kontrakttesten `test_capture_time_metadata_contract.py` mod main.
- **Seneste verificerede aktivitet/evidens:** PR-kommentar med konfliktanalyse, 2026-09-13. Kimi semantisk restanalyse 2026-09-13 (se Overlap/restdisposition). Ingen ny commit på branchen siden 2026-08-29.
- **Næste handling:** Peters beslutning om ønsket funktionalitet; derefter genimplementering mod main's modulariserede struktur + gentest, før merge/deploy. Sporet som R03 i `Pakke_Governance_Review_2026-09/DISPOSITION.md`.
- **Blokeringsansvarlig:** Udfører ikke bekræftet — afventer eksplicit overdragelse (§14.5).
- **Opfølgning:** Før første merge/deploy fra sporet.

### #229 — `claude/pakke-hygiejne-adr` — **LUKKET 2026-09-13**

- **Status:** Lukket uden merge af Kimi 2026-09-13 under Peters mandat, efter verifikation mod aktuel main (`ebd98fff`): PR'ens 4 filer (00_START_HER, ADR-003, ADR/README, register) findes alle på main i videreudviklet form via #230→#231→#232. Kerneindhold spot-tjekket til stede (pakke-hygiejne, overhalet-og-arkiveret, Åbne spor; ADR-003 Accepted). Lukkekommentar på PR'en refererer #232 som erstatning.
- **Rest:** Ingen. Branchen `claude/pakke-hygiejne-adr` **slettes ikke** her — oprydning følger den samlede R04-triage (§14.4). PR-lukningen bevarer GitHub's `refs/pull/229/head` som recovery-reference.

### Rapporterede, ikke-verificerede lokale tilstande

Disse er reconciliation-input fra andre sessioner, **ikke** verificeret af denne leverance,
og ikke inspiceret eller ændret her (jf. scope-grænsen "ingen branch-/worktree-/stash-sletning
eller -undersøgelse i denne opgave):

- **Kimi rapporterer 5 delte, lokale stashes** i det fælles repository (nyere observation,
  afløser den tidligere rapport om 3 — ikke undersøgt her, og GitHub kan ikke verificere
  lokal stash-state):
  `stash@{0}` "codex preserve generated source inventory", `stash@{1}` "PR #92 edge
  image-deletion rebuild", `stash@{2}` "pre-headend-deploy-cmdb-main-duplicate-20260824",
  `stash@{3}` "edge-terminal-renderer safety backup", `stash@{4}` "wp4-in-progress".
  Status: **Kimi-reported / local verification pending** — fremstilles ikke som verificeret
  repository-state. `stash@{3}` er nu read-only inspiceret (ikke poppet/droppet) i forbindelse
  med shell-endpoint-assessmenten nedenfor: dens eneste berøring af `edge/scripts/totp-service.py`
  er en urelateret kosmetisk UI-tekstændring, ikke relevant for shell-sikkerhedsspørgsmålet.
- **Claude rapporterer yderligere lokale worktrees** på maskinen ud over dem der er i aktivt
  brug i denne governance-leverance (fx flere `timelapse-pro-*`-mapper knyttet til ældre
  Codex-spor). Deres clean/uncommitted-tilstand er ikke undersøgt. Status: **reported /
  local verification pending**.

Ingen af disse må antages tomme, forældede eller sikre at fjerne, før en session med
mandat til det faktisk har inspiceret dem.

## Reserverede/planlagte spor (ikke startet endnu — nævnt i eksisterende dokumentation)

| Emne | Reference | Status |
|---|---|---|
| ADR-002 — payload-pakkeformat, signering, proces-sandbox, control/data-plane-kontrakter | Nævnt i `ADR-001` §Afgrænsning, `Claude_QA_Review_2026-07-17.md`, `HANDOVER_LOG.md` (flere entries) | Uskrevet. Start ikke en branch under navnet "ADR-002" uden at have læst disse referencer først. |

## Backlog — historisk oprydning (ikke del af denne ADR's proces, men samme bekymring)

Ved den oprindelige forespørgsel blev **127 remote branches** rapporteret uden en bevaret, frosset population. Det er en historisk kontekst-observation, ikke et verificeret beslutningsgrundlag. De senere bevarede populationer er 122 og 123 reelle branches; deres indbyrdes forskel er dokumenteret nedenfor. Forskellen til 127 kan ikke rekonstrueres præcist uden den oprindelige råliste og må ikke tilskrives bestemte mutationer som bevist. De tre oprindelige PR'er blev kun indledningsvist screenet.

### Branchscreening med bevaret population

Aktuelt evidenssæt: [BRANCH_SCREENING.json](Pakke_Governance_Review_2026-09/BRANCH_SCREENING.json) og [rå remote-refs](Pakke_Governance_Review_2026-09/BRANCH_REFS_FROSSET.tsv). Metode og reproduktion findes i [dispositionspakken](Pakke_Governance_Review_2026-09/DISPOSITION.md).

Codex-observation `2026-09-13T08:45:40.420260+00:00`, base `13a0d3b3af67a36adf9115d0911aaf2a687bca15`: **123** remote branches ekskl. main = **13** ancestry-merged + **110** ikke-ancestry-merged; de 110 = **51** uden plus-markerede patches + **59** med plus-markerede patches. Alle summer kontrolleret. Hver post indeholder head/base-SHA og rå git-cherry-output. Ingen af kategorierne er sletteautorisation eller semantisk triage.

Historisk korrektion: de tidligere 127/112/57/56-tal er trukket tilbage som uafklaret population. [Kimis originale evidensbilag fra 499d266d](Pakke_Governance_Review_2026-09/KIMI_EVIDENS_ORIGINAL.md) er nu bevaret uændret med checksum. Dets 124 refs omfatter main og et HEAD-alias `origin`. Når begge udelades, er den reelle population **122 = 13 ancestry-merged + 109 øvrige; 109 = 51 plusfri + 58 med restpatches**. Refantal, klassifikationsantal, SHA-sammenhæng og summer er kontrolleret mod bilaget; den historiske kommandokørsel er ikke rekonstrueret ud fra hukommelse.

Sammenligning af de to bevarede populationer viser præcis én tilføjelse i Codex' senere måling: `origin/kimi/review-pakke-governance-20260913`. Ingen fælles head-SHA'er har ændret sig, og ingen refs fra Kimis reelle population mangler. Dermed er forskellen 122/123 og 58/59 forklaret ved konkrete data. Det er populations-/konsistenskontrol, ikke semantisk triage eller sikker sletning.

`git cherry` sammenligner individuelle patch-ID'er. Aggregate squash-merges, merge-commits og semantisk ækvivalens kræver særskilt review. Ved gentagelse klassificeres de gemte SHA'er, ikke levende branchnavne. En ny remote-liste er en ny observation.

Kimi har rapporteret syv remote-branchsletninger; originalrapporten bevares. Ingen branch er slettet i denne review-/slutkandidatrunde.

### Resterende oprydning

- [ ] Genoptæl og triagér branches med uabsorberede patches én for én (ADR-003-processen:
      overhalet-med-begrundelse / rebase-og-merge / afventer Peter). Prioritér nyeste først.
- [ ] Revurder kandidater med patch-ækvivalens. Før eventuel oprydning: afklar restindhold, aktive ejere/worktrees, uncommitted/untracked data, release/rollback-afhængigheder og holdbar recovery-reference. Ingen automatisk sletning.
- [ ] Efter sweep: opdatér denne sektion med resultat, eller fjern den hvis sweepen er
      udført og ikke fandt yderligere glemt arbejde.

## Hvordan du bruger dette register

**Før du starter en ny pakke:** tjek om noget i "Åbne spor" allerede rører de filer/det
domæne du er ved at gå i gang med. Hvis ja — læs den PR/branch, afgør om dit arbejde
supplerer, erstatter eller er redundant med det, og sig det til Peter hvis det er uklart.

**Før du merger eller opdaterer en pakke til at følge main:** tjek at intet i "Åbne spor"
bliver overskrevet af din merge uden at være taget stilling til. Se `ADR-003` for den
fulde proces.

**Efter en merge:** flyt den mergede pakke ud af "Åbne spor". Hvis dit arbejde gør et
andet åbent spor helt eller delvist overflødigt, noter det i sporets række (ikke bare
tavshed) og giv besked i `HANDOVER_LOG.md`.


## Fælles drift af registeret

Følg [samarbejdsmodellen §14](SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md#14-bindende-regel-for-pakker-spor-og-reconciliation). Registeret er et dateret koordineringsindeks, ikke en distribueret lås eller erstatning for Git/GitHub, GRC og CMDB. Skriv altid PR # eller update #; numrene er forskellige identiteter.

Hver aktiv post kræver session/ejer, formål/domæne, base/head-SHA, relationer/overlap, restkrav og disposition, test-/runtimebevis, næste handling, blokeringens ansvarlige og dateret opfølgning. Status skelner registreret, aktiv, afventer reconciliation, blokeret, integreret, verificeret og overhalet-og-arkiveret. Ukendt ejerskab er en afklaringsopgave, ikke accepteret permanent tilstand. En forældet dato giver ikke ret til at overtage en andens arbejdsmappe.

**Tilføjet 2026-09-16 (Governance Propagation-integration, jf. §16.10 og OP-001 Step 7):** et fuldt spor (§14.6) for en consequential ændring kræver desuden et **cross-repo/website-paavirkning**-felt, med præcis ét af tre reviewbare svar (ingen bar afkrydsning):
1. **Identificeret + propageret** — berørte mål (repo/artefakt/publikation) navngivet, og opdateringen dér udført/verificeret; henvis til den konkrete ændring.
2. **Ingen paavirkning fundet, evidensbaseret** — den negative konklusion er understøttet (jf. OP-001 Step 7's evidensstandard: Verified/Derived, ikke Assumed), ikke en antagelse; angiv hvad der blev tjekket.
3. **Uafklaret gab** — henvis til en Mission Framework Finding (fx `FF-TLP-0001`) eller et navngivet opfølgningspunkt i dette register, med ejer og disposition.

Feltet gælder fremadrettet fra denne dato og ved næste substantielle review ELLER HANDLING paa et
eksisterende spor — **"handling" inkluderer eksplicit merge, lukning, genoptagelse af implementering,
eller enhver anden disposition af sporet, ikke kun en formel skriftlig gennemgang.** Et spor der blot
staar og venter paa Peters merge-beslutning (fx #214, som pt. ikke har feltet) skal faa feltet udfyldt
**som en del af** den handling der merger/afslutter det — merge alene, uden at udfylde feltet foerst,
er en bypass af denne regel, ikke en undtagelse fra den. Eksisterende åbne spor (#214/#163/#159
nedenfor) er **ikke** baglæns udfyldt med dette felt alene for fuldstændighedens skyld; det tilføjes
naar sporet alligevel revideres ELLER der handles paa det.

| Spor | Koordinationsansvar | Næste handling / blokering | Opfølgning |
|---|---|---|---|
| Sammenlægning af de tre input | Codex, denne session | Verificér dokumenter og lever samlet PR | Denne session |
| Historisk branchtriage (R04) | **Overdraget til Claude 2026-09-13** (Peter, eksplicit mandat — Kimi utilgængelig et par uger). Kimi pilot 1 (8 branches) + Claude batch 2 (9 branches, 1 stop-gate) udført. Se `R04_BRANCHTRIAGE_PILOT_1_2026-09-13.md` (Kimi, bevaret uændret) og `R04_BRANCHTRIAGE_BATCH_2_2026-09-13_CLAUDE.md` (Claude, ny). | 17 af ~59 branches triageret. `codex/edge-terminal-renderer` er et åbent stop-gate-fund (aktivt shell-endpoint, konflikt med `agent/core-design-principles`, tilknyttet stash@{3}) — afventer Peters beslutning før videre batches. | Efter Peters beslutning om stop-gate-fundet |
| `agent/core-design-principles` (R04-fund) | Claude, semantisk analyse 2026-09-13 — se `Arkitektur/CORE_DESIGN_PRINCIPLES_ANALYSE_2026-09-13_CLAUDE.md` | Reelt arkitektonisk divergens fundet mellem dokumentets Del II (Bluetooth Local Service Gateway) og mains faktiske, simplere BLE-teknikerløsning. Peter skal beslutte retning (arkivér/udvid/ny ADR) | Peters beslutning |
| PR #163 og #159 | Codex for næste vurdering | Frisk restanalyse/rebase i isoleret worktree; dette dokumentarbejde udfører ikke kodeintegrationen | Næste integrationssession, senest ønsket 2026-09-14 |
| PR #214 | Codex for koordinationsafklaring; oprindeligt Claude | Genbekræft ejer, main/head og CI før disposition | Næste integrationssession, senest ønsket 2026-09-14 |
| PR #229 | Codex for reconciliation | Undersøg restdiff mod #230/fælles resultat før lukning; ingen tavs kassation | Ved fælles PR-afslutning |
| Codex-forslag dc171e42 / 1a26103e | Codex | Procedure og Framework/Platform-input overført; historisk 333-ref/27-worktree-snapshot bevares i original commit som recovery-indeks, ikke aktuel status | Ved fælles PR-afslutning |
| Updates #273/#298/#272/#275–#280 | Codex for næste kontrol, Peter for nødvendige driftsbeslutninger | Frisk CMDB/pakkesæt og kompatibilitet/recovery før installation. Ingen installation som del af governance-merge | Før genoptagelse af update-opgaven |
| Framework/Platform-feedback | Codex | Samlet input §15 findes; upstream-review/disposition udestår | Efter fælles dokumentreview |

Datoer er opfølgningskrav, ikke bevis for kørende baggrundsarbejde. Ingen scheduler er oprettet. Udføreren skal ved næste session gennemgå forfaldne/uejede opgaver og udføre næste skridt eller synliggøre prioriteringsbeslutningen. Påstå ikke at alle opgaver allerede er under udførelse.

### Disposition af de tre forslag

- Claude: ADR-003, oprindeligt register, indekshenvisninger og konfliktanalyse bevares fra #230.
- Kimi: historisk sweep og fokus på squash/patch-ækvivalens bevares; tal og slettekonklusion korrigeres ovenfor, ingen sikker slettepopulation erklæret.
- Codex: §14/§15, agentloadere, opfølgning og rest-/recoverykrav integreres. Den lange historiske inventarliste kopieres ikke ind som et andet aktivt register; den er stadig genskabelig fra `dc171e42` på den bevarede forslagsbranch.
- Fravalgt: automatisk sletning ud fra alder/0 patches; implicit ADR-accept ved merge; udokumenteret påstand om fuld triage. Selve indholdet og historikken bevares med begrundelse.


## Ejerskab og aktivitet — præcisering efter review

Koordinationstabellens tidligere "Codex"-rækker er forslag til næste koordinering, ikke permanent mandat eller bevis for aktivitet. Bekræftet mandat i denne runde (historisk, forud for accept): **Codex / session med PR #232, udpeget af Peter til reviewsammenlægning**; senest verificeret aktivitet ved den tid: kandidatens commit og handover. **Opdateret 2026-09-13:** Peter har siden registreret formel accept af ADR-003 + §14 (se ADR-003 Accept-linje og §Governance-afslutning nedenfor); "før endelig ADR-accept" beskriver derfor ikke længere den aktuelle tilstand. Mandatet for de resterende konsistensrettelser på #232 blev efterfølgende midlertidigt overdraget til Claude, mens Codex-sessionen var utilgængelig (se HANDOVER_LOG.md, denne dato).

For branchtriage, PR-rebases, scheduler og Platform-implementering er aktiv udfører **ikke bekræftet**; blokering: prioritering/overdragelse skal afklares. Peter er beslutningsejer, Codex samler de konkrete næste leverancer i dispositionspakken. Ved næste session skal de tidligere opfølgningsdatoer kontrolleres, og aktivitet markeres uverificeret, hvis der ikke foreligger nyt bevis. Ingen automatisk overtagelse eller stille fristforlængelse.

Let spor og fuldt spor følger §14.6; kontrakt-/governanceændringer er fulde spor. Git/PR leverer revisioner og commits, så de ikke skal kopieres manuelt i alle felter. Oprindeligt reviewmateriale og alle fund/dispositioner findes i [reviewdispositionen](Pakke_Governance_Review_2026-09/DISPOSITION.md).

## Partner- og kompetenceudvidelse 2026-09-13

PR #232 udvides efter Peters instruktion med faste deltagere Kimi/Z.ai samt ad hoc-onboarding og [kompetence-/routingforslag](AI_KOMPETENCER_OG_OPGAVEROUTING.md). Udfører: Codex i samme isolerede reviewspor. Næste handling: dokumentreview af udvidelsen og budgetafklaring før eventuel pilot. Tidligere genreviews gælder den tidligere kandidat, ikke dette nye scope. Ingen runtime- eller upstream-ændring.

### Cross-repo placeringsoplæg

Peter autoriserede 2026-09-13 undersøgelse og forslag til CI/Framework/Platform. Codex har leveret konkret destinations- og pilotoplæg i kompetencedokumentets §8, inklusive fundet uoverensstemmelse i CI-programkortet. Aktiv leverance: dette oplæg i PR #232. Upstream-ændringer/pilot er ikke udført; næste handling er review og afgrænsede upstream-forslag med frisk overlapkontrol. Den eksisterende §14-procedure kan anvendes uafhængigt af routingforslaget.

## Edge lokal shell-endpoint — sikkerhedsassessment 2026-09-13

Peter mandaterede en read-only arkitektur-/sikkerhedsassessment af main's eksisterende
`/mgmt/cli/bash/*` (Bluetooth TOTP-portal, `edge/scripts/totp-service.py`), affødt af
R04-stop-gate-fundet om `codex/edge-terminal-renderer`. Se
[EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md](EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md)
for fuld evidens. Kernefund: endpointet giver en uaudited, fuldt privilegeret (root)
interaktiv shell, uden den samme session-audit main allerede har for den sammenlignelige
break-glass SSH-mekanisme. Eksplicit markeret som en sikkerhedsrisiko til Peters beslutning
— ingen ændring af endpointet foretaget. R04 batch 3 afventer denne beslutning.

## Lifecycle-beslutning: edge shell-adgang (ADR-004, Proposed) — 2026-09-13

Efter R04-stop-gate-fundet om `codex/edge-terminal-renderer` (se PR #235) og en read-only
sikkerhedsassessment af `/mgmt/cli/bash/*` (se PR #236) har Peter truffet en eksplicit
lifecycle-beslutning: general-purpose/root shell-adgang på edge er en **bevidst accepteret
development/stabilization-capability** i denne fase — den fjernes, begrænses eller erstattes
IKKE af typed operations før et fremtidigt, evidens-udløst review (ikke en dato). Se
[ADR-004](ADR/ADR-004-development-and-recovery-shell-access.md) (Proposed).

To opfølgende anbefalinger (ingen implementering udført endnu):
- [SHELL_SECURITY_IMPROVEMENTS_2026-09-13_CLAUDE.md](SHELL_SECURITY_IMPROVEMENTS_2026-09-13_CLAUDE.md) — additive audit-/session-logging der genbruger det eksisterende break-glass-mønster, uden ny Headend/netværksafhængighed.
- [R04_EDGE_TERMINAL_RENDERER_ANBEFALING_2026-09-13_CLAUDE.md](R04_EDGE_TERMINAL_RENDERER_ANBEFALING_2026-09-13_CLAUDE.md) — `codex/edge-terminal-renderer` omklassificeret fra "stop-gate/uønsket" til "indeholder reelle, genbrugelige robusthedsforbedringer" (multi-IP session-tracking, aktiv shell-oprydning ved session-udløb, polling-transport, xterm.js). Anbefaling: scoped reimplementering, ikke direkte merge af hele branchen. Stash/provenance urørt.

`agent/core-design-principles`s "No General-purpose Shell"-princip er **ikke** kasseret — det
forbliver et muligt fremtidigt målprincip, som ADR-004 midlertidigt fraviger i denne fase.

## Edge shell-robusthed — scoped implementering 2026-09-13 (afventer fysisk-edge-test)

Peter godkendte retningen i ADR-004 (Proposed, afventer afprøvning på rigtig edge før
formel accept) og gav mandat til scoped implementering af multi-IP session-tracking,
shell-session-cleanup ved expiry/logout, og local-first audit-logging (genbrug af
break-glass-mønstret). Implementeret mod `origin/main` = `d04798e4`, se
[SHELL_ROBUSTNESS_IMPLEMENTATION_2026-09-13_CLAUDE.md](SHELL_ROBUSTNESS_IMPLEMENTATION_2026-09-13_CLAUDE.md)
for fuld detalje, tests og kendte rests. Polling-transport og xterm.js er bevidst
udskudt — kræver fysisk-edge/live-browser-verifikation. Ingen merge udført; separat PR
fra #235/#236/#237.

## Edge-terminal xterm.js-genbrug — #239 (afventer fysisk-edge-test)

- **Mandat/session:** Claude, 2026-09-13, efter Peters fysiske test viste at #238s direct-Edge-terminal havde en daarlig emulator (Ctrl-C/Tab/pil-taster/Home-End fejlede).
- **Formaal/scope:** Erstat den haandrullede ANSI-strippende textarea-renderer med xterm.js (samme bibliotek/version som Headends "Aabn terminal"), vendoret lokalt. Behold #238s websocket-transport, multi-IP-robusthed, session-cleanup og local-first audit uaendret. Ny dynamisk resize.
- **Berørte domæner/kontrakter:** `edge/scripts/totp-service.py`, nye vendorede filer under `edge/scripts/static/xterm/`, `tests/test_edge_technician_terminal_runtime.py`.
- **Base/head:** PR #239, head **`e6e690588dec95a41ef83f4bfdd3ffb59ae0a589`**, base `main`. `mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`.
- **Overlap/restdisposition:** Ingen kendt overlap med andre aabne spor. Se `EDGE_TERMINAL_CAPABILITY_REGRESSION_2026-09-13_CLAUDE.md` for fuld genbrugsarkitektur-begrundelse.
- **Seneste verificerede aktivitet/evidens:** CI groen (Python Syntax Check, Web UI Build Check) efter en `check_dir=False`-rettelse af en StaticFiles-regression. 86/86 relevante tests PASS lokalt. Fysisk Edge-acceptancetest (Ctrl-C, Tab, history, Home/End, resize, offline) IKKE udfoert endnu.
- **Naeste handling:** Afventer Peters review + fysisk Edge-test foer merge.
- **Blokeringsansvarlig:** Peter (fysisk test).
- **Opfoelgning:** Ved fysisk-test-resultat.

## Capability Register-governance-forslag — #240 (review-klart forslag, IKKE implementeret)

- **Mandat/session:** Claude, 2026-09-13/14, efter en uafhaengig arkaeologi-review fandt at Capability Register-forslaget oversaa `UI_USECASE_CATALOG_2026-08-26.md`; videreudviklet efter en automatiseret adversarial review (`chatgpt-codex-connector[bot]`, 11 punkter) og en parallel revision af z.ai (GLM-5.3, v4, Edge1/pydantic out-of-sample-test).
- **Formaal/scope:** Foreslaa (ikke implementere) et Capability Register (GRC `item_type='capability'`) der forbinder capability -> usecase (`UI_USECASE_CATALOG`) -> autoritativ+historisk implementering -> automatisk verifikation -> runtime-/fysisk observation. Foreslaar en ny §16-governance-regel. Ren dokumentation, ingen kode-/skemaaendring.
- **Berørte domæner/kontrakter:** `Dokumentation/CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` (v1-v4+), `UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`, denne registerpost. Ingen kodefiler.
- **Base/head:** PR #240, head opdateres ved naeste push (se PR'en for aktuel SHA — flere sessioner (Claude + z.ai) skriver til samme branch, saa SHA'et her aeldes hurtigt).
- **Overlap/restdisposition:** Ingen kendt overlap med andre kodeaendrende spor (rent dokumentationsforslag). Bemaerk selv-reference: denne registerpost eksisterede ikke foer PR #240s egen adversarial review paapegede det (P1-fund) — et konkret eksempel paa det forslaget selv adresserer.
- **Seneste verificerede aktivitet/evidens:** Historisk selvtest mod 6 kendte haendelser + et out-of-sample-crash-test mod Edge1/pydantic-incidenten (klassificeret NOT PREVENTED af den frosne v3, se §5 i final-proposal-dokumentet). En uafklaret modsigelse mellem to sessioners Pi-hole/Edge1-fund er eksplicit flaget (§5a), ikke harmoniseret.
- **Naeste handling:** En fuld arkitektur-/impact-analyse af 16 Peter-godkendte governance-principper er udfoert 2026-09-14 (`16_PRINCIPLES_GOVERNANCE_ARCHITECTURE_IMPACT_ANALYSIS_2026-09-14_CLAUDE.md`, analyse alene, intet implementeret) — afventer nu Peters OG ChatGPTs gennemgang af analysen foer nogen implementering autoriseres.
- **Blokeringsansvarlig:** Peter (governance-beslutning).
- **Opfoelgning:** Ved Peters §16-stilling.

## Governance-afslutning 2026-09-13

Peter har accepteret ADR-003/§14 og autoriseret afslutning af PR #232. Review/syntese er afsluttet; de åbne implementeringsspor forbliver synlige i dispositionslisten. Routing og upstream-placering er Proposed; Solar Eclipse er udskudt efter Peters instruktion og blokerer ikke disse spor.
