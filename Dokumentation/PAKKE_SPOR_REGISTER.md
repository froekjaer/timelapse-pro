# Pakke-/spor-register — åbne branches og PR'er på tværs af AI-sessioner

> **Fælles reviewrunde:** [Reviewpakke v1.0](PAKKE_GOVERNANCE_REVIEWPAKKE_2026-09.md) — fastlåst baseline, beslutningspunkter og fælles svarskabelon før endelig accept.

**Formål:** supplement til `HANDOVER_LOG.md`. Handover-loggen er kronologisk og god til
"hvad skete der i denne opgave"; dette register er et **stående overblik** over hvilke
pakker (branches/PR'er) der er åbne *lige nu*, så ingen session — Claude, Codex, Kimi
eller Peter — starter et nyt spor uden at vide at et overlappende spor allerede findes,
og ingen glemt branch rådner uden at nogen bemærker det.

**Proces:** se `ADR/ADR-003-pakke-hygiejne-mod-legacy-branches.md` for reglen dette
register understøtter. Kort version: før du merger eller opdaterer en pakke, tjek denne
liste for overlap; efter merge, ret listen til.

**Sidst opdateret:** 2026-09-13 (Claude, efter Peters forespørgsel om #214/BEHIND-status; Kimi: tilføjet målt branch-sweep, se §Backlog)

---

## Åbne spor (aktive PR'er)

| Pakke / branch | PR | Forfatter | Berører (domæner) | Status | Handling |
|---|---|---|---|---|---|
| `claude/globalconfig-parallel-load` | [#214](https://github.com/froekjaer/timelapse-pro/pull/214) | Claude | `timelapse-ui/src/pages/GlobalConfigPage.tsx` (frontend, ingen overlap med andre spor) | CI grøn, `BEHIND` main (ingen konflikt — main har ikke rørt samme fil) | Klar til opdatering + merge når Peter godkender |
| `codex/edge-post-restart-health-handshake` | [#163](https://github.com/froekjaer/timelapse-pro/pull/163) | Codex | `edge/agent.py`, `edge/update_lifecycle.py`, `edge/scripts/watchdog.sh`, `headend/main.py`, `headend/services/post_restart_health.py` | **CONFLICTING** mod main (main har selvstændigt videreudviklet samme kodeområde, se analyse i PR-kommentar) — **foreløbigt ikke fuldt overhalet ifølge Claudes strengsøgning**; ikke uafhængig semantisk verifikation. Funktionaliteten (stabilitetsvindue + Headend-sweeper for hængende handshakes) blev ikke fundet ved den søgning | Afventer rebase mod aktuel main + gentest. Se PR-kommentar for detaljeret konfliktanalyse. |
| `codex/fix-capture-time-and-edge2-evidence` | [#159](https://github.com/froekjaer/timelapse-pro/pull/159) | Codex | `headend/main.py`, `headend/capture_api_helpers.py` (ny, ren tilføjelse), `timelapse-ui/src/pages/DevicePage.tsx`, `timelapse-ui/src/components/CaptureThumbnailCard.tsx`, `timelapse-ui/src/lib/captureTime.ts`, `timelapse-ui/src/types/index.ts` | **CONFLICTING** mod main (DevicePage/CaptureThumbnailCard ændret uafhængigt af senere lightbox/prefetch-arbejde) — **foreløbigt ikke fuldt overhalet ifølge Claudes strengsøgning**; ikke uafhængig semantisk verifikation. De eksplicitte `captured_at_local/_utc/_timezone`-felter fra capture-listen/timeline-API'et blev ikke fundet ved den søgning | Afventer rebase mod aktuel main + gentest. Se PR-kommentar for detaljeret konfliktanalyse. |

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

Koordinationstabellens tidligere "Codex"-rækker er forslag til næste koordinering, ikke permanent mandat eller bevis for aktivitet. Bekræftet mandat i denne runde: **Codex / session med PR #232, udpeget af Peter til reviewsammenlægning**; senest verificeret aktivitet: denne slutkandidats commit og handover. Næste handling er at levere kandidat/disposition til Peter og målrettet genreview, før endelig ADR-accept.

For branchtriage, PR-rebases, scheduler og Platform-implementering er aktiv udfører **ikke bekræftet**; blokering: prioritering/overdragelse skal afklares. Peter er beslutningsejer, Codex samler de konkrete næste leverancer i dispositionspakken. Ved næste session skal de tidligere opfølgningsdatoer kontrolleres, og aktivitet markeres uverificeret, hvis der ikke foreligger nyt bevis. Ingen automatisk overtagelse eller stille fristforlængelse.

Let spor og fuldt spor følger §14.6; kontrakt-/governanceændringer er fulde spor. Git/PR leverer revisioner og commits, så de ikke skal kopieres manuelt i alle felter. Oprindeligt reviewmateriale og alle fund/dispositioner findes i [reviewdispositionen](Pakke_Governance_Review_2026-09/DISPOSITION.md).

## Partner- og kompetenceudvidelse 2026-09-13

PR #232 udvides efter Peters instruktion med faste deltagere Kimi/Z.ai samt ad hoc-onboarding og [kompetence-/routingforslag](AI_KOMPETENCER_OG_OPGAVEROUTING.md). Udfører: Codex i samme isolerede reviewspor. Næste handling: dokumentreview af udvidelsen og budgetafklaring før eventuel pilot. Tidligere genreviews gælder den tidligere kandidat, ikke dette nye scope. Ingen runtime- eller upstream-ændring.
