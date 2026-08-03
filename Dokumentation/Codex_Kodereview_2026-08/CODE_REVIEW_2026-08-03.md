# TimeLapse Pro - kodegennemgang 2026-08-03

## Konklusion

Systemet har fungerende sikkerhedskontrol: signerede release-artifacts, Edge
pull uden direkte Edge-internet, GPG-verificerede image-inputs, atomiske
receipts og en separat lokal teknikerflade. De 39 fokuserede
release-/image-/backup-/driftskontrakter bestod.

Det er dog **ikke klar til en ny produktionsgodkendelse**. Tre P0-fund skal
lukkes og retestes, før OS-bundles eller ny BT-PAN-provisionering kan
accepteres som produktionsegnet. `headend/main.py` er 18.541 linjer med 234
direkte routes, selv om ADR-princippet er at flytte nye routes ud i moduler.

## Fund

### P0-01 - fælles BT-PAN TOTP-fabrikshemmelighed

**Evidens:** `headend/main.py:4075`, `headend/main.py:5270`,
`headend/database.py:333` og `edge/scripts/totp-service.py:123` falder alle
tilbage til den samme indbyggede TOTP-hemmelighed og `sid=factory-default`.
QR-endpointet kan udstede den for et kamera uden override.

**Konsekvens:** En kendt fælles bootstrap-hemmelighed giver ikke identitet pr.
Edge/kamera. Det er uforeneligt med IEC 62443 unik identitet/autentisering,
ISO 27001 adgangskontrol og CRA secure-by-default.

**Afhjælpning:** Fjern fallback. Opret en kryptografisk tilfældig, unik
hemmelighed ved kamera-/Edge-provisionering. Ikke-provisioneret Edge skal
blokeres og vise en tydelig status. Migrer eksisterende enheder kontrolleret
med Edge-sync, bekræftelse og tilbagekaldelse af gammel hemmelighed.

**Status:** Aaben. Der er ingen test, der forbyder fabriksfallback.

### P0-02 - OS-bundlebuilder har ukontrolleret input i Docker-kørsel

**Evidens:** `headend/main.py:7332-7387` og `headend/main.py:7719-7790`.
Admin-API'et accepterer `image`, `architecture`, `source_ref` og `category`.
Byggeren interpolerer dele af dem i `bash -lc` og monterer en outputmappe med
`chmod 0777`; katalogbyggeren opretter ogsaa `0666` filer.

**Konsekvens:** Supply-chain-/command-injection-risiko i buildmiljøet, som
efterfølgende signerer OS-artifacts. Admin-only er ikke en tilstrækkelig
barriere for vilkårlige images eller shell-strenge.

**Afhjælpning:** Brug parameteriserede Docker/argv-kald og en valideret
JSON-plan, aldrig sammensat shelltekst. Tillad kun understøttede
arkitekturer og image-digests fra allowlist. Valider device-ID, indeslut
plan/output i godkendt storage-rod, brug 0750/0640 og tilføj negative tests.

**Status:** Aaben. Nuværende testpakke tester artifact-kontrakt, ikke
builder-inputvalidering.

### P0-03 - integrationstest kan ramme aktiv Headend

**Evidens:** `tests/conftest.py:17-21` bruger `timelapse_test`, men
`BASE_URL` falder tilbage til `http://127.0.0.1:8000`, den aktive Headend.
Mange af 544 integrationstests opretter brugere, sender POST/PUT eller
undersøger reelle installationsstier.

**Konsekvens:** En test kan påvirke R&D-driftsdata eller udstyr, mens
database-fixtures tror, at de bruger testdata.

**Afhjælpning:** Opret separat test-Headend, port, PostgreSQL og storage.
Gør `TIMELAPSE_TEST_BASE_URL` obligatorisk for `-m integration`, og afvis
port 8000, operative database og operativ storage. Del markører i
`api_isolated`, `hardware`, `destructive` og `manual`.

**Status:** Aaben. De 544 tests er ikke kørt mod aktiv Headend.

### P1-01 - rollback er uatomisk

**Evidens:** `edge/agent.py:2010` anvender `bash -c` og kopierer
`prev/*` oven paa aktiv release. Globbet springer dotfiles over, returncode
kontrolleres ikke, og kopieringen er ikke atomisk.

**Afhjælpning:** Brug release-cursor/symlink eller `shutil` uden shell.
Verificer receipt og filmanifest før service-start. Test dotfiles, afbrudt
kopiering og forkert hash.

### P1-02 - backup er delvist forældet

**Evidens:** Ældre backupkode i `headend/main.py` refererer til gamle
LaunchAgent-navne, `.env`-stier og `/Volumes/data-fast`. Det nye verificerede
Restic-projektbackupflow bruger `/data-fast`, men erstatter ikke systembackup
for PostgreSQL/media.

**Afhjælpning:** Konsolider systembackup om den logiske storage-rodkonfig,
aktuelle LaunchDaemon-/environmentfiler og PostgreSQL dump/restoretest.

### P1-03 - artifact-signering falder tilbage til hashbinding

**Evidens:** `headend/main.py:6590-6635` returnerer `sha256:<digest>` og
`system-hash`, hvis GPG mangler eller fejler.

**Afhjælpning:** Gør kryptografisk GPG-signering obligatorisk for staging og
produktion. Hashbinding maa kun bruges som tydeligt markeret lab-evidens.

### P1-04 - frontend-afhængigheder har kendte advisories

**Evidens:** `npm audit --omit=dev` 2026-08-03: 4 high og 1 moderate.
Direkte afhængigheder er `axios` og `react-router-dom`; transitive er
`react-router`, `follow-redirects` og `form-data`.

**Afhjælpning:** Opgrader i kontrolleret testrelease med UI-regression og
låste, godkendte versioner. Undgaa blind `npm audit fix` i aktiv arbejdskopi.

### P1-05 - kodekvalitetsgates er ikke effektive nok

**Evidens:** Ruff: 2.103 fund. ESLint: 165 errors og 20 warnings.
Derudover advarer Vite om 1,55 MB hovedbundle og ineffektiv dynamic import.

**Afhjælpning:** Gate ny/aendret kode med ruff, ESLint, compile/build og
maalrettede tests. Flyt én afgrænset domæneflade ad gangen ud af `main.py`.

### P2-01 - aktiv dokumentation og deploymentstier er ikke synkroniseret

**Evidens:** `00_START_HER.md` beskriver stadig Vite LaunchDaemon og
`/Volumes/data-fast` som eneste rod, mens aktiv UI er statisk Nginx og den
logiske sti er `/data-fast`. Flere tests/installere har maskinspecifikke
absolute stier.

**Afhjælpning:** Opdater aktive driftsdokumenter, og parameterisér tests og
installere. Historiske dokumenter beholdes som historik.

## Positiv evidens

- Edge release-artifacts er immutabelt lagret, verificeret og scope-kontrolleret.
- Edge legacy-flow anvender ikke direkte apt, Git eller Internet.
- Image-manifester kræver pinnede checksums og afviser hash-only trust.
- Lokal teknikerflade er HTTPS/TOTP-baseret; interaktiv shell er off som standard.
- Thumbnail-læseendpoints genererer ikke billeder synkront.
