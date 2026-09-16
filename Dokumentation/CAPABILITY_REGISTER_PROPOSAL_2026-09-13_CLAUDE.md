# Capability Register — revideret forslag (v2)

**Forfatter:** Claude Sonnet 5, 2026-09-13
**Status:** FORSLAG — ikke implementeret, kraever Peters beslutning.
**Erstatter:** `CAPABILITY_REGISTER_PROPOSAL_2026-09-13_CLAUDE.md` (v1, paa
PR #239's branch) — v1 overSAA en eksisterende, direkte relevant struktur.
Denne version retter det og tilfoejer et lag, ikke kun en type-udvidelse.

## Hvad der aendrede sig siden v1

**RETTELSE (2026-09-14):** dette dokument (v2) er selv erstattet af
`CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` (v3), som
retter ni konkrete fejl en automatiseret review fandt i BAADE dette
dokument og `UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`
(deriblandt: skematisk ugyldigt `has_usecase`-link-design nedenfor i
Sec"Foreslaaet skemaforslag"; undervurderet implementeringsomfang;
manglende link-API). Se v3 for den korrigerede, review-klare version.
Dette dokument bevares uaendret som korrektionsspor.

En uafhaengig arkaeologi-review fandt `Dokumentation/UI_USECASE_CATALOG_2026-08-26.md`
— et allerede-eksisterende, 294-linjers praktisk usecase-katalog
(oprettet af Peter i PR #141), som v1 af dette forslag ikke fandt. Se
`UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`
for fuld, selvstaendigt verificeret evidens (historikkaeden er
efterproevet punkt for punkt, ikke antaget) og en aerlig analyse af hvorfor
hverken R04/#235-#238 eller min egen v1-soegning fandt den.

Dette AENDRER svaret paa spoergsmaalet fra v1. Det handler ikke laengere kun
om "skal GRC have `item_type='capability'`" — det handler om at der allerede
findes FIRE lag, der hver loeser en del af problemet, og som skal
**forbindes eksplicit**, ikke duplikeres eller erstattes.

## Det samlede lag-billede (verificeret, ikke antaget)

```
Capability (intent/invariants, GRC item_type='capability' - NY)
    |
    v
Usecase(s) (UI_USECASE_CATALOG_2026-08-26.md - EKSISTERER ALLEREDE)
    |  ID, Start, Handling, Forventet resultat, Sikkerhed/audit, Status
    v
Implementation (kildekode - eksisterer allerede, ikke et register)
    |
    v
Tests/runtime evidence
    |-- automatiske tests + architecture ratchets (eksisterer allerede)
    |-- GRC grc_test_runs (eksisterer allerede, environment='lab'/'physical_edge')
    `-- fysisk/runtime-verifikation (dokumenteret manuelt indtil videre)

Sideordnet, IKKE en del af kaeden - provenance/beslutning/arbejdstilstand:
  ADR (arkitekturbeslutning)  |  HANDOVER_LOG (kronologisk driftslog)  |
  PAKKE_SPOR_REGISTER (branch-/pakke-sporing)
```

**UI_USECASE_CATALOG_2026-08-26.md's egen selvbeskrivelse bekraefter
allerede noejagtigt denne rolle-adskillelse:** *"Dette dokument er ikke en
erstatning for GRC-registeret eller CI. Det er den menneskelige 'kan vi
faktisk bruge systemet?'-liste."* Og `UI_TESTJOURNAL_v1.md` (samme families
soesterdokument) siger tilsvarende: *"Autoritativ testcase-, run-, finding-
og evidensstatus ligger i PostgreSQL GRC-registeret... Journalen er narrativ
evidens, ikke statuskilde."* Med andre ord: **denne lagdeling var allerede
den erklaerede hensigt** i repoets egen dokumentation, den var bare aldrig
forbundet til en formel GRC-`capability`-type eller haandhaevet som en
soegepligt.

## Svar paa Peters konkrete spoergsmaal

- **GRC forbliver den autoritative strukturerede capability-/verifikations-
  butik.** Ja — udvides med `item_type='capability'` (som i v1), men et
  capability-item skal nu ALTID linke til sine usecase(r) via `grc_links`
  (`relationship='has_usecase'`, target kan vaere et `grc_evidence`-opslag
  der peger paa `UI_USECASE_CATALOG_2026-08-26.md#UC-SSH-002` indtil/hvis
  usecases ogsaa faar egne GRC-raekker).
- **`UI_USECASE_CATALOG_2026-08-26.md` skal bevares og videreudvikles som
  det menneskelaesbare usecase-lag.** Ja — det er allerede egnet til formaalet
  og skal ikke erstattes af noget nyt. Det skal dog **synliggoeres** (linkes
  fra `00_START_HER.md`/`DOKUMENTPAKKE_OVERSIGT_v10.md`, som i dag ikke
  naevner det overhovedet - en konkret, let rettelig discoverability-fejl).
- **Menuguides forbliver afledt brugerdokumentation.** Ja — ingen aendring;
  de er allerede eksplicit markeret som afledt af UI-koden, ikke en
  selvstaendig sandhedskilde.
- **Automatiske tests/architecture ratchets giver maskinel haandhaevelse.**
  Ja, uaendret — men et capability-item boer linke til de konkrete testfiler
  der haandhaever det (fx `tests/test_edge_technician_terminal_runtime.py`
  for `CAP-EDGE-RECOVERY-TERMINAL`), saa forbindelsen er eksplicit i stedet
  for at skulle genopdages hver gang.
- **ADR/HANDOVER/PAKKE_SPOR forbliver provenance-/beslutnings-/
  arbejdstilstandslag, ikke capability-butikker.** Ja, uaendret fra v1 —
  ingen af dem skal duplikere capability- eller usecase-indhold, kun
  reference det.

## Revideret skemaforslag (samme minimale aendring som v1, plus konvention)

Uaendret fra v1: ny migration der tilfoejer `'capability'` til
`grc_items.item_type` CHECK-constraint + `ITEM_TYPES` i
`headend/api/grc_register_api.py`. Tilfoejet konvention (ikke
skema-haandhaevet, ligesom `relationship`/`evidence_type` i forvejen er
frie strenge):
- `relationship`: tilfoej `has_usecase` (capability -> usecase-reference).
- `evidence_type`: tilfoej `usecase_catalog_entry` (bruges til
  `grc_evidence.uri`, fx en anker-reference til
  `UI_USECASE_CATALOG_2026-08-26.md#UC-SSH-002`).

## Den reviderede governance-regel — daekker BEGGE fejl fra i dag

v1's forslag daekkede kun "check capability-ækvivalens foer disposition."
Det daekkede ikke fejl #2 (historisk implementering blev ikke genfundet foer
genimplementering — hvilket ogsaa skete i dag: multi-IP-sessionsmodellen i
#238 blev genopfundet, selvom den allerede fandtes, live-testet, i commit
`d67ca26d`). Revideret §16-forslag til
`SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` (additiv, ikke en aendring af det
allerede accepterede §14):

