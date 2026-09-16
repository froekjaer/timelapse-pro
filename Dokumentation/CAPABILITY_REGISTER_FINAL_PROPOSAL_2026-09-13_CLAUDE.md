# Capability Register — final proposal (review-ready, v4)

**Forfatter:** Claude Sonnet 5, 2026-09-13 · **v4-revision:** z.ai (GLM-5.3), 2026-09-14 — efter
uafhængig adversarial review af den frosne v3 (`a5422a60`) og out-of-sample crash-test mod
Edge1-incidenten. Se §0 og §5. · **v4+-tilføjelser:** Claude Sonnet 5, 2026-09-14 — lagt oven
paa z.ai's v4 uden at overskrive den (§2a, §5a, §5b): fire skemahuller Codex-reviewet fandt som
v4 ikke daekkede; en direkte LAN-adgang-til-8443-undersoegelse; og en (siden LUKKET, se §5a)
EKSPLICIT modsigelse mellem denne sessions Pi-hole-fund og z.ai's Edge1-fund (jf. §16.8's egen
regel om ikke at harmonisere modstridende evidens stiltiende — modsigelsen blev holdt aaben
indtil Peter leverede autoritativ, fysisk/SSH-verificeret evidens, ikke gaettet paa). · **Beslutningsejer-disposition,
2026-09-14 (§5b):** Peter har afklaret :8443-management-capabilitys tiltaenkte scope som
bevidst multi-netvaerk (IKKE BT-PAN-only) — `0.0.0.0`-binding er korrekt adfaerd, dokumentation
der siger BT-PAN-only er forældet. Provenance for denne intent-konflikt (dokumenteret intent →
observeret runtime → konflikt rapporteret → beslutningsejer-disposition) er bevaret i sin fulde
fire-trins-form i §5b, ikke stiltiende omskrevet.
**Status (opdateret v6, 2026-09-16):** FORSLAG, IKKE formelt accepteret i SAMARBEJDSMODEL — §16-teksten
selv er stadig ikke tilfoejet noget governance-dokument dér. Men "INTET implementeret" er nu STALE og
ERSTATTES her, ikke stiltiende: arkitekturretningen er godkendt (§0a), Mission Framework-opstroems-
propagationsreglen ER implementeret og merged (`mission-framework` PR #13), og TimeLapse-siden (OP-001
cache/arkitektur C, W1/W2/W3, PAKKE_SPOR-udvidelse) ER implementeret og testet (Wave 2, se §7). GRC-skema
fortsat uændret; `UI_USECASE_CATALOG_2026-08-26.md` fortsat ikke selv rettet. Peter er beslutningsejer for
den resterende, adskilte formelle §16-accept-handling.
**z.ai's endelige uafhaengige verifikation, 2026-09-14** (mod `2b270323`): "READY AFTER
NON-MATERIAL FIX" — to ikke-materielle rettelser identificeret (Pi-hole-provenance-lukning,
§16.3 self-accept-bypass), begge udfoert i denne revision. Ingen §16-accept udfoert af denne
verifikation eller af denne revision — det forbliver Peters separate, fremtidige handling.
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
| **v5** | denne revision, 2026-09-14 | Efter Peters ARKITEKTURGODKENDELSE (§0a, bevaret ordret) af PR #240 ved `7ed3e3dd`: §16b/§16c's tidligere "anbefalet, ikke anvendt"-formuleringer fra analyserapporten er nu ANVENDT direkte i selve klausulteksten (materiel-paavirkning i §16b, risiko/impact ikke varighed i §16c); ny REUSE>EXTEND>NEW-disposition tilfoejet; "tynd prototype tilladt hvis ikke konkurrerende source-of-truth"-kriterium tilfoejet til de AI-routing-relaterede DECISION REQUIRED-punkter; W1's forkerte "PAKKE_SPOR_REGISTER §16"-reference rettet til korrekt placering. **Godkendelsen daekker arkitekturretningen, IKKE formel §16-accept eller merge — begge afventer fortsat wiring+verificering.** |
| **v6** | denne revision, 2026-09-16 (Wave 2, Claude Sonnet 5) | Efter Mission Framework Wave 1 (canonical OP-001 Step 7 + Framework Findings faktisk implementeret og merged, `mission-framework` PR #13) og Peters valg af OP-001-integrationsarkitektur **C** (canonical + kontrolleret lokal cache/fallback): ny **§16.10** (cross-repo/publikations-propagation, reference til kanonisk kilde, ikke fork); TimeLapse's OP-001-kopi migreret fra "vendoret, verbatim" til scriptet cache (`refresh_op001_cache.py`, `OP-001.provenance.json`, VERIFIED/STALE/UNKNOWN); alle fire loader-filer opdateret (terminologi + §16-status, inter-fil-drift fundet og rettet — se §7); `PAKKE_SPOR_REGISTER.md`s §14.6-felter udvidet med cross-repo/website-paavirkningsfelt; **W3 (PR-template) EKSEKVERET**, tidligere "IKKE eksekveret." Formel §16-ACCEPT (SAMARBEJDSMODEL) fortsat IKKE udfoert — uaendret fra v5, ingen mandat i denne boelge til at aendre det. |

---

## 0a. Peters arkitekturgodkendelse, 2026-09-14 (bevaret ordret)

Peter godkendte arkitekturretningen i PR #240 ved head `7ed3e3ddab56997ad41067b4ba73e36093f310f2` (analyserapportens sidste, adversarial-review-korrigerede revision). Bevaret ordret som provenance:

> Jeg godkender arkitekturretningen i PR #240 ved head `7ed3e3ddab56997ad41067b4ba73e36093f310f2` som grundlag for den videre implementering.
>
> Godkendelsen omfatter mine 16 godkendte governance-principper og den analyserede arkitektoniske placering af dem.
>
> Godkendelsen betyder ikke, at de identificerede capabilities, GRC-/Compliance Cockpit-funktioner, AI-routing/autonomi, monitoring eller upstream Mission-komponenter allerede er implementeret, compliant eller verificeret.
>
> REUSE skal foretrækkes før EXTEND, EXTEND før NEW, og generiske cross-project funktioner skal som udgangspunkt placeres i det korrekte upstream-lag frem for at skabe parallelle TimeLapse-specifikke løsninger.
>
> Hvor upstream-arkitekturen endnu ikke er moden nok, må en tynd TimeLapse-implementering/prototype anvendes til at validere behov og arkitektur, hvis den ikke etablerer en konkurrerende source of truth eller låser den generiske løsning til TimeLapse.
>
> §16, §16a, §16b og §16c samt W1/W2 skal nu bringes i overensstemmelse med den godkendte arkitektur, men acceptance og merge sker først efter den nødvendige wiring og verificering.
>
> De resterende DECISION REQUIRED-punkter må ikke antages løst af denne godkendelse. De skal enten forelægges mig, når de bliver materielle for implementeringen, eller løses inden for et allerede eksplicit delegeret mandat.
>
> Peter, Decision owner, 2026-09-14

**Praecist omfang af godkendelsen (ikke udvidet, ikke indskraenket):**
- **Godkendt:** de 16 principper selv; deres arkitektoniske placering (§2's fire-lags-kortlaegning); REUSE>EXTEND>NEW som disposition-raekkefoelge; "tynd prototype tilladt hvis den ikke etablerer en konkurrerende source-of-truth eller laaser en generisk loesning til TimeLapse" som kriterium for fremtidige lignende afvejninger (IKKE en forudbestemt konklusion for nogen konkret DECISION REQUIRED-sag); at §16/§16a/§16b/§16c/W1/W2 nu bringes i overensstemmelse med denne arkitektur.
- **IKKE godkendt/IKKE antaget loest:** nogen konkret capability, GRC-/Compliance-Cockpit-funktion, AI-routing/autonomi-mekanisme, overvaagning, eller upstream Mission-komponent som allerede implementeret/compliant/verificeret; nogen af de resterende DECISION REQUIRED-punkter (herunder om `AI_KOMPETENCER_OG_OPGAVEROUTING.md` skal danne grundlag for en tynd lokal prototype — det AFGOERES IKKE her, kun kriteriet for en fremtidig afgoerelse er nu givet); formel §16-accept (markering af §16 som "Accepted" i SAMARBEJDSMODEL); merge af PR #239/#240.

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

## 2a. Yderligere skemahuller fundet ved automatiseret review (ikke daekket af v4's Sec2)

**Tilføjet (Claude Sonnet 5), 2026-09-14 — uafhaengigt genverificeret,
ikke blot accepteret.** v4's Sec2 er markeret "uændret fra v1-v3, minimal"
og daekker derfor ikke fire konkrete, verificerede implementeringshuller
den automatiserede review (`chatgpt-codex-connector[bot]`, PR #240) fandt
i v1/v2. De staar stadig aabne mod DENNE version og boer indgaa i en evt.
implementeringsbeslutning:

1. **Skematisk ugyldigt link-design:** at knytte en usecase-kataloglinje
   til en capability via `grc_evidence` fungerer ikke — `grc_links.source_
   item_id`/`target_item_id` er begge NOT NULL foreign keys til
   `grc_items.id` (`v23_grc_register.sql`), mens `grc_evidence` har sit
   eget, adskilte primaernoegle-rum. Et `has_usecase`-link kan derfor enten
   fejle paa foreign-key-tjekket, eller ved et uheld ramme et forkert
   `grc_items`-opslag med samme numeriske id. Reel loesning: enten en
   `grc_items`-raekke pr. usecase, eller evidence knyttet direkte til
   capability-item'et (`grc_evidence.item_id`), ikke et `grc_links`-forsoeg.
2. **Duplikeret skema-sandhedskilde:** `headend/database.py:1368-1371`
   definerer sin EGEN, uafhaengige `ck_grc_items_type`-CHECK-constraint med
   kun de oprindelige seks typer. Databaser initialiseret via ORM (ikke kun
   via migrationsscriptet) ville stadig afvise `capability`-raekker uden
   denne rettet parallelt med migrationen.
3. **UI-hardkodning:** Compliance-UI'et hardkoder den samme seks-vaerdis
   TypeScript-union og filterliste to steder
   (`timelapse-ui/src/pages/CompliancePage.tsx:181` og `:698`) — uden
   opdatering her er den nye type usynlig/ufiltrerbar i selve UI'et.
4. **Ingen link-API/UI:** der findes i dag ingen generisk API/UI til at
   oprette eller inspicere `grc_links`-relationer — `grc_register_api.py`
   opretter kun ét fast, hardkodet link i sit bootstrap-endpoint. Uden en
   skrive-/laesesti forbliver capability-til-usecase-sporbarhed usynlig og
   kun tilgaengelig via direkte SQL.

**Konklusion:** "minimal ny struktur" (v4's F6-praecisering) er korrekt
paa SKEMA-niveau (én ny item-type, to konventionsvaerdier), men en
FUNGERENDE implementering kraever ogsaa punkt 1-4 ovenfor. Dette forslag
forbliver et forslag om skemaet; punkt 1-4 er dokumenteret her saa en
fremtidig implementeringsbeslutning ikke undervurderer det reelle omfang.

## 3. Forslag til §16 (additiv til det allerede accepterede §14; underklausuler renummureret 16.1–16.9 pr. F4, 16.10 tilfoejet i v6)

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
> mangel, med begrundelse). **En accepteret mangel der påvirker en consequential capability
> kræver eksplicit godkendelse af beslutningsejeren. En agent kan identificere, dokumentere
> og anbefale accept af manglen, men kan ikke acceptere manglen på beslutningsejerens vegne**
> — agenten identificerer, dokumenterer evidens/risiko/muligheder og kan anbefale en
> disposition; beslutningsejeren accepterer, udskyder eller afviser den. *(Tilføjet 2026-09-14
> efter et fund fra z.ai: uden dette kunne en agent formelt "acceptere" sin egen undtagelse
> ved blot at kalde den en "accepteret mangel med begrundelse.")*
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
>
> **16.10 Cross-repository/publikations-propagation (reference, ikke fork — ny i v6, 2026-09-16).**
> En consequential ændring omfattet af 16.1 skal ogsaa opfylde den kanoniske Mission Framework
> Governance Propagation-regel: OP-001 Step 7 (cross-repo/publikations-paavirkning, begge
> retninger, evidenskrav for negative konklusioner, gab-registrering) + Framework Findings
> (opstroems-kanal for generiske laeringer). **Denne klausul gengiver IKKE Step 7's tekst** —
> se den kanoniske kilde (`froekjaer/mission-framework`, `docs/operational/OP-001-Mission-
> Operational-Preamble.md`), cachet lokalt per dette repos C-arkitektur (`Dokumentation/
> mission-framework/README.md`). Det TimeLapse-specifikke bidrag her er UDELUKKENDE hvor
> fuldfoerelsesevidensen for et TimeLapse-arbejdsspor registreres: `PAKKE_SPOR_REGISTER.md`s
> §14.6-felter (udvidet, se HANDOVER 2026-09-16) for lokale/ingen-paavirkning-konklusioner, og
> en Mission Framework Finding (jf. `FF-TLP-0001`) naar en generisk opstroems-relevant laering
> identificeres. §16.1's Visible-Preamble-Record-agtige fuldfoerelseskrav (punkt 6, runtime-
> evidens) og OP-001 Step 7's fuldfoerelseskrav er bevidst parallelle, ikke duplikerede: OP-001
> Step 7 gaelder for enhver Mission Framework-deltager generelt; 16.10 praeciserer kun HVOR
> TimeLapse konkret registrerer sin del af den samme forpligtelse.

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

## 5a. Pi-hole og Edge1 — LUKKET 2026-09-14 (var modstridende evidens, nu afklaret; korrektionsspor bevaret nedenfor)

**Tilføjet (Claude Sonnet 5), 2026-09-14.** Foer z.ai's v4-revision var
tilgaengelig, havde jeg allerede udfoert en selvstaendig, netvaerksbaseret
undersoegelse af Edge1's `.134`-uopnaaelighed
(`EDGE1_8443_UNREACHABLE_ROOT_CAUSE_2026-09-13_CLAUDE.md`, ikke aendret af
denne revision). Min konklusion dengang: `.134` svarede som en **Pi-hole-
enhed** (lighttpd, Pi-hole blocking-page paa port 80), og jeg konkluderede
at IP'en sandsynligvis var DHCP-genudlejet til en ANDEN, urelateret fysisk
enhed — baseret UDELUKKENDE paa netvaerks-scanning (ping/curl/openssl),
UDEN SSH-adgang til nogen Edge.

z.ai's v4 (Sec5, baseret paa en "uafhaengig recovery-undersoegelse" —
formentlig med reel SSH/enhedsadgang jeg ikke selv havde) giver en anden
forklaring: Edge1 crash-loopede pga. et `pydantic`/`pydantic_core`-
version-mismatch, og "Pi-hole var installeret men **urelateret** (fjernet
separat efter Peters beslutning)."

