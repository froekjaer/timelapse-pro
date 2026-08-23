# GRC — punkter der afventer beslutning + fjernet/genskabt funktionalitet

**Dato:** 2026-08-19
**Forfatter:** Kimi (AI-assistent, review-session)
**Kildegrundlag:** `main` @ `c130fc9`, fuld gennemlæsning af `Dokumentation/HANDOVER_LOG.md` (1.979 linjer), `AGENTS.md`, `OP-001-Mission-Operational-Preamble.md`, `RISK_ASSESSMENT_v10.md`, `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`, `GO_LIVE_CHECKLIST_v10.md`, `STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md` samt verifikation direkte i koden hvor muligt.

> **Begrænsning:** GRC-registret (`grc_items`) ligger i produktions-PostgreSQL og er ikke tilgængeligt fra dette review-miljø. Listen bygger på handover-loggens eksplicitte GRC-referencer krydstjekket mod risikodokumenter og kode. Hvor et punkt kun findes i databasen, er det markeret eksplicit.

---

## Del 1 — Punkter der afventer Peters beslutning (prioriteret efter kritikalitet)

### 1. 🔴 Kritisk — `FIND-DEVICES-PLAINTEXT-SSH-KEY-COLUMN`

- **Sag:** `devices`/`Camera`-tabellen har historisk indeholdt Edge SSH-private-keys i plaintext. PR #73 (2026-08-17, ChatGPT) pensionerede alle aktive læse-/skrive-/injektions-veje (tenant-scoped `410 Gone` på download, ingen keypair-generering i provisioning/image-builder), men **legacy-kolonnen og dens data ligger stadig i databasen**.
- **Der skal besluttes:** Kontrolleret migration/retirement af escrow-data — men først efter at berørte enheder reelt har/genererer deres egen operationelle SSH-identitet, ellers mister vi adgangen til enhederne (jf. ChatGPTs advarsel i handover 2026-08-17 12:32).
- **Kilde:** HANDOVER_LOG.md linje 68, 84-91.

### 2. 🔴 Kritisk — `FIND/ACT-BREAKGLASS-EMERGENCY-ACCESS-*` (registreret 2026-08-19)

- **Sag:** Der findes **to modstridende break-glass-designs**:
  - Den **faktisk deployede** model: `emergency`-konto med shell `/opt/timelapse/edge/scripts/breakglass_shell_wrapper.sh`, udelukkende pubkey-baseret, password-login låst. Koden ligger kun i PR #9 (lukket 2026-08-06 **uden merge**) og i et gammelt artifact-snapshot. Verificeret 2026-08-19: `breakglass_shell_wrapper.sh` findes **ikke** i `edge/scripts/` på `main`.
  - Den **mergede** model: `headend/database.py:1117 BreakGlassAccount` + `headend/cmdb.py` — password-baseret, Fernet-krypteret, checkout med auto-rotation; docstringen erkender selv at edge-siden (kontooprettelse, rotation) er TODO.
- **Konsekvens:** Der er reelt **ingen dokumenteret, fungerende nødadgangsvej til edge-enheder i produktion i dag**.
- **Der skal besluttes:** Hvilket design er det rigtige (pubkey-only vs. password-checkout), og hvordan konvergensen sker. Det er en arkitekturbeslutning, ikke en kodefix.
- **Kilde:** HANDOVER_LOG.md linje 34, 106; kode verificeret.

### 3. 🟠 Major — R06: device fjernet midt i en rollout

- **Sag:** Hvis en enhed decommissiones mens en multi-device-rollout kører, kan rollout-status ikke nå en terminal tilstand korrekt. Tre løsningsmuligheder er dokumenteret: (a) permanent blokering af decommission under rollout, (b) nuværende adfærd (uændret), (c) "delvist bekræftet"-markering. En rådgivende SABSA/ISO27001 A.8.32-baseret anbefaling peger på **(c)**.
- **Der skal besluttes:** Valg mellem (a)/(b)/(c). Har afventet siden **2026-07-05** — det ældste ubesluttede punkt i registret.
- **Kilde:** RISK_ASSESSMENT_v10.md linje 901, 1052-1068.

