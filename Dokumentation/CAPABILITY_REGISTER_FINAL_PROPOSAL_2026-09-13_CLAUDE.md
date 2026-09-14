# Capability Register — final proposal (review-ready, v4)

**Forfatter:** Claude Sonnet 5, 2026-09-13 · **v4-revision:** z.ai (GLM-5.3), 2026-09-14 — efter
uafhængig adversarial review af den frosne v3 (`a5422a60`) og out-of-sample crash-test mod
Edge1-incidenten. Se §0 og §5.
**Status:** FORSLAG, review-klar — INTET implementeret. GRC-skema uændret, §16 ikke tilføjet noget
governance-dokument, `UI_USECASE_CATALOG_2026-08-26.md` ikke selv rettet. Peter er beslutningsejer.
**Konsoliderer:** `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md` (v1 på PR #239, v2 på denne
PR) og `UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`. De forudgående
dokumenter er **bevaret uændrede** som korrektionsspor — se §9. Intet i denne fil omskriver dem
stiltiende; egne v3-fejl korrigeres med synlig markering, ikke sletning.

---

## 0. Revisionshistorik og korrektionsspor for denne fil

| Version | Hvor | Ændring |
|---|---|---|
| v1 | PR #239 | Første forslag (overså `UI_USECASE_CATALOG`) |
| v2 | `50a1cd31` | Revideret efter arkæologi-fundet af kataloget |
| v3 | `a5422a60` (frossen review-SHA) | Konsolideret "review-ready" + historisk selvtest |
| **v4** | denne revision | Korrigeret efter uafhængig adversarial review (fund F1–F6, alle efterverificeret) + **out-of-sample crash-test mod Edge1-incidenten** (§5). Hovedændringer: (a) selvtest sag 1 og 2 korrigeret (F1/F2); (b) test-fejlklasser adskilt (F5); (c) ny **§16.9** (deployment-accept: observeret runtime-sundhed som succeskriterium) udledt af Edge1-fejlklassen; (d) ny valgfri **§16c** (sundhedsalarmering); (e) præcisering af "minimal ny struktur" (F6); (f) underklausuler renummureret 3.x → 16.x (F4); (g) **minimum wiring-forslag som del af acceptpakken** (F3, §7). |

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
    (nuværende kildekode/komponent-reference
     + eksplicit git log --all-søgning for et evt. tabt/kendt-godt spor)
        |
        v
Automatisk verifikation
    (tests, architecture ratchets — håndhæver invarianterne maskinelt)
        |
        v
Runtime-/fysisk observation og evidens
    (faktisk observeret adfærd på en rigtig Edge/i produktion —
     adskilt fra og ikke erstattet af "testen er grøn")
