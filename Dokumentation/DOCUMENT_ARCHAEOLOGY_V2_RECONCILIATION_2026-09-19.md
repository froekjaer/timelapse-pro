# TimeLapse Pro — Knowledge Archaeology v2 reconciliation

**Dato:** 2026-09-19  
**Status:** EVIDENCE / WORKING RECONCILIATION — ikke autoritativ GRC  
**Relation:** Supporting evidence for `DOCUMENT_ARCHAEOLOGY_CLOSURE_LEDGER_2026-09-17.md`.

## Formål

Dette dokument fastholder den nye v2-forensic extraction/reconciliation som evidenslag. Det ændrer ikke current GRC, fryser ikke Golden Capabilities og gør ikke historiske implementation claims til current truth.

## Fresh GitHub reconciliation 2026-09-19

- Fresh pagineret GitHub branch-listing: **139 remote branches** (page 1 = 100, page 2 = 39, page 3 = 0).
- `main` er fortsat `928134be847eb96df25455736f6acd766aff84f2`.
- PR #243 er fortsat **OPEN / NOT MERGED**; head `27cc5747be4826e1c3551e17972f4bfc034db15d`, base recorded by PR metadata as `8452c5ef264d85823dce149a3bb371142d598569`.
- PR #243 må ikke merges som del af archaeology.

## v2 forensic extraction accounting

Den lokalt kørte v2-pipeline blev designet til at undgå v1's branch-tip-only/per-file subprocess problem og til at bevare Git-history, branch-tip, unreachable og filesystem provenance med SHA-256 dedupe.

Resultatpakken gav følgende accounting:

| Metric | Count |
|---|---:|
| Configured/existing local roots | 20 / 20 |
| Canonical remote branches | 139 |
| Provenance records | 177,934 |
| Unique SHA-256 artifacts | 20,126 |
| EXTRACTED | 19,976 |
| SENSITIVE_HOLD | 120 |
| UNREADABLE | 14 |
| POINTER | 15 |
| EMPTY | 1 |
| PARTIAL | 0 |
| Accounted status sum | 20,126 |

**Balance = PASS**, men PASS betyder kun, at alle artefakter fundet af v2 har en disposition; det er ikke alene knowledge-closure.

### Named/path-based document universe

- **1,583** unikke artefakter har egentlig navngivet/path-baseret provenance.
- **1,567** af disse har recoveret tekst.
- De resterende named artifacts er **15 Google pointer sources + 1 empty file**.
- De **14 UNREADABLE** artefakter er pathless unreachable candidates; ingen af dem ligger i det navngivne/path-baserede dokumentunivers.
- En fast første requirements/risk/architecture/runbook/governance-udvælgelse giver **552** unikke named artifacts. Et tidligere foreløbigt tal 557 korrigeres hermed.

### Pathless forensic tail

Størstedelen af de 20,126 SHA-artefakter er pathless/unreachable forensic candidates. De må ikke tælles som 1:1 'dokumenter'. De skal reconciles mod named SHA/content og vurderes for genuinely novel knowledge. Pathless status er provenance-usikkerhed, ikke i sig selv et `CRITICAL_KNOWLEDGE_GAP`.

## Centrale recovery-resultater

De tidligere `BINARY_GAP`-kilder er nu lokalt ekstraheret i v2-resultatet, herunder `Startkrav.docx` og historiske familier af Roadmap, SABSA Architecture/Risk, Edge Runbooks, RBAC, Security/Compliance og System Inventory. Sensitive chat/risk-materialer ligger i `SENSITIVE_HOLD` og må ikke publiceres råt.

`Startkrav` bekræfter pre-Git product intent, bl.a. unattended/stabil mastdrift, lokal buffer, lokal kvalitetskontrol, efterfølgende transfer, remote management/bootstrap, multi-tenancy og Headend/Edge-separation. Det betyder, at repositoryets initial commit er Git-baseline, ikke requirement-baseline.