### 4. 🟠 Major — `TL-DCA63234D813` stale credential / udfasning

- **Sag:** Enheden er gammel/inaktiv; dens stale credential-runbook er **forberedt men IKKE eksekveret** ("kræver din bekræftelse først"). Runbook-forfatteren fandt **ingen eksplicit beslutning om udfasning** noget sted i HANDOVER_LOG.
- **Der skal besluttes:** Udfas enheden formelt (og eksekver runbooken), eller behold den aktiv med roterede credentials.
- **Kilde:** STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md linje 4, 9.

### 5. 🟡 Moderat — `ACT-CMDB-APT-SOURCE-TRACKING` (docker-ce-kanalen)

- **Sag:** CMDB-update-tracking sporer kun versionsdrift på allerede-sporede pakker. Docker CE's eget apt-repo (`repo.huaweicloud.com/docker-ce`) er **slet ikke under sporing** — et containerd major-version-spring (1.7→2.2) blev observeret ugoverneret 2026-08-16.
- **Der skal besluttes:** Skal docker-ce-kanalen ind under CMDB-sporing (kræver ny dataindsamling: apt-kilde/oprindelse), eller skal den eksplicit dokumenteres som **bevidst usporet**?
- **Kilde:** HANDOVER_LOG.md linje 101-102, 124-125, 146.

### 6. 🟡 Moderat — Break-glass-opfølgninger fra SEC-016-lukningen

- **Sag a:** SEC-016's oprindelige anbefaling punkt 3 — *dokumentér SSH/konsol som sanktioneret break-glass for allerede udrullede enheder uden per-enhed-secret* — er **stadig ikke udført**.
- **Sag b:** Peter har spurgt om `orangepi`-brugerens password bør gøres til et formelt break-glass-credential. Blokeret af at `/etc/sudoers.d/timelapse-breakglass` (root-only) ikke kunne læses i review-sessionen — for ikke at designe noget der duplikerer/konflikter med eksisterende indhold.
- **Der skal besluttes:** Aflæs indholdet af sudoers-filen (eller giv lov til at designe uden), og godkend dokumentationen af SSH/konsol som break-glass.
- **Kilde:** HANDOVER_LOG.md linje 113-114; SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md.

### 7. 🟡 Moderat — System-hash fallback for artifact-signatur (F-005 fra kimi-2026-08-15.md)

- **Sag:** Headend accepterer fortsat `signed_by="system-hash"` (hash-binding uden GPG-nøgle) som signaturgrundlag for artifacts. Verificeret live 2026-08-19: `headend/main.py:6706`, `6728`, `6992-6997`.
- **Der skal besluttes:** Formaliser en PO-risikoaccept af fallback'en, eller fjern den og kræv GPG-signering overalt.
- **Kilde:** kimi-2026-08-15.md (F-005); kode verificeret.

### 8. 🟢 Lav — Drifts- og prioriteringsvalg uden sikkerhedskarakter

- **(a) CMDB baseline-reconciliation scheduling:** findes kun som on-demand admin-endpoint (`POST /api/admin/devices/{id}/cmdb/reconcile-baseline`). Beslut om den skal wires ind i en periodisk baggrundsjob. (HANDOVER_LOG.md linje 102)
- **(b) NPU-modelvej:** installér eksisterende `.nb`-model på TL-C87FF9587CA0, eller kør den fulde trænings-pipeline (`mine_qa_training_candidates.py` → `train_edge_qa_model.py` → ACUITY) først? (HANDOVER_LOG.md linje 172-174)
- **(c) Open-Meteo/geokodning:** stillingtagen til geokodning af Travbyen/"Mod baggård" (ingen GPS i DB for disse) før meteorologiske data kobles på QA-analysen. (HANDOVER_LOG.md linje 172)
- **(d) Google Drive Photos Library:** skal Photos Library overhovedet sikkerhedskopieres (26,7 GB footprint, 25,6 GB swapped)? Herefter: kontrolleret Drive-genstart + overvej automatisk memory-pressure guard før lokal vision-inference. (HANDOVER_LOG.md linje 470-478)

