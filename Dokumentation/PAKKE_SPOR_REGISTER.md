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

**Sidst opdateret:** 2026-09-13T14:20Z (Claude — verificeret reconciliation efter #232-merge, mandat fra Peter. Baseline frisk-kontrolleret mod `origin/main` = `ebd98fffc8d506be252ccd930ac8ef2f53aea809` via `gh api` + `git ls-remote`, ikke antaget uændret. #229 lukket; #214 verificeret klar men ikke pushet — se kollisionsfund; #163/#159 semantisk restanalyse tilføjet.)

---

## Åbne spor — fulde felter (§14.6)

Base/head-SHA'er og mergeable-status er hentet frisk 2026-09-13T14:20Z; de ældes med
tiden — se PR'en for den aktuelt gældende SHA, ikke kun tallet her. Main er verificeret
uændret siden #232-merge (`git log ebd98fff..origin/main` = tom).

### #214 — `claude/globalconfig-parallel-load`

- **Mandat/session:** Claude (oprindelig forfatter). **Kollisionsfund 2026-09-13:** en anden sessions worktree på denne maskine (`timelapse-pro-kimi-ratelimit`, formodet Kimi) havde allerede en **ny, ikke-pushet lokal commit** `bde560eb` på præcis denne branch — en ren rebase af samme fix oven på aktuel main (`ebd98fff` som forælder). Worktreen var clean (intet uncommitted). Jeg har **ikke** rørt den, rebaset over den eller pushet noget, jf. §14.2. Verificerede i stedet indholdet i en isoleret, separat kopi.
- **Formål/scope:** Fjern unødig sekventiel netværkstur i `GlobalConfigPage.tsx::loadBase()` — samme waterfall-mønster som #213 (UsersPage).
- **Berørte domæner/kontrakter:** `timelapse-ui/src/pages/GlobalConfigPage.tsx` (frontend). Ingen kendt overlap med andre åbne spor.
- **Base/head:** PR #214 på origin er stadig `bed3cf14ce5952843f6688ab331f81f666811db8` (ikke opdateret). Den klar-til-push, endnu ikke-pushede kandidat er `bde560eb0c0922e631d997edfb8284f6af4464e1` (parent = `ebd98fff` = aktuel main — ren, konfliktfri rebase, verificeret med `git merge-base --is-ancestor`).
- **Overlap/restdisposition:** Ingen overlappende pakke rører samme fil. Intet indholdsmæssigt restkrav.
- **Seneste verificerede aktivitet/evidens:** Kandidaten `bde560eb` verificeret af Claude 2026-09-13 i isoleret kopi: `npx tsc --noEmit` rent, `npm run lint:gate` → 183 problemer (3 færre end baseline 186, ingen nye). Indholdet (Promise.all-flatning) er identisk med det oprindeligt godkendte.
- **Næste handling:** **Afventer koordinering, ikke teknik.** Nogen skal beslutte hvem der pusher `bde560eb` til `origin/claude/globalconfig-parallel-load` — enten den session der forberedte den (formodet Kimi), eller Claude efter eksplicit go, for at undgå at to sessioner pusher divergerende versioner af samme rebase.
- **Blokeringsansvarlig:** Uafklaret — Peter bør bekræfte hvem der fuldfører pushet.
- **Opfølgning:** Før næste forsøg på at opdatere denne PR.

### #163 — `codex/edge-post-restart-health-handshake`

- **Mandat/session:** Claude fik mandat til semantisk restanalyse 2026-09-13 (ikke merge). Brugt den eksisterende clean worktree `timelapse-pro-edge-health-handshake` (uændret, stadig på PR-head, ingen andre sessioner registreret der).
- **Formål/scope:** Post-restart health-stabilitetsvindue for app-updates + Headend-sweeper der markerer hængende post-restart-handshakes som `failed`/`blocked`.
- **Berørte domæner/kontrakter:** `edge/agent.py`, `edge/update_lifecycle.py`, `edge/scripts/watchdog.sh`, `headend/main.py`, `headend/services/post_restart_health.py`.
- **Base/head:** PR #163, head `4c0cfba268da35af3b213a1a628ffb5d40cfdfa3`, base `main`. Reel konflikt genbekræftet mod aktuel main med `git merge-tree`: `edge/agent.py`, `headend/main.py`, `headend/tests/test_update_lifecycle.py`, `HANDOVER_LOG.md`.
- **Semantisk restanalyse (ny, 2026-09-13):**
  - **Allerede på main (ikke en rest):** en fungerende, men enklere mekanisme — `awaiting_restart_health` → `health_confirmed` i `edge/update_lifecycle.py`, sat via `mark_pending_app_update_health_confirmed()` når `_finalize_pending_app_update_health()` (agent.py:2394) bekræfter at release-kvitteringen matcher (`release_receipt_matches_artifact`). Der er også en **eksisterende, uafhængig sikkerhedsmekanisme** #163 ikke nævner: en `systemd-run`-guard-unit (`timelapse-app-update-guard-{id}`) startes før genstart og kan rulle tilbage hvis `health_timeout_s` (default 180s) overskrides. Class-strukturen (`EdgeAgent`, samme metodenavne) er uændret — main.py's agent.py er vokset (4231 linjer mod #163's 3916), ikke omstruktureret her.
  - **Stadig manglende på main (reel rest, ikke bare screening):** (1) intet stabilitetsvindue efter health_confirmed — main markerer bekræftet ved første succesfulde tjek, ikke efter en vedvarende periode; (2) ingen `ssh_tunnel_connected`-tjek i selve health-checket; (3) **ingen Headend-side sweeper overhovedet** — bekræftet ved grep i `headend/services/` og `headend/main.py`: intet matcher `stale.*installing`, `handshake_missing` eller lignende. Kun en generisk `legacy_backlog_sweep.py` for helt andre ting (thumbnails/AI-tags) findes.
  - **Hvad korrekt integration kræver:** **Ikke** en ren cherry-pick/rebase af #163's diff — den forudsætter at omdøbe `mark_pending_app_update_health_confirmed`/`awaiting_restart_health` til `record_pending_app_update_health_probe`, hvilket ville ændre schemaet for `state`-feltet i den lokale pending-update-marker-fil på edges. Da denne mekanisme er i reel produktions-/lab-brug (jf. HANDOVER_LOG's update-flow-arbejde), risikerer en navn-/schema-ændring at være inkompatibel med allerede afventende opdateringer på rigtige enheder. **Anbefalet tilgang:** genimplementér #163's forbedringer (stabilitetsvindue, ekstra tjek, Headend-sweeper) som et **additivt lag oven på** de eksisterende `awaiting_restart_health`/`health_confirmed`-navne og den eksisterende guard-unit — ikke som en erstatning af dem.
- **Næste handling:** Implementering (ikke udført her — uden for dagens mandat) af ovenstående additive tilgang, i den eksisterende worktree.
- **Blokeringsansvarlig:** Udfører ikke bekræftet — afventer eksplicit tildeling.
- **Opfølgning:** Før første merge/deploy fra sporet.

### #159 — `codex/fix-capture-time-and-edge2-evidence`

- **Mandat/session:** Claude fik mandat til semantisk restanalyse 2026-09-13 (ikke merge). Ingen dedikeret lokal worktree fundet for denne branch på maskinen — analyse udført via fetch af PR-refs, ingen ny worktree oprettet unødigt.
- **Formål/scope:** Eksplicitte lokal-/UTC-/tidszonefelter fra capture-liste- og timeline-API'et, så thumbnail-tidsstempler ikke afhænger af browserens tidszonegæt.
- **Berørte domæner/kontrakter:** `headend/main.py`, `headend/capture_api_helpers.py` (ny, ren tilføjelse), `timelapse-ui/src/pages/DevicePage.tsx`, `timelapse-ui/src/components/CaptureThumbnailCard.tsx`, `timelapse-ui/src/lib/captureTime.ts`, `timelapse-ui/src/types/index.ts`.
- **Base/head:** PR #159, head `eaa0289267f67edd734a7aa28ea18380d4afd0e8`, base `main`. Reel konflikt genbekræftet med `git merge-tree`: `headend/main.py`, `headend/requirements.txt`, `CaptureThumbnailCard.tsx`, `DevicePage.tsx`, `types/index.ts`, `HANDOVER_LOG.md`.
- **Semantisk restanalyse (ny, 2026-09-13):**
  - **Allerede på main (ikke en rest):** `headend/main.py::list_captures()` (linje ~11223) findes uændret i navn/placering og returnerer stadig kun ét naivt `captured_at`-felt (`c.captured_at.isoformat()`) — ingen anden kode andetsteds i main dækker samme behov.
  - **Stadig manglende på main (reel rest):** de eksplicitte `captured_at_local`/`captured_at_utc`/`captured_timezone`-felter i selve API-svaret findes fortsat ikke. `headend/capture_api_helpers.py` (som ville levere dem) findes stadig ikke i main — bekræftet ren, konfliktfri tilføjelse.
  - **Hvad korrekt integration kræver:** Fordi `list_captures()` stadig er let identificerbart og uændret i struktur, er patch-overfladen lille og lokaliseret — det er ikke et arkitektur-konflikt som #163, men et almindeligt rebase-konflikt pga. main's uafhængige lightbox-/prefetch-arbejde i `DevicePage.tsx`/`CaptureThumbnailCard.tsx` (proximity, ikke design-uenighed). Anbefalet tilgang: rebase, tilføj `capture_api_helpers.py` uændret, kald den fra `list_captures()`, og genforen UI-filerne manuelt linje for linje (mindre risiko end #163).
- **Næste handling:** Implementering (ikke udført her — uden for dagens mandat) af ovenstående.
- **Blokeringsansvarlig:** Udfører ikke bekræftet — afventer eksplicit tildeling.
- **Opfølgning:** Før første merge/deploy fra sporet.

### #229 — `claude/pakke-hygiejne-adr` — **LUKKET 2026-09-13, uden merge**

- **Disposition:** Lukket. Verificeret linje-for-linje (`git diff origin/main origin/claude/pakke-hygiejne-adr`) at hver eneste linje branchen tilføjer i forhold til main er en tidligere, ukorrigeret version af noget main allerede har i forbedret form (gammel "Proposed"-header, det ukvalificerede "127 branches", den gamle letvægts-tabel, samarbejdsmodellens gamle titel). Intet unikt indhold tabt.
- **Bemærkning om samtidighed:** Kimi lukkede PR'en (via Peters GitHub-konto) med samme konklusion **ét sekund før** Claudes eget lukningsforsøg landede som kommentar på den allerede lukkede PR. Ufarligt dobbeltarbejde — begge nåede uafhængigt samme, korrekte konklusion. Branch `claude/pakke-hygiejne-adr` er **ikke** slettet (afventer samlet R04-triage, jf. begge lukningskommentarer).
- **Erstatningsreference:** #232 (merged som `ebd98fff`).

### Rapporterede lokale tilstande — nu delvist verificeret

- **Kimis 5 rapporterede stashes: bekræftet at eksistere** ved `git stash list` i det delte repository (`/Volumes/data-fast/peter-home/projects/timelapse-pro`), 2026-09-13. Fulde, faktiske beskeder (mere præcise end den tidligere paraphrase):
  `stash@{0}` "codex preserve generated source inventory" (branch `codex/fix-capture-time-and-edge2-evidence`);
  `stash@{1}` "PR #92 edge image-deletion rebuild — awaiting Peter's review, unrelated to SSH-fix deploy, stashed only to unblock Deploy-to-Mac-mini-Headend's tracked-changes guard" (branch `fix/sshd-authorized-keys-command-missing-u-token`);
  `stash@{2}` "pre-headend-deploy-cmdb-main-duplicate-20260824" (branch `codex/update-queue-hygiene`);
  `stash@{3}` "pre-main-deploy-safety-backup-20260815T125231Z" (branch `codex/edge-terminal-renderer`);
  `stash@{4}` "wp4-in-progress-before-ci-hotfix" (branch `codex/wp4-edge-image-provisioning`).
  Status opgraderet fra "reported/pending" til **existence verified via `git stash list` 2026-09-13; content not inspected, not popped**. GitHub kan stadig ikke verificere dette — det er en lokal maskine-observation.
- **Worktrees direkte relevante for dagens fire spor — verificeret clean** (ingen uncommitted ændringer) 2026-09-13: `timelapse-pro-edge-health-handshake` (#163, klar til brug), `timelapse-pro-governance-review` (**stale** — stadig på `786c4bdb`, før F1/F2 og #232-merge; harmløst, men bør opdateres før brug), `timelapse-pro-governance-merged`, `timelapse-pro-package-governance` (begge Codex' ældre, nu fuldt supersedede governance-forslag). `timelapse-pro-kimi-ratelimit` var ved sidste tjek på `kimi/review-pakke-governance-20260913`, men er nu (se #214 ovenfor) på `claude/globalconfig-parallel-load` med en ny, ikke-pushet commit — mappenavnet ("ratelimit") matcher ikke det aktuelt checked-out spor, hvilket kan indikere et navneskifte i formål. Ikke rørt.
- **Øvrige ~15 worktrees og alle `/private/tmp/*`-worktrees:** ikke undersøgt i denne runde (hører til R04's fulde historiske triage, eksplicit separat scope). De prunable `/private/tmp/*`-poster er bekræftet at pege på allerede-forsvundne mapper — ingen data at redde der, kun stale Git-metadata; underliggende branches er intakte (stikprøve: `codex/capture-assignment-metadata` findes stadig lokalt og på remote).

Ingen stash poppet, intet worktree ændret eller slettet.

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

| Spor | Koordinationsansvar | Næste handling / blokering | Opfølgning |
|---|---|---|---|
| Sammenlægning af de tre input | Codex, denne session | Verificér dokumenter og lever samlet PR | Denne session |
| Historisk branchtriage | Codex for ejerskabsafklaring; Kimi har tilbudt udførelsen, men start er ikke bekræftet | Aftal aktiv udfører før parallel sweep; genoptæl med faste SHA'er, prioritér sikkerhed, ucommitted materiale og driftskonsekvens før alder | Næste integrationssession, senest ønsket 2026-09-14 |
| PR #163 og #159 | Codex for næste vurdering | Frisk restanalyse/rebase i isoleret worktree; dette dokumentarbejde udfører ikke kodeintegrationen | Næste integrationssession, senest ønsket 2026-09-14 |
| PR #214 | Codex for koordinationsafklaring; oprindeligt Claude | Genbekræft ejer, main/head og CI før disposition | Næste integrationssession, senest ønsket 2026-09-14 |
| PR #229 | **Afsluttet 2026-09-13:** lukket uden merge (Kimi + Claude, uafhængigt, samme konklusion) — se fulde felter ovenfor | Restdiff verificeret linje-for-linje; fuldt supersedet af #232 | Afsluttet |
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

## Governance-afslutning 2026-09-13

Peter har accepteret ADR-003/§14 og autoriseret afslutning af PR #232. Review/syntese er afsluttet; de åbne implementeringsspor forbliver synlige i dispositionslisten. Routing og upstream-placering er Proposed; Solar Eclipse er udskudt efter Peters instruktion og blokerer ikke disse spor.
