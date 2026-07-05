# TimeLapse Pro - system health register

**Status:** Arbejdsversion 0.1  
**Dato:** 2026-05-23  
**Formål:** Første prioriterede gennemgang af fejl, mangler og risici i kodebase, deploy-flow og driftsartefakter.  
**Scope i denne version:** Update/deploy, secrets/data hygiene, UI, test/build, Edge/Headend-kontrakt og compliance-relevante gaps.

## Test- og verifikationsstatus

| Check | Resultat | Note |
|---|---:|---|
| `npm run build` i `timelapse-ui` | OK | Build lykkes. Vite advarer om stor bundle på ca. 1.020 kB minified og ineffektiv dynamic import af `src/api/client.ts`. |
| `npm run lint` i `timelapse-ui` | Fejl | 197 errors og 8 warnings. Mange er `any`, unused imports og React hook-regler, men der er også reelle fejlindikatorer. |
| `pytest -q` | Ikke kørt | `pytest` findes ikke i aktiv Python (`No module named pytest`). |
| Signeret dokumentationscommit | OK | Commit `35e937d` har god GPG-signatur fra `TimeLapse Pro <github@froekjaer.dk>`. |

## Prioritering

- **P0:** Skal håndteres før push/deploy eller før repo/exports deles bredere.
- **P1:** Høj risiko for forkert drift, sikkerhedsbrud eller compliance-gap.
- **P2:** Reelle fejl eller mangler der bør løses tidligt, men som ikke alene blokerer.
- **P3:** Kvalitet, vedligehold, teknisk gæld eller polish.

## Fund

### HLTH-001 - Utrackede exports indeholder secrets og person-/systemdata

**Prioritet:** P0  
**Område:** Data hygiene, Git hygiene, compliance, GDPR, ISO 27001, CRA  
**Status:** Åben

**Observation:** `headend/exports/notebooklm_20260512_223936/` ligger utracked i worktree og indeholder databaseeksport med følsomme felter, blandt andet API tokens, password hashes, TOTP-secret, SFTP password/config overrides og kunde-/site-/device-data.

**Risiko:** Hvis mappen ved en fejl bliver committed, delt eller sendt til AI/notebook-værktøjer uden maskering, eksponeres driftshemmeligheder og kundedata. Det er en direkte compliance- og sikkerhedsrisiko.

**Evidens:** `git status` viser `headend/exports/` som utracked. `rg` fandt blandt andet `api_token`, `password_hash`, `totp_secret`, SFTP password og konkrete kunde/site/device records i `headend/exports/notebooklm_20260512_223936/notebooklm_export.jsonl`.

**Foreslået rettelse:**

- Tilføj `headend/exports/` til `.gitignore`.
- Flyt eller slet lokale exports efter aftale.
- Lav en sikker eksportfunktion, der masker secrets som `***` eller refererer til secret IDs.
- Definer en policy for NotebookLM/AI-eksport: ingen rå secrets, tokens, password hashes, TOTP secrets eller kundedata uden eksplicit anonymisering.

### HLTH-002 - `secrets/` ligger utracked i repo-roden

**Prioritet:** P0  
**Område:** Secrets management, Git hygiene  
**Status:** Åben

**Observation:** `secrets/` ligger utracked, og `rg --files` viser blandt andet `secrets/gcp-service-account.json`.

**Risiko:** Service account-nøgler eller andre hemmeligheder kan ved en fejl blive committed. Det er uforeneligt med ISO 27001/IEC 62443 change control og CRA secure development-praksis.

**Foreslået rettelse:**

- Tilføj `secrets/` til `.gitignore`.
- Flyt hemmeligheder ud af repoet til en lokal secret store eller deployment-specifik placering.
- Rotér alle nøgler, hvis de allerede har været delt eller eksporteret til eksterne systemer.

### HLTH-003 - Edge app-update bruger stadig direkte GitHub/origin

**Prioritet:** P1  
**Område:** Update/deployment, Edge offline capability, architecture  
**Status:** Mitigeret i kode, arkitekturarbejde mangler

**Observation:** Edge har stadig direkte Git-flow i både `edge/agent.py` og `deploy/edge_update.sh`.

**Evidens:**

