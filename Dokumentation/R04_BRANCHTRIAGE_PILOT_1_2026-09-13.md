# R04 Branchtriage — Pilot-batch 1 (8 branches)

**Dato:** 2026-09-13 · **Udfører:** Kimi · **Baseline:** main `ebd98fffc8d506be252ccd930ac8ef2f53aea809`
**Population:** De 58 rest-patch-branches fra den frosne måling (KIMI-03-evidensbilaget, commit `499d266d`).
**Scope:** Klassifikation og evidensindsamling. **Ingen** sletning, merge, lukning eller driftsændring.

## Metode (pr. branch)

1. `git cherry origin/main <branch>` — patch-screening (kun screening, aldrig bevis).
2. `git diff --stat origin/main...origin/<branch>` — hvilke filer røres.
3. **Indholdsverifikation:** for hver central fil — findes den på main? Hvis ja: `diff` af faktisk indhold (branch vs main). Hvis nej: er indholdet semantisk dækket andetsteds (funktioner, tests, dokumenter søgt med `grep` på main)?
4. **Beslutningskontekst:** er der en GRC-risikoaccept, ADR eller handover-entry der bevidst har fravalgt branchens tilgang? (En branch der implementerer det modsatte af en formel beslutning er ikke "mangler på main" — den er dispositioneret.)
5. Klassifikation: **absorberet** / **absorberet+main-videreudviklet** / **superseded-ved-beslutning** / **unikt indhold — kræver disposition** / **uklar**.

## Fund pr. branch

### 1–3. `security/closure-headend-deploy-integrity` (0b141512), `-current` (c4ec3548), `-final` (34e63ada) — 2026-08-16

**Klassifikation: Absorberet (iterationskæde, -final er den absorberede sluttilstand).**

Evidens: De tre varianter afviger indbyrdes (base→-current: 95 linjer; base→-final: 503 linjer) — det er iterationshistorik, ikke tre løsninger. -final's indhold er verificeret på main: (a) `tests/test_security_closure_deploy_integrity.py` findes på main og main's version er en **superset** (main har 22 ekstra linjer: worktree-deploy-testen `test_deploy_uses_dedicated_worktree_not_the_interactive_checkout`); (b) -final's ci.yml-ændringer — fjernelse af GPG-tag-check og "Record previous revision / timelapse-previous-sha"-mekanismen — er **byte-identiske** med main (diff tom). Yderligere verifikation før disposition: kør main's eksisterende testfil (den dækker branchens påstande); ingen.

### 4. `codex/security-closure-f005` (7de91fad) — 2026-08-15

**Klassifikation: Superseded-ved-beslutning (formel risikoaccept F-005).**