> **§16 — Capability- og usecase-tjek foer aendring af en consequential
> capability.**
>
> Foer en branch/change klassificeres `absorbed`/`superseded`, ELLER foer en
> ny implementering af en bruger-, drifts-, recovery-, sikkerheds- eller
> anden consequential capability paabegyndes, skal foelgende identificeres
> og dokumenteres eksplicit:
>
> 1. **Capability-intent/invarianter** (GRC `item_type='capability'`, hvis
>    registreret).
> 2. **Relevante usecase(r)** (`UI_USECASE_CATALOG_2026-08-26.md` eller dens
>    efterfoelger) og deres aktuelle status.
> 3. **Nuvaerende autoritative implementering** (fil/komponent-reference).
> 4. **Historisk/kendt-god implementering, hvor en saadan findes** — soeg
>    eksplicit i `git log --all`/branches/stashes for den paagaeldende
>    komponent, ikke kun i den aktuelle mains historik.
> 5. **Automatisk verifikation** (hvilke tests haandhaever invarianterne i
>    dag).
> 6. **Runtime-/fysisk verifikation, hvor det er relevant for capability'en.**
>
> **Fravaer af et capability- eller usecase-opslag for et omraade der aabenlyst
> paavirker en consequential capability er IKKE tilladelse til at fortsaette
> uden videre — det er i sig selv et dokumentationshul, der skal
> disponeres eksplicit** (registreres som en ny `capability`/`usecase`-post,
> eller bevidst noteret som en accepteret mangel, med begrundelse).
>
> En forbedring af én del af en registreret capability maa ikke stiltiende
> forringe en anden del af samme capability (fx: en ny renderer maa ikke
> fjerne en allerede-fungerende sessionsmodel; en ny sessionsmodel maa ikke
> fjerne en allerede-fungerende renderer — begge dele skete uafhaengigt af
> hinanden i dette repos historik og skal begge undgaas fremover).

Dette daekker eksplicit begge fejl Peter identificerede: (1) eksisterende
capability ikke tjekket foer aendring — daekket af punkt 1-2 plus
"fravaer er ikke tilladelse"-saetningen; (2) eksisterende implementering/
historik ikke genfundet foer geninplementering — daekket af punkt 4, som nu
er et EKSPLICIT, navngivet soegetrin (ikke underforstaaet i "brug GRC"),
netop fordi dagens erfaring viser at et rent GRC-/ADR-fokuseret tjek ikke
i sig selv ville have fundet hverken usecase-kataloget eller den tabte
`d67ca26d`-implementering.

## Tredje fejl fundet i dag: en "ikke fundet"-konklusion var selv en falsk negativ

