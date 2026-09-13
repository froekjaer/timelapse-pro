# UI_USECASE_CATALOG: uafhaengig verifikation + hvorfor det blev overset

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Formaal:** Svare paa Peters konkrete opgave: verificer den uafhaengige
reviews historik-paastand selvstaendigt (ikke tage den for givet), og forklar
hvorfor `UI_USECASE_CATALOG_2026-08-26.md` ikke blev fundet hverken under
R04/#235-#238 eller under dagens Capability Register-soegning.

## 1. `UI_USECASE_CATALOG_2026-08-26.md` — verificeret

- **Findes paa main**, oprettet i commit `6bc5d1e4` / PR #141
  ("fix(updates): clean stale queue states and clarify UX"), forfattet af
  **Peter**, 2026-08-26. Bemaerk: PR-titlen naevner intet om usecases eller
  et katalog — dokumentet (294 linjer) blev bundlet ind i en ellers
  usaerelateret update-queue-rettelse.
- Dokumentets egen formaalstekst bekraefter den uafhaengige reviews paastand
  ordret: *"Praktisk katalog til manuel gennemgang af alt klikbart... Status:
  Arbejdsdokument til UAT, support, demo, regressionsproever og senere
  automatisering."* Og eksplicit: *"Dette dokument er ikke en erstatning for
  GRC-registeret eller CI. Det er den menneskelige 'kan vi faktisk bruge
  systemet?'-liste."*
- Indeholder strukturerede usecase-ID'er (`UC-DASH-*`, `UC-AUTH-*`,
  `UC-DEV-*`, `UC-SSH-*`, `UC-TECH-*`, m.fl.), hver med Start/Handling/
  Forventet resultat/Sikkerhed-audit/Status (`READY`, `NEEDS TESTDATA`,
  `CONTROLLED UAT`, `BLOCKED`, `READ-ONLY PASS`).