- [edge/agent.py](/Users/peter/projects/timelapse-pro/edge/agent.py:763) `_check_update()` bruger `git fetch origin main` og `git pull origin main`.
- [edge/agent.py](/Users/peter/projects/timelapse-pro/edge/agent.py:895) `_run_update()` kalder `deploy/edge_update.sh` for app-opdateringer.
- [deploy/edge_update.sh](/Users/peter/projects/timelapse-pro/deploy/edge_update.sh:45) bruger `git fetch origin main`.
- [deploy/edge_update.sh](/Users/peter/projects/timelapse-pro/deploy/edge_update.sh:60) bruger `git pull origin main`.

**Risiko:** Bryder kravet om at Edge ikke nødvendigvis har Internet og skal opdateres via Headend. Det kan give fejlede updates i produktion og gør change-ticket/artifact-signering svær at håndhæve.

**Foreslået rettelse:**

- Deaktiver eller udfas den gamle `update_requested`/`git pull`-vej. Første mitigation er implementeret ved at gøre legacy git-update opt-in via `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1`.
- Erstat app-update med Headend-medieret artifact download fra et signeret release manifest.
- Edge skal verificere artifact hash/signatur og rapportere per-target resultat tilbage til Headend.

### HLTH-004 - GPG-tag-check verificerer ikke nødvendigvis den version der installeres

**Prioritet:** P1  
**Område:** Supply chain, signing, update integrity  
**Status:** Mitigeret i kode, arkitekturarbejde mangler

**Observation:** `deploy/edge_update.sh` finder seneste tag og verificerer taggets signatur, men opdaterer derefter til `origin/main`.

**Evidens:** [deploy/edge_update.sh](/Users/peter/projects/timelapse-pro/deploy/edge_update.sh:23) verificerer latest tag, mens [deploy/edge_update.sh](/Users/peter/projects/timelapse-pro/deploy/edge_update.sh:60) puller `origin main`.

**Risiko:** En god signatur på et tag beviser ikke, at den commit der installeres fra `origin/main`, er den samme som tagget. Det giver falsk sikkerhed omkring signering.

**Foreslået rettelse:**

- Legacy scriptet er gjort opt-in via `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1`, så det ikke bruges som uheldig produktionsdefault.
- Artifact manifest skal binde `release_id`, commit/tag, hash, signer og SBOM sammen.
- Edge skal verificere præcis det artifact eller commit-id, den installerer.
- Git-baseret deploy bør ikke bruges direkte på Edge i produktion.

### HLTH-005 - UI approval modal sender ikke valgte approval options

**Prioritet:** P1  
**Område:** UI/API-kontrakt, update governance  
**Status:** Åben

**Observation:** UI har felter til miljø og scope, men `approve()` sender kun en tom POST uden body.

**Evidens:** [UpdatesPage.tsx](/Users/peter/projects/timelapse-pro/timelapse-ui/src/pages/UpdatesPage.tsx:232) kalder `/approve` uden body, mens modalens valgte værdier ligger i `approveOpts` omkring [UpdatesPage.tsx](/Users/peter/projects/timelapse-pro/timelapse-ui/src/pages/UpdatesPage.tsx:210). Backend forventer `ApprovePayload` med `environment`, `scope`, `scope_id` og `target_device_ids` i [headend/main.py](/Users/peter/projects/timelapse-pro/headend/main.py:1800).

**Risiko:** Bruger tror, de godkender til test eller specifikt device, men backend bruger defaults. Det kan udløse forkert deployment-scope eller produktion i stedet for test.

**Foreslået rettelse:**

- Send `approveOpts` som JSON body.
- Valider `scope_id` ved device-scope.
- Vis en review/confirm opsummering før godkendelse, når scope er global eller production.

### HLTH-006 - Update API returnerer ikke alle felter UI forventer

**Prioritet:** P2  
**Område:** UI/API-kontrakt  
**Status:** Åben

**Observation:** UI-typen forventer `environment`, `deployed_count` og `failed_count`, men `/api/updates/pending` returnerer dem ikke.

**Evidens:** UI interface i [UpdatesPage.tsx](/Users/peter/projects/timelapse-pro/timelapse-ui/src/pages/UpdatesPage.tsx:28) indeholder felterne. Backend response i [headend/main.py](/Users/peter/projects/timelapse-pro/headend/main.py:1783) returnerer kun basisfelter til `approved_by`.

**Risiko:** UI skjuler eller viser forkert deployment-status, og test/prod promotion bliver svær at forstå.

