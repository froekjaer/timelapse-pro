# R04 Branchtriage — Batch 2 (Claude, efter Kimis pilot)

**Model/session:** Claude (Sonnet 5, denne session) · **Dato:** 2026-09-13
**Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf` (verificeret via `gh api` + `git ls-remote`, ikke antaget)
**Mandat:** Peter, 2026-09-13 — Kimi utilgængelig i et par uger; R04 videreført med samme eller højere evidensniveau. Kimis pilotrapport (`Dokumentation/R04_BRANCHTRIAGE_PILOT_1_2026-09-13.md`) er bevaret uændret som provenance og er **ikke** rettet her, selv hvor jeg har supplerende evidens.
**Population:** De 59 "patches_to_review"-branches fra `BRANCH_SCREENING.json` (frosset 2026-09-13T08:45:40Z mod `13a0d3b3`), minus de 8 allerede triagerede i pilot 1, minus kendte, aktivt sporede branches (#159/#163/#214/#229/#232-kæden).

## Metode (identisk med pilot 1, se dér for fuld beskrivelse)

1. `git diff --stat $(git merge-base origin/main <branch>) <branch>` — branchens **egen** patch-overflade, ikke støj fra at main er vokset (afgørende for gamle branches — treprikke-diff mod frisk main giver 300+ filer støj for enhver månedsgammel branch).
2. For hver rørt fil: findes den på main? Er main's version en **superset** (samme funktioner/indhold + mere), byte-identisk, eller divergerende?
3. Beslutningskontekst: GRC/HANDOVER/ADR-tjek for bevidst fravalg.
4. Iterationskæder (samme emne, -current/-ci-varianter) analyseret samlet, dispositioner sporet enkeltvis.

## Fund pr. branch/kæde

### 1. `security/closure-test-target-isolation` (`0b1415...`→nej, head `40e0dda7`) + `-current` (`0b616709`)

**Klassifikation: Absorberet.**

Evidens: Egen patch-overflade er kun `tests/conftest.py` + `tests/test_security_closure_f004.py` (83+42 linjer). Begge filer findes på main; `tests/conftest.py` er **byte-identisk** (`diff` tomt) mellem branch og main. Testfilen findes på main under samme navn.

### 2. `security/closure-update-authority-h123` (`16bd9641`) + `-h123-ci` (`5e1272c4`)

**Klassifikation: Absorberet, main videreudviklet.**

Evidens: Egen overflade er `headend/main.py`, `headend/services/update_authority.py` (ny), test + (i -ci-varianten) en kontraktdokumentation. `update_authority.py` findes på main som **superset**: samme kernefunktion (`environment_permits_target` el. lign., fail-closed på ukendt device-environment) plus en ekstra `_ALL_ENVIRONMENTS_MARKER`-udvidelse main har tilføjet senere. Testfilen `test_update_authority_scope_environment.py` findes på main.

### 3. `security/closure-technician-auth-xss` (`d5e5f2db`)

**Klassifikation: Absorberet.**

Evidens: `headend/services/technician_auth_security.py` — **byte-identisk** med main. `tests/test_technician_auth_xss_closure.py` findes på main. Handover-entry fra branchen (9 linjer) er indholdsmæssigt dækket af main's HANDOVER_LOG (samme emne, XSS-lukning teknikerauth).

### 4. `security/closure-zai-critical-redaction` (`ca44af0b`)

**Klassifikation: Absorberet, main videreudviklet.**

Evidens: `headend/redaction_api.py` — main er en **superset** (samme `_find_image_path`-kernelogik plus senere tilføjet `FalsePositiveResponse`/`mark_false_positive`-workflow, som ikke fandtes på branchen). `tests/test_security_closure_zai_redaction.py` findes på main.

### 5. `security/closure-real-artifact-signature-verification` (`d384d1d6`)

**Klassifikation: Absorberet.**

Evidens: `edge/security.py` — main har **nøjagtig samme funktionsliste** (12 funktioner, `verify_update_artifact`, OpenPGP-signaturverifikation m.fl.), kun flere kommentarlinjer. `headend/services/artifact_trust.py` byte-identisk. `tests/test_artifact_openpgp_verification.py` findes på main.

### 6. `codex/security-closure-f001` (`540daea4`) + `security/closure-mainpy-p0-f001` (`4c4aa28f`) — **iterationskæde**

**Klassifikation: Absorberet (kæde; -mainpy-p0 er den absorberede sluttilstand).**

Evidens: Begge fjerner den hardkodede fælles fabriks-TOTP-hemmelighed (`JBSWY3DPEHPK3PXP`) fra `headend/main.py::get_config()` til fordel for en fail-closed `"unprovisioned"`-tilstand. Verificeret: `JBSWY3DPEHPK3PXP` findes **0 gange** på main; main har præcis samme `{"secret": "", "sid": "unprovisioned"}`-mønster. Den ældre gren (`codex/security-closure-f001`) har testfilen `test_security_closure_f001.py` (uden main-modstykke ved dette navn); den nyere (`-mainpy-p0-f001`) har `test_security_closure_f001_current.py`, som **findes på main** og indholdsmæssigt dækker samme scenarie under et andet, mere præcist testnavn (verificeret ved diff af testindhold: samme påstand, omdøbt testfunktion). `-mainpy-p0-f001` tilføjer desuden `path_security.py` og `local_service_security.py`, begge byte-identiske med main.

### 7. `security/closure-os-builder-f002` (`342854b9`)

**Klassifikation: Absorberet.**

Evidens: `headend/services/os_builder_security.py` — byte-identisk med main. `tests/test_os_builder_security.py` findes på main.

### 8. `fix/edge-post-restart-health-rollback` (`a289393d`, 2026-08-16)

**Klassifikation: Absorberet — historisk oprindelse til mains nuværende mekanisme.**

Evidens: Dette er **ikke** en konkurrent til #163 (som jeg tidligere har analyseret separat) — det er ældre (16/8 vs. #163's 30/8) og er ikke i ancestor-forhold til #163 (`git merge-base --is-ancestor` begge veje: nej). Sammenligning af `edge/update_lifecycle.py`s funktionsliste mellem denne branch og main: **identisk** (`mark_pending_app_update_health_confirmed`, `awaiting_restart_health`, `rolled_back_by_guard`, `_report_rollback_from_restored_release` m.fl. — samme navne, samme rækkefølge). Dette bekræfter: den simple health-confirmation-mekanisme jeg tidligere fandt på main (og som #163 forsøger at udvide med et stabilitetsvindue) stammer historisk herfra, ikke fra #163. Fuldt absorberet; intet resterende unikt indhold.

### 9. `codex/edge-terminal-renderer` (`35ad6cc5`, seneste commit 2026-08-08) — **STOP-GATE, eskaleres til Peter**

**Klassifikation: Ikke disponeret — kræver Peters beslutning.**

Dette er den mest konsekvensfulde enkeltstående fund i denne batch. Branchens navn matcher ikke dens seneste commit-besked ("test(camera): add behavioural tests..."), og dens merge-base ligger helt tilbage ved PR #7 — usædvanligt gammel og strukturelt kompleks (101 filer, 10.480 linjer mod merge-base). Ved nærmere gennemgang indeholder den en commit-kæde (`afdc3e01`…`b25703ed`, 2026-08-03) der forbedrer et **allerede eksisterende** lokalt shell-endpoint i `edge/scripts/totp-service.py` (`/mgmt/cli/bash/*`): main bruger i dag en WebSocket-baseret variant (`/mgmt/cli/bash/ws`); denne branchs commits beskriver eksplicit at gøre det samme **uden WebSockets**, med korrekt terminal-kontrolsekvens-rendering og en "controlling terminal" — hvilket antyder kendte, uløste begrænsninger i main's nuværende implementering, som aldrig blev rettet.

**Hvorfor dette er et stop-gate, ikke en rutineklassifikation:**
1. Det rører et **allerede aktivt, sikkerhedsrelevant** lokalt shell-adgang-endpoint (`/mgmt/cli/bash`) — ikke et forkastet forslag, men noget der kører på main i dag.
2. Det er i direkte spænding med et princip fra `agent/core-design-principles` (samme batch, se separat analyse): "No General-purpose Shell" / "intet `POST /run-command`-endpoint i normal service-mode" — main har allerede sådan et endpoint. De to fund bør læses sammen.
3. **`b25703ed` (og de fire commits før den) er selve HEAD på min egen sessions oprindelige worktree-branch** (`claude/kind-shamir-29fe84`) — dvs. min session blev startet fra et punkt der inkluderer dette arbejde uden at det er på main. Det betyder der kan være yderligere kontekst om hvorfor dette aldrig blev merget, som jeg ikke selv har adgang til.
4. En af de fem stashes Kimi rapporterede (`stash@{3}`, "pre-main-deploy-safety-backup-20260815T125231Z") blev taget netop **på** `codex/edge-terminal-renderer` — der kan være yderligere, ikke-committed kontekst i den stash der er relevant her. Jeg har **ikke** poppet eller inspiceret stashens indhold (uden for denne opgaves mandat).

**Ingen disposition foreslået.** Dette kræver Peters vurdering af (a) om main's nuværende WebSocket-baserede shell-løsning har kendte problemer der bør rettes fra denne branch, (b) om det generelle shell-endpoint overhovedet bør bestå i sin nuværende form, og (c) om stash@{3}'s indhold er relevant og bør gennemgås af nogen med mandat til det.

## Foreløbigt resultat, batch 2

| Klassifikation | Antal branches | Refs |
|---|---|---|
| Absorberet (evidens: superset/identisk indhold på main) | 8 | test-target-isolation×2, update-authority-h123×2, technician-auth-xss, zai-redaction, real-artifact-signature, os-builder-f002, edge-post-restart-health-rollback |
| Absorberet (iterationskæde) | 1 kæde (2 refs) | security-closure-f001 → mainpy-p0-f001 |
| **Stop-gate — Peters beslutning krævet** | 1 | codex/edge-terminal-renderer |

**Ingen af disse er foreslået slettet.** Ingen branch/worktree/stash er rørt destruktivt. `codex/edge-terminal-renderer` og dens tilknyttede stash `stash@{3}` skal eksplicit **ikke** disponeres før Peter har taget stilling.

## Metode-læring, tilføjet af Claude

- To-prikke-diff mod merge-base (ikke tre-prikke mod aktuel main) er afgørende for gamle branches — reducerer støj fra hundredvis af filer til branchens faktiske patch-overflade.
- "Superset-testen" (findes filen på main, og er main's version længere/nyere med samme kernefunktioner) holdt for 8 af 9 branches i denne batch — konsistent med Kimis pilot-læring.
- Branch-*navne* kan være misvisende for indhold (`codex/edge-terminal-renderer`'s seneste commit-besked matcher ikke dens navn) — commit-historik og faktisk diff er nødvendige, navnet alene er ikke nok.
