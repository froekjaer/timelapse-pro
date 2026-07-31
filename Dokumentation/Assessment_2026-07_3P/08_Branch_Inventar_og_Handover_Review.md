# 08 — Branch-inventar (alt uden for main) + Handover-review

## Del A — Kode uden for `main` i `timelapse-pro`

**Fakta:** `git branch -r` på `froekjaer/timelapse-pro` viser **kun** `origin/main`. Der findes ingen andre remote-branches i timelapse-pro-repoet. Alt kode-arbejde er allerede på main; der er intet forældreløst kodespor at hente hjem **i dette repo**.

**Nuance (vigtig):** "Uden for main" betyder i praksis to andre ting her:
1. **Ucommittede working-tree-ændringer** på Peters maskiner — handover-loggen refererer gentagne gange docs/kode der stod ucommittet og "afventer Peters commit/push" (agent-lockout M-05: sandkassen havde ingen GitHub-nøgle). Disse kan **ikke** ses fra GitHub; kun Peter kan tjekke `git status` lokalt på Mac Mini / arbejdsmaskine. **➡️ Peter:** kør `git status` + `git stash list` på begge maskiner og bekræft at intet uncommitted er efterladt (se handover-review nedenfor for konkrete kandidater).
2. **Mission-Platform-repoet** indeholder relaterede spor (se del B).

## Del B — Relaterede branches i `froekjaer/Mission-Platform`

Ud over de syv REVIEW-001-reviewbranches + freeze-arkivet findes tre foundation-branches, ingen merget til Mission-Platforms main:

| Branch | +ahead/-behind vs main | Seneste | Indhold |
|---|---|---|---|
| `agent/foundation-architecture` | +10 / −11 | 2026-07-20 | ADR-0001-vision, mission-meta-model, architecture-tests |
| `foundation-release-0.1` | +4 / −5 | 2026-07-21 | mission-core JSON-schema 0.1, versioning-governance, eksempel-mission |
| `architecture/programme-manifest` | +1 / −0 | 2026-07-26 | `programme.yml` (programme-rolle-erklæring) |

**Vurdering:** Disse er framework-/empiri-artefakter, ikke timelapse-produktionskode. De hører til konsolideringen af Mission Framework (dok. 06), ikke til timelapse-pro main. **Anbefaling:** behandl dem i Mission-Platform-sporet efter meta-review; de skal **ikke** merges ind i timelapse-pro. Bland ikke de to repos' main-brancher.

## Del C — Handover-review: åbne tråde der ikke må glemmes

Systematisk gennemgang af `HANDOVER_LOG.md` (1417 linjer) for markører (➡️, afventer, mangler, pas på, uncommitted). De vigtigste **stadig-åbne** tråde:

| Ref | Tråd | Status nu (verificeret i kode HEAD) |
|---|---|---|
| **SEC-016** | Default TOTP-secret `JBSWY3DPEHPK3PXP` fail-open | **STADIG ÅBEN** → eskaleret til TPA-00 KRITISK (verificeret `main.py:4075/5270`, `database.py:333`, `edge/scripts/totp-service.py:123`) |
| **GOV-01** | Ratchet-baseline hævet 18.483→18.549 uden dokumenteret undtagelse (K3 fejlede i praksis) | Baseline nu 18.541; undtagelsesregel stadig ikke vedtaget. **➡️ Peter:** vedtag RATCHET-EXCEPTION-regel |
| **GEN-01** | SFTP-ingress (22222) er IKKE et trin i headend-generatoren | **STADIG ÅBEN** → se dok. 09; generatoren siger selv "Fase 2b er manuelt trin" |
| **GEN-02** | `sftp_port`-default 22→22222 | Bør verificeres; lille fix |
| **GEN-03/04/11** | Tunnel-port-beslutning, allokator-range-kollision (2201++→2222 ved enhed 22), hvor prod-edge-images bygges | **➡️ Peter-beslutninger** — udestår |
| **R09 / P0-03** | Off-site backup + restore-test-evidens | Go-live-blocker; ikke evidenseret |
| **R20** | Incident Response-procedure | Mangler |
| **repositories.py `_normalize_tag_for_similarity` self-bug** | Crash på `/api/ai/vocabulary/similar` | **RETTET** (verificeret: metoden har nu `self`, `main`-kald linje 355) |
| **Deprecation** | Node20/checkout@v4, `on_event`-startup | Åben, lav prioritet (TPA-14) |
| **Docs-oprydning** | ISSUES.md forældet, `docs/` vs `Dokumentation/`-split, `.bak`-filer | Delvist; `PRIORITIZED_BACKLOG.md.bak` findes stadig i repo-rod |

**Ting handover'en flagger som "afventer Peter" der bør bekræftes lukket:** de mange "uncommitted — afventer Peters commit/push"-noter (2026-07-18 ×3 m.fl.). Da alt nu ER på main (kun main findes), er de sandsynligvis committet — men **➡️ Peter bør bekræfte** at intet blev efterladt i et working tree, særligt `.claude/`-beslutningen og drawio-tempfilen (`.$*.dtmp` → tilføj til `.gitignore`).

**Glemt i selve handover-skabelonen?** Skabelonen mangler et felt for **GRC-registrering** (fund skal i PostgreSQL-GRC, men skabelonen minder ikke om det) og for **verifikation efter deploy**. Anbefaling: tilføj de to linjer til skabelonen, så intet fund kun lever i markdown.
