# Pakke-/spor-register — åbne branches og PR'er på tværs af AI-sessioner

**Formål:** supplement til `HANDOVER_LOG.md`. Handover-loggen er kronologisk og god til
"hvad skete der i denne opgave"; dette register er et **stående overblik** over hvilke
pakker (branches/PR'er) der er åbne *lige nu*, så ingen session — Claude, Codex, Kimi
eller Peter — starter et nyt spor uden at vide at et overlappende spor allerede findes,
og ingen glemt branch rådner uden at nogen bemærker det.

**Proces:** se `ADR/ADR-003-pakke-hygiejne-mod-legacy-branches.md` for reglen dette
register understøtter. Kort version: før du merger eller opdaterer en pakke, tjek denne
liste for overlap; efter merge, ret listen til.

**Sidst opdateret:** 2026-09-13 (Claude, efter Peters forespørgsel om #214/BEHIND-status)

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

Repoet har **127 remote branches** i alt (talt 2026-09-13). Kun de tre ovenfor er
trieret i denne omgang, fordi de var det konkrete udgangspunkt for Peters forespørgsel.
De resterende ~124 er **ikke** gennemgået endnu — nogle er formodentlig allerede mergede
og blot ikke pruned, andre kan være reelt, glemt arbejde som #163/#159 viste sig at være.

- [ ] Kør en fuld sweep: for hver remote branch uden åben PR, tjek `git log main..<branch>`
      for unikt indhold. Branches med 0 unikke commits kan slettes uden risiko. Branches
      med unikke commits skal vurderes som #163/#159 blev det her.
- [ ] Overvej at lave dette til et engangsscript (ikke en stående proces) — det er en
      oprydningsopgave, ikke noget der gentages, når §"Åbne spor" ovenfor holdes ved lige
      fremadrettet.
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