**Disse to fund er IKKE identiske, og jeg harmoniserer dem IKKE stiltiende
(jf. Sec16.8, som denne fil selv foreslaar):**
- Hvis Pi-hole faktisk kørte PAA/naer Edge1's egen IP og blev "fjernet" —
  betyder det at Pi-hole var installeret OVENPAA eller VED SIDEN AF Edge1
  (ikke en helt urelateret tredje enhed andetsteds paa DHCP-lejemaalet, som
  jeg antog), hvilket rejser et nyt, uafklaret spoergsmaal: **hvordan og
  hvorfor endte en Pi-hole-installation paa/naer en produktions-Edge, og er
  det relateret til eller uafhaengigt af pydantic-crashloopet?**
- Min egen `.134`-observation (Pi-hole svarende paa port 80/8443-refused)
  var et faktisk, reproducerbart netvaerksfund paa undersoegelsestidspunktet
  — den er ikke forkert i sig selv, men min FORTOLKNING af det
  ("sandsynligvis en anden fysisk enhed via DHCP") staar nu i spaending
  med z.ai's "installeret men urelateret, fjernet."
- **Jeg beder Peter om en praecisering** frem for selv at vaelge mellem de
  to fortolkninger: sad Pi-hole fysisk paa Edge1's egen hardware, paa en
  separat enhed der delte IP via DHCP, eller noget tredje? Dette paavirker
  om Sec16c (sundhedsalarmering) ogsaa boer daekke "uventet software paa en
  registreret capability's vaert", ikke kun service-crash-loops.

