# Semantisk analyse — `agent/core-design-principles` mod aktuel main

- **Model/session:** Claude (Sonnet 5, denne session)
- **Tidspunkt:** 2026-09-13
- **Baseline:** `origin/main` = `d04798e4ab4716832be576b3134e46b55a994ecf` (verificeret via `gh api repos/.../commits/main` + `git ls-remote`)
- **Branch analyseret:** `agent/core-design-principles`, head `320281b698c8a0114e2389f3b3f778f2c806573d` (2026-07-31, forfatter `github@froekjaer.dk`)
- **Metode:** Læst hele `Dokumentation/Arkitektur/TimeLapse_Core_Design_Principles_v1.md` (585 linjer) i sin helhed. For hver central påstand: verificeret mod faktisk kode/adfærd på main (grep, `git log -S`, `git blame`), ikke kun filnavne. Krydstjekket mod ADR-001 (Accepted), eksisterende BLE-teknikerarbejde, og retention-relateret kode.
- **Mandat:** Peter, 2026-09-13 — semantisk analyse, **ingen integration eller cleanup**.

## Sammenfatning

Dokumentet er et 585-linjers, gennemarbejdet forslag til tværgående designprincipper (Del I) og en detaljeret Bluetooth-baseret lokal servicearkitektur (Del II), skrevet 2026-07-31. Det er selv eksplicit mærket **Proposed**, ikke bindende. Analysen nedenfor er ikke en anbefaling om at integrere eller forkaste — det er et klassificeret faktagrundlag til Peters beslutning, som opgaven kræver.

**Vigtigste enkeltfund:** Del I's centrale, mest konsekvensfulde princip (Princip 2/3 — "projektdata slettes aldrig automatisk") er **allerede implementeret på main**, og har været det **siden før dokumentet blev skrevet** (commit `15038101`, 2026-07-15 — to uger før dokumentets dato). Dokumentets egen "åbne afklaringer"-tabel beskriver dette forkert som en åben konflikt mod "eksisterende automatisk cleanup" — den beskrivelse er nu selv forældet.

## Klassifikation

### A) Allerede dækket på main

- **Princip 2 (Projektdata slettes aldrig automatisk) og Princip 3 (Retain until explicit disposition):** `headend/main.py::_run_retention_cleanup()` er allerede en no-op der eksplicit logger *"Capture deletion is prohibited"* og altid returnerer `deleted_count: 0` — implementeret **2026-07-15** (`fix(storage): enforce immutable capture retention on headend`), to uger *før* dette dokument. Sletning sker kun via `headend/services/capture_deletion_service.py::delete_capture()`, som kræver eksplicit `deletion_reason` (whitelist: defective/unwanted/gdpr_request/other), `performed_by`, og skriver en uafhængig `CaptureDeletionLog`-audit-post. Dette er funktionelt identisk med principperne, allerede håndhævet i kode — ikke kun i hensigt.
- **Princip 16 (Platform/payload adskilt):** Dokumentet selv erklærer sig konsistent med ADR-001 (Accepted). Ingen konflikt, ingen ny beslutning nødvendig.
- **Princip 8 (integritet/checksums), delvist:** Signerede update-artifacts, SHA-256-baseret release-kvittering (`release_receipt_matches_artifact`) og backup-integritetsverifikation (`backup_integrity.validate_plain_pg_dump`) findes allerede i separate, modne undersystemer — spredt, men reelt implementeret, ikke kun princip.
- **Princip 12 (least privilege / explicit authority), delvist:** RBAC-roller (admin/operator/viewer m.fl.), `require_role()`-guards og tidsbegrænsede provisioning-tokens findes allerede.

### B) Stadig relevant og unikt (ikke bygget, intet der modsiger det)

- **Princip 4-6 (eksplicit projekt-lifecycle med tilstande `planned→...→deleted`, styret "Afslut projekt"-flow):** Verificeret at der **ikke** findes en `Project`-model i `headend/database.py` — den eksisterende model er stadig Customer → Site → Camera/Device, præcis som dokumentets egen "as-is"-tabel siger. Dette er reelt, ikke-bygget arbejde.
- **Princip 9-11, 21-25 (evidens/fortolkning-adskillelse, fail-safe, sikkerhed integreret, standarder risikobaseret, observability, alarm-lifecycle):** Generiske, velargumenterede principper uden et enkelt canonisk referencepunkt i repoet i dag — spredt praksis, men ikke samlet som håndhævet politik nogen steder.
- **De 6 kandidat-ADR'er i §49** (Local Service Gateway, Physical Presence Requirement, Bluetooth as Bootstrap Transport, Capability-based Service Authorization, No General-purpose Shell, Retain until Explicit Disposition): Ingen af dem er blevet til en faktisk ADR. Kun `ADR-001` og `ADR-003` findes i `Dokumentation/ADR/`.