Evidens: `headend/services/artifact_trust.py` findes på main, men i en **anden, nyere udgave** (main's docstring: "cryptographically signed release sources are deployable"). Branchens to testfiler findes **ikke** på main — og deres påstande (`test_edge_rejects_system_hash_artifact_even_with_trusted_fingerprint`, `test_edge_rejects_hash_only_signature_under_named_signer`) er i **direkte modstrid** med den formelle risikoaccept `Dokumentation/RISIKOACCEPT_F-005_SYSTEM_HASH_2026-09-11.md` (Peter, 2026-09-11; GRC `RISK-ARTIFACT-SYSTEM-HASH-FALLBACK` = accepted, `FIND-...-F005` = closed). Branchen er ikke "glemt funktionalitet" — den er den strammere løsning, Peter bevidst fravalgte. Yderligere verifikation før disposition: bekræft at GRC-item stadig står som accepted; arkiverings-reference til risikoaccept-dokumentet som erstatningsbevis.
**Sideobservation (ikke R04-scope):** main's `artifact_trust.py`-docstring ("cryptographically signed") og risikoacceptens ordlyd (hash-binding accepteret uden GPG-nøgle) kan læses som i spænding — værd at afstemme i en separat opgave. Ikke verificeret dybere her.

### 5. `fix/update-rollback-idempotency` (0093c2a7) — 2026-08-16

**Klassifikation: Absorberet.**

Evidens: Alle fire nøglefunktioner fra branchens `edge/update_lifecycle.py`-ændring findes på main: `_expected_release_identity`, `release_receipt_matches_artifact`, `_safe_edge_output_paths`, `restore_previous_app_release`. `release_receipt_matches_artifact` er **linje-identisk** (diff tom). Branchens testfil `tests/test_edge_update_lifecycle_closure.py` findes på main. (Denne funktion er samme som §14.3 nu citerer som eksisterende delkontrol.) Yderligere verifikation før disposition: ingen udover standardkontrol.

### 6. `fix-ordered-offline-apt-install` (49055da6) — 2026-09-04

**Klassifikation: Tilsyneladende absorberet, main videreudviklet — én restkontrol udestår.**

Evidens: `tests/test_fetch_os_bundle.py` findes på main, og main's version indeholder **flere** tests end branchens (bl.a. den lokale apt-index-test fra 2026-09-07, som kun er på main). Dvs. branchens testindhold er dækket og overhalet af nyere arbejde. Restkontrol: branchen rører 7 filer — de øvrige 6 (bl.a. `tests/architecture_baseline.json` og kodefiler) er ikke verificeret fil-for-fil endnu. Yderligere verifikation før disposition: diff de resterende 6 filer mod main.

### 7. `docs/kimi-handover-2026-08-20` (af2f7d6e) — 2026-08-23

**Klassifikation: Absorberet.**

Evidens: Branchens eneste unikke indhold er en handover-entry ("PR #90-konflikt løst + PR #89 mergeklar", 21 linjer). Præcis denne entry findes på main's HANDOVER_LOG.md (verificeret med grep). Yderligere verifikation: ingen.

### 8. `agent/core-design-principles` (320281b6) — 2026-07-31, forfatter `github@froekjaer.dk`

**Klassifikation: UNIKT INDHOLD — kræver Peters disposition. Pilotens hovedfund.**

Evidens: Tilføjer `Dokumentation/TimeLapse_Core_Design_Principles_v1.md` (**585 linjer**) som **ikke findes på main**, plus pointere i 00_START_HER, ADR/README, DOKUMENTPAKKE_OVERSIGT, SABSA_Architecture_v10, fuld dokumentation og en 97-linjers handover-entry. Det er præcis den type "glemt, reelt arbejde" R04 skal fange: en færdig designdokument-pakke fra 31. juli, aldrig merget. Oprettet på en `agent/`-branch — sandsynligvis et tidligt agent-workflow-eksperiment. Yderligere verifikation før disposition: (a) læs dokumentet og vurder om indholdet er dækket af ADR-001/nyere arkitektur; (b) afklar med Peter om det skal integreres eller arkiveres med begrundelse.

## Metode-læring fra piloten

1. **`git cherry` alene vildleder i begge retninger:** 7 af 8 branches viste unikke patches — men kun 1 af 8 har reelt unikt indhold. Squash/rebase på main ødelægger patch-ID'er, mens indholdet allerede er på main.
2. **Superset-tjekket er den stærkeste hurtige test:** findes filen på main, og er main's version længere/nyere? Så er branchen næsten sikkert absorberet.
3. **Beslutningskontekst er afgørende:** F005-branchen så ud som "manglende sikkerhedsfix" — men var en bevidst fravalgt løsning. Uden risikoaccept-tjekket havde jeg fejlklassificeret den som "skal integreres".
4. **Iterationskæder (samme branch-navn + -current/-final) skal triages som kæde**, ikke som tre uafhængige spor.
5. **Tidsforbrug:** ~4–6 værktøjskald pr. branch i denne batch. Realistisk tempo for de resterende 50: 4–6 yderligere batches.

## Foreløbigt resultat

| Klassifikation | Antal (af 8) | Branches |
|---|---|---|
| Absorberet (evidens: superset/identisk indhold på main) | 5 | deploy-integrity ×3, rollback-idempotency, kimi-handover |
| Absorberet, restkontrol udestår | 1 | fix-ordered-offline-apt-install |
| Superseded-ved-beslutning | 1 | codex/security-closure-f005 |
| Unikt indhold — disposition hos Peter | 1 | agent/core-design-principles |
| Uklar | 0 | — |

**Ingen af disse er foreslået slettet.** Næste skridt afventer Peters go på metoden.