**STATUS (historisk, bevaret uaendret):** Punktet forblev AABENT gennem to
foregaaende forespoergsler — Peter refererede til en "already supplied
Pi-hole evidence correction" som ikke var modtaget i denne samtale eller
som ny commit paa branchen. Ingen loesning blev fabrikeret i den periode.

**LUKKET 2026-09-14 — autoritativ evidens nu modtaget direkte fra Peter
(beslutningsejer, fysisk/SSH-verificeret via reverse-tunnel til
`TL-C87FF9587CA0`):**

1. Peter forbandt gennem den verificerede reverse-tunnel til
   `TL-C87FF9587CA0`.
2. Runtime identificerede maskinen som hostname `timelapse0101`, LAN-IP
   `192.168.86.134`.
3. Pi-hole var DIREKTE observeret installeret paa netop denne Edge1
   (pakkerne `pihole`, `pihole-FTL`).
4. Pi-hole blev efterfoelgende fjernet fra samme Edge1.
5. Netvaerks-/DNS-drift blev verificeret bevaret efter fjernelsen.
6. Pi-hole var UREL­ATERET til :8443-udfaldet.
7. Den faktiske :8443-rodaarsag var det inkompatible afhaengighedspar:
   `pydantic 2.13.5` + forkert `pydantic_core 2.49.0` (kompatibel
   kendt-god core: `2.46.5`) — uaendret fra z.ai's v4-fund (§5).