**Foreslået rettelse:** Udvid API response med `environment`, `target_device_ids`, `deployed_count`, `failed_count`, `deployed_at` og `rollback_at`.

### HLTH-007 - Update scope matcher ikke dokumenterede krav

**Prioritet:** P1  
**Område:** Update policy, multi-tenant governance  
**Status:** Åben

**Observation:** Backend-modellen omtaler `global|customer|site|device`, UI approval understøtter kun `global|device`, og dokumenter/brugerkrav kræver også kamera/logisk camera-scope.

**Evidens:**

- [headend/database.py](/Users/peter/projects/timelapse-pro/headend/database.py:256) dokumenterer `global|customer|site|device`.
- [UpdatesPage.tsx](/Users/peter/projects/timelapse-pro/timelapse-ui/src/pages/UpdatesPage.tsx:37) typer kun `global|device`.
- [AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md](/Users/peter/projects/timelapse-pro/Dokumentation/AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md:97) beskriver scopekravet.

**Risiko:** Kundespecifik/site-/kamera-godkendelse kan ikke håndhæves pålideligt i UI eller datamodel.

**Foreslået rettelse:** Udvid scope til `global|customer|site|camera|device`, og bind camera-scope til `DeviceAssignment`, så fysisk device kan udskiftes uden at miste policyhistorik.

### HLTH-008 - Per-target deployment state mangler

**Prioritet:** P1 (nedjusteret fra P0 2026-07-05 — flush-regressionen er nu committet/deployet, se nedenfor; forbliver P1 og ikke ✅ Løst indtil live multi-device-test er kørt)
**Område:** Rollout, rollback, audit
**Status:** 🟡 Flush-rettelse committet (`1e3c3321`, af Codex), deployet og health-checket 2026-07-05 nat — resterer kun live multi-device-rollout-verifikation (se nedenfor)

**Oprindelig observation (forældet pr. 2026-07-05):** `PendingUpdate.status` er global for hele update-posten. En enkelt Edge-report sætter hele update-status til `deployed` eller `rolled_back`.

**KORREKTION 2026-07-05 (Claude):** Den oprindelige evidens var forældet — `update_targets`-tabellen (`headend/database.py::UpdateTarget`) fandtes allerede, blev populeret pr. Edge-report, og var allerede eksponeret via `/api/updates/{id}/flow-status` samt vist per-device i `UpdatesPage.tsx` (kodet siden juni 2026). Den reelle, stadig-aktuelle del af risikoen var i stedet: `/api/updates/report` satte den GLOBALE `PendingUpdate.status` direkte fra ÉT enkelt device's rapport uden hensyn til scope — for `scope=global/customer/site` (flere targets) kunne dermed ét device alene gøre hele rollout'en "deployed" eller "rolled_back", mens resten stadig var undervejs. `_update_flow_stage()` i samme fil forudsatte allerede (via sine "Edge arbejder"/"Afventer Edge heartbeat"-grene) at status burde blive stående på "approved" indtil alle targets er færdige — så bugfixen følger kodens eget eksisterende designintent, ikke ny adfærd.

**Rettet i kode, committet/pushet af Codex (`61802951`) og deployet:** `headend/main.py::report_update` — for `scope="device"` (ét target) er adfærden uændret (øjeblikkelig flip, som hidtil testet/brugt). For multi-target scopes venter global status nu på at ALLE kendte targets (via `_resolve_update_targets`) har rapporteret en terminal-status (deployed/rolled_back/failed), før `PendingUpdate.status` flippes — ved blandet udfald (nogle deployed, nogle fejlet) sættes status konservativt til `rolled_back`. Som sidegevinst er `deployed_count` (der aldrig blev inkrementeret ved success, jf. `Update_Flow_v10.md` linje 549) nu korrekt for begge stier. `dk.froekjaer.timelapse-headend` genstartet 2026-07-05 nat; `/api/health` svarede 200 OK.