```

**Sideordnede lag, IKKE en del af kæden — provenance/beslutning/arbejdstilstand, uændrede roller:**

| Struktur | Rolle | Ændres af dette forslag? |
|---|---|---|
| GRC-register | Autoritativ, struktureret capability-/verifikationsbutik | Udvides med `item_type='capability'` |
| `UI_USECASE_CATALOG_2026-08-26.md` | Menneskelæsbart UAT-/usecase-lag | Bevares; bør synliggøres fra `00_START_HER.md` |
| Tests/architecture ratchets | Maskinel håndhævelse af invarianter | Uændret; capability-items bør linke til dem |
| Menuguides (`MENUGUIDE_*_v1.md`) | Afledt brugerdokumentation | Uændret |
| ADR | Enkeltstående arkitekturbeslutning + provenance | Uændret |
| HANDOVER_LOG | Kronologisk driftslog/arbejdstilstand | Uændret (fortsat append-only, nyeste øverst) |
| PAKKE_SPOR_REGISTER | Branch-/pakke-/sporsporing (§14, §16-forslag) | Uændret |

> **Præcisering (F6, v4):** `GRC item_type='capability'` er en **bevidst, minimal NY struktur
> inde i den eksisterende autoritative butik** — ikke et separat, konkurrerende register, men
> heller ikke bogstaveligt "ingen ny struktur". Formålet er sammenkobling af eksisterende lag;
> den nye struktur er præcis én item-type og to konventionsværdier (§2).

## 2. Foreslået skemaændring (uændret fra v1–v3, minimal)

1. Ny migration: tilføj `'capability'` til `grc_items.item_type` CHECK-constraint.
2. `headend/api/grc_register_api.py`: tilføj `"capability"` til `ITEM_TYPES`.
3. Konvention (ikke skema-håndhævet; `relationship`/`evidence_type` er allerede frie strenge):
   `relationship` får `has_usecase`, `evidence_type` får `usecase_catalog_entry` og
   `known_good_reference`.

## 3. Forslag til §16 (additiv til det allerede accepterede §14; underklausuler renummureret 16.1–16.9 pr. F4)

> **§16 — Capability- og usecase-tjek før ændring af en consequential capability.**
>
> **16.1 Før disposition eller ændring.** Før en branch/change klassificeres
> `absorbed`/`superseded`, ELLER før en consequential ændring af en bruger-, drifts-,
> recovery-, sikkerheds- eller anden consequential capability påbegyndes — **herunder
> ændring af capability'ens leverance via deployment-, update- eller dependency-flow** —
> skal følgende identificeres og dokumenteres eksplicit:
> 1. Capability-intent/invarianter (GRC `item_type='capability'`, hvis registreret).
> 2. Relevante usecase(r) (`UI_USECASE_CATALOG_2026-08-26.md` eller dens efterfølger)
>    og deres aktuelle status. **Fravær af en dækkende usecase er selv et fund** (jf. 16.3),
>    ikke et grønt lys.
> 3. Nuværende autoritativ implementering (fil/komponent-reference).
> 4. Historisk/kendt-god implementering, hvor en sådan findes — via en **eksplicit
>    `git log --all`/branch-/stash-søgning for den pågældende komponent eller det
>    pågældende problem**, ikke kun nuværende mains historik.
> 5. Automatisk verifikation (hvilke tests håndhæver invarianterne i dag — og hvilken
>    fejlklasse de i så fald har: **dækningsgap** vs. **adfærds-lock-in**, jf. nedenfor).
> 6. Runtime-/fysisk verifikation, hvor det er relevant — **et bestået testsuite er ikke
>    i sig selv bevis for at capability'en faktisk virker i drift**; observeret
>    runtime-adfærd er en selvstændig evidenskilde, ikke en delmængde af testresultatet.
>
> **16.2 Søg efter problemet, ikke kun efter løsningens navn.** Søgningen i 16.1 pkt. 1–4
> skal dække det underliggende problem/den ønskede capability, ikke kun den terminologi en
> foreslået ny løsning selv introducerer. En søgning der kun bruger ens egne foreslåede
> navne/termer og konkluderer "intet fundet" er ikke tilstrækkelig.
>
> **16.3 Fravær er et dokumentationshul, ikke tilladelse.** Fravær af et registreret
> capability- eller usecase-opslag for et område der åbenlyst påvirker en consequential
> capability er IKKE tilladelse til at fortsætte uden videre — det skal disponeres eksplicit
> (registreres som en ny `capability`/`usecase`-post, eller bevidst noteret som en accepteret
> mangel, med begrundelse).
>
> **16.4 Capability-ækvivalens, ikke patch-ækvivalens.** Commits, filer, funktioner, tests
> eller ren patch-/diff-ækvivalens er IKKE i sig selv tilstrækkeligt bevis for at en
> historisk branch/change er `absorbed` eller `superseded`, når den påvirker en registreret
> capability. Den aktuelle implementering skal sammenholdes med capability'ens intent og
> invarianter, ikke kun med dens kode.
>
> **16.5 Ingen stiltiende degradering.** En forbedring af én del af en registreret
> capability må ikke stiltiende forringe en anden del af samme capability (fx: en ny
> renderer må ikke fjerne en allerede-fungerende sessionsmodel; en ny sessionsmodel må
> ikke fjerne en allerede-fungerende renderer).
>
> **16.6 Kildefriskhed før søgning.** Enhver søgning der skal understøtte 16.1 pkt. 1–4
> skal først bekræfte at dens datakilde er autoritativ/frisk (for git: eksplicit
> `origin/<default-branch>` eller en navngiven, verificeret commit — ikke en lokal
> arbejdskopis `HEAD` uden først at sammenligne `git rev-parse HEAD` mod
> `git rev-parse origin/main`).
>
> **16.7 Standard for en konsekvent fraværskonklusion.** En "IKKE
> FUNDET/EKSISTERER IKKE"-konklusion, der har konsekvens (fx retfærdiggør at springe et
> genfindingstrin over), må først opfylde: (a) bekræftet kildefriskhed (jf. 16.6), og
> (b) mindst to uafhængige søgemetoder (fx både indholds-`grep` OG
> `git log --diff-filter=A`/`gh search`). Uden begge dele rapporteres konklusionen som
> **IKKE VERIFICERET**, ikke som fravær. En sådan konklusion skal citere den
> reproducerbare kommando/metode, så den kan efterprøves uafhængigt.
>
> **16.8 Modstridende evidens forbliver eksplicit.** Når to kilder (fx en commit-besked
> og en observeret systemtilstand, eller to sessioners fund) modsiger hinanden, skal begge
> udsagn bevares synligt side om side, indtil modsigelsen er aktivt afklaret — ikke
> stiltiende harmoniseret.
>
> **16.9 Deployment-accept: observeret runtime-sundhed er en del af succeskriteriet.**
> *(Ny i v4 — udledt af Edge1-out-of-sample-testen, §5; generel regel, ikke
> incident-specifik.)* En ændring der leverer kode, konfiguration eller afhængigheder til
> en registreret consequential capability er **først gennemført/succesfuld, når den berørte
> capability er observeret sund i drift efter ændringen** — servicen oppe og svarende,
> kritisk funktionskontrol gennemført, og de tiltænkte adgangsveje fungerende. For
> automatiserede leveranceflow (fx update-godkendelse/rollout) indgår denne observation som
> en **gate**: et target/canary der ikke er **observeret sundt**, er ikke en bestået
> udrulning — uanset rapporteret deploy-status i database eller UI.

> **Note om test-fejlklasser (F5, v4):** 16.1 pkt. 5 skelner mellem (1) **dækningsgap** —
> tests øver aldrig den faktiske capability (direct-Edge-terminalens renderer var dette:
> tests verificerede session/transport, aldrig interaktiv terminal-adfærd) — og (2)
> **adfærds-lock-in** — tests gennemtvinger aktivt degraderet/forkert adfærd som korrekt
> (release-artifact-håndlisten, hvor kontrakttesten selv kodificerede den forkerte liste).
> Klasserne er ikke ækvivalente: 16.9 (runtime-observation) adresserer hul-blindhed;
> ratchet-krav (§16a) adresserer lock-in. [KORRIGERET v4: v3 brugte lock-in-formuleringen
> om terminal-sagen.]

## 4. Historisk selvtest — seks kendte hændelser (korrigeret v4)

Selvtesten er korrigeret efter adversarial review uden at svække den overordnede ærlighed:
2 solidt fanget, 2 delvist, 2 uden for mekanismens formål — men med **rettelser til sag 1
og 2** (F1/F2) og præcisering af sag 3 (F5). "Gate" refererer til lagene i §1.

| # | Hændelse | Ville §16 have opdaget/stoppet den? | Ved hvilken gate | Begrundelse |
|---|---|---|---|---|
| 1 | **Direct-Edge terminal** (xterm.js-regression, PR #198/#238) | **JA — via historisk søgning (4) alene** *[KORRIGERET v4: v3 angav også usecase-gate 2 — det var overbelastet]* | Gate 4 | Kataloget har **ingen** usecase der dækker den direkte-Edge portal-terminals interaktive capability: `UC-SSH-002/003` dækker *headend-tunnel*-terminalen (en anden flade), `UC-TECH-001–003` dækker ServiceSession/relæ/lease. PR #198 rørte `totp-service.py` = den direkte flade. Fangsten bæres alene af gate 4: `d67ca26d` (xterm.js, live-testet) lå hele tiden i `git log --all`. **Fraværet af en dækkende usecase er selv et §16.3-dokumentationshul** — usecase-lagets blind vinkel var medvirkende. Tests = **dækningsgap** (ikke lock-in, jf. noten i §3). |
| 2 | **SEC-016 factory TOTP** | **PARTIELT** *[KORRIGERET v4: v3 klassificerede hele historikken som uden for rækkevidde — for smalt]* | 16.1.1 (intent/invarianter), hvis registreret | Der skal skelnes: **(A) det oprindelige sikkerhedsfund** (usikker delt demo-secret) er et aldrig-tidligere-flagget factory-default — uden for denne mekanismes formål; dækkes af sikkerhedsreview. **(B) lukning-uden-erstatning** — den konsekvente hændelse (jf. HANDOVER 2026-08-16): den usikre bootstrap-vej blev fjernet **uden erstatning**, hvorved commissioning/bootstrap-capability'en regresserede og enheder blev fysisk låst ude. (B) ER en capability-regression, som 16.1.1 ville have flagget, hvis en CAP-post med invarianten "commissioning kræver en bootstrap-adgangsvej" havde eksisteret. Del (B) hører hjemme i selvtesten som DELVIST fanget. |
| 3 | **Release-artifact hand-liste** (`f1100e30`, 4 manglende edge-moduler, crash loop) | **DELVIST/NEJ i nuværende omfang** | Ingen af gates rammer direkte | Root cause: håndholdt modulliste der gik forældet under vækst. Dette er klassens tydeligste eksempel på **adfærds-lock-in**: kontrakttesten kodificerede selv den forkerte liste og forblev grøn. Kræver navngiven udvidelse (§16a), ikke noget der allerede er dækket. |
| 4 | **Global Config** (merge-argumenter omvendt; virkede reelt aldrig for de fleste felter) | **DELVIST** | Usecase (2), kun hvis udført | `UC-CONF-002` ("Gem override… NEEDS TESTDATA") dækkede præcis scenariet men var ikke udført. Modellen identificerer den utestede risiko, men garanterer ikke eksekvering inden for en tidsramme; opdagelsen skete via Peters direkte observation. Ingen tabt historisk implementering (fejlen var der fra kodens oprindelse). |
| 5 | **OS-catalog hardcoded ubuntu:24.04** (`d3be534d` 08-08, gentaget i `b6377636`/PR #205 09-09) | **JA** | Historisk søgning (4) | #205's commit-besked nævner ikke den tidligere fix (verificeret: 0 forekomster). En `git log --all --grep "ubuntu:24.04"` **finder** `d3be534d` (strengen står i commit-bodien) — modstykke-formuleringen "højst sandsynligt" fra v3 kan opgraderes til **demonstrerbart**. Dybere strukturel pointe står ved magt: nye call sites tilføjes uden routing gennem den centrale resolver. |
| 6 | **Virtuel-device-sletning** (Travbyen, ad hoc/manuel, ikke kodebaseret) | **NEJ i nuværende afgrænsning** | uden for §16's scope | Manuel/operationel handling uden PR/branch. HANDOVER noterer at "ingen kode i repoet implementerer denne oprydning" og advarer om en tredje gang. Kræver §16b. |

**Opsummering (uændret antal, justeret sammensætning):** 2 solidt (terminal — nu via gate 4 alene;
OS-catalog-gentagelse), 2–3 delvist (Global Config; release-artifact; SEC-016's
lukning-uden-erstatning — *opgraderet fra "uden for scope" i v3*), 1–2 uden for mekanismen
(SEC-016's oprindelige fund; virtuel-device-sletning).

## 5. Out-of-sample crash-test — Edge1-incidenten (2026-09-14, efter frysning)

Incidenten opstod **efter** at v3 blev frosset (`a5422a60`) og er brugt som uafhængig test:
modellen er **ikke** modificeret for at gøre den bestående — se klassifikationen.

**Verificeret hændelseskæde (uafhængig recovery-undersøgelse):** Edge1 (`TL-C87FF9587CA0`)
tabte sin direkte TOTP-portal på :8443. Rodårsag: `timelapse-totp.service` crash-loopede
(~13.039 genstarter over ~19 timer) fordi et dependency-update (2026-09-11) installerede
`pydantic_core 2.49.0` ved siden af `pydantic 2.13.5`, der kræver core 2.46.5 (exact-pin).
Genoprettelse af det konsistente par (`pydantic_core 2.46.5`, identisk med kendt-god Edge2)
genoprettede straks stabil drift. Pi-hole var installeret men **urelateret** (fjernet separat
efter Peters beslutning). Yderligere verificerede observationer: den defekte bundle nåede kun
Edge1 (canary-scope begrænsede uventet skaden); der var ingen effektiv postflight/canary-sundheds-
gate der forhindrede accept af en død canary; ~13.039 genstarter frembragte ingen alarm;
`fetch_python_bundle.py` ser ikke ud til at validere exact-afhængighedsrelationer
(pydantic → pydantic_core) — *implementationsobservation, afventer verificering af ejer, ikke
antaget som faktum her*.

**Svar på de otte testspørgsmål (mod frossen §16 v3):**

1. **Capability:** Direkte lokal adgang til Edge — TOTP recovery-/management-portalen på :8443
   (bruger-/drifts-/recovery-capability).
2. **Relevante invarianter:** (a) `timelapse-totp` kører og svarer HTTPS på 8443; (b) portalen er
   nåbar fra tiltænkte adgangsveje; (c) runtime-miljøet er internt konsistent (servicens imports
   lykkes — pydantic↔pydantic_core-exact-pin er en sådan invariant, om end implicit);
   (d) (a)–(c) består efter ændringer i leverancen.
3. **Eksisterende usecases:** Ingen der dækker portalens egen tilgængelighed/sundhed.
   `UC-LOCAL-001/002` dækker admin-UI'ets oversigtsside, ikke portalen på enheden. **Dækningsgap.**
4. **Ville frossen §16 have forhindret den inkompatible udrulning?** **Nej.** V3's triggers var
   (i) branch-disposition og (ii) "ny implementering påbegyndes". En rutinemæssig
   dependency-udrulning gennem det etablerede update-flow er ingen af delene. Ingen af de 6 lag
   spørger "er afhængighedssættet internt konsistent efter installation?".
5. **Ville den have detekteret at canaryen blev usund?** **Nej** — intet krav om post-deploy
   sundhedsobservation; 3.1.6 adskilte kun evidens-kilder konceptuelt.
6. **Krævede den observeret runtime-sundhed før succes?** **Nej** — ikke bindende i v3.
7. **Ville den have detekteret 13.039 genstarter?** **Nej** — intet om alarming i v3.
8. **Kunne en agent være fuldt §16-v3-compliant og stadig forårsage præcis denne incident?**
   **Ja.** Compliance var opnåelig uden at røre pin-konsistens eller canary-sundhed; selv en
   3.3-"dokumenteret mangel"-notering kunne være disponeret som accepteret uden Peter.

**Klassifikation (mod frossen v3): NOT PREVENTED.** Frøet til detektion fandtes i 3.1.6
("runtime ≠ test"), men var ikke bindende for deployment-accept — og ærlig konstatering er,
at en retroaktiv "den ville have fanget den" ville være præcis den strækning, selvtesten
lovet at undgå.

**Udledt mindste generelle regel (optaget som §16.9):** *En ændring der leverer kode/konfig/
afhængigheder til en consequential capability er først gennemført, når capability'en er
observeret sund i drift — og for automatiserede flows er dette en gate, ikke en rapport.*
Reglen er udledt af fejlklassen "capability dør efter tilsyneladende succesfuld leverance"
og er formuleret generelt (ingen henvisning til pydantic, Edge1 eller TOTP i selve klausulen).

**Sekundær læring (til separat behandling, ikke §16-tekst):** canary-scope begrænsede skaden
uden at være designet til det; manglende flapping-alarm lod 13.039 genstarter passere uomtalt →
forslået som valgfri **§16c** (nedenunder) + som observation til update-governance-sporet.

## 6. Navngivne, valgfrie udvidelser (disposition v4)

- **§16a — drift-modstandsdygtige invarianter (FASTHOLDT som valgfri):** registrerede
  capability-items markerer afhængighed af håndholdte lister/konstanter (release-manifests,
  hardcodede versions-/imagenavne) og kræver programmatisk udledning eller eksplicit
  fuldstændigheds-/ratchet-test. Bevis: sag 3 (adfærds-lock-in). Edge1 tilføjer intet nyt
  bevis for/immer imod — uændret.
- **§16b — manuelle/ad hoc operationelle handlinger (FASTHOLDT som valgfri, med afklaret
  afgrænsning):** dokumentationskrav for engangs-operationelle handlinger mod en registreret
  capabilitys data (Travbyen-klassen). Kerne-triggeren (16.1) dækker fra v4 **automatiserede
  leveranceflow** (deployment/update); rene manuelle data-operationer forbliver i §16b, så
  kernen ikke bykratiseres.
- **§16c — sundhedsalarmering (NY, valgfri):** vedvarende fejlsignaler for en registreret
  capability (fx service-restart-løkker, gentagne health-check-fejl) skal rejse en synlig
  alarm/GRC-finding uden manuel opdagelse. Bevis: 13.039 genstarter uden alarm (Edge1) og
  BT-TOTP/kapabiliteter der "fejlede stille siden hardeningen" (HANDOVER 2026-08-24-klassen).

## 7. Minimum wiring-forslag for §16 (DEL AF ACCEPTPAKKEN — ikke valgfri senere forbedring)

Princip (F3): **én kanonisk regel** (PAKKE_SPOR_REGISTER §16) + **routing fra den obligatoriske
operationelle path**. Ingen duplikering af §16-tekst i flere filer. Følgende er foreslåede
*eksakte* ændringer — implementeres først ved Peters accept af §16 (denne PR implementerer intet):

- **W1 — `AGENTS.md`, punkt 3 udvidelse (og søster-loaders `CLAUDE.md`/`GEMINI.md`/
  `CHATGPT-PROJECT-INSTRUCTIONS.md` m.fl., samme sætning):**
  > "Before superseding/disposing of branches, or starting or delivering a consequential
  > capability change (new implementation, or deployment/update/dependency rollout), follow
  > `Dokumentation/PAKKE_SPOR_REGISTER.md` §16: capability intent/invariants, relevant
  > usecases, authoritative + historical implementation, and verification. A capability
  > change is not complete until runtime health is observed (§16.9)."
- **W2 — `OP-001` (vendored preamble), Step 5 "Search Before Create" tilføjelse:**
  > "For consequential capabilities, the search extends to capability equivalence per
  > `PAKKE_SPOR_REGISTER` §16, and observed runtime health is part of completion (§16.9)."
- **W3 — PR-template (valgfri sekundær forstærkning):** tjekpunkt
  "§16-tjek udført: ___ (capability berørt: nej / ___)", med link. Kun hvis Peter finder
  det nyttigt udover W1/W2.

Hvorfor dette er minimum: AGENTS.md/OP-001 er de to steder alle agenter *allerede* er tvunget
igennem (AGENTS.md punkt 1 + punkt 3); PAKKE_SPOR §16 er allerede konsulteret ved
R04/disposition. W1+W2 lukker det manglende led — "agent påbegynder/implementerer/leverer" —
uden at opfinde en ny kontrolstruktur.

## 8. Spørgsmål der kræver Peters beslutning (v4)

1. Acceptér §16 kernetekst (§3, nu 16.1–16.9) som formuleret?
2. Tilføj/udskyd/afvis §16a og/eller §16b — og den nye §16c?
3. Kør GRC-migrationen (`item_type='capability'`) nu eller ved første behov (fx
   `CAP-EDGE-RECOVERY-TERMINAL` for #239)?
4. Link `UI_USECASE_CATALOG_2026-08-26.md` fra `00_START_HER.md`/
   `DOKUMENTPAKKE_OVERSIGT_v10.md` som uafhængig lavrisiko-rettelse?
5. Hvem/hvad driver eksekvering af eksisterende `NEEDS TESTDATA`-poster (sag 4 viser reelt tab)?
6. `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md`: videre sporing eller tabt/erstattet?
7. Acceptér wiring-pakken (W1+W2 obligatorisk, W3 valgfri) som betinget del af §16-accept?
8. Edge1-implementationsobservationer (pin-par-validering i `fetch_python_bundle.py`,
   postflight-gate i update-flow, flapping-alarm) er noteret til update-governance-sporet —
   bekræft at de afledes/afejes dér og valideres af ejer, ikke i denne PR.

## 9. Korrektionsspor (bevaret, ikke omskrevet)

- `UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md` — original opdagelse
  + korrektion af den falske negativ om `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md`, med den
  oprindelige forkerte påstand bevaret og markeret.
- `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md` — v1 (PR #239) og v2 (`50a1cd31`),
  bevaret som historik.
- **v3 (`a5422a60`) → v4 (denne):** korrektioner F1 (selvtest sag 1), F2 (sag 2), F4
  (renummerering), F5 (test-fejlklasser), F6 (præcisering) + ny §16.9/§16c + §5
  out-of-sample-test + §7 wiring — alle ændringer markeret inline med *[KORRIGERET v4…]*/nye
  afsnit; intet tidligere fejlindhold er slettet uopmærket.