Foreløbige evolution chains med direkte historisk støtte:

1. **Capture autonomy:** pre-Git standalone/local-buffer need → senere SABSA availability/business attribute → store-and-forward/risk treatment. Underliggende intent er fortsat kandidat til CURRENT invariant; konkrete Orange Pi/Canon/bufferstørrelser er historiske implementation choices.
2. **Multi-tenancy:** pre-Git requirement → roadmap implementation milestone → RBAC/isolation design. Roadmap-dato må ikke fejlagtigt bruges som kravets oprindelsesdato.
3. **Remote management/update:** reverse SSH / direkte Git-baserede stadier → observerede trust/authority/dependency-problemer → Headend-mediated production direction. Underliggende remote-management behov består, mens tidligere mechanisms kan være HISTORICAL/SUPERSEDED.
4. **Device identity:** MAC/device-id bootstrap convenience → senere certificate/key-based production trust. Bootstrap identity er ikke production trust anchor.
5. **Backup/recovery:** backup intent/artifacts → senere RTO/RPO/restore-test krav. `backup created` er ikke `recoverability verified`.

## Konflikt- og evidensregel

Historiske dokumenter bruger flere steder formuleringer som 'LØST', 'komplet' eller 'implementeret', samtidig med at samme eller senere kilder beskriver implementation som planlagt/ufærdig. Disse claims klassificeres som historiske claims eller `CONFLICTING`; de må ikke automatisk blive `VERIFIED`.

Bevar separationen:

`declared → configured → consumed → executed → runtime reconciled → outcome verified → evidence retained`

og:

`decision/architecture accepted ≠ capability implemented ≠ capability verified`.

## Camera direction

Archaeology ændrer ikke den besluttede retning:

- Nikon er strategisk/default for nye installationer.
- Fungerende understøttede legacy Canon-kameraer forbliver current migration/backward-compatibility intent.
- En defekt legacy Edge skal kunne erstattes uden tvunget udskiftning af et fungerende understøttet kamera.

## GAP disposition — nuværende

- `SOURCE_GAP`: ingen ny kritisk source-loss identificeret i denne reconciliation.
- `BINARY_GAP`: væsentligt reduceret, fordi centrale historiske DOCX/PDF-kilder nu er ekstraheret lokalt; hver kilde skal stadig have READ/coverage disposition før closure.
- `TECHNICAL_GAP`: connector-oversize er ikke længere nødvendigvis knowledge-loss, når samme exact source er lokalt ekstraheret; provenance/equivalence skal registreres før omklassifikation til `COVERED_GAP`.
- `POINTER`: 15 named Google pointer sources kræver reconciliation mod lokale/andre kopier eller skal stå som eksplicit gap.
- `UNREADABLE`: 14 pathless unreachable candidates; skal novelty-assesses. De er ikke på nuværende evidens `CRITICAL_KNOWLEDGE_GAP`.
- `CRITICAL_KNOWLEDGE_GAP`: **0 identificeret**, men **ikke endeligt closure-bevist**, fordi pointer/pathless novelty reconciliation ikke er færdig.

## Closure status

**IKKE LUKKET ENDNU.**

Før `DATA COLLECTION CLOSED WITH EXPLICIT GAPS` kræves stadig:

1. reconcile 15 named pointer sources;
2. novelty/redundancy assessment af pathless forensic tail, især 14 unreadable candidates;
3. registrer exact-source extraction equivalence for tidligere binary/oversize gaps;
4. opdater closure ledger med v2 accounting og gap-disposition;
5. sidste fresh branch/main/PR #243 check ved closure-tidspunktet;
6. dokumentér eksplicit om final `CRITICAL_KNOWLEDGE_GAP = 0`.

Golden Capabilities må fortsat ikke fryses, og archaeology må ikke promoveres direkte til authoritative GRC før efter synthesis/reconciliation.