8. Den tidligere hypotese om at `.134` var DHCP-genudlejet til en
   SEPARAT Pi-hole-enhed er derfor **AFKRAEFTET**.

**Praecis rekonciliering (begge observationer var korrekte; kun
FORTOLKNINGEN var forkert):**
- At `.134` eksponerede Pi-hole — **korrekt observeret**.
- At `.134` er Edge1 — **korrekt observeret** (ogsaa i min egen tidligere
  undersoegelse, som identificerede `.134` korrekt via mDNS-navnet
  `timelapse0101.local`, jf. `EDGE1_8443_UNREACHABLE_ROOT_CAUSE_2026-09-13_
  CLAUDE.md`).
- At disse to observationer sammen indebar TO FORSKELLIGE fysiske enheder
  — **forkert fortolkning**. Pi-hole var installeret PAA Edge1's egen
  hardware, ikke paa en separat, DHCP-genudlejet enhed.

Min oprindelige DHCP-genudlejnings-hypotese (§5a's foerste udgave, ovenfor,
IKKE slettet) var dermed en rimelig, men forkert, fortolkning af korrekt
observeret netvaerksdata — begaaet uden SSH/fysisk enhedsadgang, som denne
sessions sandbox aldrig har haft. Den bevares synligt her som korrektions-
spor, ikke fjernet.

**Den tilsvarende aabne spoergsmaal (tidligere §8, punkt 9) er lukket —
kraever ikke laengere en Peter-beslutning.**

## 5b. Direkte LAN-adgang til Edge:8443 — intent nu AFKLARET af Peter (beslutningsejer), 2026-09-14

**Status: LUKKET som et intent-spoergsmaal. Klassifikationen "INTENT NOT
YET VERIFIED" er AFLOEST af en eksplicit beslutningsejer-disposition.**
Provenance bevaret nedenfor i fire trin, ikke stiltiende omskrevet.