Under udarbejdelsen af dette forslag konkluderede jeg fejlagtigt at
`Dokumentation/COMPLETE_TEST_CONTINUITY_PLAN_2026-08.md` ikke var refereret
noget sted, inklusive i `HANDOVER_LOG.md`. Peter fandt selv referencen ved
manuelt at tjekke filen. Rodaarsagen (fuldt dokumenteret i
`UI_USECASE_CATALOG_DISCOVERY_AND_SEARCH_FAILURE_2026-09-13_CLAUDE.md`,
afsnit 3): soegningen blev koert mod en lokal worktree-kopi af
`HANDOVER_LOG.md` der stod paa en commit langt bagud for `origin/main` (1664
af 3119 linjer — under halvdelen af filens faktiske indhold var til stede).
En fil-friskheds-antagelse, ikke en noegleordsfejl.

Dette er en **tredje**, selvstaendig fejlklasse ud over de to Peter allerede
bad om at daekke (capability ikke tjekket foer aendring; historisk
implementering ikke genfundet foer genimplementering): **en "ikke fundet /
eksisterer ikke"-konklusion blev behandlet som et faktum uden at dens egen
grundlagsforudsaetning (frisk, autoritativ datakilde) blev verificeret
foerst.**

**Princip:** Et negativt soegeresultat er evidens for fravaer, ikke bevis
for fravaer. En "IKKE FUNDET"/"EKSISTERER IKKE"-konklusion, der har
konsekvens (fx: retfaerdiggoer at springe et genfindingstrin over, eller
klassificerer noget som endeligt tabt), maa foerst opfylde et minimums-
reproducerbarhedskrav, foer den behandles som etableret:

1. **Kildefriskhed eksplicit bekraeftet:** for git-baserede kilder, opslag
   skal ske mod `origin/<default-branch>` (eller en eksplicit angivet,
   verificeret commit/tag) — ikke mod en lokal arbejdskopis nuvaerende
   `HEAD` uden foerst at sammenligne `git rev-parse HEAD` mod `git
   rev-parse origin/main` og bekraefte de matcher (eller eksplicit
   begrunde hvorfor en aeldre reference bruges).
2. **Mindst to uafhaengige soegemetoder** for en konsekvent "ikke fundet"-
   konklusion: fx baade indholds-`grep` OG `git log --diff-filter=A`/`gh
   search`, ikke kun én metode — saadan at en enkelt kildes staleness eller
   en enkelt vaerktoejsbegraensning ikke alene kan producere konklusionen.
3. **Eksplicit skelnen mellem tre svarkategorier**, ikke kun "fundet"/"ikke
   fundet": (a) VERIFICERET FRAVAER (flere friske, uafhaengige metoder gav
   alle nul hits), (b) IKKE VERIFICERET (soegningen blev ikke udfoert med
   tilstraekkelig grundighed/friskhed til at konkludere noget), (c) UKENDT
   (spoergsmaalet ligger uden for det soegbare rum, fx en aldrig-pushet
   lokal kopi et andet sted).
4. **Reproducerbar kommando citeret i konklusionen**, saa en anden
   (menneske eller AI) kan koere noejagtig samme opslag og faa samme
   resultat — som demonstreret i korrektionen ovenfor
   (`git show origin/main:Dokumentation/HANDOVER_LOG.md | grep -n
   COMPLETE_TEST_CONTINUITY_PLAN` -> linje 1208).

Dette foreslaas tilfoejet som en fjerde, staaende klausul i §16-forslaget
ovenfor: **en konsekvent "ikke fundet/eksisterer ikke"-konklusion kraever
bekraeftet kildefriskhed og mindst to uafhaengige soegemetoder foer den
behandles som et etableret faktum; ellers rapporteres den som IKKE
VERIFICERET, ikke som fravaer.**

## Omfang - uaendret fra v1

Samme indledende liste af consequential capabilities som i v1
(`CAP-EDGE-RECOVERY-TERMINAL`, `CAP-EDGE-RECOVERY-BREAKGLASS-SSH`,
`CAP-DEPLOYMENT-UPDATE-DELIVERY`, `CAP-CAPTURE-EVIDENCE-INTEGRITY`,
`CAP-SECURITY-ACCESS-CONTROL`, `CAP-HEADEND-EDGE-SYNC`), nu med et
`has_usecase`-link til de relevante `UC-*`-ID'er i
`UI_USECASE_CATALOG_2026-08-26.md` hvor de findes.

## Hvad dette forslag stadig IKKE goer

Ingen migration er koert. Ingen kode er aendret. Ingen §16 er tilfoejet til
SAMARBEJDSMODEL-dokumentet. `UI_USECASE_CATALOG_2026-08-26.md` er ikke
rettet/udvidet endnu (kun foreslaaet linket bedre). Dette er fortsat kun et
beslutningsoplaeg.