**REGRESSION fundet 2026-07-05 (Claude, periodisk tjek, denne runde):** Byggede en rigtig kontrakttest (`headend/tests/test_report_update_rollup.py`, kører den faktiske `report_update()`-funktion mod en midlertidig SQLite-DB — IKKE en simulering) for endelig at få den "resterende live-verifikation" nedenfor dækket uden Mac Mini-adgang. Testen afslørede at den deployede `61802951`-fix ALDRIG flipper global status til `deployed`/`rolled_back` for multi-target scopes, heller ikke når alle devices reelt har rapporteret terminal — rollout'en sidder fast på "approved" for evigt. Rodårsag: `SessionLocal` er konfigureret med `autoflush=False` (`headend/database.py` linje 73), så den lige tilføjede/ændrede `target`-række for DETTE device (sidste rapportør i rollout'en) er usynlig for `db.query(UpdateTarget).filter_by(pending_update_id=u.id)...all()` få linjer nedenfor — den mangler simpelthen en `db.flush()` inden rollup-forespørgslen. Konsekvens i produktion: enhver multi-target rollout (scope global/customer/site) hvor alle devices ender i en terminal-status vil ALDRIG blive markeret "Deployet"/"Rullet tilbage" i UI — det er reelt værre end den oprindelige risiko (som var en for-tidlig flip; den nye bug er en flip der aldrig sker).