### C) Superseded/forældet

- **Dokumentets egne pointer-ændringer i `00_START_HER.md`, `ADR/README.md`:** Disse blev skrevet mod en main fra 2026-07-31 og beskriver nu forkert nutid — fx "Headend (R&D)" (main siger nu "Headend (prod)"), forældede storage-stier, en `ADR/README.md` uden ADR-003. En direkte re-applicering af branchens patch ville **reintroducere forældede driftsfakta**. Hvis dokumentet skal linkes fra disse filer, skal det gøres som en frisk tilføjelse mod nutidig main, ikke en genanvendt patch.
- Dokumentets egen "åbne afklaring" om retention (§1.1, række 1) er som nævnt ovenfor selv forældet — beskriver en konflikt der ikke længere findes i kode.

### D) Konflikt med senere accepteret/implementeret arbejde — **kræver Peters beslutning**

- **Del II (Secure Local Service Architecture, §28-50) vs. main's faktiske BLE-teknikerløsning:** Main har siden (PR #195, `634b3596`, samt tilhørende BLE-arbejde) bygget en **fungerende, men markant simplere** lokal-service-løsning: TOTP som eneste faktor (ikke fysisk knap/NFC/pairing-vindue), ingen formel rollemodel (Observer/Technician/Senior Technician/Security Administrator/Platform Administrator findes ikke), ingen "Local Service Gateway"-komponent, intet capability-manifest-JSON, ingen enterprise service-token-udstedelse (Fase 4). Til gengæld deler den faktiske implementering flere af dokumentets *underliggende* principper i ånd: fail-closed ved ugyldigt input, ingen shell/vilkårlig kommandokørsel via BLE-adapteren, alt går gennem den eksisterende capability-/audit-model (`ServicePlatform.call()`), pairing behandles ikke som autorisation.
  **Dette er ikke en ren "allerede dækket"-situation** — det er en reel arkitektonisk divergens: en simplere løsning er allerede bygget og i brug, mens dokumentet beskriver en langt mere elaboreret målarkitektur. Peter skal beslutte: (a) lad den simple løsning stå og arkivér Del II's mere elaborerede model som fremtidig, ikke-prioriteret retning; (b) brug dokumentet som roadmap til at udvide den eksisterende løsning gradvist; eller (c) formelt supersede Del II med en ny, kort ADR der beskriver den valgte, simplere retning som den faktiske beslutning.
- **Sideobservation, ikke i Del II, men direkte relevant:** Under denne batch fandt jeg en ubeslægtet, men beslægtet sag — en ældre, aldrig merget branch (`codex/edge-terminal-renderer`) forbedrer et **allerede eksisterende** generelt shell-endpoint (`/mgmt/cli/bash/*` i `edge/scripts/totp-service.py`, WebSocket-baseret på main i dag). Dokumentets egen Princip ("No General-purpose Shell", §49) og §43 ("Et POST /run-command-endpoint findes ikke i almindelig service-mode") **er i direkte modstrid med denne allerede-eksisterende, main-side funktionalitet** — main har allerede et generelt bash-shell-endpoint tilgængeligt via den lokale TOTP-gate. Se separat R04-batch-rapport for detaljer; nævnes her fordi det er direkte relevant for om Princip/ADR-kandidaten "No General-purpose Shell" overhovedet er en gyldig fremadrettet retning, eller om den kræver en bevidst undtagelse/retrofit-beslutning for det der allerede kører.

### E) Uklart / kræver Peters beslutning (ud over C/D)

- Hvorvidt de 6 kandidat-ADR'er skal tages op til formel beslutning nu, samlet eller enkeltvis, eller forblive et referencedokument.
- Om selve dokumentet (Proposed, 585 linjer, aldrig merget) skal: (a) merges som *Proposed*-referencemateriale (uden at hævde nogen del er Accepted), (b) forkortes til kun de dele der er verificeret stadig relevante (B), eller (c) arkiveres med en kort begrundelse og henvisning til hvor dets reelt værdifulde dele (projekt-lifecycle-modellen) i stedet fanges (fx som et fremtidigt kravregister-punkt).

## Stop-gate — eskaleres til Peter

Dette er **ikke** en rutine-klassifikation. Fundene under D (arkitektonisk divergens i lokal service-arkitektur, plus det tilstødende shell-endpoint-fund) er præcis den type "unik arkitektur med mulig strategisk betydning" og "konflikt med implementeret arbejde", som mandatets stop-gates beder om at eskalere frem for selv at disponere. Ingen integration eller arkivering er udført.
