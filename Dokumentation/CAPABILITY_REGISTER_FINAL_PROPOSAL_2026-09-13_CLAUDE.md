# Capability Register — final proposal (review-ready)

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Status:** FORSLAG, review-klar — INTET implementeret. GRC-skema uaendret,
§16 ikke tilfoejet noget dokument, `UI_USECASE_CATALOG_2026-08-26.md` ikke
selv rettet. Peter er beslutningsejer.
**Erstatter/konsoliderer:** Dette dokument er den samlede, endelige
version af arbejdet i `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md`
(v1 paa PR #239, v2 paa denne PR) og
`UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`.
De forudgaaende dokumenter er **bevaret uaendret** som korrektionsspor —
se §7 nedenfor. Intet i denne fil omskriver dem stiltiende.

---

## 1. Den endelige model

```
Capability / invarianter
    (GRC, ny item_type='capability' — intent, invarianter, ejer)
        |
        v
Usecase(s) / forventede resultater
    (UI_USECASE_CATALOG_2026-08-26.md — bevares, ikke erstattes;
     ID, Start, Handling, Forventet resultat, Sikkerhed/audit, Status)
        |
        v
Autoritativ + relevant historisk implementering
    (nuvaerende kildekode/komponent-reference
     + eksplicit git log --all-soegning for et evt. tabt/kendt-godt spor)
        |
        v
Automatisk verifikation
    (tests, architecture ratchets — haandhaever invarianterne maskinelt)
        |
        v
Runtime-/fysisk observation og evidens
    (faktisk observeret adfaerd paa en rigtig Edge/i produktion —
     adskilt fra og ikke erstattet af "testen er groen")
```

**Sideordnede lag, IKKE en del af kaeden — provenance/beslutning/
arbejdstilstand, uaendrede roller:**

| Struktur | Rolle | Aendres af dette forslag? |
|---|---|---|
| GRC-register | Autoritativ, struktureret capability-/verifikationsbutik | Udvides med `item_type='capability'` |
| `UI_USECASE_CATALOG_2026-08-26.md` | Menneskelaesbart UAT-/usecase-lag ("kan vi faktisk bruge systemet?") | Bevares; boer synliggoeres fra `00_START_HER.md` |
| Tests/architecture ratchets | Maskinel haandhaevelse af invarianter | Uaendret; capability-items boer linke til dem |
| Menuguides (`MENUGUIDE_*_v1.md`) | Afledt brugerdokumentation | Uaendret |
| ADR | Enkeltstaaende arkitekturbeslutning + provenance | Uaendret |
| HANDOVER_LOG | Kronologisk driftslog/arbejdstilstand | Uaendret (fortsat append-only, nyeste oeverst) |
| PAKKE_SPOR_REGISTER | Branch-/pakke-/sporsporing (§14) | Uaendret |

Dette er en **sammenkobling af eksisterende lag**, ikke et nyt, konkurrerende
register. Baade `UI_USECASE_CATALOG_2026-08-26.md` og `UI_TESTJOURNAL_v1.md`
erklaerer allerede selv noejagtig denne rollefordeling i egen tekst — den var
blot aldrig forbundet til en formel type eller en soegepligt.

## 2. Foreslaaet skemaaendring (uaendret fra v1/v2, minimal)

1. Ny migration: tilfoej `'capability'` til `grc_items.item_type` CHECK-
   constraint.
2. `headend/api/grc_register_api.py`: tilfoej `"capability"` til
   `ITEM_TYPES`.
3. Konvention (ikke skema-haandhaevet, som `relationship`/`evidence_type`
   allerede er frie strenge i dag): `relationship` faar `has_usecase`,
   `evidence_type` faar `usecase_catalog_entry` og `known_good_reference`.

## 3. Endeligt forslag til §16 (additiv til det allerede accepterede §14)

> **§16 — Capability- og usecase-tjek foer aendring af en consequential
> capability.**
>
> **3.1 Foer disposition eller aendring.** Foer en branch/change
> klassificeres `absorbed`/`superseded`, ELLER foer en ny implementering af
> en bruger-, drifts-, recovery-, sikkerheds- eller anden consequential
> capability paabegyndes, skal foelgende identificeres og dokumenteres
> eksplicit:
> 1. Capability-intent/invarianter (GRC `item_type='capability'`, hvis
>    registreret).
> 2. Relevante usecase(r) (`UI_USECASE_CATALOG_2026-08-26.md` eller dens
>    efterfoelger) og deres aktuelle status.
> 3. Nuvaerende autoritative implementering (fil/komponent-reference).
> 4. Historisk/kendt-god implementering, hvor en saadan findes — via en
>    **eksplicit `git log --all`/branch-/stash-soegning for den paagaeldende
>    komponent eller det paagaeldende problem**, ikke kun nuvaerende mains
>    historik.
> 5. Automatisk verifikation (hvilke tests haandhaever invarianterne i dag).
> 6. Runtime-/fysisk verifikation, hvor det er relevant — **et bestaaet
>    testsuite er ikke i sig selv bevis for at capability'en faktisk virker
>    i drift**; observeret runtime-adfaerd er en selvstaendig evidenskilde,
>    ikke en delmaengde af testresultatet.
>
> **3.2 Soeg efter problemet, ikke kun efter loesningens navn.** Soegningen
> i punkt 1-4 skal daekke det underliggende problem/den oenskede
> capability ("findes der allerede noget der loeser dette"), ikke kun den
> terminologi en foreslaaet ny loesning selv introducerer. En soegning der
> kun bruger ens egne foreslaaede navne/termer og konkluderer "intet
> fundet" er ikke tilstraekkelig.
>
> **3.3 Fravaer er et dokumentationshul, ikke tilladelse.** Fravaer af et
> registreret capability- eller usecase-opslag for et omraade der aabenlyst
> paavirker en consequential capability er IKKE tilladelse til at fortsaette
> uden videre — det skal disponeres eksplicit (registreres som en ny
> `capability`/`usecase`-post, eller bevidst noteret som en accepteret
> mangel, med begrundelse).
>
> **3.4 Capability-aekvivalens, ikke patch-aekvivalens.** Commits, filer,
> funktioner, tests eller ren patch-/diff-aekvivalens er IKKE i sig selv
> tilstraekkeligt bevis for at en historisk branch/change er `absorbed`
> eller `superseded`, naar den paavirker en registreret capability. Den
> aktuelle implementering skal sammenholdes med capability'ens intent og
> invarianter, ikke kun med dens kode.
>
> **3.5 Ingen stiltiende degradering.** En forbedring af én del af en
> registreret capability maa ikke stiltiende forringe en anden del af samme
> capability (fx: en ny renderer maa ikke fjerne en allerede-fungerende
> sessionsmodel; en ny sessionsmodel maa ikke fjerne en allerede-fungerende
> renderer).
>
> **3.6 Kildefriskhed foer soegning.** Enhver soegning der skal understoette
> punkt 1-4 skal foerst bekraefte at dens datakilde er autoritativ/frisk
> (for git: eksplicit `origin/<default-branch>`, eller en navngiven,
> verificeret commit — ikke en lokal arbejdskopis `HEAD` uden foerst at
> sammenligne `git rev-parse HEAD` mod `git rev-parse origin/main`).
>
> **3.7 Standard for en konsekvent fravaers-konklusion.** En "IKKE
> FUNDET/EKSISTERER IKKE"-konklusion, der har konsekvens (fx retfaerdiggoer
> at springe et genfindingstrin over), maa foerst opfylde: (a) bekraeftet
> kildefriskhed (jf. 3.6), og (b) mindst to uafhaengige soegemetoder (fx
> baade indholds-`grep` OG `git log --diff-filter=A`/`gh search`). Uden
> begge dele rapporteres konklusionen som **IKKE VERIFICERET**, ikke som
> fravaer/DOES NOT EXIST. En saadan konklusion skal citere den
> reproducerbare kommando/metode, saa den kan efterproeves uafhaengigt.
>
> **3.8 Modstridende evidens forbliver eksplicit.** Naar to kilder (fx en
> commit-besked og en observeret systemtilstand, eller to sessioners fund)
> modsiger hinanden, skal begge udsagn bevares synligt side om side, indtil
> modsigelsen er aktivt afklaret — ikke stiltiende harmoniseret eller lade
> den ene forsvinde.