**Rettelse (2026-07-05, Claude):** Tilføjet `db.flush()` i `headend/main.py::report_update` lige før rollup-forespørgslen (samme sted som ovenfor). 1-linjes ændring, ingen anden logik rørt. Alle 4 tests i `headend/tests/test_report_update_rollup.py` fejlede FØR flush-rettelsen (2 af 4 — de to der afhænger af at SIDSTE device i rollout'en flipper status) og passerer nu EFTER (4/4).

**Verifikation:** `python3 -m py_compile headend/main.py headend/database.py` ren. `pytest headend/tests/test_report_update_rollup.py -v` → 4 passed (kører den faktiske kode, ikke en model af den — se testfilens docstring for opsætning).

**OPDATERING 2026-07-05 (Claude, periodisk tjek, docs-sync):** Rettelsen er committet/pushet af Codex som `1e3c3321` (samme commit som `headend/tests/test_update_lifecycle.py`, 9 yderligere tests) og deployet: `dk.froekjaer.timelapse-headend` genstartet (`launchctl kickstart`), `/api/health` bekræftet 200 OK. Codex kørte desuden det fulde testsæt i et midlertidigt venv (`/tmp/tlp-hvenv`) →
`pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py -v` → 13 passed. Bekræftet her at `db.flush()` er til stede i den committede `headend/main.py` på nuværende `HEAD` (`git show 1e3c3321 -- headend/main.py`).

**Resterende risiko:** Live-verifikation på en faktisk multi-device rollout (2+ test-enheder, `scope=site`, bekræfte reel flip til "Deployet"/"Rullet tilbage") udestår fortsat — bevidst ikke kørt fra periodisk heartbeat, da det ændrer update-state for rigtige enheder. Dette er nu den eneste resterende del af HLTH-008/R06/P1.4.

### HLTH-009 - Policy evalueres, men enforcement er ufuldstændig

**Prioritet:** P1  
**Område:** Update governance  
**Status:** Åben

**Observation:** `get_update_policy()` returnerer policy og approved updates, men Edge eksekverer alle `approved` updates uden at tjekke vedligeholdelsesvindue, reboot-policy eller auto/manual-type på Edge-siden.

**Evidens:** [edge/agent.py](/Users/peter/projects/timelapse-pro/edge/agent.py:849) henter policy og kører første approved update. [headend/main.py](/Users/peter/projects/timelapse-pro/headend/main.py:1912) returnerer `maintenance_window`, men Edge bruger den ikke i `_check_and_apply_updates()`.

**Risiko:** Updates kan installeres uden for aftalt vindue, og OS updates kan reelt kræve reboot uden korrekt kunde-/site-politik.

**Foreslået rettelse:** Flyt beslutningen om “må denne update køre nu?” til en eksplicit resolver i Headend, og send kun runnable actions til Edge, inkl. reboot/maintenance constraints.

### HLTH-010 - Default JWT secret genereres ved processtart

**Prioritet:** P1  
**Område:** Auth/session security, operations  
**Status:** Åben

**Observation:** Hvis `JWT_SECRET` ikke er sat, genereres en ny random secret ved start.

**Evidens:** [headend/main.py](/Users/peter/projects/timelapse-pro/headend/main.py:71)

**Risiko:** Alle sessions bliver ugyldige ved restart, og miljøer kan utilsigtet køre uden eksplicit secret management. Det er driftsskrøbeligt og svært at dokumentere som kontrolleret nøglehåndtering.

**Foreslået rettelse:** I production skal manglende `JWT_SECRET` være fatal startup error. LAB kan tillade fallback, men skal logge tydeligt og markere miljøet som non-production.

### HLTH-011 - `UpdatesPage` har dublet filter-key

**Prioritet:** P2  
**Område:** UI småfejl  
**Status:** Åben

**Observation:** `FILTERS` indeholder `deployed` to gange, hvilket giver duplicate React keys og forvirrende UI.

**Evidens:** [UpdatesPage.tsx](/Users/peter/projects/timelapse-pro/timelapse-ui/src/pages/UpdatesPage.tsx:181)

**Foreslået rettelse:** Fjern dubletten.

### HLTH-012 - Frontend lint baseline er ikke grøn

**Prioritet:** P2  
**Område:** Kvalitet, CI/CD, maintainability  
**Status:** Åben

**Observation:** `npm run lint` fejler med 197 errors og 8 warnings.

**Risiko:** CI kan ikke bruges som kvalitetsgate, og reelle fejl drukner i støj.

**Foreslået rettelse:**

- Ret små åbenlyse fejl først: unused imports, duplicate keys, expressions uden effekt.
- Beslut om React Compiler-reglerne skal være hårde nu, eller om de skal justeres mens appen stabiliseres.
- Indfør lint baseline som gate, når fejlmængden er bragt ned.

### HLTH-013 - Python testmiljø mangler

**Prioritet:** P2  
**Område:** Testability, CI/CD  
**Status:** Åben

**Observation:** `pytest` er ikke installeret i aktiv Python, så backend/edge-testene kan ikke køres lokalt.

**Risiko:** Ændringer i Headend/Edge kan ikke verificeres reproducerbart.

**Foreslået rettelse:** Definer et repo-styret Python testmiljø, fx `requirements-dev.txt`, `pyproject.toml` eller `uv`, og dokumentér én kommando for test.

### HLTH-014 - Testene er primært tekst-/presence-tests

**Prioritet:** P3  
**Område:** Test quality  
**Status:** Åben

**Observation:** Flere tests læser kildefiler og tjekker om bestemte strings findes, frem for at teste API-opførsel, datamodel eller Edge/Headend integration.

**Evidens:** `tests/test_headend_endpoints.py` og `tests/test_agent_integrity.py`.

**Risiko:** Tests kan være grønne selvom integrationen er brudt, og de kan også fejle ved harmløse refactors.

**Foreslået rettelse:** Behold dem midlertidigt som smoke checks, men tilføj FastAPI TestClient-tests, databasemigrationstests og Edge API contract-tests.

### HLTH-015 - Default README er stadig Vite-template

**Prioritet:** P3  
**Område:** Dokumentation, onboarding  
**Status:** ✅ Løst 2026-07-05 (Claude, periodisk tjek) — committet/pushet af Codex som `9dda9923`

**Oprindelig observation:** `README.md` beskrev React + TypeScript + Vite-template og ikke TimeLapse Pro.

**Rettelse:** Repo-rod `README.md` erstattet med reelt projekt-README (formål/status, mappestruktur, lokal opsætning for headend/UI/edge, test-kommandoer, pointer til `Dokumentation/00_START_HER.md`, kort SABSA/ISO 27001/IEC 62443/CRA/GDPR/NIS2/AI Act-afsnit). Se GO_LIVE_CHECKLIST_v10.md H-06.

## Foreslået første rettelsespakke

Første små commit bør være lav risiko og reducere umiddelbar fare:

1. `.gitignore`: tilføj `secrets/`, `headend/exports/`, `*.bak_*`, `*.gdoc` og lokale snapshots efter konkret review.
2. `UpdatesPage.tsx`: send approve body og fjern duplicate `deployed` filter.
3. `headend/main.py`: returnér de update-felter UI allerede forventer.
4. Dokumentér at `edge_update.sh` er legacy/LAB-only, indtil Headend artifact update-flow er implementeret.

## Åbne beslutninger

- Skal lokale utrackede `headend/exports/` slettes/flyttes nu, eller bevares midlertidigt uden for repoet?
- Skal `secrets/gcp-service-account.json` roteres, eller er den allerede en testnøgle uden adgang?
- Skal vi starte med en lille hygiene/UI-fix commit, eller først designe datamodellen for change tickets/update targets?
