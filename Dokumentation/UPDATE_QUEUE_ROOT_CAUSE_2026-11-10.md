# Update-kø: rodårsag og sikker genopretning — 2026-11-10

## Konklusion

Dashboardets `14 blokeret` er ikke 14 ens deploymentfejl. Det er en blanding af:

1. normale kandidater, hvor Headend endnu forbereder et signeret offline artifact;
2. kandidater hvis pakkeliste er ændret, efter at et ældre artifact/change ticket blev bundet;
3. Edge1-kandidater uden en frisk Headend build-plan, fordi catalog-loopets PostgreSQL-forbindelse døde midt i et langsomt netværkskald;
4. seks Homebrew-kandidater baseret på stale Mac Headend-inventory, fordi node-agenten ikke kører;
5. en historisk global kandidat (#273), der i teksten er markeret superseded, men stadig står `blocked`.

Ingen af de 14 bør installeres ukritisk. Ingen update er installeret eller godkendt som del af denne analyse.

## Verificeret live-state

| Gruppe | Update-ID'er | Observation | Disposition |
|---|---|---|---|
| Python dependencies | #272, #304, #308 | Nye planer findes, men gamle signerede artifacts/tickets er fortsat bundet | Ny candidate identity afgør semantisk match; ændret pakkesæt superseder gammel række og bygger nyt artifact |
| Edge OS | #298, #306, #307, #313 | #298/#313 har gamle artifacts; #306/#307 mangler Headend-plan | Frisk plan pr. device; gamle artifacts må kun genbruges ved eksakt signeret package-target-match |
| Mac Homebrew | #275–#280 | Inventory sidst rapporteret 2026-09-23; viste målversioner er derfor stale | Reparér node-agent, modtag frisk inventory, lad CMDB supersede/oprette korrekte kandidater |
| Historisk | #273 | `resolution_reason` siger selv superseded; #290 blev senere også fejlagtigt superseded af den gamle Edge-zero-report-fejl; #313 er den nyere Edge2 security-kandidat | Luk #273 eksplicit som superseded med bevaret ticket/artifact-audit efter kode-deploy og frisk reconciliation |

## Rodårsager i kode og drift

### 1. Kandidaten havde ingen stabil identitet

Catalog-refresh muterede `version`, `package_details`, beskrivelse og plansti på en eksisterende `PendingUpdate`. Change ticket og artifact forblev bundet til rækkens ID. Auto-builderen spurgte kun: “findes der et deployable artifact?”, ikke: “er artifactet bygget til præcis denne aktuelle pakkeliste?”. Resultatet var et permanent deadlock og en trust-risiko.

Rettelsen bruger en kanonisk identitet af normaliseret pakkenavn + target-version. Installeret version, rækkefølge og katalogmetadata ændrer ikke payload-identiteten. Ændres target-sættet, bliver den gamle kandidat `superseded`, aktive targets lukkes, den ikke-terminale ticket annulleres, og et nyt kandidat-ID oprettes. Det gamle signerede artifact slettes ikke.

Artifact-match er fail-closed. Nye artifacts bærer target-listen i den signerede manifest-evidens. Ældre OS-artifacts kan kun matches via `package-manifest.json`, når filens sha256 stemmer med output-hashen i det signerede ydre manifest.

### 2. Én langlivet DB-session dækkede alle devices

OS- og Python-catalog-loopene holdt en SQLAlchemy-session åben under eksterne metadata-/builderkald. Observeret PostgreSQL-fejl lukkede forbindelsen efter Edge2, så Edge1 aldrig fik en plan. Rettelsen snapshotter kun nødvendige inventory-felter, lukker discovery-sessionen før netværksarbejdet og åbner en frisk, kort transaktion pr. device.

### 3. Edge-observation kunne overskrive Headend-authority

Edge har bevidst ingen direkte apt/internet-adgang og kan derfor rapportere fra en stale apt-cache. Når en Headend-plan findes, må den efterfølgende Edge-observation ikke længere overskrive kandidat, pakkeliste eller readiness. Headend-catalog-reconciliation er authority efter `Plan:`-evidens.

### 4. Mac node-agent kunne ikke genskabe sin log

LaunchDaemon kører least-privilege som `peter`, men stdout/stderr pegede på `/var/log/timelapse-node-agent.log`. Filen mangler, og servicebrugeren kan ikke oprette den under `/var/log`; launchd viser 2.113 runs og `EX_CONFIG`. Installeren bruger nu `/Library/Logs/TimeLapsePro/node-agent.log`, opretter katalog og fil med service-ejerskab og kan reparere plist/log uden at overskrive eksisterende config.

## Sikker rollout-rækkefølge

1. Review/merge kodeændringen og genkontrollér overlap med PR #298 (update-autorisation).
2. Deploy Headend-koden uden at godkende nogen af de eksisterende updates.
3. Reparér node-agentens plist/logplacering; verificér `state=running` og en ny `Inventar rapporteret OK`.
4. Verificér at `device_inventory.inventory_reported_at` for Mac Headend er frisk, og at #275–#280 enten er superseded eller genoprettet med aktuelle target-versioner.
5. Kør/observer OS- og Python-catalog-refresh. Kontrollér at hver ændret kandidat får nyt ID, mens gamle tickets/artifacts bevares.
6. Kontrollér artifact/package-fingerprint før godkendelse. Byg kun nye artifacts for aktuelle kandidater.
7. Markér #273 eksplicit superseded af den aktuelle Edge2-security-kandidat efter frisk kontrol; slet ikke historisk evidence.
8. Installer én testkandidat ad gangen. Kræv backup, signatur/hash-verifikation, postflight, runtime-health og rollback-evidence før næste kandidat eller promotion.

## Forebyggende kontrol

- Dashboardet viser normal artifact-forberedelse som `forberedes` og reserverer `reelt blokeret` til fejl/konflikter.
- Binding af batch-artifacts afvises med HTTP 409 ved manglende eller forkert signeret package-target-evidens.
- Catalog-refresh muterer aldrig en historisk kandidat til et nyt payload.
- Edge apt-observation kan ikke degradere en kandidat, når Headend-planen eksisterer.
- Hvert device har sin egen korte DB-transaktion under catalog-import.
- Node-agent-logplaceringen kan oprettes/genskabes af den konfigurerede ikke-root service.

## Verifikation før PR

- Python compile og shell syntax: bestået.
- 23 målrettede update-/artifact-/supersession-/node-agent-tests i en isoleret SQLite-testdatabase: bestået. En tidligere bred kørsel ramte den lokale, migrationsmæssigt forældede `timelapse_test`-database og den lokale maskines manglende node-agent; det var miljøfejl, ikke produktionsmutation eller kode-regression.
- UI TypeScript/Vite production build: bestået.
- Codex Security diff-review fandt to trust-boundary-huller undervejs (slutgate for artifact-target-match og privilegeret logsti/symlink). Begge er rettet i samme diff og dækket af regressionstest; ingen åbne reportable fund efter rettelserne.
- Der er ikke foretaget live DB-mutation, service-restart, artifact-build, approval eller installation.