- **Direkte relevant for dagens terminal-sag:** `UC-SSH-002` ("Aabn
  browserterminal | Kun trusted host + capability + MFA", status **NEEDS
  TESTDATA**) og `UC-TECH-001..003` (ServiceSession/lease/revoke-flows,
  status **NEEDS EDGE**) er nøjagtigt den capability jeg netop implementerede
  om (PR #239) — og de har staaet uafklarede siden 2026-08-26, gennem hele
  R04-, ADR-004- og #238/#239-arbejdet, uden at nogen af analyserne saa dem.

## 2. Den paastaaede historiske kaede — uafhaengigt verificeret via `git log`

Jeg har IKKE taget den uafhaengige reviews opsummering for givet; hvert
punkt er slaaet op selvstaendigt i `git log`/commit-indhold:

| Dato | Paastand | Verifikation |
|---|---|---|
| 2026-08-16 | Produktions-regression/tabte Edge-moduler + SEC-016 capability-tab | **Bekraeftet.** `f1100e30 fix(headend): release artifact manifest was missing 4 top-level edge modules` + parallel SEC-016-kaede samme dag (`b4a69cbd feat(edge): auto-sync BT-TOTP secret...(SEC-016-BOOTSTRAP-GAP)`, PR #71/#73, `92d71414 docs: SEC-016 factory BT-TOTP bootstrap gap`). |
| 2026-08-17 | OP-001 / operationelle loaders | **Bekraeftet.** `b537edf0 docs: vendor Mission Framework OP-001 + add operational loaders for Claude, Codex, ChatGPT, Kimi and Gemini`, PR #74. (Min foerste soegning med `grep "OP-001"` paa filnavne/dokumentindhold fandt IKKE dette — kun `git log --grep` paa commit-beskeder gjorde. Se afsnit 4.) |
| 2026-08-19 | Dokumentations-gap-analyse | **Bekraeftet.** `40f0ed89 docs: Kimi GRC decision-pending list + documentation gap analysis 2026-08-19`, PR #81. |
| 2026-08-23 | Bruger-/admin-menuguides | **Delvist bekraeftet, praecision afviger 3 dage.** De faktiske menuguides (`MENUGUIDE_BRUGER_v1.md`/`MENUGUIDE_ADMIN_v1.md`) blev merged **2026-08-20** (commit `aec738e1`/`510dadaa`, PR #83), ikke 2026-08-23. Der ER en relateret, ægte 08-23-begivenhed (`9bda9405 docs: opdateret GRC-beslutningsliste 2026-08-23`, PR #104) — sandsynligvis kilden til datoen i den uafhaengige opsummering, men det er en GRC-beslutningsliste-opdatering, ikke menuguidernes egen commit-dato. |
| 2026-08-26 | UI_USECASE_CATALOG | **Bekraeftet**, se afsnit 1. |

**Konklusion om historikken:** Kaeden holder overordnet, med én mindre,
identificeret unøjagtighed (menuguide-dato). Dette er vaerdifuldt at vide,
fordi det viser at selv en "uafhaengig review" kan have smaa faktuelle
upraecisioner, der er vaerd at checke — hvilket bekraefter Peters instruks om
selvstaendig verifikation frem for blind tillid.

## 3. `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md` — IKKE fundet nogen steder

Grundig soegning gav **intet resultat**:
- Ingen fil med dette navn (eller lignende, fx `*TEST_CONTINUITY*`,
  `*Testkontinuitet*`) findes i det nuvaerende tree.
- `git log --all --diff-filter=A` for dette filnavnmoenster: ingen commits —
  filen er aldrig blevet tilfoejet i noget kendt branch, heller ikke slettet
  senere (ellers ville `--diff-filter=A` stadig finde tilfoejelsen).
- Ingen tekstreference til filnavnet nogen steder i `Dokumentation/`
  (inkl. `HANDOVER_LOG.md`), hverken i naevaerende form eller med
  variationer i stavning/store bogstaver.
- `gh search code`/`gh search prs`/`gh search issues` for
  "COMPLETE_TEST_CONTINUITY_PLAN"/"test continuity plan" i repoet: **ingen
  hits**.
- Ingen af de 5 aktive git-stashes naevner den.

**Jeg kan derfor hverken bekraefte at HANDOVER_LOG faktisk refererer til
denne fil, eller at filen nogensinde er blevet committet.** Enten:
(a) den uafhaengige reviews paastand om selve HANDOVER-referencen er
unøjagtig/fejlagtig, eller (b) referencen/filen findes et sted mit repo-
niveau-soegning ikke daekker (fx en anden AI-sessions lokale, aldrig-pushede
worktree, en ekstern kanal, eller et dokument der aldrig blev git-tracket
overhovedet). Jeg rekonstruerer den IKKE, som instrueret — dette er kun en
verifikationsrapport.

## 4. Hvorfor blev `UI_USECASE_CATALOG` ikke fundet — aerlig rodaarsagsanalyse

**Under R04/#235-#238 (hele terminal-/shell-sagaen):** Ingen af de fire
dokumenter jeg producerede i den periode
(`EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md`,
`ADR-004-development-and-recovery-shell-access.md`,
`R04_BRANCHTRIAGE_BATCH_2_2026-09-13_CLAUDE.md`,
`SHELL_ROBUSTNESS_IMPLEMENTATION_2026-09-13_CLAUDE.md`) indeholder ordet
"usecase" eller nogen `UC-SSH-*`/`UC-TECH-*`-reference — verificeret direkte
(`grep` gav nul hits). Hele sagaen var udelukkende rammet som
**kode-/git-arkaeologi + sikkerhedsvurdering**: "hvordan virker dette
endpoint", "hvilken risiko har det", "hvad forbedrer den gamle branch
teknisk". Jeg spurgte aldrig "findes der et eksisterende UAT-/usecase-
katalog med dokumenterede acceptkriterier for netop denne feature." Det er
en kategorisk blind vinkel, ikke en enkeltstaaende forglemmelse — samme
mangel gentog sig konsekvent gennem fire separate dokumenter/PR'er.

**Under dagens Capability Register-soegning:** Jeg soegte specifikt efter
"capability register", "capability-register" og "kapabilitet" i
`Dokumentation/*.md` — direkte afledt af Peters egen ordlyd i mandatet, og
efter GRC/ADR/PAKKE_SPOR/HANDOVER, ligeledes de fire strukturer Peter selv
navngav. `UI_USECASE_CATALOG_2026-08-26.md` bruger intet af disse ord i sin
kerneterminologi (den kalder sig et "usecase-katalog", ikke et
"capability register"), saa et rent noegleords-baseret opslag paa "min egen
foreslaaede term" kunne aldrig finde et allerede-eksisterende dokument der
loeser samme problem under et andet navn. Det er et klassisk
bekraeftelsesbias-moenster: soeg efter bevis for at min term allerede
eksisterer, ikke efter "findes der noget der allerede loeser dette,
uafhaengigt af hvilket navn jeg selv ville have givet det."

**En strukturel medvirkende aarsag, ikke kun min egen soegesvaghed:** Hverken
`Dokumentation/00_START_HER.md` eller `Dokumentation/DOKUMENTPAKKE_OVERSIGT_
v10.md` (repoets egne navigations-/indeksdokumenter) naevner "usecase"
overhovedet — verificeret direkte. Dokumentet er reelt, grundigt og direkte
relevant, men er ikke linket fra nogen af de steder en ny laeser (menneske
eller AI) normalt ville starte. Kombineret med at det blev committet i en
PR hvis titel intet afsloerer om indholdet (#141), er dette ikke kun en
soegefejl fra min side — det er ogsaa et reelt discoverability-hul i
repoets egen dokumentationsstruktur.

**Konsekvens for governance-forslaget:** Den rettelse der er noedvendig er
derfor ikke kun "soeg bedre naeste gang" (et adfaerdsappel virker ikke som
en holdbar kontrol) men en **strukturel regel**: en Capability Register-
soegning/disposition SKAL eksplicit tjekke for et eksisterende usecase-/
UAT-katalog-opslag foer den konkluderer at der ikke findes en kendt-god
reference, uanset hvilke andre strukturer (GRC/ADR/HANDOVER) allerede er
tjekket. Se den reviderede `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md`.
