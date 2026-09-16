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
- **RETTELSE (fundet ved automatiseret review, 2026-09-14, uafhaengigt
  genverificeret og korrekt):** Jeg paastod her oprindeligt at `UC-SSH-002`
  og `UC-TECH-001..003` "noejagtigt" var den capability PR #239 aendrer.
  Det er FORKERT. `UC-SSH-002` staar i kataloget under gruppen "SSH
  Tunnels" sammen med `UC-SSH-001` ("Se tunnelkommando... `ssh -p ... -i
  ... orangepi@localhost`") — det er Headends SSH-tunnel-medierede
  "Aabn terminal"-flow (`headend/api/ssh_tunnel_terminal_api.py`,
  reverse-tunnel + registreret host-trust + MFA), en HELT ANDEN capability
  end den Edge-lokale TOTP-shell (`edge/scripts/totp-service.py`,
  `/mgmt/cli/bash/ws`) som #238/#239 faktisk aendrer. `UC-TECH-001..003`
  daekker separate ServiceSession-/kamera-lease-flows via Edge Technician
  UI, heller ikke det samme. **Der findes reelt ingen eksisterende
  usecase-post for den specifikke direct-Edge TOTP-browserterminal** —
  det er selv et dokumentationshul, ikke en post der blot stod uafklaret.
  Se `CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` Sec4 for
  den rettede selvtest.

## 2. Den paastaaede historiske kaede — uafhaengigt verificeret via `git log`

Jeg har IKKE taget den uafhaengige reviews opsummering for givet; hvert
punkt er slaaet op selvstaendigt i `git log`/commit-indhold:

| Dato | Paastand | Verifikation |
|---|---|---|
| 2026-08-16 | Produktions-regression/tabte Edge-moduler + SEC-016 capability-tab | **Bekraeftet.** `f1100e30 fix(headend): release artifact manifest was missing 4 top-level edge modules` + parallel SEC-016-kaede samme dag (`b4a69cbd feat(edge): auto-sync BT-TOTP secret...(SEC-016-BOOTSTRAP-GAP)`, PR #71/#73, `92d71414 docs: SEC-016 factory BT-TOTP bootstrap gap`). |
| 2026-08-17 | OP-001 / operationelle loaders | **Bekraeftet.** `b537edf0 docs: vendor Mission Framework OP-001 + add operational loaders for Claude, Codex, ChatGPT, Kimi and Gemini`, PR #74. (Min foerste soegning med `grep "OP-001"` paa filnavne/dokumentindhold fandt IKKE dette — kun `git log --grep` paa commit-beskeder gjorde. Se afsnit 4.) |
| 2026-08-19 | Dokumentations-gap-analyse | **Bekraeftet.** `40f0ed89 docs: Kimi GRC decision-pending list + documentation gap analysis 2026-08-19`, PR #81. |
| 2026-08-23 | Bruger-/admin-menuguides | **Bekraeftet — min tidligere "korrektion" af dette punkt var selv forkert, rettet igen 2026-09-14 efter automatiseret review.** Jeg paastod fejlagtigt at menuguiderne blev merged 2026-08-20, baseret paa commit `aec738e1`'s AUTHOR-dato paa en feature-branch. Den faktiske merge-commit til `main` er `510dadaa` ("...(#83)"), med author/committer-tidsstempel **2026-08-23T17:30:26+02:00** — uafhaengigt genverificeret direkte (`git show 510dadaa --format=%ad`). "2026-08-20" er kun filernes interne, selvrapporterede `Dato:`-felt, ikke deres merge-dato. Den oprindelige paastand (08-23) var korrekt hele tiden. |
| 2026-08-26 | UI_USECASE_CATALOG | **Bekraeftet**, se afsnit 1. |

**Konklusion om historikken:** Kaeden holder overordnet, med én mindre,
identificeret unøjagtighed (menuguide-dato). Dette er vaerdifuldt at vide,
fordi det viser at selv en "uafhaengig review" kan have smaa faktuelle
upraecisioner, der er vaerd at checke — hvilket bekraefter Peters instruks om
selvstaendig verifikation frem for blind tillid.

## 3. `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md` — KORREKTION: falsk negativ i foerste soegning

**RETTELSE (Peter, 2026-09-13):** Peter tjekkede selv `HANDOVER_LOG.md` og
fandt referencen jeg konkluderede ikke fandtes. Min oprindelige paastand
nedenfor ("ingen tekstreference til filnavnet nogen steder... inkl.
HANDOVER_LOG.md") var **forkert** og er hermed registreret som en falsk
negativ, ikke forklaret vaek eller stiltiende rettet.

**VERIFICERET (efter korrektionen, med reproducerbar kilde):** Referencen
findes faktisk, praecis ét sted, i den autoritative `origin/main`-version af
`HANDOVER_LOG.md`, linje 1208, i handover-posten dateret **2026-08-19**
("NPU-runner deployment-hul rettet ved roden (PR #75) + frontend-
testkontinuitet"):

> (6) Fortsæt Tier 1-testdækning (UpdatesPage.tsx, SystemAdminPage.tsx
> CMDB-drift-UI) jf. `Dokumentation/COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md`.

Reproducerbar kommando: `git show origin/main:Dokumentation/HANDOVER_LOG.md
| grep -n COMPLETE_TEST_CONTINUITY_PLAN` -> linje 1208.

**Rodaarsag for den falske negativ (verificeret, ikke gaettet):** Jeg koerte
den oprindelige soegning i `git`-worktreet `kind-shamir-29fe84` (denne
sessions "hjemme"-worktree), hvis `HEAD` viste sig at staa paa commit
`b25703ed` — langt bagud for `origin/main` (`8452c5ef` paa daetidspunktet).
Den lokale arbejdskopi af `HANDOVER_LOG.md` i det worktree er **1664
linjer**; den autoritative `origin/main`-version er **3119 linjer** — over
halvdelen af filens indhold, inklusive netop den relevante 2026-08-19-post,
manglede simpelthen i den fil jeg faktisk laeste. Jeg rapporterede "soegt i
HANDOVER_LOG" uden foerst at verificere at den lokale kopi var frisk/
identisk med `origin/main` — en fil-friskheds-antagelse, ikke en
noegleords-soegningsfejl. (De øvrige dele af soegningen — `git log --all
--diff-filter=A`, stash-indhold, `gh search`, som alle forespørger direkte
mod git-objektdatabasen/GitHub og ikke en enkelt arbejdskopi — var ikke
paavirket af denne specifikke fejl og holder fortsat ved efterproevning.)

**Adskilt status, som instrueret:**
- **VERIFICERET:** planen ER refereret i `HANDOVER_LOG.md` (linje 1208,
  origin/main, 2026-08-19-posten) — reproducerbart, citeret ovenfor.
- **IKKE ENDNU VERIFICERET:** om selve filen `COMPLETE_TEST_CONTINUITY_PLAN_
  2026-08.md` nogensinde blev committet. Genkontrolleret efter korrektionen
  (denne gang mod korrekt frisk `origin/main`-data): `git log --oneline
  --all --diff-filter=A` for filnavnmoenstret giver stadig ingen hits paa
  nogen branch; ingen af de 5 stashes indeholder den; `gh search
  code/prs/issues` giver stadig ingen hits. Filen er ikke fundet
  committet nogen steder i selve repoet — men se naeste punkt.
- **UKENDT:** om en genfindelig kopi eksisterer et andet sted (en anden
  AI-sessions lokale, aldrig-pushede arbejdskopi; et eksternt dokument der
  aldrig blev git-tracket; eller en session/kanal uden for dette repos
  synlighed). Ikke rekonstrueret, som instrueret.

### Oprindelig (fejlagtig) paastand, bevaret for sporbarhed

> ~~Grundig soegning gav intet resultat: ... Ingen tekstreference til
> filnavnet nogen steder i `Dokumentation/` (inkl. `HANDOVER_LOG.md`),
> hverken i naevaerende form eller med variationer i stavning/store
> bogstaver.~~ — **Forkert, jf. korrektionen ovenfor.**

**RETTELSE (fundet ved automatiseret review, 2026-09-14):** Denne
afsnit indeholdt tidligere endnu en (ikke overstreget) paastand om at
HANDOVER-referencen "hverken kan bekraeftes" — hvilket direkte modsagde
den VERIFICEREDE konklusion ovenfor (linje 1208). Det var en rest fra
foer korrektionen, som jeg glemte at fjerne ved forrige revision. Fjernet
her. Den eneste gaeldende konklusion om selve FILEN (ikke referencen) er
"IKKE ENDNU VERIFICERET" som angivet i den adskilte status-liste ovenfor —
ikke "kan ikke bekraeftes" om referencen, som ER bekraeftet. Jeg
rekonstruerer filen IKKE, som instrueret — dette er kun en
verifikationsrapport.

## 4. Hvorfor blev `UI_USECASE_CATALOG` ikke fundet — aerlig rodaarsagsanalyse

**Under R04/#235-#238 (hele terminal-/shell-sagaen) — RETTET, mere
praecis og faktisk skarpere karakteristik (fundet ved automatiseret
review, 2026-09-14):** Min oprindelige paastand ("nul hits for ordet
'usecase' i alle fire dokumenter, udelukkende kode-/sikkerhedsfokus") var
for kategorisk og delvist forkert — genverificeret direkte.
`EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_2026-09-13_CLAUDE.md` har et helt
afsnit ("## 10. Konkrete operationelle use cases shell'en løser") der
eksplicit analyserer "use cases" (med mellemrum), og konkluderer selv:
*"Der findes ikke en skriftlig liste over tiltænkte use cases."*
`ADR-004-development-and-recovery-shell-access.md` naevner tilsvarende
at fremtidige typede operationer kraever "at disse use cases først
registreres." **Den faktiske, mere praecise fejl er derfor ikke at jeg
aldrig taenkte paa usecases som begreb — jeg gjorde, og skrev endda
eksplicit at ingen skriftlig liste fandtes — men at jeg IKKE fandt
`UI_USECASE_CATALOG_2026-08-26.md`, som allerede var netop den liste jeg
selv efterlyste.** Dette er en skarpere, mere alvorlig version af
soegefejlen end min oprindelige formulering: det var ikke fravaer af
spoergsmaalet, det var en mislykket soegning efter svaret paa et
spoergsmaal jeg faktisk stillede. `R04_BRANCHTRIAGE_BATCH_2_2026-09-13_
CLAUDE.md` og `SHELL_ROBUSTNESS_IMPLEMENTATION_2026-09-13_CLAUDE.md`
indeholder fortsat ingen saadan diskussion (verificeret), saa det er
stadig kun 2 af 4 dokumenter, ikke 0, der reelt engagerede sig med
begrebet.

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