**Trin 1 — dokumenteret intent (fundet 2026-09-14, tidligere i denne
session):** `totp-service.py`s egen docstring (linje 4): *"Koerer paa
br-bt (192.168.42.1:8443 HTTPS)"* — laest som BT-PAN-bro-interfacet ALENE.
Samme antagelse laa til grund for `EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT_
2026-09-13_CLAUDE.md`s tidligere paastand ("[Verificeret] Kun br-bt...
Ingen ekstern/offentlig eksponering identificeret") — det dokument ligger
paa PR #239's branch og roeres IKKE af denne PR (uden for #240's scope),
men er hermed noteret som forældet/ufuldstaendigt paa dette punkt.

**Trin 2 — observeret runtime (fundet 2026-09-14, tidligere i denne
session):** Den faktiske `uvicorn.run(app, host="0.0.0.0", ...)` (linje
~2332) binder til ALLE interfaces; `timelapse-captive.sh`s `TL_MGMT`-
iptables-kaede anvender udelukkende `-i br-bt` og filtrerer intet paa det
almindelige LAN/WiFi-interface; `curl` mod `https://192.168.86.144:8443`
(Edge2's almindelige LAN-IP) gav et gyldigt HTTP 200-svar med login-siden.

**Trin 3 — den dermed opstaaede intent-konflikt (rapporteret i forrige
revision af denne fil):** dokumenteret intent (BT-PAN-only) stemte ikke
overens med observeret runtime (0.0.0.0, reelt LAN-tilgaengeligt). Dette
blev rapporteret som et aabent fund, ikke en konklusion om fejl/korrekthed.

**Trin 4 — Peters disposition som beslutningsejer (2026-09-14, denne
revision):** Den tiltaenkte capability er **eksplicit AFKLARET til IKKE at
vaere BT-PAN-only**. Den lokale Edge-management-/recovery-graenseflade paa
:8443 skal vaere teknisk tilgaengelig via alle relevante Edge-netvaerks-
interfaces/-net, underlagt routing og passende sikkerhedskontroller —
BT-PAN/direkte lokal recovery-netvaerk, lokal WiFi/Ethernet/LAN, kunde-LAN,
og potentielt kunde-WAN/routede net hvor deployment-krav og omgivende
netvaerkspolitik tillader det. "Lokal" beskriver den Edge-hostede
management-plan, ikke en BT-PAN-eksklusiv bindings-/accept-graense.
Fremtidige udrulninger kan kraeve at teknikere/administratorer naar Edge-
management-graensefladen via en kundes LAN/WAN i stedet for BT-PAN.

**Formel invariant (Peter, 2026-09-14 — praeciseret efter opfoelgende
mandat, den kanoniske formulering til en fremtidig `CAP-EDGE-MANAGEMENT-
REACHABILITY`-post i GRC, jf. formatet i Sec2a):**

> **Edge Management Reachability invariant.** Edge-hostede management- og
> recovery-capabilities maa ikke afhaenge af et enkelt management-netvaerk,
> -interface eller -transport. Management-/recovery-graensefladen paa
> :8443 skal vaere teknisk i stand til at blive naaet via:
> - BT-PAN / direkte recovery-netvaerk;
> - lokal WiFi/Ethernet/LAN;
> - routet/kunde-LAN;
> - kunde-WAN eller andre routede net, hvor deployment-politik, routing og
>   omgivende sikkerhedskontroller tillader det.
>
> TimeLapse Edge-implementeringen maa derfor IKKE hardkode BT-PAN som den
> eneste tilladte vej. Sikkerhed maa IKKE afhaenge af netvaerksvej-
> isolation — autentificering, autorisation, session-kontroller og andre
> gaeldende management-plan-beskyttelser skal beskytte graensefladen
> UAFHAENGIGT af hvilken tilladt netvaerksvej der bruges. "Naaelig via alle
> relevante netvaerk" betyder IKKE ubegraenset offentlig internet-
> eksponering — faktisk naaelighed er fortsat underlagt site-/kunde-
> deployment-politik, routing, firewall-regler og sikkerhedskrav.

**Konsekvenser af denne disposition (eksplicit, ikke udledt):**
- `0.0.0.0:8443`-binding er **i overensstemmelse med** den tiltaenkte
  capability og maa IKKE "rettes" til BT-PAN-only blot for at matche
  forældet dokumentation.
- Dokumentation der beskriver capability'en som BT-PAN-only (`totp-
  service.py`s docstring, `EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT`) er
  forældet/ufuldstaendig og skal behandles som saadan — en fremtidig,
  separat rettelse, ikke udfoert her (uden for #240's scope, og
  `EDGE_LOCAL_SHELL_ENDPOINT_ASSESSMENT` ligger desuden paa en anden PR).
- Der maa IKKE indfoeres interface-specifikke firewall-restriktioner der
  ville underminere denne capability.
- Netvaerks-naaelighed kan fortsat vaere begraenset af kunde-/site-routing og
  firewall-politik; Edge-arkitekturen selv maa ikke antage BT-PAN som den
  eneste vej.
- Autentificering/autorisation og recovery-sikkerhedskontroller (TOTP-login,
  session-model) skal beskytte management-graensefladen UAFHAENGIGT af hvilken
  tilladt netvaerksvej der bruges — dette aendrer ikke #238/#239s allerede
  implementerede TOTP/session-lag.
- **Ingen firewall-/iptables-/runtime-aendring er foretaget eller
  foreslaaet i denne revision**, som eksplicit instrueret. Dette er en
  intent-afklaring, ikke en godkendelse af urelaterede netvaerksaendringer.

**Praecisering af §16.8 (modstridende evidens), ikke af z.ais §16c
(sundhedsalarmering — et andet emne):** 8443-sagen viser at naar
dokumenteret intent og observeret runtime divergerer, er det IKKE
automatisk givet hvilken af de to der er "den rigtige." Her var runtime
faktisk korrekt og dokumentationen forældet — det modsatte af hvad man
kunne antage ved foerste øjekast (og det modsatte af min egen oprindelige,
forkerte konklusion i en tidligere revision af denne fil, som brugte
sagen som bevis for at "runtime afveg fra intent" uden at overveje at
INTENT selv kunne vaere det forældede led). §16.8 daekker allerede at
saadanne modsigelser skal forblive eksplicitte indtil afklaret — denne
sag er et konkret, gennemfoert eksempel paa noejagtigt det: en
beslutningsejer-disposition (Peter, ovenfor), ikke en automatisk "runtime
er forkert"-antagelse, afgjorde den.

## 6. Navngivne, valgfrie udvidelser (v5 — §16b/§16c-ordlyd nu ENDELIG, jf. Peters godkendelse §0a)

**Disposition-raekkefoelge (Peters godkendelse, §0a, ny i v5):** naar en consequential capability-aendring har flere gyldige implementeringsveje, praefereres i raekkefoelge **REUSE foer EXTEND, EXTEND foer NEW** — og generiske, tvaergaaende funktioner (jf. §2's Mission-Platform/Collaborative-Intelligence-klassificerede principper) placeres som udgangspunkt i det korrekte OPSTROEMS-lag frem for en parallel TimeLapse-specifik loesning. En TYND, lokal TimeLapse-prototype er tilladt hvor opstroems-arkitekturen endnu ikke er moden nok TIL AT validere behov/arkitektur — men KUN hvis den (a) ikke etablerer en konkurrerende source of truth, og (b) ikke laaser den generiske loesning til TimeLapse. Dette kriterium afgoer IKKE i sig selv nogen konkret DECISION REQUIRED-sag (fx AI_KOMPETENCER_OG_OPGAVEROUTING.md's rolle, §7 nedenfor) — det er den godkendte MAALESTOK en saadan sag skal vurderes imod, naar den forelaegges Peter eller loeses inden for et allerede delegeret mandat.

- **§16a — drift-modstandsdygtige invarianter (FASTHOLDT som valgfri):** registrerede
  capability-items markerer afhængighed af håndholdte lister/konstanter (release-manifests,
  hardcodede versions-/imagenavne) og kræver programmatisk udledning eller eksplicit
  fuldstændigheds-/ratchet-test. Bevis: sag 3 (adfærds-lock-in). Edge1 tilføjer intet nyt
  bevis for/imod — uændret.
- **§16b — manuelle/ad hoc operationelle handlinger (FASTHOLDT som valgfri; ordlyd nu ENDELIG,
  ikke laengere kun "anbefalet"):** §16b's dokumentationskrav udløses kun når en manuel/ad hoc
  operationel handling har **potentiel materiel påvirkning** på en registreret capabilitys
  eksistens, data, eller recovery-egenskab (Travbyen-klassen) — ikke for triviel, ubetydelig,
  daglig drift. **En handling der er teknisk reversibel er IKKE af den grund alene undtaget** —
  Travbyen var netop en "reversibel" (rekonstruerbar) sletning, der alligevel udgjorde den
  reelle regressionssag, fordi capabiliteten (synlige kameralokationer) faktisk gik tabt i
  mellemtiden. Reversibilitet kan hoejst tjene som ÉT eksempel paa triviel drift, aldrig som et
  selvstændigt kriterium der overtrumfer materiel paavirkning. Kerne-triggeren (16.1) dækker
  fortsat **automatiserede leveranceflow** (deployment/update); rene manuelle
  data-operationer med potentiel materiel paavirkning forbliver i §16b, saa kernen ikke
  bykratiseres med triviel drift.
- **§16c — sundhedsalarmering (NY, valgfri; ordlyd nu ENDELIG, ikke laengere kun
  "anbefalet"):** udløsningskriteriet for §16c er den **forventede konsekvens/risiko** ved en
  vedvarende fejlsignal for en registreret capability (fx service-restart-løkker, gentagne
  health-check-fejl), IKKE fejlens varighed. En kortvarig fejl med potentielt kritisk
  konsekvens kraever oejeblikkelig detektion/alarm; en langvarig fejl med lav konsekvens
  kraever det ikke noedvendigvis paa samme maade. **§16c maa IKKE kodificere en fast "X
  minutter foer alarm"-taerskel som det styrende kriterium.** Naar udloest, skal fejlen rejse
  en synlig alarm/GRC-finding uden manuel opdagelse. Bevis: 13.039 genstarter uden alarm
  (Edge1) og BT-TOTP/kapabiliteter der "fejlede stille siden hardeningen" (HANDOVER
  2026-08-24-klassen). Adskilt fra og IKKE en erstatning for §16.9 (post-aendrings-
  verifikation, core, obligatorisk for fuldfoerelse) — §16c er LOEBENDE overvaagning, §16.9 er
  ÉN engangs-kontrol ved aendringens afslutning.

## 7. Wiring for §16 — EKSEKVERET (v5, 2026-09-14, Peter bekraeftede "eksekvér nu")

**RETTELSE (fundet ved gennemgang efter Peters arkitekturgodkendelse):** W1's tidligere ordlyd
henviste fejlagtigt til "`Dokumentation/PAKKE_SPOR_REGISTER.md` §16" — men §16 er konsekvent
foreslaaet gennem hele dette dokument som **additiv til det allerede accepterede §14** (§3's
egen overskrift), og §14 findes bekraeftet i `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`
(§14.1-14.6, Accepted 2026-09-13), IKKE i PAKKE_SPOR_REGISTER (som kun INDEHOLDER en enkelt
§14.6-henvisning, ikke selve §14/§16-teksten). Rettet nedenfor.

**ANDEN RETTELSE, fundet under selve eksekveringen:** W2's oprindelige forslag ("tilfoej til
OP-001 Step 5") ville have redigeret `Dokumentation/mission-framework/OP-001-Mission-
Operational-Preamble.md` — men denne fil er ALLE STEDER i repoet (inkl. hvert loader-dokuments
egen punkt 1) eksplicit beskrevet som **"a vendored, verbatim copy of the canonical
procedure"**. At tilfoeje TimeLapse-lokalt indhold direkte i en vendoret, verbatim-kopi ville
selv vaere et brud paa den samme disciplin denne PR i oevrigt haandhaever (skab ikke en
TimeLapse-laast parallel af noget opstroems). Det etablerede, allerede-eksisterende moenster
(bekraeftet i alle fire loader-filer: punkt 1 henviser til OP-001, punkt 2-5 er TimeLapse-lokal
uddybning UDENFOR den vendorede fil) fulgt i stedet: W1+W2's samlede indhold er foldet ind i
loader-filerne selv, IKKE i OP-001, som forbliver uaendret og verbatim.

**Eksekveret, ikke laengere kun foreslaaet:** Peter bekraeftede eksplicit "Eksekvér wiring nu"
som svar paa det praecise spoergsmaal om §8 punkt 7's tvetydighed. Foelgende fem filer er nu
faktisk redigeret paa denne PR-branch:

- **`AGENTS.md`** (Codex/Kimi Code) — nyt afsnit tilfoejet efter den eksisterende "Mandatory
  package / track reconciliation"-sektion.
- **`CLAUDE.md`** (Claude Code) — samme tilfoejelse, samme placering (identisk sektion i begge
  filer).
- **`GEMINI.md`** (Gemini CLI) — tilfoejet til punkt 3 (denne fil har ingen separat
  reconciliation-sektion; punkt 3 er naermeste eksisterende krog).
- **`Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md`** (ChatGPT, manuel indsaettelse — autoloades
  IKKE, kraever fortsat manuel synkronisering ved fremtidige aendringer, jf. §8 punkt 12) —
  tilfoejet til den tilsvarende afsluttende paragraf.
- **`Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md`** — **BEVIDST
  IKKE aendret** (se rettelsen ovenfor).

Hver tilfoejelse siger eksplicit at §16 er "architecture-approved-but-not-yet-formally-accepted"
— ingen loader-fil paastaar at §16 er bindende governance endnu, kun at dets disciplin skal
foelges "i spirit" foran den formelle accept, praecis som Peters godkendelse §0a beskriver.

Princip (F3, uaendret): **én kanonisk regel** (`SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16,
naar formelt accepteret) + **routing fra den obligatoriske operationelle path**. Ingen
duplikering af selve §16-TEKSTEN i flere filer — hver loader-fil linker til denne PR's
proposal-dokument for den fulde tekst, i stedet for at gengive den.

- **W1 — `AGENTS.md`, punkt 3 udvidelse (og søster-loaders `CLAUDE.md`/`GEMINI.md`/
  `CHATGPT-PROJECT-INSTRUCTIONS.md` m.fl., samme sætning):**
  > "Before superseding/disposing of branches, or starting or delivering a consequential
  > capability change (new implementation, or deployment/update/dependency rollout), follow
  > `Dokumentation/SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16: capability intent/invariants,
  > relevant usecases, authoritative + historical implementation, and verification. Prefer
  > REUSE over EXTEND, EXTEND over NEW; generic cross-project functionality belongs upstream
  > (Mission Framework/Platform/Collaborative Intelligence) unless a thin, non-competing,
  > non-locking local prototype is explicitly justified. A capability change is not complete
  > until runtime health is observed (§16.9)."
- **W2 — oprindeligt foreslaaet som `OP-001` (cached preamble) Step 5-tilfoejelse, men IKKE
  saadan eksekveret** (se "ANDEN RETTELSE" ovenfor) — indholdet blev i stedet foldet ind i
  loader-filernes eget §16-afsnit (samme sted som W1, se ovenfor):
  > "For consequential capabilities, the search extends to capability equivalence per
  > `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16, and observed runtime health is part of
  > completion (§16.9)."
- **W3 — PR-template — EKSEKVERET (Wave 2, 2026-09-16):** `.github/PULL_REQUEST_TEMPLATE.md`
  oprettet (NYT — ingen template fandtes tidligere, bekræftet frisk før oprettelse). Kræver for
  consequential ændringer ét af tre reviewbare svar (identified/no impact/unresolved gap) +
  evidens/begrundelse + berørte maal + Finding/spor-reference ved uafklaret gab — IKKE en bar
  afkrydsning. Rutinemæssige, ikke-consequential PR'er kan skrive "Not consequential" og
  slette resten af blokken.

**Wave 2-genvurdering af W1 (2026-09-16), efter at Mission Framework Wave 1 faktisk blev merged:**
alle fire loader-filer (`AGENTS.md`/`CLAUDE.md`/`GEMINI.md`/`Dokumentation/CHATGPT-PROJECT-
INSTRUCTIONS.md`) opdateret to steder: (1) punkt 1's "vendored, verbatim copy"-sprog erstattet
med den nye C-arkitekturs "locally cached, script-managed mirror"-sprog (jf. `Dokumentation/mission-framework/README.md`); (2) §16-statusafsnittet opdateret til at skelne eksplicit mellem TO ting der IKKE
laengere er identiske: den KANONISKE Mission Framework Governance Propagation-regel (OP-001
Step 7 + Framework Findings) er nu FAKTISK implementeret og merged opstroems (`mission-framework`
PR #13, merge-commit `9a1a45435ed0781f987760b00722d4a7700d5052`), MENS TimeLapse's egen §16-tekst stadig IKKE er formelt accepteret her — denne
distinktion var uklar i den gamle "architecture-approved-but-not-yet-formally-accepted"-formulering
og er nu eksplicit. Reelt fundet inter-fil-drift ved gennemgang: `AGENTS.md`/`CLAUDE.md` brugte én
ordlyd, `GEMINI.md`/`Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` en anden (kortere) — begge par
er nu internt ajourførte og konsistente med hinanden (2 synkroniseringspunkter i stedet for at
antage 4 identiske filer, hvilket de aldrig reelt var).

Hvorfor dette er minimum: AGENTS.md/OP-001 er de to steder alle agenter *allerede* er tvunget
igennem (AGENTS.md punkt 1 + punkt 3); §14/§16 (SAMARBEJDSMODEL) er allerede konsulteret ved
R04/disposition. W1+W2 lukker det manglende led — "agent påbegynder/implementerer/leverer" —
uden at opfinde en ny kontrolstruktur.

## 8. Spørgsmål der kræver Peters beslutning (v5)

1. **ARKITEKTURRETNING GODKENDT (§0a, 2026-09-14) — formel §16-ACCEPT staar stadig aaben.**
   §16 kernetekst (§3, 16.1–16.9) er godkendt som arkitektonisk grundlag, men "acceptance og
   merge sker foerst efter den noedvendige wiring og verificering" (Peters ord). Formel accept
   (markering som "Accepted" i SAMARBEJDSMODEL) afventer stadig.
2. **ARKITEKTURRETNING GODKENDT (§0a) — §16a/§16b/§16c's ordlyd er nu FINALISERET (§6), ikke
   laengere kun "anbefalet."** Formel tilfoejelse/accept afventer samme gate som punkt 1.
3. Kør GRC-migrationen (`item_type='capability'`) nu eller ved første behov (fx
   `CAP-EDGE-RECOVERY-TERMINAL` for #239)? **Uaendret aabent — arkitekturgodkendelsen betyder
   IKKE at dette allerede er besluttet (§0a's eksplicitte praecisering).**
4. Link `UI_USECASE_CATALOG_2026-08-26.md` fra `00_START_HER.md`/
   `DOKUMENTPAKKE_OVERSIGT_v10.md` som uafhængig lavrisiko-rettelse?
5. Hvem/hvad driver eksekvering af eksisterende `NEEDS TESTDATA`-poster (sag 4 viser reelt tab)?
6. `COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md`: videre sporing eller tabt/erstattet?
7. **LUKKET (2026-09-14):** Peter bekraeftede eksplicit "Eksekvér wiring nu" som svar paa det
   stillede spoergsmaal. W1+W2's indhold er nu foldet ind i `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`/
   `Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` (§7). `OP-001` selv er bevidst IKKE aendret
   (bevaret som vendoret, verbatim kopi — se §7's anden rettelse). Kraever ikke laengere en
   Peter-beslutning — men bemaerk: dette er WIRING, ikke FORMEL §16-ACCEPT (SAMARBEJDSMODEL er
   ikke aendret, §16 er IKKE markeret "Accepted" noget sted) — den distinktion Peter selv
   eksplicit fastholdt i godkendelsen (§0a) staar fortsat.
8. Edge1-implementationsobservationer (pin-par-validering i `fetch_python_bundle.py`,
   postflight-gate i update-flow, flapping-alarm) er noteret til update-governance-sporet —
   bekræft at de afledes/afejes dér og valideres af ejer, ikke i denne PR.
9. **LUKKET (§5a, 2026-09-14):** Pi-hole sad direkte paa Edge1's egen hardware
   (`pihole`/`pihole-FTL`-pakker verificeret, fysisk/SSH via reverse-tunnel), ikke paa en
   separat DHCP-delt enhed. DHCP-genudlejningshypotesen er afkraeftet. Kraever ikke laengere
   en Peter-beslutning.
10. **AFGJORT (§5b, 2026-09-14):** Peter har som beslutningsejer afklaret at
    :8443-managementgraensefladen bevidst IKKE skal vaere BT-PAN-only — multi-netvaerks-
    tilgaengelighed (BT-PAN, lokal WiFi/Ethernet, kunde-LAN, potentielt kunde-WAN) ER den
    tiltaenkte capability. `0.0.0.0`-binding skal IKKE "rettes." Dokumentation der siger
    BT-PAN-only er forældet (fremtidig, separat rettelse — uden for #240's scope). Ingen
    firewall-/runtime-aendring foretaget eller foreslaaet.
11. **NY:** §2a — skal implementeringsomfanget (link-design, `database.py`-duplikat,
    UI-hardkodning, manglende link-API) indgaa i en evt. GRC-migrationsbeslutning (sp. 3),
    eller udskydes til en separat opfoelgende PR naar migrationen faktisk igangsaettes?
12. **DELVIST LUKKET (2026-09-14):** `CHATGPT-PROJECT-INSTRUCTIONS.md` er nu opdateret manuelt
    i denne PR (§7), saa den er synkroniseret paa committime. Det resterende, aabne punkt er
    PROCESSEN fremadrettet — denne fil autoloades stadig ikke, saa enhver FREMTIDIG aendring til
    §16-teksten kraever fortsat en separat, manuel opmaerksomhed for at holde den synkroniseret;
    ingen mekanisme haandhaever det automatisk. Ingen Peter-beslutning kraeves nu, men flaget som
    en kendt, vedvarende driftsrisiko.
13. **NY (Wave 2, 2026-09-16) — punkt 7's "OP-001 bevidst IKKE aendret" er delvist afloest, ikke
    modsagt:** OP-001's INDHOLD er nu opdateret til canonical Mission Framework Wave 1's version
    (Step 7 + §8 udvidelserne, PR #13 merged) — men fortsat KUN via den scriptede cache-mekanisme
    (`refresh_op001_cache.py --bootstrap`), aldrig ved haandredigering; se `Dokumentation/mission-
    framework/README.md` for den fulde C-arkitektur (canonical + kontrolleret lokal cache,
    Peters beslutning 2026-09-16). Formel §16-ACCEPT (punkt 1/2 ovenfor) er FORTSAT AABEN — Wave
    2 har IKKE markeret §16 "Accepted" i SAMARBEJDSMODEL og har ingen mandat til at goere det.
14. **NY (Wave 2, 2026-09-16):** TimeLapse's OP-001-integrationsmodel (tidligere DECISION
    REQUIRED: vendor+sync (A) / canonical-live (B) / cache+fallback (C)) er nu AFGJORT af Peter
    som **C**. Implementeret denne bølge: `Dokumentation/mission-framework/refresh_op001_cache.py`
    + `OP-001.provenance.json` (VERIFIED/STALE/UNKNOWN-friskhedsmodel) + opdateret `README.md`.
    Kraever ikke laengere en Peter-beslutning.

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