### 9. ❓ Uverificerbar — `FIND-MEM-001`

- Nævnt i seneste handover (2026-08-19) som tredje punkt der afventer Peters beslutning, men **findes ingen steder i repoet** (søgt i alle .md/.py/.sql/.json). Indhold og kritikalitet kan kun verificeres med `psql` mod `grc_items`. Muligvis relateret til memory-sagen 2026-07-20 (punkt 8d ovenfor), men det er en **antagelse, ikke verificeret**.
- **Anbefaling:** slå posten op i GRC-registret og tilføj en dokumentationsreference, så den ikke kun lever i databasen.
- **Kilde:** HANDOVER_LOG.md linje 36.

### Afventer udførelse/bekræftelse — IKKE beslutningspunkter

Til orientering; disse kræver handling eller verifikation, ikke valg:

- **GO_LIVE-blokkere:** E-02 restore-test (🔴), C-03 manuel bekræftelse af ændret super_admin-password på rd/staging/prod (🔴), A-01..A-13 netværks-/port-audits på de konkrete maskiner (🔴). C-10 (HMAC-enforcement/stale credentials) åben.
- **GPS i billedgeneratoren:** kør et frisk testbillede fra aktuel `target.yaml` og verificér at gpsd reelt installeres; harmonisér `DEVICES`-værdi mellem USBAUTO-mønsteret og `setup-gps-time.sh`s `/dev/ttyS3`; undersøg offline OS-bundle som distributionsvej for enheder uden internet.
- **Vitest-testinfrastruktur:** ligger stadig ucommittet i `/tmp/timelapse-test-continuity-plan` — har nu to gange været årsag til at et kendt fix ikke nåede main (jf. OP-001's kontinuitetsadvarsel). Bør committes/merges.
- **`ACT-EDGE-TOOLS-NPU-RUNNER-MISSING-FROM-RELEASE`:** afventer artefakt-build + governed udrulning + bekræftelse på enheden, derefter lukkes den.

---

## Del 2 — Funktionalitet fjernet undervejs: genskabt eller ej?

Spørgsmålet var om funktionalitet er blevet fjernet ved en fejl (fx under løsning af et sikkerhedsproblem) uden at blive genskabt. Gennemgang af handover-loggens selv-erkendte hændelser + sikkerheds-/oprydningscommits siden 2026-07:

### ❌ Reelt tabt — ét hul

| Funktionalitet | Hvad skete der |
|---|---|
| **`emergency` break-glass-konto på edge** | Deployet på mindst én enhed (TL-043EB9E72EFD), men koden (`breakglass_shell_wrapper.sh` m.m.) blev **aldrig merget til main** — den levede kun i PR #9, der blev lukket uden merge 2026-08-06. Parallelt blev en **anden, uforenelig** password-baseret break-glass-model merget (`BreakGlassAccount`), hvis edge-side er TODO. Nettoresultat: ingen fungerende, dokumenteret nødadgang i produktion. Nu registreret i GRC (Del 1, punkt 2). |

### ⚠️ Genskabt, men kun beskyttet af dokumentation

| Funktionalitet | Status |
|---|---|
| **Travbyen-kameraer (`TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1/2`)** | Fjernet **to gange** af en ukendt, manuel oprydningsproces (ingen kode i repoet implementerer den). Genskabt begge gange (`ACT-VIRTUAL-DEVICE-CLEANUP-001/002`). Ingen teknisk spærre mod en tredje regression — beskyttelsen er GRC-noter + handover-advarsel. Overvej en "beskyttet mod oprydning"-markering i databasen eller en `captures`-baseret sikkerhedsventil. |
| **gpsd på Hyldager-enheden (TL-043EB9E72EFD)** | Aldrig installeret fra et ældre/afvigende image (teknisk set aldrig til stede, ikke "fjernet"). Rettet manuelt 2026-08-16, men frisk-image-verifikation og offline-bundle-distribution er ikke gjort — nye enheder kan have samme hul. |

### ✅ Genskabt korrekt (lukket)

| Funktionalitet | Historik |
|---|---|
| **Live TOTP-kode på kamerasiden** | Den rå hemmelighed vistes som klartekst og forsvandt **utilsigtet** i oprydningscommit `a51ee8b4` (2026-08-03) — ingen sikkerhedsbegrundelse for netop den linje. Genskabt korrekt i PR #77 (2026-08-19, merget): rigtig beregnede roterende 6-cifret kode + ny "Lokal adgang"-adminoversigt med RBAC. |
| **Browser-SSH-terminal** | Oprindeligt fra PR #9, forsvandt da PR'en ikke blev merget. Genskabt og verificeret på `main`: `SshTunnelPage.tsx` + `SshTerminalModal.tsx` (xterm) med trust-gating (terminalen deaktiveres hvis host-identity ikke er trusted/verified). |
| **Fabriks-TOTP `JBSWY3DPEHPK3PXP` (SEC-016)** | **Bevidst fjernet** som kendt default-credential (CRA/IEC 62443-brud). Erstatningen for det legitime bootstrap-behov blev først glemt (deadlock: enhed uden secret kunne aldrig logge ind lokalt), men er nu fuldt lukket: fail-closed + per-enhed-secret obligatorisk ved image-build + trust-forankret auto-sync (PR #71) + regressionstests der forbyder reintroduktion. Kun break-glass-dokumentationen mangler (Del 1, punkt 6). |

### ✅ Bevidst deaktiveret — ikke tab

| Funktionalitet | Begrundelse |
|---|---|
| **Legacy git-update** | Opt-in bag `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1` + lab/dev-miljø; edge afviser aktivt og beder headend rydde flaget. Reversibelt, dokumenteret (VPEN-005, SYSTEM_HEALTH_REGISTER). |
| **Vite dev-server LaunchDaemon** | Deaktiveret 2026-08-03; nginx serverer den byggede UI direkte fra `dist`. Dokumenteret driftsoprydning. |
| **Ollama brugeragent** | Deaktiveret; kun system-daemonen `com.froekjaer.ollama` kører (port 11434-konflikt løst). |
| **Exposure-ramping 5000-billeders grænse** | Fjernet efter Peters eksplicitte ønske (commit `c4d2ea8`, 2026-08-16), samtidig med tilføjelse af UI-checkbox. |
| **Midlertidig legacy OS-governance patch-workflow** | Fjernet (commit `33ecac2`) — var eksplicit midlertidig. |

### Systemisk observation (kontinuitet)

Mønsteret **"rettelsen findes et sted, men når aldrig main"** er nu dokumenteret to gange på én uge: CameraPage drift-analyse-fixet sad ucommittet i en worktree (fejlen forblev live i produktion; rettet som PR #78), og vitest-infrastrukturen der ville have fanget fejlen automatisk ligger stadig ucommittet i `/tmp/timelapse-test-continuity-plan`. Samme mønster gjaldt SEC-016-dokumentationen (uddelegeret 2026-07-17, glemt, genfundet af tre separate sessioner). Det er præcis den kontinuitetsbrist OP-001 §10 beskriver empirisk — og begrundelsen for at test-infrastruktur-commit'et bør prioriteres højt, selv om det ikke lyder som et sikkerhedspunkt.

---

## Henvisninger

- `Dokumentation/HANDOVER_LOG.md` — primær kilde (især entries 2026-08-16 til 2026-08-19)
- `Dokumentation/RISK_ASSESSMENT_v10.md` (R06), `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md` (R22-R27 status: R22/R23/R24/R25/R27 verificeret lukket i koden)
- `Dokumentation/SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md`
- `Dokumentation/STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md`
- `Dokumentation/GO_LIVE_CHECKLIST_v10.md`
- `Dokumentation/kimi-2026-08-15.md` (F-005), `Dokumentation/kimi-update-flow-2026-08-15.md`
- `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md`