## 4. Historisk selvtest — seks kendte haendelser

Peter bad om at teste forslaget mod mindst seks kendte haendelser, uden at
svaekke det for at faa alle til at "bestaa." Resultatet er blandet, med
aerlig rapportering af hvor modellen ikke daekker, ikke tvunget til at
passe. "Gate" refererer til lag 1-5 i §1 ovenfor.

| # | Haendelse | Ville §16 have opdaget/stoppet den? | Ved hvilken gate | Begrundelse |
|---|---|---|---|---|
| 1 | **Direct-Edge terminal** (xterm.js-regression, PR #198/#238) | **JA** | Usecase (2) + Historisk soegning (4) | `UC-SSH-002`/`UC-TECH-001-003` eksisterede allerede fra 2026-08-26 — foer PR #198 (09-08). Et §16-tjek ved #198 ville have fundet status `NEEDS TESTDATA`, ikke lukket. `d67ca26d` (xterm.js, live-testet) laa hele tiden i `git log --all` og ville vaere fundet af en eksplicit historisk soegning. Automatisk tests (5) LAASTE faktisk den daarlige adfaerd fast som om den var korrekt — et direkte eksempel paa at "testen er groen" ikke er det samme som "capability'en virker" (jf. 3.1.6). |
| 2 | **SEC-016 factory TOTP** (delt demo-TOTP-secret som fail-open fallback, 2026-07-17-fund) | **NEJ, uden for denne mekanismes raekkevidde** | Ingen gate rammer den | Dette var et **oprindeligt sikkerhedsfund** (et aldrig-tidligere-flagget, usikkert factory-default), ikke en regression fra en tidligere kendt-god tilstand. §16's mekanisme (capability-aekvivalens, historisk genfinding af et TABT godt spor) forudsaetter at der FANDTES noget bedre at genfinde — det gjorde der ikke her. Dette daekkes af sikkerhedsreview/trusselsmodellering, ikke af Capability Register-forslaget. Aerligt rapporteret som en grænse, ikke stroekket til at "bestaa." |
| 3 | **Release-artifact hand-liste** (`f1100e30`, 4 manglende edge-moduler, crash loop) | **DELVIST/NEJ i nuvaerende omfang** | Ingen af de 5 gates rammer direkte | Root cause var en haandholdt modulliste der gik forældet i takt med at kodebasen voksede — ikke en tabt implementering og ikke en usecase-status. Et `CAP-DEPLOYMENT-UPDATE-DELIVERY`-item med et EKSPLICIT invariant om "artefakt-fuldstaendighed skal verificeres programmatisk, ikke ved haandopremsning" kunne have fanget det — men det kraever en navngiven udvidelse (§5), ikke noget der allerede er daekket. |
| 4 | **Global Config** (merge-argumenter omvendt, virkede reelt aldrig for de fleste felter) | **DELVIST** | Usecase (2), kun hvis udfoert | `UC-CONF-002` ("Gem override... NEEDS TESTDATA") eksisterede allerede i kataloget og daekker praecis dette scenarie — men var IKKE udfoert endnu. Modellen identificerer den utestede risiko korrekt, men garanterer ikke at nogen faktisk koerer UAT'en inden for en given tidsramme; opdagelsen skete reelt via Peters direkte observation, ikke via proceduren. Ingen tabt historisk implementering at genfinde (fejlen var der fra kodens oprindelse). |
| 5 | **OS-catalog hardcoded ubuntu:24.04** (`d3be534d` 08-08, **gentaget** i `b6377636`/PR #205 09-09) | **JA** | Historisk soegning (4) | `d3be534d` fiksede eksplicit "every call site" en maaned foer — men PR #205's commit-besked naevner IKKE `d3be534d` eller nogen tidligere fiks overhovedet, hvilket taler for at git-historikken ikke blev tjekket foerst. Et eksplicit `git log --all --grep`-soegning efter "ubuntu 24.04"/"OS catalog" foer #205 ville hoejst sandsynligt have fundet `d3be534d` og rejst spoergsmaalet "hvorfor er dette tilbage, naar vi allerede fiksede alle call sites?" — potentielt afsloerende en dybere strukturel aarsag (nye call sites tilfoejes uden at route gennem den centrale `_resolve_os_catalog_image()`-funktion). |
| 6 | **Virtuel-device-sletning** (Travbyen, `TL-IMPORT-*` unassigned to gange, ad hoc/manuel, ikke kodebaseret) | **NEJ i nuvaerende afgraensning** | Uden for §16's nuvaerende scope | §16 er skrevet om branch-disposition/kodeaendringer. Dette var en **manuel/ad hoc operationel handling** (formentlig direkte SQL/oprydningskommando) uden nogen PR/branch at anvende §16 paa. HANDOVER_LOG selv noterer eksplicit at "ingen kode i repoet implementerer denne oprydning" og advarer om at det kan ske en TREDJE gang. Kraever en udtrykkelig udvidelse af §16's anvendelsesomraade for at daekke manuelle/operationelle handlinger mod en registreret capabilitys underliggende data — ikke kun kodeaendringer. |

**Opsummering, uden pynt:** 2 af 6 sager (terminal, OS-catalog-gentagelse)
ville §16, som formuleret, sandsynligvis have fanget solidt. 2 (Global
Config, release-artifact) er kun delvist daekket og kraever enten en
proces-tilfoejelse (execution af NEEDS TESTDATA) eller en navngiven
udvidelse (drift-modstandsdygtige invarianter) for fuld daekning. 2
(SEC-016 oprindelige fund, virtuel-device ad hoc-sletning) ligger reelt
uden for denne mekanismes formaal og boer ikke tvinges ind i den.

## 5. Foreslaaede, navngivne udvidelser (ikke implementeret, til Peters stilling)

Baseret paa selvtesten ovenfor, to konkrete, minimale forslag ud over §16's
kernetekst — begge markeret som SEPARATE, valgfrie tilfoejelser, ikke en del
af §16's kerne, saa Peter kan acceptere §16 uden at skulle acceptere disse:

- **§16a (forslag):** et registreret capability-item boer eksplicit
  markere hvis dets implementering er afhaengig af en haandholdt
  liste/konstant/opremsning der historisk er gaaet forældet under vaekst
  (fx release-manifests, hardcodede versions-/imagenavne) — og enten
  foretraekke programmatisk udledning frem for haandopremsning, eller
  kraeve en eksplicit fuldstaendigheds-/architecture-ratchet-test.
- **§16b (forslag):** §16's anvendelsesomraade udvides eksplicit til ogsaa
  at omfatte **manuelle/ad hoc operationelle handlinger** (ikke kun
  kode-PR'er) mod data der tilhoerer en registreret capability — fx en
  engangs-SQL-oprydning mod `devices`/`device_assignments` for en
  capability som "virtuelle import-enheder skal bevares selvom de aldrig
  har heartbeat."

## 6. Sporgsmaal der kraever Peters beslutning

1. Skal §16 (kerneteksten i §3) accepteres som formuleret?
2. Skal §16a og/eller §16b tilfoejes, udskydes, eller afvises?
3. Skal GRC-migrationen (`item_type='capability'`) implementeres nu, eller
   afvente et konkret behov (fx naar `CAP-EDGE-RECOVERY-TERMINAL` skal
   registreres for #239)?
4. Skal `UI_USECASE_CATALOG_2026-08-26.md` linkes fra `00_START_HER.md`/
   `DOKUMENTPAKKE_OVERSIGT_v10.md` som en umiddelbar, lavrisiko rettelse
   uafhaengigt af resten af forslaget?
5. Hvem/hvad skal drive udfoerelsen af eksisterende `NEEDS TESTDATA`-poster
   (fx `UC-CONF-002`, som sag 4 ovenfor viser reelt kunne have fanget en
   longstanding bug)? Dette forslag identificerer hullet men foreslaar
   ingen ejerskabs-/tidsramme-mekanisme, medmindre Peter oensker det.
6. `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md` forbliver IKKE VERIFICERET
   (fil aldrig fundet committet) — skal der bruges tid paa at spore den
   yderligere (fx sporge Kimi/Codex-sessioner direkte), eller behandles
   tabt/erstattet af det naervaerende arbejde?

## 7. Korrektionsspor (bevaret, ikke omskrevet)

- `UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md` —
  original opdagelse + den senere korrektion af den falske negativ om
  `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md`, med den oprindelige forkerte
  paastand bevaret og markeret, ikke slettet.
- `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md` — v1 (paa PR #239) og
  v2 (paa denne PR, denne fils direkte forloeber) — bevares som historik;
  dette dokument er den konsoliderede v3/endelige version.
