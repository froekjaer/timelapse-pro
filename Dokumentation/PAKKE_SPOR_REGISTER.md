# Pakke-/spor-register — åbne branches og PR'er på tværs af AI-sessioner

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
| `codex/edge-post-restart-health-handshake` | [#163](https://github.com/froekjaer/timelapse-pro/pull/163) | Codex | `edge/agent.py`, `edge/update_lifecycle.py`, `edge/scripts/watchdog.sh`, `headend/main.py`, `headend/services/post_restart_health.py` | **CONFLICTING** mod main (main har selvstændigt videreudviklet samme kodeområde, se analyse i PR-kommentar) — **ikke overhalet**, funktionaliteten (stabilitetsvindue + Headend-sweeper for hængende handshakes) findes ikke andre steder i main | Afventer rebase mod aktuel main + gentest. Se PR-kommentar for detaljeret konfliktanalyse. |
| `codex/fix-capture-time-and-edge2-evidence` | [#159](https://github.com/froekjaer/timelapse-pro/pull/159) | Codex | `headend/main.py`, `headend/capture_api_helpers.py` (ny, ren tilføjelse), `timelapse-ui/src/pages/DevicePage.tsx`, `timelapse-ui/src/components/CaptureThumbnailCard.tsx`, `timelapse-ui/src/lib/captureTime.ts`, `timelapse-ui/src/types/index.ts` | **CONFLICTING** mod main (DevicePage/CaptureThumbnailCard ændret uafhængigt af senere lightbox/prefetch-arbejde) — **ikke overhalet**, de eksplicitte `captured_at_local/_utc/_timezone`-felter fra capture-listen/timeline-API'et findes stadig ikke i main | Afventer rebase mod aktuel main + gentest. Se PR-kommentar for detaljeret konfliktanalyse. |

## Reserverede/planlagte spor (ikke startet endnu — nævnt i eksisterende dokumentation)

| Emne | Reference | Status |
|---|---|---|
| ADR-002 — payload-pakkeformat, signering, proces-sandbox, control/data-plane-kontrakter | Nævnt i `ADR-001` §Afgrænsning, `Claude_QA_Review_2026-07-17.md`, `HANDOVER_LOG.md` (flere entries) | Uskrevet. Start ikke en branch under navnet "ADR-002" uden at have læst disse referencer først. |

## Backlog — historisk oprydning (ikke del af denne ADR's proces, men samme bekymring)

Repoet havde **127 remote branches** i alt (talt 2026-09-13). Kun de tre ovenfor var
trieret i første omgang, fordi de var det konkrete udgangspunkt for Peters forespørgsel.

### Målt sweep 2026-09-13 (Kimi) — første kortlægning er udført

Metodekorrektion ved sammenlægning: `git log main..branch` måler ancestry, mens
`git cherry` sammenligner individuelle patches. Ingen af dem afgør alene semantisk
restværdi. Flere commits samlet i ét squash-commit kan ikke generelt genkendes af
`git cherry`; forskelle i patch-ID kan derfor både være forventede og relevante.

Kimis rapport angiver 127 remote branches, 112 ikke-merged, 57 absorberede og 56
med rester. **57 + 56 = 113**, så population/tidspunkt/klassifikation er endnu ikke
afklaret. Tallene bevares som historisk rapport, ikke som verificeret partitionssum
eller slettegrundlag. En branchliste med base/head-SHA og metodeoutput kræves ved
næste sweep. Påstanden om fulde rådata i denne fils historik er ikke verificeret her.

Kimi rapporterer sletning af syv egne remote branches knyttet til PR #218–#224.
Denne sammenlægning har ikke selv slettet eller genverificeret disse refs. Den
rapporterede handling er ikke en generel regel om automatisk sletning ved merge.

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
