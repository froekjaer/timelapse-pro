# TimeLapse Pro — SABSA/ISO 27001/IEC 62443/CRA/NIS2/GDPR Risikovurdering (v10, konsolideret) + Virtuel Penetrationstest

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Forfatter:** Peter Frøkjær / TimeLapse Pro
**Afløser/konsoliderer:** `RISK_ASSESSMENT_v7_2026-06-23.md` (backbone) + `Claude_`/`Codex_RISK_ASSESSMENT_v7` + `RISK_ASSESSMENT_v6.md` (+ `TimeLapse_SABSA_Risk_Assessment.docx` v2–v6), `QA_Pentest_Risk_Assessment_2026-06-21`, `QA_SABSA_Reassessment_2026-06-22`, `VIRTUAL_PENTEST_STATUS_2026-05-28`, `SABSA_RISK_ANALYSIS_UPDATE_2026-05-28`. Tidligere versioner arkiveret i `Gamle versioner/`.
**Status:** Gældende — pre-production LAB/R&D

> v7 inkorporerer allerede v6-risikoregisteret + pentest-historikken (se §2). §13–§15 nedenfor bevarer v6's PKI/CA-design + Key Management UI-spec og Codex' standardmapping/go-no-go, så intet fra tidligere versioner tabes.

---

## 0. Kildegrundlag og begrænsninger

Denne version er baseret på de lokale dokumenter i `Dokumentation/`, kode-/konfigurationsgennemgang og non-destruktive lokale driftstjek 2026-06-23.

Dokumentkorpus:

- 79 lokale filer fundet i `Dokumentation/`.
- 54.470 tekstlinjer udtrukket til analyse-korpus.
- Markdown, konfigurationsfiler og de fleste `.docx`-filer er læst.
- Google Drive-pointere (`.gdoc`, `.gslides`) er identificeret, men ikke hentet via Drive i denne lokale kørsel.
- 2 ældre `.docx` timeoutede ved lokal tekstkonvertering.
- PDF-hardwaremanualer indgår som kendte kilder, men blev ikke tekstudtrukket lokalt.

Nyeste/gældende assessment-, update-, config-, Nikon-, go-live- og portdokumenter er vægtet højest. Ældre dokumenter er primært brugt til historik og konfliktidentifikation.

---

## 1. Scope og formål

Denne vurdering dækker hele TimeLapse Pro-systemet:

- **Edge-lag:** OrangePi 4 Pro (TL-C87FF9587CA0 aktiv, TL-DCA63234D813 stale) med Nikon Z30-kamera
- **Headend-lag:** Mac Mini (FastAPI/uvicorn, PostgreSQL 17, nginx, Ollama, node-agent)
- **Transport-lag:** SFTP (port 22222), HTTPS/JWT (API), SSH-tunnel (autossh)
- **Præsentations-lag:** React/Vite UI
- **Public URL:** https://timelapse.froekjaer.dk

Formålet er at konsolidere alle tidligere assessments, dokumentere lukket/åbent status på hvert fund, og producere et opdateret risikobillede.

---

## 2. Status på tidligere assessments

### Fra RISK_ASSESSMENT_v6 (maj 2026)

| Risk | Åbent punkt fra v6 | Status juni 2026 |
|---|---|---|
| R01 — SFTP chroot | SFTP chroot implementeret | ✅ Løst |
| R02 — UI RBAC | RBAC implementeret; MFA nu policy-drevet + enforced (2026-07-02) | ✅ Løst — MFA enforced for admin/super_admin |
| R03 — Hardware-historik | Camera/Pi-kobling implementeret | ✅ Løst |
| R04 — Remote adgang | Reverse SSH tunnel implementeret | ✅ Løst |
| R05 — Kompromitteret edge | CA/mTLS mangler, disk-kryptering mangler | 🔴 Åben |
| R06 — Opdateringsfejl | Artifact-model og staged rollout implementeret | ✅ Løst (lab) |
| R07 — Nøgle-kompromittering | Key Management UI implementeret, HMAC på aktive noder | ✅ Delvist |
| R08 — Man-in-the-middle | HTTPS, JWT — CA-pinning/mTLS mangler | 🟡 Delvist |
| R09 — Backup | Off-site backup mangler, restore-test mangler | 🔴 Åben |
| R10 — SSH tunnel misbrug | Deny-flag og audit-log implementeret | ✅ Løst |
| PKI/intern CA | Planlagt, ikke implementeret | 🔴 Åben |
| MFA | Åbent fra v6 | ✅ Løst 2026-07-02 — policy-drevet, enforced for admin/super_admin (TOTP) |

### Fra VIRTUAL_PENTEST_STATUS_2026-05-28

| Fund | Status |
|---|---|
| HLTH-001 Utrackede exports | Delvist — gitignore tilføjet, rotation mangler |
| HLTH-002 secrets/ utracked | Delvist — gitignore OK, rotation/validering mangler |
| HLTH-003 Edge direkte GitHub | Opt-in via legacy flag; legacy paths skal fjernes |
| HLTH-004 GPG tag-check | Delvist — GPG-signering nu i peter's keyring og virker |
| HLTH-005/006 UI approval | Delvist — endpoint-felter OK, kamera/site-scope mangler |
| HLTH-007 Update scope | Delvist — API OK, UI har kun global/device |
| HLTH-008 Per-target deployment | Mangler stadig |
| HLTH-009 Policy enforcement | Åben — Edge maintenance/reboot enforcement mangler |
| HLTH-010 Default JWT secret | ✅ Løst — JWT_SECRET sat stabilt i LaunchAgent |
| HLTH-011 Duplicate filter key | ✅ Løst |
| HLTH-012 Frontend lint | Åben — 219+ fejl, ikke i CI gate |
| HLTH-013/014 Python test | Delvist — pytest + 18 passed; mangler edge/headend contract tests |
| HLTH-015 README er Vite-template | Åben |
| VPEN-001 Key lifecycle | Delvist — aktiv Edge + headend agent HMAC virker; stale credentials |
| VPEN-002 Signed change workflow | Delvist — change tickets genereres, men ikke signerede |
| VPEN-003 Backup/failover | Åben — restore-test mangler |
| VPEN-004 CMDB coverage | Delvist — node-agent stoppet 2026-06-22 |
| VPEN-005 Legacy update paths | Delvist — opt-in; bør fjernes fra production |
| VPEN-006 SAST backlog (73 signals) | **Triage afsluttet 2026-07-05 (periodisk tjek #19) — se VPEN-2026-008 og VPEN-2026-009:** signal-optællingen var oprindeligt upålidelig (scanner-fejl rettet, 2 selvreferencer fjernet). Alle 4 kategorier (80/80 aktuelle signaler: `hardcoded_secret_terms`, `shell_execution`, `legacy_update_paths`, `dangerous_file_ops`) er nu gennemgået enkeltvis. Ingen bekræftede reelle sårbarheder — ét opmærksomhedspunkt til Peter (lokalt dev-værktøj `claude_proxy.py`s `shell=True`, afhænger af filrettigheder på `.claude_proxy/`) |
| VPEN-007 AI resource governance | Åben |

### Fra QA_Pentest_Risk_Assessment_2026-06-21

| Fund | Status |
|---|---|
| P1 CMDB anonym | ✅ Løst — /api/cmdb/ returnerer 401 |
| P1 OS bundle cross-release | ✅ Løst — suite udledes fra os_name |
| P1 Edge stale vist online | ✅ Delvist — CMDB list/detail rettet; andre UI-flader ikke |
| P1 Nikon Z30 config drift | 🔴 Åben — focus, ISO, WB drift stadig |
| P2 Open WebUI nede | 🟡 Åben — skal besluttes prod vs. lab |
| P2 Frontend lint gæld | 🔴 Åben |
| GDPR-evidens mangler | 🔴 Åben |

### Fra QA_SABSA_Reassessment_2026-06-22

| Fund | Status |
|---|---|
| P1 Storage path /Volumes/data | ✅ Løst — rettet til /Volumes/data-fast i DB |
| P1 Node-agent stoppet | 🔴 Åben — ikke loaded i launchctl |
| P1 node-agent root-ejet | 🔴 Åben — /opt/timelapse-node-agent er root-ejet |
| P1 Update #33 peger på stale Edge | 🟡 Info — skal koordineres |
| P2 Storage root spredt i kode | 🟡 Delvist — DB rettet, men hardcoded paths kan stadig eksistere |
| P2 Secrets i LaunchAgent | 🟡 Acceptabelt for nu, ikke moden model |

---

## 3. SABSA Business Attribute Profile (opdateret)

| # | Attribut | Aktuel vurdering | Score |
|---|---|---|---|
| 1 | Availability | Headend kører stabilt; capture og upload virker; node-agent nede | 🟡 Gul |
| 2 | Integrity | Signed artifact-flow for app virker; OS E2E på aktiv Edge mangler | 🟡 Gul |
| 3 | Confidentiality | RBAC/auth virker; CMDB lukket; secrets i LaunchAgent | 🟡 Gul |
| 4 | Accountability | Change tickets genereres; audit trail delvist; node-agent nede | 🟡 Gul |
| 5 | Authenticity | HMAC på aktive noder; stale credentials; CA/mTLS mangler | 🟡 Gul |
| 6 | Manageability | Remote SSH tunnel; config-resolution UI; Global Config hierarki | 🟢 Grøn |
| 7 | Continuity | Store-and-forward; circular buffer; rollback ved update-fejl | 🟡 Gul |
| 8 | Extensibility | Multi-tenant hierarki; driver abstraction; HAL | 🟢 Grøn |
| 9 | Privacy | SFTP chroot; RBAC customer_id scope; GDPR-evidens mangler | 🟡 Gul |
| 10 | Auditability | GRC cockpit; rapporter pr. standard; update audit; DPIA mangler | 🟡 Gul |
| 11 | Resilience | Rollback virker; backup/restore-test mangler | 🟡 Gul |

**Samlet SABSA-posture: LAB-klar, ikke production-klar.**

---

## 4. Opdateret risikoregister

### R01 — Uautoriseret adgang til billeddata via SFTP
- **Status:** ✅ Kontrolleret
- **Implementerede kontroller:** SFTP chroot (internal-sftp), per-site brugere, port 22222 med sftp_*-match, afvisning på port 22/2222
- **Residualrisiko:** 🟢 4

### R02 — Uautoriseret adgang til admin-UI
- **Status:** ✅ Kontrolleret (opdateret 2026-07-02; MFA-dækning korrigeret 2026-07-03)
- **Implementerede kontroller:** RBAC med 4 roller, JWT 12t, bcrypt, require_role() på endpoints. **MFA er nu policy-drevet og enforced** (Codex): default påkrævet for `super_admin` + `admin` via `mfa_required_by_role`; global override + `mfa_exempt_usernames`; requests uden MFA-verificeret session → `403`. Se `RBAC_Remote_Operational_v10.md` §3.
- **KORREKTION 2026-07-03 (Claude, frisk kodegennemgang, bekræftet af Codex):** MFA-tjekket var kun implementeret i `main.py::require_role()` — CMDB-routerens og ITIM-routerens egne, uafhængige RBAC-broer (`cmdb.py::_require_cmdb_role`, `itim.py::_require_role`) tjekkede rolle, men ALDRIG MFA. Det betød i praksis, at hele CMDB (inkl. break-glass password-checkout) og ITIM kunne tilgås af en admin/super_admin-session, der aldrig havde gennemført MFA — uanset denne rækkes "✅"-status. **Rettet i kode** på branch `claude/security-hardening-2026-07-03` (VERIFICERET I KODE + lokal testklient: viewer uden MFA → 200, admin uden MFA-verificeret session → 403 "MFA kræves", admin med MFA-verificeret session → 200, på både `/api/cmdb/*` og `/api/itim/*`). **VERIFICERET LIVE:** afventer Codex/Peters commit+genstart af headend. Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.2/§2.3 for fuld analyse.
- **Åbent:** WebAuthn er separat flag (default off) — TOTP dækker MFA-kravet indtil videre. Claude/Codex-testkonti er fritaget under udvikling. Break-glass rate-limit/IP-allowlist er fortsat opt-in (env-var), men MFA-kravet dækker nu også dette endpoint.
- **Residualrisiko:** 🟢 4 i kode pr. 2026-07-03 (var reelt 🟡 6-8 for CMDB/ITIM-flader indtil denne rettelse — nedgraderes til 🟢 4 for alle flader først når live-verificeret efter genstart)

### R03 — Tab af billedhistorik ved hardwarefejl
- **Status:** ✅ Kontrolleret (korrigeret 2026-07-03 — se note)
- **Implementerede kontroller:** Camera/Pi-kobling, DeviceAssignment-historik, captures knyttet til camera_id
- **KORREKTION 2026-07-03 (Claude, frisk kodegennemgang):** Linjen "captures knyttet til
  camera_id" var reelt IKKE sand før denne dato — `Capture` havde kun `device_id` (fysisk
  Edge), ikke `camera_id` (logisk kamera-lokation). Det betød at det ønskede
  Global/kunde/site/kamera-lokation → Edge-hierarki manglede sit sidste led: en defekt Edge
  kunne ikke udskiftes eller genbruges et andet sted uden reelt at miste den logiske
  sammenhæng mellem billedhistorik og lokation (kun `DeviceAssignment`-historikken fandtes,
  men blev ikke brugt til at berige `Capture`-rækker). **Nu rettet i kode og verificeret**
  (schema-migration v12 + `_resolve_capture_camera_customer()` + additivt
  `camera_id`-filter på `/api/admin/captures` + `headend/tools/backfill_capture_camera_customer.py`
  til historiske rækker) — se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.4/§2.5 og
  `HANDOVER_LOG.md` 2026-07-03 12:20. Backfill af historiske produktionsdata afventer Peter/Codex'
  gennemgang af dry-run-output.
- **Residualrisiko:** 🟢 3 — backfill af produktionsdata kørt komplet 2026-07-03 (alle 27.662 captures har `camera_id`/`customer_id`/`site_id` udfyldt hvor muligt, se R16)

### R04 — Ingen remote adgang ved netværksfejl
- **Status:** ✅ Kontrolleret
- **Implementerede kontroller:** Reverse SSH tunnel (autossh), audit-log, deny-flag pr. customer/site
- **Residualrisiko:** 🟢 3

### R05 — Kompromitteret edge-enhed (fysisk adgang)
- **Status:** 🔴 Åben
- **Implementerede kontroller:** API JWT, HMAC, SFTP key-auth
- **Åbent:** Disk-kryptering (LUKS/overlayFS), intern CA + client certs, boot-level hardening
- **Sandsynlighed:** 2, **Konsekvens:** 4, **Score:** 🟠 8

### R06 — Ondsindet eller fejlet opdatering
- **Status:** ✅ Kontrolleret (lab)
- **Implementerede kontroller:** Offline artifact-model, change tickets, staged rollout, rollback,
  `update_targets`-tabel med per-device status eksponeret via `/api/updates/{id}/flow-status` og
  vist i UI (siden juni 2026)
- **KORREKTION 2026-07-05 (Claude, periodisk tjek):** "Per-target deployment status mangler" var
  delvist forældet — data/API/UI fandtes allerede. Den reelle, resterende del af risikoen var at
  `/api/updates/report` satte den globale `PendingUpdate.status` fra ét enkelt device-report,
  så én enhed kunne gøre en hel multi-target rollout (global/customer/site) "deployed"/
  "rolled_back" mens andre devices stadig var i gang. **Rettet i kode, committet/pushet af Codex
  (`61802951`) og deployet** (headend genstartet, `/api/health` 200 OK, 2026-07-05 nat): global
  status for multi-target scopes venter nu på at alle kendte targets har rapporteret
  terminal-status; `deployed_count`/`failed_count` beregnes nu korrekt (var også en bug — se
  `Update_Flow_v10.md` linje 549). Se `SYSTEM_HEALTH_REGISTER.md` HLTH-008 for fuld analyse.
  Verificeret isoleret (py_compile + Python-simulering) FØR deploy; live multi-device-rollout
  IKKE testet endnu.
- **REGRESSION i den deployede fix (fundet 2026-07-05, Claude, periodisk tjek, samme dag):** Byggede
  en rigtig kontrakttest (`headend/tests/test_report_update_rollup.py`) der kører den faktiske
  `report_update()`-kode mod en midlertidig SQLite-DB (ikke en simulering). Testen viste at den
  deployede `61802951`-fix manglede en `db.flush()` før rollup-forespørgslen (`SessionLocal` har
  `autoflush=False`, jf. `database.py` linje 73) — konsekvensen er at global status for
  multi-target rollouts ALDRIG flipper til `deployed`/`rolled_back`, heller ikke når alle devices
  reelt er terminale, fordi det SIDSTE device's egen rapport er usynlig for dets egen
  rollup-forespørgsel. Det er reelt værre end den oprindelige risiko (for-tidlig flip er erstattet
  af en flip der aldrig sker — rollout'en hænger fast på "approved"). 1-linjes rettelse
  (`db.flush()`) er lavet i `headend/main.py` og verificeret: 2 af 4 tests fejlede uden rettelsen,
  4/4 passerer med den.
- **OPDATERING 2026-07-05 (Claude, periodisk tjek, docs-sync):** Flush-rettelsen er nu
  committet/pushet af Codex (`1e3c3321`, samme commit som H-05-testene) og deployet — headend
  genstartet (`launchctl kickstart`) og `/api/health` bekræftet 200 OK samme nat (se HANDOVER_LOG,
  Codex-entry "HLTH-008 regression + H-05 tests + H-06 README udført"). Codex kørte desuden
  `pytest tests/test_report_update_rollup.py tests/test_update_lifecycle.py -v` i eget venv →
  13/13 passed. Verificeret her (2026-07-05, Claude) at `db.flush()` faktisk er i den committede
  `headend/main.py` på nuværende `HEAD` (`git show 1e3c3321 -- headend/main.py`).
- **Åbent:** Live multi-device-rollout-test (2+ test-enheder, `scope=site`, bekræfte at update
  reelt flipper til "Deployet"/"Rullet tilbage" og ikke kun forbliver "Godkendt") er stadig IKKE
  kørt — bevidst ikke gjort fra periodisk heartbeat, da det ændrer update-state for rigtige
  enheder (kræver Peter/Codex, kontrolleret). OS E2E på aktiv Edge også stadig ikke testet.
- **NYT, separat gap — device-decommission midt i rollout (fundet 2026-07-05, Claude, periodisk
  tjek #9; formaliseret her 2026-07-05, periodisk tjek):** `_resolve_update_targets()` opgør
  `total` ud fra devices der p.t. findes i CMDB. Hvis et device slettes fra CMDB (fx udskiftet/
  decommissioned hardware, jf. R16-mønsteret) MENS det har en igangværende, ikke-terminal
  rollout-status (fx `downloading`), forsvinder det fra `total`-optællingen — så snart de
  RESTERENDE devices i rollout'en er terminale, flipper global status til `deployed`, selvom det
  fjernede device reelt aldrig afsluttede sin installation. Dette er en anden mekanisme end
  HLTH-008-flush-bugget (som nu er rettet) og opstår kun i det snævrere tilfælde at et device
  fysisk forsvinder fra CMDB midt i en rollout — dokumenteret som en kontrakttest, der bekræfter
  den faktiske (ikke hypotetiske) nuværende opførsel:
  `headend/tests/test_update_lifecycle.py::test_device_removed_from_cmdb_mid_rollout_does_not_prematurely_flip`
  (committet i `1e3c3321`). **Ikke rettet i kode** — kræver først en produktbeslutning af Peter,
  da alle tre løsninger har reelle afvejninger: (a) tæl fjernede devices som permanent
  "ikke-terminal" → kan blokere en rollout for evigt hvis decommission er hyppig, (b) udelad
  fjernede devices fra `total` som nu (nuværende adfærd) → kan skjule at et device aldrig nåede at
  fuldføre før det blev udskiftet, (c) log/marker rollup'en som "delvist bekræftet" når et device
  forsvinder midt i en ikke-terminal status, uden at blokere den. Ingen af de tre er rettet endnu.
- **Claudes anbefaling (rådgivende — periodisk tjek #54, IKKE en beslutning, kun beslutningsstøtte
  for at afkorte en flere-ugers-gammel afventende produktbeslutning):** (c) frem for (a) og (b),
  ud fra et SABSA/revisionsspor-perspektiv. (a) permanent blokering giver en tilgængeligheds-
  /driftsrisiko der vokser med udskiftningsfrekvensen (kan låse en rollout for evigt uden manuelt
  indgreb) — uforholdsmæssigt, da et decommissioned device pr. definition ikke længere er en del
  af den aktive flåde. (b), nuværende adfærd, er mest lempelig men skaber et falsk "fuldt
  bekræftet"-signal i rollup'en — problematisk for et revisionsspor/change management-formål
  (ISO/IEC 27001 A.8.32), da udrulningsstatus ikke længere er retvisende. (c) bevarer et
  retvisende, ikke-blokerende signal (rollout afsluttes operationelt, men audit-sporet viser
  eksplicit at ét device forsvandt midt i en ikke-terminal status i stedet for at tie det ihjel)
  og har lavest implementeringsomkostning af de to sikre valg (kun en ny statusværdi, ingen ny
  blokerende UI-tilstand). Peter træffer stadig selve valget.
- **Residualrisiko:** 🟡 6 (nedjusteret fra 🟠 8 2026-07-05 — kodefix + unit/contract-tests er nu
  committet, deployet og health-checket, så "stuck forever"-bugget er reelt lukket i produktion;
  holdes på 🟡 og ikke 🟢 indtil en faktisk multi-device rollout er live-verificeret end-to-end, og
  indtil ovenstående decommission-gap er besluttet/lukket)

### R07 — Nøgle-kompromittering
- **Status:** 🟡 Delvist kontrolleret
- **Implementerede kontroller:** Key Management UI, HMAC enforcement, GPG-signering
- **Åbent:** Stale/legacy credentials (TL-DCA63234D813); intern CA ikke implementeret
- **Residualrisiko:** 🟡 6

### R08 — Man-in-the-middle
- **Status:** 🟡 Delvist kontrolleret
- **Implementerede kontroller:** HTTPS, TLSv1.2/1.3, JWT, HSTS, nginx security headers
- **Åbent:** CA-pinning, mTLS (edge client-cert)
- **Residualrisiko:** 🟡 6

### R09 — Dataredundans og backup
- **Status:** 🟠 Delvist lukket (2026-07-04 nat, Claude) — se fund og rettelser nedenfor
- **Implementerede kontroller:** Backup til /Volumes/Backup (sti rettet); edge circular buffer
- **KRITISK FUND (Claude, 2026-07-04 nat, under design af restore-test-procedure):** `backup_include_images`-indstillingen har eksisteret i UI'en (BackupPage.tsx) og blevet gemt via `PUT /api/admin/backup/settings` — men blev **aldrig læst** af `_run_backup_archive()`. Reelt betød det, at TimeLapse Pro's ca. 27.000+ produktionsbilleder ALDRIG har været omfattet af backup, uanset hvad administratoren valgte i UI'en — kun database + en fast liste config-filer blev sikkerhedskopieret. Tilsvarende blev `backup_auto_interval` gemt i DB men aldrig konsumeret — der har ALDRIG kørt en automatisk backup, kun manuelle klik i UI'en.
- **Rettet (samme nat):**
  1. `_get_backup_include_images()` tilføjet og wired ind i `_run_backup_archive()` — når slået til, kører en `rsync -a` billedspejling af `_sftp_base_path()` til `{base_dir}/timelapse-images-mirror/` (holdt UDENFOR tar.gz'en, da billedtræet kan være mange GB/TB; fejl her er non-fatal og stopper ikke DB/config-delen).
  2. `_backup_auto_loop()` tilføjet og startet ved opstart — tjekker `backup_auto_interval` hvert 10. min og kører faktisk automatisk backup ved `daily`/`weekly` (matcher UI'ens faktiske valgmuligheder i BackupPage.tsx).
  - Verificeret: `py_compile` ren; logik gennemgået mod eksisterende `_get_setting`/`_sftp_base_path`-mønstre i kodebasen. **IKKE afprøvet på reelt produktionsdatasæt** (kræver reel kørsel på Mac Mini'en for at bekræfte rsync-tid/diskplads for et fuldt billedtræ) — det bør Peter/Codex køre og bekræfte inden go-live regnes for fuldt dækket her.
- **Fortsat åbent (kan IKKE lukkes uden reel kørsel på levende infrastruktur — realistisk ikke færdigt til go-live "i morgen"):** Off-site/3-2-1-kopi (billedmirroren ligger stadig kun lokalt/NAS, ingen ekstern kopi), reel restore-test (gendan fra arkiv til et tomt miljø og verificér), backup change ticket, RTO/RPO-dokumentation.
- **Sandsynlighed:** 2, **Konsekvens:** 4, **Score:** 🟠 8 (uændret indtil rsync-billedbackup er bekræftet kørt mindst én gang i produktion og restore-test er udført)

### R10 — SSH tunnel misbrug
- **Status:** ✅ Kontrolleret
- **Implementerede kontroller:** Deny-flag, SshTunnelLog, restricted shell
- **Residualrisiko:** 🟢 2

### R11 — CMDB/inventory uautoriseret adgang (NY)
- **Status:** ✅ Løst
- **Implementerede kontroller:** /api/cmdb/ kræver viewer-rolle; HMAC kræves for device-tokens
- **Residualrisiko:** 🟢 3

### R12 — GDPR/billeddata uden compliance-evidens (NY)
- **Status:** 🔴 Åben
- **Sandsynlighed:** 3, **Konsekvens:** 4, **Score:** 🟠 12
- **Mangler:** DPIA pr. kunde/site, retention policy, adgangslog pr. billede, sløring/redaction workflow, databehandleraftale, subprocessor-liste (Gemini/Google Cloud)
- **Anbefaling:** DPIA-template, retention-policy i DB pr. camera, download-audit log
- **TILFØJELSE 2026-07-04 (Claude):** GPS/lokationsmetadata (breddegrad/længdegrad/højde pr. optagelse) er nu reelt implementeret og verificeret i produktion (kildeprioritet enhed/kamera > site, signeret GPS-fix fra kameraet kan ikke overskrives, kilde vises i UI). Dette er personoplysning i GDPR-forstand (præcis geografisk placering af overvågningsudstyr, potentielt private adresser) og falder ind under nærværende risiko — DPIA/retention-arbejdet (se §11 P0) skal eksplicit dække GPS-feltet, ikke kun selve billedet. Ingen kodeændring nødvendig, men scope for DPIA-template bør nævne det eksplicit.
- **TILFØJELSE 2026-07-04 (nat, Claude):** DPIA-skabelon, retention-policy-design og subprocessor-liste udarbejdet — se `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`. Dette er tekniske/organisatoriske UDKAST (ikke juridisk godkendt), og retention er kun et design, ikke implementeret kode. Databehandleraftale og brudprocedure er bevidst IKKE dækket (kræver jurist). Fandt undervejs R18 (separat, urelateret produktionsbug — rettet, se nedenfor).
- **TILFØJELSE 2026-07-05 (Claude, periodisk tjek):** Opfulgte DPIA-dokumentets §4-anbefaling ("Bekræft Gemini/Vertex AI's faktiske region-indstilling som allerførste skridt") ved kodegennemgang af `headend/ai/gemini_service.py`/`headend/main.py`/`headend/ai/ai_batch_submit.py`. Fund: Vertex-region defaulter til `europe-west1` (EU) hvis `GOOGLE_CLOUD_LOCATION` ikke er sat, OG `POST /api/admin/ai-batch/...`-endepunktet (API-stien bag "Kør AI-batch nu" i UI'et) havde allerede et tjek der stopper jobbet, hvis det konfigurerede `gemini_gcs_bucket_region` ikke matcher Vertex-regionen — MEN `headend/ai/ai_batch_submit.py` (CLI-scriptet til manuel bulk re-tag, kører direkte på Mac Mini'en, samme Vertex-batch-upload) havde INTET tilsvarende tjek. En operatør der kørte CLI-scriptet i stedet for UI-knappen kunne dermed sende et helt bulk-batch-job til et forkert-region GCS-bucket uden nogen advarsel. Rettet: logikken er udtrukket til én delt funktion (`validate_batch_bucket_region()` i `gemini_service.py`), brugt af begge indgange, med 6 nye kontrakt-tests (`headend/tests/test_gemini_region_guard.py`) samt kørsel af hele den eksisterende test-suite (19/19 bestået) og `py_compile` på alle rørte filer. **Fortsat IKKE bekræftet af denne runde** (kræver live-adgang til den faktiske produktions-`GOOGLE_CLOUD_LOCATION`/`gemini_gcs_bucket_region`-værdi, som Claude ikke har): at de FAKTISK konfigurerede værdier i produktion reelt er sat til EU-regioner — kun at koden nu konsekvent HÅNDHÆVER match mellem de to, uanset hvilken indgang der bruges. Se `GO_LIVE_CHECKLIST_v10.md` §G for status.
- **TILFØJELSE 2026-07-05 (Claude, Peters miljøafklaring + Codex-præcisering):** Peter har bekræftet at der allerede findes en **databehandleraftale med kunden Kirkbi A/S** (som ejer Site "Travbyen", hvorfra billederne i R&D-miljøet er importeret). Dette er en delvis, ikke fuld, lempelse af "databehandleraftale mangler". Codex' vigtige præcisering (fastholdt her): dette dækker lovligt behandlingsgrundlag for drift/support, men er IKKE i sig selv det samme som fri R&D-agentadgang til kundebilleder til AI/QA-udvikling — det er et separat spørgsmål, adskilt fra selve DPA-eksistensen. Se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §4 for de tre adskilte spørgsmål og forbehold: aftalen skal verificeres til også at dække TimeLapse Pro's FAKTISKE nuværende behandling (AI/Gemini cloud-eskalering, GPS-metadata), før den kan bruges som fuld GDPR-evidens for G-03 i `GO_LIVE_CHECKLIST_v10.md`. Nye kunder ud over Kirkbi A/S kræver fortsat hver deres egen aftale.
- **TILFØJELSE 2026-07-05 (Claude, opfølgning) — udviklingsanvendelse eksplicit tilladt:** Peter har oplyst at der, UD OVER selve databehandleraftalen, er givet **eksplicit tilladelse til at Travbyen-billederne anvendes i forbindelse med udviklingen af TimeLapse Pro**. Dette besvarer direkte Codex' tidligere rejste punkt 2 (agent-udviklingsadgang til reelle kundebilleder er et separat spørgsmål fra selve DPA'en) — det er nu udtrykkeligt dækket for udviklingsformål, ikke kun antaget. Dækker IKKE automatisk andre formål (fx offentlig markedsføring af billederne) — kun udvikling. Nye kunder kræver en tilsvarende eksplicit tilladelse, ikke kun en DPA.

### R17 — Debug/lab mode kan efterlades aktiveret uden overvågning (NY, fundet 2026-07-04)
- **Status:** 🟢 Rettet og deployet (2026-07-05, Claude periodisk tjek + Codex-deploy) — kode
  committet (`44b78fb7`), deployet på Headend, service genstartet (health 200 OK), `npm run build`
  lykkedes på Mac'en. **Manuel UI-smoketest (aktivering/deaktivering af lab mode + kortvarig lav
  `TIMELAPSE_DEBUG_MODE_MAX_HOURS` for at bekræfte auto-timeout) er bevidst IKKE kørt endnu**, da
  det ændrer live device-state og bør gøres kontrolleret af Peter/Codex — se
  `HANDOVER_LOG.md` 2026-07-05 (nat) "Codex: R17 debug/lab mode deploy-verifikation".
- **Fund (Claude, ifm. GPS-fejlsøgning):** `debug_mode.enabled` er en flad, per-enhed config-nøgle (ingen DB-kolonne, ingen udløb/TTL), sat udelukkende via `PUT /api/admin/devices/{id}/debug` (kræver admin-rolle — ingen adgangskontrol-svaghed). Mens aktiv holder edge-agenten kamera-relæet konstant tændt og springer den normale optagelsesplan over (interaktiv "lab"-tilstand til kamera-tuning). Fundet aktiveret på et produktionskamera (TL-C87FF9587CA0), tilsyneladende en efterladt flag fra en tidligere test-session — opdaget udelukkende ved manuel log-gennemgang, ikke via noget dashboard/alarm.
- **Konsekvens:** Ingen adgangskompromittering, men operationel/tilgængelighedsrisiko: uventet konstant relæ-belastning, optagelsesplan brydes uden varsel, og (jf. GPS-fixet 2026-07-04) reduceret GPS-pålidelighed pga. relæets effekt på GPS-modtagerens strømforsyning. Ingen automatisk måde at opdage "enhed X har kørt i lab mode i N dage" på.
- **Sandsynlighed:** 3, **Konsekvens:** 2, **Score (før fix):** 🟡 6
- **Anbefaling (oprindelig):** CMDB/dashboard-indikator for `debug_mode.enabled=true` pr. enhed; overvej auto-timeout (fx maks. 4-8 timer, kræver eksplicit forlængelse); log aktivering/deaktivering (hvem/hvornår) til audit/SIEM.
- **Implementeret (Claude, 2026-07-05, se `HANDOVER_LOG.md` 2026-07-05 00:33):** Alle tre
  anbefalinger dækket i `headend/main.py`: (1) `GET /api/admin/devices` eksponerer nu
  `debug_mode_enabled`/`debug_mode_enabled_at` pr. device, med badge i `SystemAdminPage.tsx`
  og "Aktiv siden"-visning i `LabPage.tsx`; (2) ny baggrundstråd
  `_debug_mode_auto_timeout_loop()` slukker automatisk debug_mode efter
  `TIMELAPSE_DEBUG_MODE_MAX_HOURS` (default 8t, konfigurerbar); (3) `set_debug_mode()` logger nu
  aktivering/deaktivering (bruger, tidspunkt) som SIEM-event (`debug_mode_change`/
  `debug_mode_auto_timeout`). Ingen DB-skemaændring — alt gemt i eksisterende
  `device_config`-JSON-kolonne.
- **Verifikation her (Claude, sandbox):** `py_compile` ren; isoleret simuleret test af
  auto-timeout-beslutningslogik (5 cases, alle bestod); frontend `tsc -b` (typecheck) grøn. Fuld
  `npm run build` kunne ikke køres i sandbox (manglende native rolldown-binding for sandboxens
  CPU-arkitektur — sandbox-begrænsning, ikke kode-relateret).
- **Verifikation efter deploy (Codex, 2026-07-05 nat):** commit `44b78fb7` pushet;
  `dk.froekjaer.timelapse-headend` genstartet med `launchctl kickstart`,
  `https://timelapse.froekjaer.dk/api/health` svarede 200 OK; `npm run build` lykkedes på den
  rigtige maskine (kun eksisterende, urelaterede warnings — bekræfter at rolldown-fejlen i
  sandbox var et sandbox-artefakt, ikke en reel byggefejl). Score nedgraderet til 🟢. **Fortsat
  åbent:** den manuelle funktionelle smoketest (aktiver/deaktiver lab mode på et testdevice og se
  badge + "Aktiv siden" i UI'en, midlertidigt sænke `TIMELAPSE_DEBUG_MODE_MAX_HOURS` for at
  bekræfte at auto-timeout-loopet rent faktisk slukker og logger `debug_mode_auto_timeout`, samt
  at `debug_mode_change`-eventet dukker op på SIEM-siden) er bevidst udskudt af Codex, da det
  ændrer live device-state — regnes ikke for 100% lukket før dette er kørt.
- **Kosmetisk opfølgning (Claude, 2026-07-05 01:06):** `debug_mode_change` og
  `debug_mode_auto_timeout` manglede ikon/label i `SIEMPage.tsx` (`EVENT_META`) — de ville
  vises som generisk `Activity`-ikon uden dansk label i events-listen. Tilføjet: `Bug`-ikon
  (amber) for `debug_mode_change`, `Timer`-ikon (lilla) for `debug_mode_auto_timeout`. Rent
  UI, ingen skema-/API-ændring. Ændrer intet ved den fortsat udestående manuelle smoketest ovenfor.

### R13 — Node-agent nede på Headend (NY)
- **Status:** 🟠 Plan klar (2026-07-04 nat), IKKE eksekveret endnu
- **Konsekvens:** CMDB inventory for Mac Mini er stale; patch/risk score ufuldstændig
- **Handling:** Genetabler som user LaunchAgent under peter (ikke root) — se
  `NODE_AGENT_USER_LAUNCHAGENT_MIGRATION_v1.md` for konkret, trin-for-trin plan
  (kommandoer klar til at køre, ikke eksekveret af mig — kræver adgang til Mac Mini'en)

### R14 — Nikon Z30 camera config drift (NY)
- **Status:** 🟠 Delvist rettet (2026-07-05, Claude periodisk tjek) — selve detektionsmekanismen
  rettet og verificeret isoleret; IKKE end-to-end verificeret på levende Z30-hardware
- **Sandsynlighed:** 4, **Konsekvens:** 3, **Score (før fund nedenfor):** 🟠 12
- **Handling:** Nikon Z30 capabilities-mapping; skeln readonly vs. enforceable; "desired state" + "accepted equivalent labels"
- **Fund (Claude, ved scoping af denne opgave):** `edge/diagnostics/camera_diagnostics.py::collect_camera_diagnostics`
  sammenlignede aldrig reelt Z30'ens config mod forventede værdier. To uafhængige bugs:
  1. `expected_overrides` (bygget i `edge/agent.py` fra `camera.*`-config via
     `_build_camera_commands()`) **erstattede** `FLEET_DEFAULTS` fuldstændigt i stedet for at
     merge — en enhed uden egne overrides fik et TOMT forventnings-dict, altså ingen
     drift-check overhovedet.
  2. Nøglenavnene matchede aldrig hinanden: den profil-bevidste Z30-driver
     (`gphoto2_driver.CAMERA_PROFILES["Nikon Z30"]`) bygger overrides som fulde gphoto2-stier
     (`/main/imgsettings/iso=200`), mens `CAMERA_CONFIG_PARAMS` bruger korte kanoniske navne
     (`iso`, `white_balance`, …). For Canon (kort-form-nøgler uden underscore, fx
     `whitebalance`) var mismatchet mindre alvorligt men stadig reelt (`whitebalance` ≠
     `white_balance` osv.). Praktisk konsekvens: drift-alarmering var reelt inaktiv for stort
     set alle parametre på begge kameratyper, stille — ingen fejl, ingen log, bare aldrig en
     alarm.
- **Rettet (kode):** `edge/diagnostics/camera_diagnostics.py` — nyt `_canonicalize_config_key()`
  oversætter kanonisk navn/kort gphoto2-navn/fuld gphoto2-sti til samme kanoniske nøgle før
  sammenligning; `expected_overrides` merges nu pr. nøgle oven på `FLEET_DEFAULTS` i stedet for
  at erstatte. Nyt `non_enforceable_keys`-parameter udelader parametre som den aktive
  kameraprofil selv markerer readonly (fx Z30's `focusmode`, som allerede var markeret
  `"skip": True` i driveren, men blev spurgt om alligevel) — disse rapporteres i nyt felt
  `camera_config_non_enforceable` i stedet for at kunne fejlalarmere. `edge/agent.py` udleder nu
  `non_enforceable_keys` direkte fra `driver.get_profile_summary()["config_commands"]` (samme
  kilde som driveren selv bruger), så der ikke er to steder der skal holdes i sync.
- **Verifikation her:** `py_compile` ren på begge filer. Simuleret Z30-scenarie (mock af
  gphoto2-læsning): reelt ISO-drift (200→800) fanges korrekt; hvidbalance-ækvivalente labels
  ("Automatic" vs. fleet-default "AWB White") fejlalarmerer IKKE; `focus_mode` optræder ALDRIG i
  drift-listen, kun i `camera_config_non_enforceable`; tomt `expected_overrides`-dict falder nu
  korrekt tilbage til `FLEET_DEFAULTS` i stedet for at slå drift-check helt fra.
- **IKKE verificeret / fortsat åbent (før i dag):** ingen live-test på faktisk Z30-hardware endnu
  (kræver Orange Pi-adgang, ikke noget jeg kan køre selv); `aperture`/`shutter_speed` har fortsat
  ingen drift-check-mål (bevidst — de er capture-settings, ikke fleet-politik, men bør besluttes
  eksplicit, ikke bare antaget); ingen bredere "desired state"-model på tværs af flere
  kameratyper end Canon/Z30. Score nedgraderes IKKE til grøn før live-verifikation.
- **Opfølgning 2026-07-05 (Claude, periodisk tjek): UI/CMDB-visning af `camera_config_non_enforceable`
  implementeret + en uafhængig, reel bug fundet og rettet undervejs.**
  - **Fund undervejs (utilsigtet, opdaget ved scoping af UI-opgaven):**
    `GET /api/admin/devices/{device_id}` (`headend/main.py::get_device_detail`) hentede
    `Diagnostic`-rækken (`diag = db.query(Diagnostic)...first()`) men **serialiserede den aldrig i
    responsen** — ingen `"diagnostics"`-nøgle i det returnerede JSON overhovedet. `git log -L` viser
    dette har været sådan siden ca. 15. april 2026. Konsekvens: HELE "Hardware diagnostik" og
    "Kamera diagnostik"-panelet på enhedssiden (`DevicePage.tsx` → `StatsTab`) har vist tomt for
    enhver enhed i produktion i månedsvis — CPU-temp, SSD, NTP-offset, batteri, lukkertæller,
    config-drift, alt sammen. Stille fejl: frontend tjekker defensivt `diagnostics &&`/`diagnostics?.`
    overalt, så der opstod hverken en JS-fejl eller en synlig fejlbesked — panelet forsvandt bare
    fuldstændig fra siden.
  - **Rettet (kode, ikke rørt live services):**
    1. `headend/main.py::get_device_detail` bygger nu en `"diagnostics"`-dict fra `diag`
       (alle felter frontendens `Diagnostic`-type forventer: cpu/ram/ssd/ntp/netværk/kamera/capture-
       felter) og returnerer den. Ren tilføjelse — ingen eksisterende nøgler i responsen ændret.
    2. Ny kolonne `Diagnostic.cam_non_enforceable_json` (`headend/database.py`), skrevet ved hvert
       heartbeat (`headend/main.py` ~linje 3628) fra `cam.get("camera_config_non_enforceable", [])`,
       og inkluderet i den nye diagnostics-serialisering.
    3. Selvhelende, idempotent DB-migration **v14** tilføjet i `startup()`
       (samme mønster som v9-v13): `ALTER TABLE diagnostics ADD COLUMN cam_non_enforceable_json TEXT`
       — kører automatisk ved næste headend-genstart, ingen manuel SQL-kommando nødvendig.
    4. Frontend (`timelapse-ui/src/types/index.ts`, `DevicePage.tsx`): nyt felt i `Diagnostic`-typen;
       ny informativ (ikke-alarm) boks under drift-sektionen der lister non-enforceable parametre
       med samme danske labels som drift-visningen (delt `CAM_PARAM_LABELS`-konstant).
  - **Verifikation her:** `py_compile` ren på `headend/main.py` + `headend/database.py`. `npx tsc -b`
    (hele UI) grøn uden fejl. Selvstændig Python-simulering af hele kæden (edge-payload →
    heartbeat-lagring → device-detail-serialisering → frontend-parsing) bekræfter at
    `camera_config_drift` og `camera_config_non_enforceable` round-tripper korrekt, og at et tomt
    non-enforceable-array ikke fejler/ikke viser en tom boks. `git status --short` viser kun de 4
    forventede ændrede filer.
  - **IKKE gjort — bevidst:** ingen live-test mod faktisk Postgres/Orange Pi (kræver Mac
    Mini-adgang); ingen ændring af selve R14-scoren udover at markere UI-delen løst — den
    grundlæggende "IKKE verificeret på levende hardware"-status fra tidligere står stadig ved magt.
    DB-migrationen er additiv/nullable og selvhelende ved opstart, så intet manuelt SQL-skridt er
    nødvendigt fra Codex/Peter — kun almindelig git pull + headend-genstart.
  - **Opfølgning 2026-07-06 (periodisk tjek #64, Claude): rådgivende SABSA-anbefaling til
    aperture/shutter_speed-drift-beslutningen (§11 P1.3, sidste åbne underpunkt).**
    - **Nuværende kode (bekræftet ved læsning, ikke antaget):** `camera_diagnostics.py` har hverken
      `aperture` eller `shutter_speed` i `CAMERA_CONFIG_PARAMS`/`FLEET_DEFAULTS` — og
      `SHORT_KEY_ALIASES` mapper eksplicit `"shutterspeed"`/`"shutter_speed"`/`"aperture"` til
      `None` ("no drift-check target exists ... intentionally dropped, not a bug"). Konsekvens:
      selv hvis en tekniker satte en per-device override for disse to parametre i dag, ville den
      blive stille droppet af `_canonicalize_config_key()` — og værdierne indgår slet ikke i
      `camera_config`/CMDB-observability i dag (ingen audit-spor overhovedet for disse to felter).
    - **Tre muligheder:**
      (a) Lad stå uændret permanent — ingen overvågning, ingen synlighed. Risiko: en utilsigtet
      eller ondsindet ændring af eksponering kan stille forringe optagelseskvaliteten for et
      kundesite uden nogen alarm eller audit-spor.
      (b) Tilføj fleet-wide `FLEET_DEFAULTS`-baseline og håndhæv som de øvrige parametre. Risiko:
      aperture/shutter_speed er legitimt site-/scene-specifikke (forskellig lysforhold pr.
      lokation/årstid) — én fælles fleet-værdi vil udløse konstante falske drift-alarmer, hvilket
      undergraver tilliden til hele drift-alarm-funktionen (alert fatigue, jf. ISO/IEC 27001
      A.5.7-hensyn om overvågningens reelle effektivitet).
      (c) **Anbefalet:** Opt-in pr. enhed, efter nøjagtig samme mønster som R14-rettelsen allerede
      har bygget for de øvrige parametre: tilføj aperture/shutter_speed som **observability-only**
      felter (aktuel værdi ind i `camera_config`/CMDB uanset), men **uden** en `FLEET_DEFAULTS`-
      værdi. En tekniker der bevidst fastlåser en manuel eksponeringsindstilling for et konkret
      site kan sætte `camera.aperture`/`camera.shutter_speed` i den enheds eksisterende per-device
      override-konfiguration (`expected_overrides` — samme mekanisme som alle andre parametre
      allerede bruger) — herved opt'er enheden ind i drift-check udelukkende mod SIN EGEN ønskede
      værdi. Enheder uden override får synlighed uden alarmstøj (samme informationsniveau som det
      allerede byggede `camera_config_non_enforceable`-felt).
    - **Vigtig teknisk advarsel før implementering — grundet i faktisk kode, ikke antagelse:** i
      modsætning til de øvrige `CAMERA_CONFIG_PARAMS`-nøgler er aperture/shutter_speed's gphoto2-
      stier IKKE ens på tværs af kameraprofiler i denne flåde. `edge/camera/drivers/gphoto2_driver.py`
      viser at nogle profiler læser lukkertid via `/main/capturesettings/shutterspeed` og blænde
      via `/main/capturesettings/aperture`, mens mindst én anden profil (Canon-konvention) i
      stedet bruger `/main/capturesettings/f-number` for blænde (med `shutterspeed`/`shutterspeed2`-
      fallback for lukkertid). `camera_diagnostics.py::CAMERA_CONFIG_PARAMS` antager derimod ÉN
      fast gphoto2-sti pr. kanonisk nøgle, brugt direkte i `_read_gphoto2_param(path)` — præcis
      samme klasse nøgle-mismatch som gjorde drift-detektion stille inaktiv indtil 2026-07-05-
      rettelsen. En naiv tilføjelse af blot én fast sti (fx `"aperture": "/main/capturesettings/aperture"`)
      ville derfor stille fejle på Canon-kroppe der bruger `f-number`, og gengive præcis samme bug
      for netop disse to nye parametre. Korrekt implementering kræver enten (i) en per-profil
      sti-liste med fallback (som `_read_capture_settings()` allerede gør, gphoto2_driver.py
      linje ~174-221), eller (ii) genbrug af driverens allerede profil-bevidste
      `_read_capture_settings()`-output i stedet for endnu en, parallel rå gphoto2-læsning inde i
      `camera_diagnostics.py`.
    - **Anbefaling:** (c), implementeret via (ii) — led driverens allerede korrekte, profil-
      bevidste eksponeringslæsning ind i diagnostics-dict'et, i stedet for at tilføje nye faste
      stier til `CAMERA_CONFIG_PARAMS`. Vend samtidig `SHORT_KEY_ALIASES`' `shutterspeed`/
      `shutter_speed`/`aperture`-poster fra `None` til deres kanoniske navne, så en device-level
      override, når den først sættes, ikke længere bliver stille droppet.
    - **IKKE implementeret i kode denne runde:** dette rører præcis den samme
      camera-config-drift-logik der forårsagede den oprindelige R14-bug, og `mcp__workspace__bash`
      er fortsat nede (se HANDOVER_LOG, nu 12.+ selvstændige bekræftelse) — jeg kan derfor ikke
      køre `py_compile` eller de eksisterende diagnostics-tests for at verificere en ændring før
      jeg står inde for den, og efter dette projekts "dobbelttjekker før du udfører"-regel vil jeg
      ikke gætte mig frem i netop denne drift-detektionskode uden at kunne teste den. Dette er ren
      beslutningsstøtte + en implementeringsnote til Codex (som har shell-adgang) til at tage op.

### R15 — `/api/siem/*` uden autentificering (NY, fundet + rettet 2026-07-03)
- **Status:** ✅ Kontrolleret i kode og **live-verificeret** (Peter, 2026-07-03: health `200`, `GET /api/siem/events` uden auth → `401`)
- **Fund:** `GET /api/siem/events|summary|threats` havde ingen `Depends(get_current_user)`/rolletjek — enhver (og med nginx stadig public på `*:80/443`, potentielt enhver på internettet) kunne læse security-events, source-IP'er og brute-force-data uden login. `POST /api/siem/events/{device_id}` kunne modtage fabrikerede events for et vilkårligt device_id uden HMAC/token.
- **Implementerede kontroller (kode):** GET-endpoints kræver nu `viewer`-rolle + samme MFA-politik som resten af systemet; POST-ingest kræver nu gyldigt device-token via samme `_verify_device_token()`-kæde som øvrige edge-endpoints (HMAC/attestation).
- **Sandsynlighed før fix:** 4, **Konsekvens:** 3, **Score (før fix):** 🟠 12 → **Residualrisiko efter fix:** 🟢 4
- Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.1.

### R16 — Kryds-kunde-lækage af billeddata ved Edge-gentildeling (NY, fundet + rettet 2026-07-03)
- **Status:** ✅ Rettet, committet (`bb18421`), deployet og **backfillet komplet i produktion**
- **Fund (Claude, under implementering af fase 3):** Tenant-isolation på `Capture`-rækker var udelukkende baseret på et LIVE opslag: "hvilke devices tilhører denne kunde LIGE NU" (`Device.customer_id`). Hvis en fysisk Edge-enhed går i stykker, genbruges og fysisk tildeles en ANDEN kunde (almindeligt scenarie — det er netop derfor kamera-lokation/Edge-binding-hierarkiet findes, jf. R03), fik den NYE kunde automatisk adgang — via galleri-liste, EXIF, sletning og filservering — til ALLE billeder taget mens enheden tilhørte den FORRIGE kunde. Dette er en konkret, udnyttelig instans af det generelle §2.4-fund (tenant-isolation kun applikationsdisciplin), ikke blot en teoretisk risiko.
- **Implementerede kontroller (kode):** Adgangskontrol på Capture-niveau bruger nu primært `Capture.customer_id` (frosset på optagelsestidspunktet, v12-feltet fra fase 2) i stedet for det live device-opslag — en historisk rækkes ejerskab ændrer sig ikke længere, når det fysiske device sidenhen omfordeles. Fallback til det gamle device-opslag bevares kun for rækker, der endnu ikke er backfillet. Centraliseret i `_capture_is_allowed()`/`_capture_tenant_clause()` (main.py), dækker liste, statistik, søgning, sletning, EXIF og filservering (52 kaldsteder, 4 kernefunktioner ændret).
- **Backfill 2026-07-03 (Peter):** Alle 27.662 produktions-captures har nu `customer_id`. Undervejs fandtes ét device (`TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1`, bulk-importeret) uden kunde-kobling i CMDB — rettet via `assign`-endpointet, hvorefter backfillen dækkede de sidste 5.029 rækker. Ingen rækker afhænger længere af device-fallback'en.
- **Sandsynlighed før fix:** 3 (kræver at en enhed reelt genbruges på tværs af kunder — forventeligt over enhedens levetid), **Konsekvens:** 4 (eksponering af en anden kundes overvågningsbilleder — GDPR-relevant), **Score (før fix):** 🟠 12 → **Residualrisiko efter fix:** 🟢 4
- Se `Claude_Kritisk_Statusgennemgang_2026-07-03.md` §2.4/§2.5/§6 og `HANDOVER_LOG.md` 2026-07-03 13:15 + 14:00.

### R18 — Manglende `gdpr_manager.py` crashede Gemini-eskaleringsgodkendelse stille (NY, fundet + rettet 2026-07-04)
- **Status:** ✅ Selve integritetsbugget rettet i kode; **GDPR-detektionslageret er stadig ikke implementeret** (se R12)
- **Fund (Claude, ifm. DPIA-research):** `headend/ai/ai_router.py` importerede `GDPRManager` fra `gdpr_manager.py` på modul-niveau — en fil der reelt ikke findes i kodebasen (kun forventet/dokumenteret, aldrig skrevet). `review_api.py::_run_gemini_for_approved` (kørt som `BackgroundTasks.add_task` fra `POST /api/review/escalation/approve`) lazy-importerer denne router, så hver gang en admin godkendte eskalerede billeder til Gemini-analyse, crashede baggrundsjobbet øjeblikkeligt på importen — stille, da FastAPI's `BackgroundTasks` ikke propagerer exceptions til HTTP-svaret. Admin fik "godkendt"-kvittering; Gemini-analysen skete aldrig. Formentlig gældende siden denne kode blev skrevet.
- **Konsekvens:** Integritets-/tilgængelighedsrisiko for review-workflowet (ikke en adgangs-/lækagerisiko) — eskalerede billeder, som admin bevidst har prioriteret til grundigere cloud-analyse, er reelt aldrig blevet analyseret. Sekundært en governance-risiko: hvis `has_gdpr_data` nogensinde var blevet sat, ville GDPR-detektioner (ansigt/nummerplade/person) heller ikke kunne gemmes isoleret.
- **Implementerede kontroller (kode):** Import gjort lazy/guardet (`try/except ModuleNotFoundError`); det eneste brugssted logger nu en tydelig, synlig fejl i stedet for at crashe hele modulet. Reproduceret og verificeret (isoleret Python-import bekræftede fejlen før fix, lykkedes efter).
- **Åbent:** (1) `gdpr_manager.py` er stadig ikke skrevet — GDPR-detektioner kan fortsat ikke gemmes isoleret, dækket af R12. (2) Ingen historisk genkørsel af tabte Gemini-eskaleringer er foretaget — kræver først en opgørelse af hvilke `analysis_ids` reelt blev "godkendt" uden effekt.
- **Sandsynlighed:** var 5 (skete ved hver eneste godkendelse), **Konsekvens:** 2 (workflow-fejl, ikke datalækage), **Score:** var 🟡 10 → **Residualrisiko efter fix:** 🟢 3 (workflowet virker igen; GDPR-dele af R12 uændret åbne)
- Se `HANDOVER_LOG.md` 2026-07-04 (nat).

### R19 — Agent-adgang til fremtidig prod-fysisk-system ikke formelt udelukket, mens maskinen allerede håndterer live kundedata (NY, 2026-07-05, uddybet 2026-07-06)
- **Status:** 🟢 Politik besluttet (2026-07-05, Peter, ordret): "Hverken Codex eller dig har eller vil få adgang til staging og Prod. Kun vores R&D udviklingssystem." Dette er en permanent, bekræftet DEFAULT-politik (default-deny) — ikke længere kun en anbefaling. **Uddybet 2026-07-06 (Peter):** en kontrolleret, tidsbegrænset, logget undtagelsesvej ("break-glass") til installation/fejlsøgning er nu godkendt ved siden af default-deny — se `Claude_Support_Access_Model_2026-07-06.md` (design-notat, INGEN kode/CA bygget endnu: separat Support-CA, korttidslevende SSH-certifikater, kunde-samtykke-tjek, signeret ticket + audit). Dette er ikke en svækkelse af R19 — det er den samme risikomodel som "ingen adgang", blot med en dokumenteret, sporbar proces for de tilfælde hvor Peter selv vurderer at agent-hjælp er nødvendig, i stedet for en udokumenteret ad-hoc-løsning, hvis behovet alligevel skulle opstå i praksis. **Teknisk håndhævelse af selve default-deny (Codex' agent/service-principal-forslag) er stadig ikke kodet** — se `HANDOVER_LOG.md` 2026-07-05 — men politikken gælder allerede nu ved menneskelig disciplin (Peter foretager selv al installation på staging/prod, se `INSTALLATION_GUIDE_HEADEND_v1.md`, undtagen ved en fremtidig, aktiveret break-glass-session). Residualrisiko forbliver 🟡 5 (uændret ved denne uddybning, da intet er bygget endnu — vurderes på ny når Support-CA/scriptet er kodet og testet).
- **Kontekst (Peters miljøafklaring, se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`):** Den fremtidige `timelapsepro.dk`-prod-vært er et helt andet fysisk system end det nuværende R&D-system (Mac Mini). Denne prod-maskine kører **allerede i dag** CrushFTP til udveksling af kundedata og det legacy timelapse-system, TimeLapse Pro skal erstatte — dvs. den håndterer reelle kunders data NU, selvom TimeLapse Pro-applikationen ikke er deployet dertil endnu.
- **Fund/vurdering (Claude):** Codex' oprindelige forslag antog implicit at prod-isolation primært er en fremtidig "ved cutover"-opgave. Den antagelse holder ikke — hvis der nogensinde skulle opstå agent-adgang (SSH-nøgle, deploy-key, API-token) til denne maskine, ville det være en adgang til et system med LIVE personoplysninger allerede i dag, ikke et tomt fremtidigt system.
- **Åbent:** (1) Eksplicit bekræftelse af, at ingen agent-brugte credentials nogensinde er blevet oprettet på eller givet adgang til denne maskine. (2) Den bredere `AgentPrincipal`/miljøflag-model (Codex' forslag) er stadig kun et designforslag — se `HANDOVER_LOG.md` 2026-07-05 for Claudes fulde svar (SABSA/IEC 62443-vurdering: trust boundary bør være en infrastruktur-zone, ikke kun en applikations-env-flag). (3) Staging (§1 i miljødokumentet) er endnu ikke etableret som kørende system — dens agent-adgangsniveau er ikke besluttet.
- **Anbefaling:** Behandl "ingen agent-adgang til den fysiske prod-maskine" som gældende FRA NU (allerede en de-facto-politik, ikke noget der først skal håndhæves ved launch), og prioritér §6-zonemodellens udvidelse med et miljø-lag (se nedenfor) højt i P0/P1-arbejdet med agent-adgangsmodellen.
- **Kodeaudit 2026-07-06 (periodisk tjek #65, Claude): `TIMELAPSE_ENV`-terminologi-drift fundet —
  en konkret implementeringsfælde for `AgentPrincipal`-håndhævelsen (M-05).**
  `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §2 fastlægger de kanoniske miljønøgler som
  **`rd`/`staging`/`prod`** (bekræftet af `deploy/install/install_headend.sh` linje 100-102, som
  hårdt afviser andre værdier: `TL_ENV skal være rd, staging eller prod`). Ved faktisk kodelæsning
  (ikke antagelse) af alle nuværende `TIMELAPSE_ENV`-forbrugssteder viste det sig at **ingen af dem
  kender til `"rd"`** — de er alle skrevet før miljøafklaringen 2026-07-05 og bruger stadig den
  gamle `lab`-terminologi:
  1. `edge/agent.py` linje 1479-1482 — den eneste reelt farlige af de tre: allowlisten for den
     legacy git-baserede emergency-opdateringssti er `{"lab", "dev", "development"}` (**"rd"
     indgår ikke**). Hvis `TIMELAPSE_ENV=rd` nogensinde sættes eksplicit på R&D-maskinen (jf.
     HANDOVER_LOG.md 2026-07-05's egen anbefaling om at gøre dette "inden `AgentPrincipal`-koden
     begynder at bruge denne variabel"), vil legacy-opdateringsstien blive **permanent blokeret**,
     selv med `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1` sat — stille, kun en logadvarsel
     ("headend_signed_artifact_required"). Retningen er fail-safe (blokerer mere, ikke mindre —
     ingen sikkerhedsregression), men er et reelt funktionelt hul, der bør rettes FØR omdøbningen,
     ikke opdages bagefter under fejlsøgning.
  2. `headend/main.py` linje 81 og `headend/siem.py` linje 402 — begge falder tilbage til
     default-strengen `"lab"` hvis `TIMELAPSE_ENV` er usat. Ufarligt i praksis, da
     installationsscriptet altid sætter variablen eksplicit, men er endnu et sted samme
     terminologi-drift ville dukke op hvis nogen læser koden som reference. `siem.py` linje 402-406
     bruger desuden `mode == "lab"` til at vælge SIEM-logniveau (`info` vs. `warning`) — en
     omdøbning til `rd` ville stille sænke logverbositeten på selve udviklingsmaskinen (kosmetisk/
     observability-effekt, ikke en sikkerhedsregression, men uønsket).
  - **Anbefaling til Codex/Peter (kan udføres uden designdiskussion — ren terminologi-fix, ikke en
    ny beslutning):** Før `TIMELAPSE_ENV=rd` sættes noget sted i praksis, opdatér de 3 ovenstående
    steder til enten (a) at behandle `rd` som synonymt med `lab`/`dev`/`development` i alle tre
    checks, eller (b) fuldt migrere til kun `rd`/`staging`/`prod` og fjerne de gamle synonymer —
    (b) er at foretrække, da det fjerner selve tvetydigheden fremfor at udvide den, og passer bedst
    med at `AgentPrincipal`/miljøflag-modellen (§6 punkt 5 i `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`)
    nu skal bygges på netop denne variabel som single source of truth. Bør løses FØR selve
    `AgentPrincipal`-middleware-koden påbegyndes, så håndhævelsen bygges på en allerede-konsistent
    variabel i stedet for at arve tre forskellige ad-hoc-tolkninger.
  - **Rettet 2026-07-06 (periodisk tjek #84, Claude) — valgte option (a), ikke (b):** tilføjede
    `"rd"` som synonym til det eksisterende `{"lab", "dev", "development"}`-sæt i
    `edge/agent.py` linje 1479-1482 (den reelt farlige af de tre — luk­ker fail-safe-hullet der
    ville have blokeret legacy-emergency-opdateringsstien permanent, hvis `TIMELAPSE_ENV=rd`
    sættes) og i `headend/siem.py` linje 402-406 (`mode in ("lab", "rd")` i stedet for kun
    `mode == "lab"` — bevarer `info`-logniveau i R&D fremfor at falde til `warning`).
    `headend/main.py` linje 81/14593 krævede INGEN rettelse — den sammenligner allerede kun mod
    `{"prod", "production"}`, som forbliver korrekt uanset om variablen sættes til den gamle eller
    nye ikke-prod-terminologi. **Bevidst valg af (a) frem for den i #65 foretrukne (b):** en fuld
    migration væk fra `lab`/`dev`/`development` risikerer at bryde en eksisterende, kørende
    installation, hvis den faktiske R&D-maskine i dag har `TIMELAPSE_ENV` sat til en af de gamle
    værdier (ukendt herfra — ingen shell-adgang til at verificere den faktiske miljøvariabel på
    Mac Mini'en). Den additive (a)-løsning er bagudkompatibel og ikke-brydende under alle
    omstændigheder; en senere oprydning til (b) kan stadig ske som en bevidst, separat
    terminologi-commit når Peter/Codex har bekræftet at ingen live-system længere sætter de gamle
    værdier. **Testet:** ingen automatiseret testsuite dækker disse linjer (`edge/` har ingen
    `tests/`-mappe), så ændringen er verificeret ved (1) manuel linje-for-linje syntakskontrol af
    de to diffs (afbalancerede parenteser/mængder, uændret indrykning) og (2) manuel sporing af
    kontrolflowet — `mcp__workspace__bash` fejlede fortsat (`useradd`-fejlen, 34. selvstændige
    bekræftelse), så `py_compile` kunne ikke køres denne runde. **Committet, merget og deployet
    2026-07-06:** Peter kørte `py_compile` manuelt (OK), committede via PR #1
    (`claude/capture-camera-location-2026-07-03` → `main`), CI (`python-check`/`ui-check`) kørte
    grønt, og `deploy-macmini`-jobbet genstartede rd-headend med den nye kode. Faldgruben er
    dermed reelt lukket, ikke kun rettet i working tree.
- **M-05 "layer 2"-kode skrevet 2026-07-06 (Claude), IKKE testet/committet/deployet endnu:**
  Peter bad eksplicit om at fortsætte til selve `AgentPrincipal`-håndhævelsen, samtidig med at
  Codex var utilgængelig ("Codex sover til den 9. juni"), så dette blev udført solo af Claude
  med ekstra fokus på "dobbelttjekker før du udfører" (læste den fulde oprindelige Codex-
  proposal + Claudes egen 5-trins-plan igen, og User.role/`_ROLE_HIERARCHY`/`get_current_user()`-
  koden grundigt, før noget blev ændret). Scope er bevidst begrænset til trin 2 af 5 (env-flag +
  hård afvisning) — IKKE det fulde `AgentPrincipal`/`AgentToken`/`AgentElevationGrant`-skema
  (trin 3), som er en separat, større beslutning (ny tabel, tokenudstedelse, elevation-flow).
  Implementering (`headend/main.py`, `headend/database.py`):
  1. Ny reserveret rolleværdi `role="agent"` (User.role er allerede en fri `String(50)`, ingen
     DB-migration nødvendig — additivt).
  2. `_agent_role_blocked_in_this_environment(role)` — ren, ikke-DB-konfigurerbar funktion:
     True hvis rolle (case/whitespace-normaliseret) er "agent" OG `TIMELAPSE_ENV` er
     staging/prod/production. Bevidst IKKE en DB-policy-indstilling (i modsætning til fx
     `mfa_exempt_usernames`) — må ikke kunne slås fra ved en fejl i kunde-/site-/kamera-
     konfigurationshierarkiet.
  3. Håndhævet to steder: (a) `/api/auth/login` — afvises FØR password-verifikation, med
     samme generiske 401-fejlbesked som forkert password (undgår rolle-/brugernavn-lækage til
     en ekstern klient); (b) `get_current_user()` — det CENTRALE håndhævelsespunkt, da alle
     cookie/JWT-autoriserede endpoints går gennem denne ene funktion. Dette dækker også
     allerede udstedte sessions (fx hvis en maskines `TIMELAPSE_ENV` ændres efter login, eller
     ved en gendannet DB-kopi) — ikke kun nye login-forsøg.
  4. `_log_agent_lockdown_status()` — `log.critical()` ved hvert opstart i staging/prod (samme
     SIEM-synligheds-mønster som C-03's `_warn_if_default_admin_password_active()`), `log.info()`
     ellers.
  5. En "agent"-rolle-bruger har med denne ændring reelt INGEN rettigheder nogetsteds i dag,
     heller ikke i rd — `_ROLE_HIERARCHY.get(user.role, {user.role})` falder tilbage til
     `{"agent"}`, som intet endpoint kræver. Det er en bevidst, dokumenteret sideeffekt (ingen
     regression), ikke en ny funktion — reel brug af rollen kræver trin 3.
  - **Testet:** 15 nye pytest-tests i `headend/tests/test_agent_principal_lockdown.py`, samme
    mønster som C-03-testfilen (direkte funktionskald mod `main.py`, midlertidig SQLite-DB, ingen
    live Postgres/headend rørt). Dækker `_agent_role_blocked_in_this_environment()` i alle
    miljøer, `get_current_user()`'s afvisning af eksisterende sessions (kerne-scenariet),
    at almindelige menneskelige roller ALDRIG rammes, at afvisningen logges `critical`, og
    opstartsloggens to grene. Bevidst IKKE testet: selve `/api/auth/login`-endpointet via et
    rigtigt HTTP-kald (dekoreret med `@limiter.limit(...)`/slowapi, som forventer en fuld ASGI-
    kontekst — ingen eksisterende test i denne mappe gør det; login()'s nye linjer er en tynd,
    mekanisk anvendelse af samme allerede-testede helper). Se testfilens docstring for en
    anbefalet manuel curl-efterprøvning på en rigtig kørende instans.
  - **IKKE endnu:** `py_compile`/`pytest` kørt (Claudes sandbox `mcp__workspace__bash` fejlede
    igen med samme `useradd`-fejl, genbekræftet 2026-07-06 lige før denne kodesession), commit,
    merge, deploy. Afventer Peters terminal — samme mønster som forrige rettelser denne uge.
    Indtil da forbliver residualrisikoen UÆNDRET (kun kildekode-tilstedeværelse ændrer intet i
    et kørende system).
- **Sandsynlighed:** 1 (ned fra 2 — eksplicit, ordret politik-bekræftelse fra Peter 2026-07-05, plus en dedikeret installationsguide der gør Peter uafhængig af agent-hjælp på staging/prod), **Konsekvens:** 5 (uændret — ville stadig være et reelt databrud på live kundedata + legacy-system, hvis det skete), **Score:** 🟡 5 (ned fra 🟠 10, uændret ved denne kodesession — se ovenfor)

---

## 5. Virtuel penetrationstest — opdatering juni 2026

**Metode:** Ikke-destruktiv. Ingen aggressiv scanning, brute force eller exploit-forsøg. Code review + API-test + konfigurationsanalyse.

### 5.1 Angrebsflader

| Flade | Status |
|---|---|
| https://timelapse.froekjaer.dk/ | Oppe, TLS OK, HSTS, security headers OK |
| /api/health | 200 OK, ingen auth krævet (intentionelt) |
| /api/cmdb/ | 401 ✅ |
| /api/admin/* | 401 uden auth ✅ |
| /api/auth/login | Rate-limited (10r/m) ✅ |
| 127.0.0.1:8000 | Intern, ikke eksponeret direkte |
| 127.0.0.1:11434 (Ollama) | Intern, ikke eksponeret |
| 127.0.0.1:8080 (OpenWebUI) | Intern; OpenWebUI er nede |
| Port 22222 (SFTP) | Eksponeret; sftp_*-brugere begrænset til internal-sftp |
| Port 22 (SSH) | System SSH; TimeLapse-brugere blokeret af Match-regler |
| Port 80 (nginx redirect) | Redirect til HTTPS ✅ |
| Port 443 (nginx/TLS) | Se port-afsnit — SKAL flyttes |

### 5.2 Nye fund (juni 2026)

#### VPEN-2026-001 — nginx lytter på public 80/443
**Prioritet:** P1 (blocker for go-live)
**Beskrivelse:** nginx binder til `*:80` og `*:443` **på `rd`** (dette er OK dér — `rd` kører ikke
CrushFTP). **Opdateret 2026-07-05 (2. korrektion):** Den forrige opdatering af dette fund (samme
dato) konkluderede "direkte nginx-eksponering på standard 443/80 er den faktiske
målarkitektur" for prod — **det var forkert**. Peter har efterfølgende bekræftet at **CrushFTP
allerede kører på BÅDE staging-iMac'en og prod-Mac Mini'en** og optager 21/22/80/443 dér.
TimeLapse Pro's nginx må derfor ALDRIG binde til 80/443 på staging/prod. Den faktiske
målarkitektur for staging/prod er i stedet: nginx på **port 8443** (direkte offentligt bundet,
ikke Cloudflare Tunnel), certifikat via **DNS-01** (`certbot-dns-cloudflare`, rører ingen port).
Kompenserende kontroller (gyldigt cert, fail2ban, rate-limiting) er fortsat kritiske, da der ikke
er en Cloudflare-edge foran til at absorbere scanning/DDoS (medmindre Peter senere aktivt vælger
Cloudflares gratis DNS-proxy foran 8443 — valgfrit, ikke besluttet).
**Anbefaling:** ~~Migrer til Cloudflare Tunnel + nginx på `127.0.0.1:18443`~~ — udgår.
~~Direkte nginx-eksponering på standard 443/80~~ — udgår for staging/prod (CrushFTP-konflikt). I
stedet: nginx på port 8443, gyldigt Let's Encrypt-certifikat (DNS-01), fail2ban aktivt,
rate-limiting på login/API (se `GO_LIVE_CHECKLIST_v10.md` §A, A-01–A-04/A-10/A-13, og
`PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 for den fulde begrundelse).

#### VPEN-2026-002 — SSH port 22 eksponeret til internet
**Prioritet:** P1
**Beskrivelse:** Port 22 er synlig i ældre port-/asset-evidens som macOS/system-SSH på `rd`. På
staging/prod kan port 22 desuden være ejet af CrushFTP (SFTP-tjeneste) — bekræft pr. maskine med
`lsof` før nogen TimeLapse-tjeneste antages at kunne bruge porten. TimeLapse's egne sftp_*-brugere
er blokeret via Match-regler på `rd`, men admin-SSH-adgang må ikke være en uklassificeret public
produktionsflade nogen steder.
**Anbefaling:** Flyt admin SSH til non-standard administrativ kanal eller bag VPN/IP-allowlist
(Cloudflare Access er en valgfri ekstra mulighed, men Tunnel-produktet indgår ikke i den besluttede
arkitektur). Aktiver fail2ban. Brug ikke TCP/22 til TimeLapse SFTP — brug 22222 (se §4 i
PORT_AUDIT-dokumentet).

#### VPEN-2026-003 — Secrets i LaunchAgent plist-fil
**Prioritet:** P2
**Beskrivelse:** JWT_SECRET og BREAK_GLASS_ENC_KEY er sat i LaunchAgent-plist-filen på disk i plaintext. Filen kan læses af root og peter.
**Anbefaling:** Migrer til macOS Keychain eller krypteret secrets-fil med passphrase. Acceptabelt i lab.

#### VPEN-2026-004 — ESLint-gæld (222 fejl/advarsler tilbage, ned fra 271)
**Prioritet:** P2 (blocker for production release)
**Beskrivelse:** Frontend-lint fejlede med 271 problemer (2026-07-04). Dette skjuler potentielle regressions og sikkerhedsproblemer.
**Status 2026-07-04 (nat, Claude):** 49 mekaniske/sikre fejl rettet (ubrugte imports/variable, tomme blokke, ternary-som-udtryk) — bevidst IKKE rørt: 154 `no-explicit-any` (kræver typedesign), 34 `react-hooks/static-components` + 18 `exhaustive-deps` + 9 `set-state-in-effect` + 1 `purity` (kræver manuel vurdering pr. sted for at undgå adfærdsændringer/render-loops). Se `HANDOVER_LOG.md` for fuld liste.
**Anbefaling:** Indfør lint-gate i CI. Triage og fix resten i overvågede batches — IKKE automatisk/uovervåget, da flere kategorier (særligt `exhaustive-deps`) kan introducere regressions hvis rettet blindt.

#### VPEN-2026-005 — Open WebUI uden klar prod/lab-rolle
**Prioritet:** P2
**Beskrivelse:** OpenWebUI er ikke kørende. Knap i UI peger på den. Rollestatus er uafklaret.
**Anbefaling:** Beslut prod vs. lab. Hvis prod: launchd service, health-check, RBAC via nginx auth_request.

#### VPEN-2026-006 — GCP Service Account secret i repo-struktur
**Prioritet:** P1
**Beskrivelse:** `secrets/gcp-service-account.json` er utracked af Git (gitignore), men filen eksisterer på disk med private_key.
**Anbefaling:** Rotér nøglen med jævne mellemrum. Dokumentér hvem der har adgang. Aldrig vis/log private_key.

#### VPEN-2026-007 — Captures AI backlog uden retention-politik
**Prioritet:** P2/GDPR
**Beskrivelse:** 25.574 captures, heraf 2.535 uden AI-analyse og 3.033 uden tags. Ingen retention policy implementeret.
**Anbefaling:** Retention policy i DB pr. camera. Adgangslog pr. billede/download.

#### VPEN-2026-008 — AI Ops' SAST-snapshot talte tredjeparts-bibliotekskode med som egne signaler (NY, fundet + rettet 2026-07-05, Claude periodisk tjek)
**Prioritet:** P2 (dataintegritet i GRC-evidens, ikke selv en sårbarhed)
**Beskrivelse:** `_aiops_static_scan()` i `headend/main.py` (grundlaget for VPEN-006's "73 SAST-signaler") sprang kun stier over ved et EKSAKT match på en hel path-del (`venv`, `node_modules` osv.). Den lokale, `.gitignore`'ede mappe `artifacts/edge-qa-training/.venv-edge-qa-train-py312/` indeholder et komplet vendored virtualenv (sympy, onnxruntime, onnx, fsspec, networkx, packaging m.fl.) fra en tidligere trænings-kørsel — ikke committet til Git, men til stede på disk. En reproduktion af scanneren i denne runde viste at 72 af 80 (scannerens hårde loft) rapporterede "signaler" reelt kom fra denne tredjeparts-kode, ikke fra TimeLapse Pro. Værre: fordi scanneren stopper ved 80 fund og traverserer dybde-først, blev loftet brugt op af denne støj FØR resten af repoet (inkl. `headend/main.py` selv) nåede at blive scannet — så den tekst der reelt vises for et menneske i AI Ops-cockpittet kunne mangle rigtige fund fra vores egen kode.
**Rettet (kode + tests):** Skip-logikken er udtrukket til en ren funktion `_aiops_scan_should_skip_path()`, som nu også springer `artifacts/` (eksakt topniveau-match), enhver sti-del der starter med `.venv`, og enhver sti-del der indeholder `site-packages`/`dist-packages` over. 6 nye kontrakt-tests i `headend/tests/test_aiops_static_scan.py` (inkl. det konkrete tilfælde ovenfor samt regressionstests for at rigtig produktkode, fx `headend/main.py`, `claude_proxy.py`, fortsat scannes). Hele test-suiten kørt i midlertidig venv: **29/29 bestået** (23 eksisterende + 6 nye).
**Konsekvens for VPEN-006:** Efter rettelsen viser en reproduktion at scanneren nu rammer det samme 80-punkts loft udelukkende med signaler fra egen kode (mest `headend/main.py`: `subprocess.run`/`unlink`/`rmtree`-kald i backup-, thumbnail- og docker-relateret driftskode). Det betyder VPEN-006's underliggende antal reelt formentlig ER STØRRE end de oprindelige "73" (som var domineret af støj), ikke mindre. Selve triagen (kategorisering i accepted safe pattern / needs guardrail / needs test / needs change ticket, jf. den oprindelige VPEN-006-anbefaling) er IKKE udført i denne runde — det er et betydeligt, separat arbejde der kræver gennemgang af hvert enkelt fund, og bør ikke forceres igennem overfladisk i en 20-minutters periodisk kørsel.
**Ikke gjort — bevidst:** Ingen ændring af selve "80 fund"-loftet eller af hvilke filtyper/mønstre der scannes — kun stien der forårsagede falsk støj er rettet. Ingen commit/push (Peter/Codex committer selv, se HANDOVER_LOG).

#### VPEN-2026-009 — Første reelle triage-batch af VPEN-006's SAST-signaler + endnu en scanner-selvreference fundet og rettet (NY, 2026-07-05, Claude periodisk tjek #18)
**Prioritet:** P2 (dataintegritet i GRC-evidens + triage-fremdrift, ingen af de gennemgåede signaler var reelle sårbarheder)
**Baggrund:** Efter VPEN-2026-008's sti-fix (samme dag) blev en ny reproduktion kørt for at påbegynde selve triagen (kategorisering i accepted safe pattern / needs guardrail / needs test / needs change ticket, jf. VPEN-006's oprindelige anbefaling).
**Ny scanner-selvreference fundet og rettet:** Reproduktionen viste at `_aiops_static_scan()`s egen `patterns`-opslagstabel i `headend/main.py` (linje ~15214-15217) uundgåeligt indeholder sine egne søgeord som bogstavelig tekst (fx `token=`, `subprocess.run`, `unlink(`, `git pull`) — scanneren matchede derfor sin EGEN definition som 4 garanterede selvreferentielle fund ved hver eneste kørsel, ét pr. kategori, helt uafhængigt af resten af repoet (samme grundmønster som VPEN-2026-008, men en anden årsag). **Rettet:** ny hjælpefunktion `_aiops_scan_should_skip_line()` springer linjer med markøren `AIOPS-SCAN-IGNORE-SELF` over; markøren er sat på de 4 pattern-definitionslinjer. Under verifikation blev en anden-ordens variant af samme problem opdaget og rettet: den første udgave af rettelsens egne forklarende kommentarer/docstring gengav søgeordene ordret i prosa (fx "fx `token=`"), hvilket fik scanneren til at flage selve fix'ets dokumentation som 3 NYE selvreferentielle fund. Kommentarerne er omskrevet til at beskrive mønsteret uden at gengive de faktiske søgeord — en advarsel til fremtidige vedligeholdere om præcis denne faldgrube er tilføjet i docstringen.
**Ny test:** `headend/tests/test_aiops_static_scan.py` udvidet med 3 nye tests — 2 rene funktionstests af `_aiops_scan_should_skip_line()`, samt én regressionstest der kører den fulde `_aiops_static_scan()` mod det virkelige repo og bekræfter at ingen fund indeholder opslagstabellens egne kategori-nøgler som snippet-tekst. Hele test-suiten: **32/32 bestået** (29 eksisterende + 3 nye), `py_compile` ren.
**Effekt:** `finding_count` rammer stadig det hårde 80-punkts loft (uændret), men `files_scanned` steg fra 39 til 40 og de 4 pladser der tidligere gik til scannerens egen kode går nu til reelle, andre findings — en lille, men reel forbedring af signalkvaliteten.
**Triage af tre kategorier (56 af 80 aktuelle signaler), efter fixet ovenfor:**
- **`hardcoded_secret_terms` (10 signaler) — alle false positive.** Samtlige gennemgået i kildekoden: hvert fund er en variabel-/kwarg-reference (`token=req.bootstrap_token`, `wifi_password=wifi_password`, `.filter_by(token=token)` osv.), aldrig en bogstavelig streng-literal med et faktisk hemmeligt indhold. Mønsteret matcher enhver `ord=`-tildeling uafhængigt af højresiden, så det kan strukturelt ikke skelne en variabel-reference fra en hardcoded værdi. **Anbefaling (lav prioritet, IKKE udført):** forbedre heuristikken til kun at flage når højresiden ligner en streng-literal (fx `token="..."` eller `token='...'`), hvilket ville eliminere denne kategoris falske-positiv-rate uden at miste reel dækning.
- **`shell_execution` (40 signaler) — 1 reel opmærksomhedspunkt, resten false positive/lavrisiko.** 39 af 40 er `subprocess.run`/`subprocess.check_output`-kald med en liste af argumenter (ikke en sammensat streng) og UDEN `shell=True` — denne form er strukturelt immun over for shell-injektion uanset indholdet af argumenterne. Nøjagtig ét sted i hele det scannede repo bruger `shell=True` med et fuldt dynamisk kommando-indhold: `claude_proxy.py` linje 40-41 — et lokalt, ikke Git-sporet, netværksfrit udviklingsværktøj (fil-baseret IPC: læser en kommando fra `.claude_proxy/cmd_in.json` og eksekverer den via shell). Dette er bevidst design (et generelt kommando-eksekveringsværktøj), ikke en kodefejl — men det er reelt et lokalt "kør vilkårlig kommando"-værktøj, og risikoen afhænger fuldt ud af filrettighederne på `.claude_proxy/`-mappen. **Anbefaling (til Peter, ikke hastende):** bekræft at `.claude_proxy/` har restriktive filrettigheder (ikke skrivbar for andre lokale brugere/processer), og overvej om værktøjet bør slettes/flyttes uden for repo-roden når det ikke er aktivt i brug, netop fordi det ikke er en del af det leverede produkt.
- **`legacy_update_paths` (5 signaler) — alle kendte, accepterede mønstre, ingen nye fund.** `deploy/edge_update.sh` er eksplicit gated bag `TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE` (default fra, jf. VPEN-005, allerede kendt/dokumenteret). `deploy/headend_poller.sh`s `git pull origin main` er selve den eksisterende, accepterede deployment-mekanisme for headend (ikke en "legacy" sårbarhed — scanneren kan strukturelt ikke skelne produktions-deploy-git-pull fra et sikkerhedsproblem). `e2e_test.sh`s to `git pull`-linjer er dev/test-tooling til at synkronisere kode til en test-edge-enhed. Ingen ændring anbefalet.
- **`dangerous_file_ops` (24 signaler) — triageret 2026-07-05, periodisk tjek #19. Alle 24 gennemgået enkeltvis; ingen reelle sårbarheder.** Fordeling: 18 i `headend/main.py`/`headend/itim.py` (temp-fil-oprydning efter upload-SHA-mismatch, backup-arkivering, thumbnail-generering, storage-writable-probes, capture/bulk-delete) — alle er `unlink(missing_ok=True)`/`try/except`-beskyttet oprydning af kendte, ikke-brugerkontrollerede sti-mønstre (faste probe-/tmp-navne, `NamedTemporaryFile`, `.thumbs`/`.headend-thumbs`), eller kører bag `require_role("admin")` + `_find_image()`s glob-baserede opslag mod fastlagte storage-roots (filnavne saniteres allerede ved indlæsning via `_sanitize_filename()`/`_sanitize_device_id()`, som eksplicit afviser `..`/`/`/`\\`, så path traversal via `capture.filename` kan strukturelt ikke opstå). 3 i `headend/tools/fetch_os_bundle.py`/`build_edge_disk_image.py` er admin-kørte offline build-CLI'er (`argparse`), ikke web-eksponerede — `rmtree`/`unlink` rammer kun værktøjets eget, eksplicit angivne output-/tmp-directory. 1 i `headend/tools/backfill_thumbnails.py` er samme mønster (tmp-fil-oprydning ved thumbnail-regenerering). 1 i `headend/tools/inject_wifi_image.py` er faktisk et `chown`/`chmod`-fund (ikke unlink/rmtree) inde i en indlejret bash-heredoc der kører INDE I et loop-mountet OS-image under offline disk-image-bygning — sætter restriktive rettigheder (700/600) og faste UID'er (0 for root, 1000 for standardbruger) på `.ssh`, dvs. gør adgangen STRAMMERE, ikke løsere; ingen risiko. De resterende 3 (`claude_proxy.py`) er samme lokale, ikke-Git-sporede udviklingsværktøj som allerede flagget under `shell_execution` ovenfor — unlink af værktøjets egne state-filer (`cmd_in.json`, lockfil), ingen ny risiko ud over den allerede noterede.
**Konklusion for VPEN-006:** Alle 4 kategorier (80/80 signaler) er nu triageret på tværs af de to runder (periodisk tjek #18 + #19). Ingen af de 80 aktuelle SAST-signalerne udgør en bekræftet, reel sårbarhed. Det ene reelle opmærksomhedspunkt (`claude_proxy.py`s `shell=True`, se ovenfor) er ikke en kodefejl i produktet, men et lokalt dev-værktøj hvis risiko afhænger af filrettigheder Peter bør bekræfte. VPEN-006/§11 P2.4 kan nu markeres som **triage afsluttet, ingen fund kræver kodeændring** — se opdateret §11 P2.4.
**Verifikation:** Ingen ny kode ændret denne runde (ren gennemgang/triage af eksisterende, allerede committede findings) — derfor ingen ny test nødvendig. `_aiops_static_scan()` genkørt i samme midlertidige venv/sqlite-opsætning som tidligere runder for at hente den aktuelle, fulde `dangerous_file_ops`-liste (24/24 gennemgået mod faktisk kildekode med `sed`/`grep`, ikke kun snippets).
**Ikke gjort — bevidst:** Ingen kodeændring foretaget (ingen fund krævede det). Den lave-prioritets forbedring af `hardcoded_secret_terms`-heuristikken (kun flage streng-literaler) fra periodisk tjek #18 er fortsat ikke implementeret — bevidst, lav prioritet. Ingen commit/push nødvendig (ingen filer ændret ud over denne dokumentation + HANDOVER_LOG).

**Verifikation (VPEN-2026-009, kodefix-delen):** `python3 -m py_compile main.py database.py tests/test_aiops_static_scan.py` ren. `pytest tests/` (hele `headend/tests/`): **32/32 bestået**. Kørte `_aiops_static_scan()` direkte to gange (før/efter fix) for at bekræfte at ingen fund længere refererer scannerens egen opslagstabel-definition. `git diff --stat` bagefter: kun `headend/main.py` (+32/-5) og `headend/tests/test_aiops_static_scan.py` (+42/-1) ændret.
**Ikke gjort — bevidst (kodefix-delen):** Ingen ændring af det hårde 80-fund-loft. Ingen commit/push (Peter/Codex committer selv).

---

## 6. IEC 62443 zone-model (opdateret)

```
Zone 0: Public internet
  ↕ Conduit: nginx (direkte TLS-termination — port 443/80 på rd, port 8443 på staging/prod)
Zone 1: DMZ / Reverse proxy (nginx)
  ↕ Conduit: nginx → uvicorn 127.0.0.1:8000
Zone 2: Headend applikation (FastAPI, PostgreSQL)
  ↕ Conduit: API → Ollama 127.0.0.1:11434
Zone 3: AI/Tooling services (Ollama, OpenWebUI)
  ↕ Conduit: HTTPS/JWT → Edge API
Zone 4: Edge management (Reverse SSH tunnel, update artifacts)
  ↕ Conduit: SFTP port 22222, gphoto2, GPIO
Zone 5: Kamera/relay/lokal enhedsgrænseflade

(Kun på staging/prod, sameksisterende men UDENFOR TimeLapse Pro's zonemodel:)
Zone X: CrushFTP — ejer 21/22/80/443 på disse to maskiner. Ingen conduit mellem
        Zone X og TimeLapse Pro's zoner — adskillelsen er ren portadskillelse,
        ikke en netværksmæssig segmentering (samme OS/vært).
```

**RETTET 2026-07-05 (periodisk tjek #33, derefter igen samme dag efter Peters CrushFTP-
bekræftelse):** Zone 0/1 nævnte oprindeligt "Cloudflare"/"Cloudflare Tunnel" som conduit/reverse-
proxy-lag; det blev først rettet til "direkte nginx-TLS-termination på standard 80/443" — men
DEN rettelse var også ufuldstændig, fordi CrushFTP allerede ejer 80/443 på staging- og
prod-maskinerne (bekræftet af Peter, se `PORT_AUDIT_og_WEBSITE_v10.md` §3). Diagrammet er nu
rettet en 2. gang: `rd` bruger fortsat 80/443 (ingen CrushFTP dér), mens `staging`/`prod` bruger
port **8443** og en ny "Zone X" er tilføjet for at gøre CrushFTP's sameksistens eksplicit i
modellen, i stedet for blot at antage den væk. Cloudflare som ren DNS-proxy/WAF (orange cloud,
ikke Tunnel) foran port 8443 er fortsat en åben, valgfri undervariant (se
`GO_LIVE_CHECKLIST_v10.md` A-11).

**Implementeringsstatus:**
- Zone 0→1: 🟠 nginx/TLS — direkte eksponering på port 8443 endnu ikke bygget på staging/prod (se GO_LIVE_CHECKLIST §A-01–A-03/A-13); TLS-konfiguration i sig selv OK i `rd` (standard 80/443, ingen CrushFTP-konflikt dér)
- Zone 1→2: ✅ reverse proxy
- Zone 2→3: 🟡 Ollama intern, OpenWebUI nede
- Zone 2→4: ✅ JWT/HMAC; stale credentials
- Zone 4→5: ✅ gphoto2/GPIO

**TILFØJELSE 2026-07-05 (Claude, Peters miljøafklaring) — miljø-zoner (ortogonalt lag):**
Zonemodellen ovenfor beskriver netværkslag INDENFOR ét kørende system. Peter har nu bekræftet en
separat, ortogonal zone-dimension: tre FYSISK adskilte miljøer — `rd` (nuværende Mac Mini,
`timelapse.froekjaer.dk`), `staging` (planlagt, 3. server/iMac, software-parity med prod) og
`prod` (planlagt, helt andet fysisk system, `timelapsepro.dk` — kører allerede i dag CrushFTP med
live kundedata + det legacy-system TimeLapse Pro skal erstatte). Se
`MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` for fuld beskrivelse og R19 for risikovurderingen af
agent-adgang på tværs af disse miljøer. IEC 62443-anbefaling: behandl `rd`↔`staging`↔`prod` som en
zone-grænse på linje med (ikke underordnet) zonerne 0-5 ovenfor — specifikt bør ingen conduit
(secret, credential, netværksrute) krydse `prod`-grænsen for agent-brug, uanset hvor godt de
interne zoner 0-5 er implementeret på selve prod-systemet.

---

## 7. CRA-vurdering (Cyber Resilience Act)

| CRA-krav | Status |
|---|---|
| Secure by design/default | 🟡 Delvist — RBAC, auth, signed updates; MFA/CA mangler |
| Vulnerability handling | 🟡 — SAST backlog, ingen formaliseret CVE-process |
| Security update mechanism | 🟡 — Offline artifact-model virker i lab; prod E2E mangler |
| SBOM | 🟡 — SBOM-felter i update-model; ikke automatisk genereret |
| Technical documentation | 🟡 — Dokumentation foreligger; ikke struktureret som CRA-evidenspakke |
| Lifecycle support commitment | 🔴 — Supportperiode ikke erklæret |
| Reproducible builds | 🟡 — Artifact-build er reproducerbar for app; OS bundle strikt |
| No direct internet update from device | ✅ — Edge bruger Headend som update authority |

---

## 8. NIS2-vurdering

NIS2 gælder potentielt for kritisk infrastruktur og vigtige tjenester. TimeLapse Pro er ikke NIS2-pligtigt som produkt, men kunder i bygge-, anlægs- og infrastruktursektoren kan have NIS2-forpligtelser, der stiller krav til leverandører.

| NIS2-kontrolområde | Status |
|---|---|
| Risk management (Art. 21) | 🟡 — Risikovurdering dokumenteret; behandlingsplan mangler ejere/deadlines |
| Supply chain security | 🟡 — Signed artifacts; subprocessor-liste mangler |
| Incident handling & reporting | 🔴 — Incident response procedure ikke dokumenteret |
| Business continuity | 🔴 — Backup/restore-test mangler |
| Security in network & systems | 🟡 — Se zonemodel ovenfor |
| Access control | ✅ — RBAC implementeret |
| Cryptography | 🟡 — TLS/JWT/GPG OK; intern CA mangler |
| Human resources security | 🔴 — Ikke formaliseret |
| Asset management | 🟡 — CMDB virker; node-agent nede |

---

## 9. GDPR-vurdering

| GDPR-artikel | Krav | Status |
|---|---|---|
| Art. 25 — Privacy by design | Data protection by default | 🟡 Delvist |
| Art. 32 — Sikkerhed | Tekniske og organisatoriske foranstaltninger | 🟡 Delvist |
| Art. 33/34 — Brudnotifikation | Procedure ved databrud | 🟠 Anbefalet (G-06) — udkast/anbefaling foreligger, ikke en fuld, godkendt procedure |
| Art. 35 — DPIA | Billedovervågning med høj risiko | 🟠 Skabelon klar (G-01, 2026-07-04) — mangler udfyldelse pr. kunde/site + juridisk godkendelse |
| Art. 28 — Databehandleraftale | Aftale med Peter/TimeLapse Pro | 🟠 Delvist (G-03) — Kirkbi A/S (Site Travbyen) har en eksisterende aftale, dækning mod faktisk nuværende behandling (AI/Gemini, GPS) og agent-adgang er ikke verificeret; fortsat 🔴 for nye kunder |
| Art. 13/14 — Oplysningspligt | Information til registrerede | 🟠 Skitse-tekst klar (G-07, 2026-07-04) — kræver juridisk godkendelse |
| Retention | Opbevaringsbegrænsning | 🔴 Design klar (G-02, 2026-07-04) — IKKE implementeret i kode endnu |
| Adgangslog | Log pr. billede/download | ✅ Implementeret og testverificeret 2026-07-05 (G-05) — `CaptureAccessLog` + `_log_capture_access()`, 4/4 + 41/41 tests bestået |
| Subprocessorer | Google Cloud/Gemini, evt. andre | 🟡 Udkast-liste klar (G-04, 2026-07-04 nat) — ikke juridisk bekræftet/offentliggjort |

**Anbefaling:** Inden første rigtige produktionssite:
1. DPIA-template udfyldes pr. kunde/site + juridisk godkendes (skabelon findes, se `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`)
2. Retention policy implementeres i kode pr. kamera (design findes)
3. ~~Download/adgangslog implementeres~~ — implementeret 2026-07-05
4. Databehandleraftale-template færdiggøres og bruges til nye kunder (Kirkbi A/S er allerede dækket)

**TILFØJELSE 2026-07-05 (Claude, periodisk tjek #31, docs-sync):** Tabellen ovenfor var kommet
bagud ift. `GO_LIVE_CHECKLIST_v10.md` §G (G-01 til G-07) og `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`
— 6 af 9 rækker viste stadig blankt "🔴 Mangler"/"Ikke dokumenteret", selvom skabeloner/udkast er
skrevet siden 2026-07-04, og Adgangslog-rækken var slet ikke opdateret efter G-05 blev
implementeret og testverificeret 2026-07-05. Ingen NY information tilføjet her — ren
sammenkøring med allerede eksisterende, dateret status fra §11 P0 #3, G-01–G-07 og
`DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`. Ingen kode rørt.

---

## 10. Samlet risikooversigt

| Risk | Score | Trend siden v6 |
|---|---|---|
| R01 SFTP data-adskillelse | 🟢 4 | ↓↓ Løst |
| R02 UI adgangskontrol (MFA mangler) | 🟡 6 | ↓ Forbedret |
| R03 Hardware-historik | 🟢 3 | ↓↓ Løst |
| R04 Remote adgang | 🟢 3 | ↓↓ Løst |
| R05 Kompromitteret edge | 🟠 8 | → Uændret |
| R06 Opdateringsfejl | 🟡 6 | ↓ Forbedret, IKKE 🟢 — flush-regression rettet/deployet 2026-07-05, men holdes på 🟡 indtil live multi-device-rollout er verificeret OG device-decommission-midt-i-rollout-gap'et er besluttet (se R06-detaljer) |
| R07 Nøgle-kompromittering | 🟡 6 | ↓ Forbedret |
| R08 Man-in-the-middle | 🟡 6 | ↓ Forbedret |
| R09 Backup | 🟠 8 | → Uændret |
| R10 SSH tunnel misbrug | 🟢 2 | ↓ Løst |
| R11 CMDB anonym adgang | 🟢 3 | ✅ Ny/løst |
| R12 GDPR-evidens | 🟠 12 | 🆕 Ny |
| R13 Node-agent nede | 🟡 6 | 🆕 Ny |
| R14 Nikon Z30 config drift | 🟠 12 | ↓ Delvist rettet 2026-07-05 (detektionsmekanisme + UI-visning + en uafhængig diagnostics-bug rettet), ikke live-verificeret på hardware |
| R15 SIEM uden auth + MFA-gab CMDB/ITIM | 🟢 4 | ✅ Ny/løst — fundet og rettet, live-verificeret 2026-07-03 |
| R16 Kryds-kunde-lækage ved Edge-gentildeling | 🟢 4 | ✅ Ny/løst — fundet, rettet og backfillet komplet i produktion 2026-07-03 |
| R17 Debug/lab mode uden overvågning | 🟢 (deployet) | ↓ Rettet 2026-07-05, committet (`44b78fb7`) og deployet af Codex, health 200 + `npm run build` OK; manuel UI-smoketest (aktiver/deaktiver + auto-timeout) fortsat ikke kørt |
| R18 Manglende gdpr_manager.py crashede Gemini-godkendelse | 🟢 3 | ✅ Ny/løst — fundet og rettet 2026-07-04, GDPR-dele af R12 uændret åbne |
| R19 Agent-adgang til fremtidig prod-fysisk-system ikke formelt udelukket | 🟡 5 | → Uændret 2026-07-06 — default-deny-politik bekræftet, nu uddybet med en godkendt (men ikke bygget) kontrolleret break-glass-undtagelsesvej, se `Claude_Support_Access_Model_2026-07-06.md`; teknisk håndhævelse af default-deny (defense-in-depth) mangler stadig |

**Kritiske/blokkerende risici for go-live (Internet):** R05, R09, R12, nginx port-eksponering (VPEN-2026-001, opdateret målarkitektur 2026-07-05 — se GO_LIVE_CHECKLIST §A). R16 er fuldt lukket (kode + deploy + backfill). R19 er nedjusteret men ikke fuldt lukket.

---

## 11. Prioriteret risikobehandlingsplan

### 🔴 P0 — Blokkerer production/Internet-eksponering
1. **Opdateret 2026-07-05 (Peters arkitekturbeslutning, 2. korrektion samme dag):** ~~Migrer
   nginx væk fra public 80/443 → Cloudflare Tunnel~~ — udgår, Cloudflare Tunnel er IKKE
   prod-målarkitekturen. ~~Direkte nginx-eksponering på standard 443/80~~ — udgår OGSÅ for
   staging/prod, fordi CrushFTP allerede kører på begge disse fysiske maskiner og ejer 21/22/80/443
   (bekræftet af Peter). Faktisk krav er i stedet: **direkte nginx-eksponering på port 8443** med
   gyldigt Let's Encrypt-certifikat udstedt via **DNS-01** (`certbot-dns-cloudflare`, rører ingen
   port), hostname-baseret routing og fail2ban/rate-limiting som kompenserende kontrol (ingen
   Cloudflare-edge til at absorbere scanning/DDoS, medmindre Cloudflares valgfrie DNS-proxy
   aktiveres foran 8443 senere). Marketingsitet hostes separat fra disse maskiner. Se
   `GO_LIVE_CHECKLIST_v10.md` §A (A-01–A-04/A-13, korrigeret 2026-07-05) og
   `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 for den fulde begrundelse.
2. Backup + restore-test dokumenteret (R09)
3. DPIA-template + retention policy (R12)
4. Node-agent genetableret (R13)
5. HMAC enforcement globalt — stale credentials migreret/afviklet
6. Bekræft/håndhæv nul agent-adgang til det fremtidige prod-fysiske-system (R19) — bør behandles
   som gældende FRA NU, ikke først ved cutover, da maskinen allerede kører live kundedata via
   CrushFTP/legacy-systemet. Se `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md`. **Delvist fremskridt
   2026-07-06 (periodisk tjek #84):** forudsætningen fra #65 (`TIMELAPSE_ENV`-terminologi-drift,
   se R19-detaljeafsnittet) er nu rettet i `edge/agent.py` og `headend/siem.py` (tilføjet `"rd"`
   som synonym til `lab`/`dev`/`development`). **Committet, merget og deployet 2026-07-06
   (Peter):** via PR #1 (`claude/capture-camera-location-2026-07-03` → `main`), CI grøn,
   `deploy-macmini`-jobbet genstartede rd-headend — faldgruben er dermed reelt lukket på rd,
   ikke kun rettet i working tree (se R19-detaljeafsnittet for fuld sporing). **Selve
   `AgentPrincipal`/miljøflag-håndhævelsen (M-05, "layer 2" — env-flag + hård afvisning i
   `/api/auth/login` og `get_current_user()`) er nu KODET 2026-07-06 (Claude, Peter bad
   eksplicit om at fortsætte mens Codex var utilgængeligt)** — se R19-detaljeafsnittet for fuld
   implementeringsdetalje. 15 nye pytest-tests skrevet (`headend/tests/test_agent_principal_
   lockdown.py`), men **IKKE kørt/committet/merget/deployet endnu** (afventer Peters
   `py_compile`+pytest-bekræftelse, samme mønster som #84/#85). Bevidst kun trin 2 af 5 i den
   oprindelige byggerækkefølge — det fulde `AgentPrincipal`/`AgentToken`/`AgentElevationGrant`-
   skema (trin 3) er en separat, større, endnu ikke påbegyndt beslutning. Blokkeren nedjusteres
   IKKE til lukket, før test+deploy er bekræftet.

### 🟠 P1 — Skal lukkes inden første rigtige kunde-site
1. MFA/WebAuthn til admin-login (R02)
2. Intern CA + device client certs (R05, R07, R08) — design-notat FÆRDIGT
   (`Claude_Intern_CA_mTLS_Design_2026-07-05.md`), alle 4 åbne designspørgsmål besvaret af Peter
   2026-07-05 (Model B, 10-års konfigurerbar cert-levetid, permanent HMAC+mTLS, retrofit af
   eksisterende R&D-device) — ingen blockers tilbage, kodefasen kan påbegyndes som ny, afgrænset
   opgave (auth-nær, kræver ekstra dobbelttjek, bevidst ikke startet i denne session)
3. Nikon Z30 config-model — desired state + accepted equivalents (R14); detektion + UI-visning
   af non-enforceable parametre er nu på plads (2026-07-05), resterer kun live-verifikation på
   hardware og en eksplicit beslutning om aperture/shutter_speed-drift-mål (rådgivende SABSA-
   anbefaling givet 2026-07-06, periodisk tjek #64 — se R14-detaljeafsnittet: opt-in pr. enhed,
   IKKE fleet-baseline; kræver profil-bevidst gphoto2-sti-læsning, ikke implementeret endnu)
4. **Per-target deployment status (update-flow) — flush-regression fundet OG rettet, kun
   live-test resterer:** data/API/UI fandtes allerede; rest-bug'en fra P1.4 (global status
   flippet af ét device-report i multi-target rollouts) blev rettet i kode 2026-07-05 (Claude),
   committet/pushet af Codex (`61802951`) og deployet — men den deployede rettelse manglede selv
   en `db.flush()` (fundet 2026-07-05, Claude, via en rigtig kontrakttest,
   `headend/tests/test_report_update_rollup.py`), så multi-target rollouts i stedet hang fast på
   "approved" for evigt. Denne flush-regression er nu OGSÅ committet/pushet af Codex (`1e3c3321`,
   samme commit som H-05-testene) og deployet — headend genstartet, `/api/health` 200 OK,
   13/13 tests bestået (2026-07-05 nat). Nedjusteret fra P0 til P1 — se R06,
   `SYSTEM_HEALTH_REGISTER.md` HLTH-008. Eneste resterende del: en faktisk live multi-device
   rollout-test (2+ enheder, `scope=site`) der bekræfter reel flip til deployed/rolled_back
5. ~~ESLint-gate i CI~~ — ratchet-gate implementeret 2026-07-05 (fejler kun ved FLERE
   problemer end baseline 222, kræver ikke oprydning af eksisterende problemer først), committet/
   pushet af Codex (`68805577`). Resterer kun: bekræfte at GitHub Actions-runneren faktisk viser
   det nye "ESLint gate"-step grønt ved næste push/PR

### 🟡 P2 — Production hardening
1. Disk-kryptering på Edge (R05)
2. Off-site backup (R09)
3. ~~GDPR adgangslog pr. billede~~ — implementeret og testverificeret 2026-07-05 (ny
   `CaptureAccessLog`-tabel + `_log_capture_access()`, kaldt fra
   `GET /api/images/{device_id}/{filename}`, kun fuldopløsningsbilledet, ikke thumbnails);
   Codex kørte 4/4 + 41/41 tests grønt og har committet/pushet. Se `GO_LIVE_CHECKLIST_v10.md`
   §G-05.
4. ~~SAST backlog triage (73 signaler)~~ — **Triage afsluttet 2026-07-05 (periodisk tjek #19).**
   Selve tallet "73" var oprindeligt upålideligt (scanneren talte vendored tredjeparts-
   bibliotekskode og sin egen pattern-opslagstabel med som egne signaler, se VPEN-2026-008/-009);
   begge scanner-fejl er rettet og testdækket (32/32 bestået). Alle 4 kategorier af de 80
   aktuelle signaler er nu gennemgået enkeltvis — `hardcoded_secret_terms` (10),
   `shell_execution` (40), `legacy_update_paths` (5) og `dangerous_file_ops` (24). **Ingen
   bekræftede reelle sårbarheder.** Ét opmærksomhedspunkt til Peter (ikke hastende): bekræft
   restriktive filrettigheder på `.claude_proxy/` (lokalt, ikke Git-sporet dev-værktøj med
   `shell=True` mod fil-baseret IPC — se VPEN-2026-009). **Opfølgning 2026-07-05 (periodisk
   tjek #20, Claude):** den noterede men ikke-udførte `hardcoded_secret_terms`-heuristik-
   forbedring er nu implementeret — ny `_aiops_scan_is_secret_value_literal()` kræver at
   højresiden af tildelingen ligner en bogstavelig streng-literal (starter med `'`/`"`) før
   linjen flages; rene variabel-/kwarg-referencer (fx `token=req.bootstrap_token`,
   `wifi_password=wifi_password` — dvs. netop det mønster alle 10 tidligere false positives
   i denne kategori havde) tælles ikke længere med. 5 nye tests i
   `headend/tests/test_aiops_static_scan.py` (14/14 bestået i kategorien, 37/37 i hele
   `headend/tests/`-suiten). Reproduktion efter fix: `hardcoded_secret_terms` bidrager nu 0
   fund (var 10); det uændrede 80-fundsloft betyder de frigjorte pladser i stedet dækker flere
   reelle filer (`files_scanned` steg fra 40 til 48 i denne reproduktion) — ingen nye reelle
   fund i de øvrige 3 kategorier som følge heraf. Ingen kodeændring i selve scan-logikkens
   øvrige kategorier eller i det hårde loft.
5. Secrets → macOS Keychain
6. AI resource governor + Ollama beslutning
7. ~~CMDB-indikator/auto-timeout for debug/lab mode pr. enhed (R17)~~ — kode deployet
   2026-07-05, kun manuel smoketest udestår (se R17 ovenfor)

---

## 12. Dokumenthistorik

| Version | Dato | Vigtigste ændringer |
|---|---|---|
| 1.0–5.0 | apr 2026 | Initial assessments, Sprint A–C |
| 6.0 | maj 2026 | RBAC, SSH tunnel, Camera/Pi-kobling, intern PKI-plan |
| Pentest | maj 2026 | 73 SAST signals, key lifecycle gaps, backup gaps |
| QA | jun 2026 | CMDB lukket, OS bundle fix, HMAC enforced |
| SABSA reassessment | jun 2026 | Storage path fix, node-agent nede, go/no-go |
| **7.0** | **jun 2026** | **Konsolideret — alle fund, alle statusser, ny GDPR/NIS2/CRA-sektion, port-gaps** |
| 10 (tilføjelse) | 2026-07-04 | Claude: R17 (debug/lab mode uden overvågning, fundet ifm. GPS-fejlsøgning) tilføjet; R12 udvidet med GPS/lokationsmetadata-note |
| 10 (tilføjelse) | 2026-07-05 | Claude (periodisk tjek): R14 — fundet og rettet at config-drift-detektion reelt var inaktiv (key-mismatch + FLEET_DEFAULTS blev erstattet, ikke merged); rettelse verificeret isoleret, IKKE på live hardware |
| 10 (tilføjelse) | 2026-07-05 (nat) | Claude (periodisk tjek, docs-sync): R17 opdateret fra "rettet i kode, ikke deployet" til "deployet af Codex, health+build OK, kun manuel smoketest udestår" — dokumentet var kommet bagud ift. HANDOVER_LOG efter Codex' deploy-verifikation |
| 10 (tilføjelse) | 2026-07-05 01:28 | Claude (periodisk tjek): §13.3 og §11 P1.2 opdateret med henvisning til nyt design-notat `Claude_Intern_CA_mTLS_Design_2026-07-05.md` (#52) — intern CA/mTLS-arkitektur, ingen kode rørt, afventer Peters valg mellem Cloudflare Access mTLS og ende-til-ende-model |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #4) | Claude: R14 UI/CMDB-visning af `camera_config_non_enforceable` implementeret (ny DB-kolonne + selvhelende v14-migration + frontend-info-boks); undervejs fundet og rettet en uafhængig, reel bug — `get_device_detail` returnerede aldrig "diagnostics"-nøglen, så hele Hardware/Kamera-diagnostik-panelet har vist tomt for alle enheder siden ~15. april |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #6) | Claude: R06/HLTH-008/UPD-012 "per-target deployment status" — fandt at data/API/UI faktisk allerede fandtes siden juni 2026 (dokumenterne var forældede); rettede den reelle rest-bug: global `PendingUpdate.status` blev sat af ét device-report i multi-target rollouts. Rettet i kode, verificeret isoleret, afventer commit/push + live-test |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #7, docs-sync) | Claude: §11 P1.4/P1.5, R06 og §12 opdateret — Codex har siden committet/pushet/deployet HLTH-008-fixet (`61802951`, headend genstartet, health 200 OK) og H-02 ESLint-gaten (`68805577`); dokumenterne var kommet bagud. Kun live multi-device-rollouttest (P1.4) og bekræftelse af grøn GitHub Actions-kørsel (H-02/P1.5) resterer nu |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #8) | Claude: skrev en rigtig kontrakttest (`headend/tests/test_report_update_rollup.py`) mod den faktiske `report_update()`-kode (SQLite, ikke simulering) — startpunkt for GO_LIVE_CHECKLIST H-05. Testen afslørede en REGRESSION i den allerede deployede `61802951`-fix: manglende `db.flush()` betød at multi-target rollouts aldrig flippede til deployed/rolled_back, selv når alle devices var terminale (P1.4/R06/HLTH-008 genåbnet til P0). 1-linjes rettelse lavet og testverificeret (4/4 passed), IKKE committet/deployet endnu |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #11, docs-sync) | Claude: R06/§11 P1.4, `SYSTEM_HEALTH_REGISTER.md` HLTH-008/HLTH-015, `GO_LIVE_CHECKLIST_v10.md` H-05/H-06/§K og `KRAVREGISTER_og_STATUS_v10.md` UPD-012 opdateret — Codex har siden committet/pushet/deployet flush-rettelsen (`1e3c3321`, inkl. H-05-testene, 13/13 bestået) og README-oprydningen (`9dda9923`, H-06), samt genstartet headend og bekræftet health 200 OK (se HANDOVER_LOG "nat"-entry). Dokumenterne sagde stadig "IKKE committet endnu" og var dermed kommet bagud. R06/HLTH-008/UPD-012 nedjusteret fra P0/🟠 til P1/🟡 (kode er live, kun live multi-device-rollout-test resterer nu); HLTH-015 lukket ✅ |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #12) | Claude: bekræftede at forrige rundes docs-sync (P1.4/HLTH-008/H-05/H-06/UPD-012) er committet af Peter/Codex som `c7d409cb` — ingen uncommittede docs-ændringer længere. Fandt derefter et separat, uafhængigt stale-doc-fund i `GO_LIVE_CHECKLIST_v10.md` H-04 (ikke i denne fil): repo-plisten for headend var allerede omlagt til en secret-fri system-LaunchDaemon-version (`deploy/launchd/macos/dk.froekjaer.timelapse-headend.plist`, committet 2026-07-03 af Codex i `d7a952db`), men checklisten sagde stadig "🟠 Mangler". Rettet — se GO_LIVE_CHECKLIST_v10.md. Ingen ændring nødvendig i denne fil (RISK_ASSESSMENT), da VPEN-2026-003 (P2, plaintext secrets i `/etc/timelapse/headend.env` på disk, Keychain-migration) er en separat, fortsat reelt åben risiko, adskilt fra H-04s Git-hygiejne-scope |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #16) | Claude: formaliserede device-decommission-midt-i-rollout-gap'et i R06 (først fundet/testdokumenteret 2026-07-05 periodisk tjek #9, men aldrig tilføjet til selve risikodokumentet — flere efterfølgende runder havde flagget dette som udestående). Ingen kodeændring; ren dokumentation af en allerede committet, eksisterende kontrakttest samt de tre løsningsmuligheder Peter skal vælge imellem, før kode kan skrives |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #17) | Claude: VPEN-2026-008 (NY) — fandt at AI Ops' SAST-snapshot (grundlaget for VPEN-006/§11 P2.4's "73 signaler") fejlagtigt talte en lokal, gitignore'et vendored virtualenv (`artifacts/edge-qa-training/.venv-edge-qa-train-py312/`, tredjeparts-biblioteker som sympy/onnxruntime) med som egne signaler, og at det hårde 80-fund-loft blev brugt op af denne støj før egen kode blev scannet. Rettet i `_aiops_static_scan()`/ny `_aiops_scan_should_skip_path()`, testdækket (6 nye + 23 eksisterende tests, 29/29 bestået i midlertidig venv). Reel triage af signalerne i egen kode er fortsat udestående — se §11 P2.4 |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #18) | Claude: VPEN-2026-009 (NY) — fandt og rettede endnu en scanner-selvreference (pattern-opslagstabellen matchede sig selv; under verifikation blev også en anden-ordens variant i fix'ets egne kommentarer fundet og rettet), testdækket (3 nye tests, 32/32 bestået). Gennemførte derefter en første triage-batch af VPEN-006's SAST-signaler — `hardcoded_secret_terms`, `shell_execution`, `legacy_update_paths` (56 af 80) — ingen reelle sårbarheder, ét opmærksomhedspunkt (lokalt dev-værktøj `claude_proxy.py`'s `shell=True`). `dangerous_file_ops` (24) resterer til næste runde. Se §11 P2.4 |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #19) | Claude: afsluttede VPEN-006's SAST-triage — gennemgik den resterende `dangerous_file_ops`-kategori (24 signaler) enkeltvis mod faktisk kildekode. Ingen reelle sårbarheder: temp-fil-oprydning bag `try/except`/`missing_ok=True`, admin-gated capture-sletning via saniteret filnavn-opslag (`_sanitize_filename`/`_sanitize_device_id` afviser path traversal), offline admin-CLI-værktøjer (`argparse`, ikke web-eksponeret), og ét `chown`/`chmod`-fund der reelt STRAMMER rettigheder (700/600) på `.ssh` inde i et loop-mountet OS-image. Alle 4 kategorier (80/80 signaler) er nu triageret på tværs af tjek #18+#19 — §11 P2.4 og §2 opdateret til "triage afsluttet". Ingen kodeændring (ingen fund krævede det); ingen commit/push nødvendig |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #20) | Claude: implementerede den i #18/#19 noterede men ikke-udførte `hardcoded_secret_terms`-heuristik-forbedring — ny `_aiops_scan_is_secret_value_literal()` kræver en bogstavelig streng-literal på højresiden før en linje flages, så variabel-/kwarg-referencer (mønsteret bag alle 10 tidligere false positives i denne kategori) ikke længere tælles med. 5 nye tests (`headend/tests/test_aiops_static_scan.py`, 14/14 i filen, 37/37 i hele `headend/tests/`-suiten). Reproduktion bekræfter `hardcoded_secret_terms` nu bidrager 0 fund (var 10); §11 P2.4 opdateret. Ingen commit/push (Peter/Codex committer selv) |
| 10 (tilføjelse) | 2026-07-05 (Peters miljøafklaring) | Claude: R19 (NY) tilføjet — agent-adgang til det fremtidige prod-fysiske-system (`timelapsepro.dk`, kører allerede CrushFTP+legacy med live kundedata) er ikke formelt udelukket. R12 udvidet med Kirkbi A/S-databehandleraftale-note (delvis, ikke fuld, lempelse). §6 zone-model udvidet med et miljø-lag (`rd`/`staging`/`prod`), ortogonalt på de eksisterende netværkszoner. Nyt dokument `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` oprettet som kanonisk topologi-kilde. Ingen kode ændret — ren dokumentation af Peters arkitekturbeslutning, som svar på Codex' agent/service-principal-forslag (se `HANDOVER_LOG.md`) |
| 10 (tilføjelse) | 2026-07-05 (installationsscript-runde) | Claude: R19 nedjusteret 🟠10→🟡5 — Peter har ordret bekræftet permanent nul-agent-adgang-politik for staging/prod. Rettet en væsentlig fejlantagelse på tværs af dokumenterne: Cloudflare Tunnel er IKKE prod-målarkitekturen (Peter vil bevidst undgå den) — GO_LIVE_CHECKLIST §A (A-01–A-04) omskrevet til direkte nginx-eksponering (matcher allerede byggede `www/index.html` + nuværende `rd`-nginx-mønster). CA/mTLS-designdokumentet (#52) opdateret: Model B (ende-til-ende mTLS) valgt fremfor Model A (Cloudflare Access), Root CA-nøgle placeres pt. på R&D-maskinen (Peters valg, fleksibelt design). Nyt installationsscript + -guide oprettet til headend på staging/prod, da Peter skal kunne installere selvstændigt uden agent-adgang |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #31) | Claude: §9 GDPR-vurderingstabellen var kommet bagud ift. `GO_LIVE_CHECKLIST_v10.md` §G (G-01–G-07) og `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` — 6 af 9 rækker rettet fra blankt "🔴 Mangler" til deres reelle, allerede daterede status (skabeloner/udkast fra 2026-07-04, Adgangslog ✅ implementeret 2026-07-05). Ren sammenkøring af eksisterende status, ingen ny vurdering, ingen kode rørt |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #33) | Claude: §11 P0.1, VPEN-2026-001 (§5.2) og §6 zone-model-diagrammet var alle stadig kommet bagud ift. Peters arkitekturbeslutning (installationsscript-runden, samme dag) — nævnte fortsat "Migrer til Cloudflare Tunnel", selvom `GO_LIVE_CHECKLIST_v10.md` §A allerede var omskrevet til direkte nginx-eksponering (Cloudflare Tunnel bevidst fravalgt af Peter for prod); zone-modellen var udtrykkeligt nævnt som modsagt i samme HANDOVER_LOG-runde men blev aldrig selv rettet dengang. Alle tre rettet til at henvise til den faktiske målarkitektur. Ren tekstrettelse af allerede besluttet arkitektur, ingen ny vurdering, ingen kode rørt |
| 10 (tilføjelse) | 2026-07-05 (port-korrektionsrunde, 2.) | Claude: Forrige rundes "direkte nginx-eksponering på standard 443/80" (samme dag) var SELV en fejlantagelse — Peter bekræftede at CrushFTP allerede kører på BÅDE staging-iMac'en og prod-Mac Mini'en og optager 21/22/80/443 dér. VPEN-2026-001, VPEN-2026-002, §6 zone-model (ny "Zone X"-note for CrushFTP), §10 (henvisning), §11 P0.1 alle rettet en 2. gang til den nu endeligt aftalte arkitektur: backend på port **8443** (direkte, ikke Tunnel), certifikat via **DNS-01**/`certbot-dns-cloudflare` (rører ingen port), marketingsite hostet separat. Samme rettelse ført igennem `GO_LIVE_CHECKLIST_v10.md` §A/§I/§J/§L, `PORT_AUDIT_og_WEBSITE_v10.md` (hele dokumentet), `install_headend.sh`, `example-staging.conf`/`example-prod.conf`, `INSTALLATION_GUIDE_HEADEND_v1.md`, `www/index.html`. Ren arkitekturkorrektion, ingen nyt risikofund ud over selve dobbelt-fejlen (dokumenteret som en proces-læring: konsultér `PORT_AUDIT_og_WEBSITE_v10.md` FØR man "retter" portarkitektur — det dokument havde allerede forudset CrushFTP-co-residence-risikoen for måneder siden) |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #41) | Claude: §13.3 havde stadig den GAMLE "Blocker for kode: valg mellem Cloudflare Access mTLS og ende-til-ende mTLS ... kræver Peter/Codex' input"-tekst, selvom §11 P1.2 (og designdokumentets §10, jf. tjek #37) allerede korrekt viste at Model B var valgt og alle 4 designspørgsmål besvaret. §13.3 er nu rettet til at matche §11 P1.2 — samme docs-lag-drift-mønster som tjek #37 fandt i selve HANDOVER_LOG'ens "næste skridt"-noter, blot denne gang inde i selve risikodokumentet. Ren tekstrettelse, ingen ny vurdering, ingen kode rørt |
| 10 (tilføjelse) | 2026-07-05 (periodisk tjek #54) | Claude: R06 device-decommission-gap'et (afventet Peters beslutning siden tjek #16) fik tilføjet en rådgivende SABSA/ISO27001 A.8.32-baseret anbefaling (mulighed (c), "delvist bekræftet"-markering, frem for (a) permanent blokering eller (b) nuværende adfærd) med begrundelse, som beslutningsstøtte — Peter træffer stadig selve valget. Ingen kode rørt, ingen af de tre løsninger implementeret |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek #64) | Claude: R14's sidste åbne underpunkt (aperture/shutter_speed-drift-mål, afventet siden 2026-07-05) fik en rådgivende SABSA/ISO27001-baseret anbefaling — mulighed (c) opt-in pr. enhed (observability-only som standard, enforceable kun efter eksplicit per-device override), frem for (a) status quo eller (b) fleet-wide baseline. Fandt undervejs, ved læsning af faktisk kode (`gphoto2_driver.py`), at aperture/shutter_speed's gphoto2-stier IKKE er ens på tværs af kameraprofiler (Canon `f-number` vs. øvrige `aperture`/`shutterspeed`) — samme nøgle-mismatch-klasse som forårsagede den oprindelige R14-bug — og flaggede dette som en implementeringsfælde for den der udfører (c). Ren beslutningsstøtte + implementeringsnote, ingen kode ændret (bash utilgængeligt denne runde, kan ikke teste en ændring i netop denne drift-detektionskode) |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek #65) | Claude: R19 fik tilføjet et konkret kodeaudit-fund forud for `AgentPrincipal`-håndhævelsen (M-05) — de 3 nuværende kodesteder der læser `TIMELAPSE_ENV` (`edge/agent.py`, `headend/main.py`, `headend/siem.py`) kender endnu ikke den kanoniske værdi `"rd"` (besluttet 2026-07-05, `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §2), kun den ældre `lab`/`dev`/`development`-terminologi. Værst: `edge/agent.py`'s legacy-opdaterings-allowlist ville reelt (fail-safe, men funktionelt) blokere en gyldig sti hvis `TIMELAPSE_ENV=rd` sættes uden samtidig kode-opdatering. `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §6 punkt 5 opdateret med samme krydshenvisning. Ren kodeaudit + dokumentation, ingen kode ændret (kræver test, bash utilgængeligt denne runde) — anbefaling givet til Codex/Peter om at rette terminologien FØR selve håndhævelses-middlewaren bygges |
| 10 (tilføjelse) | 2026-07-06 | Claude: R19 uddybet efter Peters anmodning om en kontrolleret, tidsbegrænset, logget break-glass-undtagelsesvej til staging/prod-support-adgang (installation/fejlsøgning), ved siden af den fortsatte default-deny-standardtilstand. Nyt design-notat `Claude_Support_Access_Model_2026-07-06.md` (separat Support-CA fra device-CA'en i #52, korttidslevende SSH-certifikater med kryptografisk indbygget udløb, kunde-samtykke-tjek pr. aktivering, signeret ticket + audit-log — ingen kode/CA bygget endnu). §13.2 (cert-levetider) opdateret separat samme dag med Peters CA/mTLS-designsvar (10-års konfigurerbar device-cert-levetid, permanent HMAC+mTLS, retrofit af R&D-device til mTLS) — se `Claude_Intern_CA_mTLS_Design_2026-07-05.md`s egen dokumenthistorik. `MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md` §5 og `GO_LIVE_CHECKLIST_v10.md` M-02/M-08 opdateret tilsvarende. Ingen kode rørt. |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek #84) | Claude: R19/§11 P0 #6 og `GO_LIVE_CHECKLIST_v10.md` M-05 opdateret — #65's `TIMELAPSE_ENV`-terminologi-drift-fund er nu FAKTISK RETTET i kode (ikke kun dokumenteret): `"rd"` tilføjet som synonym til `lab`/`dev`/`development` i `edge/agent.py` (den fail-safe, men funktionelt farlige legacy-opdaterings-allowlist) og `headend/siem.py` (SIEM-logniveau-default); `headend/main.py` krævede ingen ændring (sammenligner allerede kun mod `prod`/`production`). Valgte bevidst den additive løsning (a) frem for #65's foretrukne fulde migration (b), da (b) risikerer at bryde en kørende installation uden mulighed for at verificere den faktiske miljøvariabel (ingen shell-adgang). Verificeret manuelt (linje-for-linje syntakstjek af diff'ene) — `py_compile` kunne ikke køres, `mcp__workspace__bash` fejlede fortsat (34. selvstændige bekræftelse). Selve M-05-håndhævelsen (AgentPrincipal-middleware) er stadig ikke bygget — kun en forudsætnings-faldgrube er ryddet. Ikke committet (Peter/Codex committer selv). |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek #85) | Claude: `GO_LIVE_CHECKLIST_v10.md` C-03 (standard super_admin-password) fik ny vedvarende SIEM-varsling — `_warn_if_default_admin_password_active()` (headend/main.py) kører ved hvert opstart (ikke kun ved brugeroprettelse) og logger `log.critical(...)` hvis en aktiv admin/super_admin-konto stadig autentificerer mod "changeme" (bcrypt `_verify_password`, salt-uafhængigt). 6 nye tests i `headend/tests/test_default_admin_password_warning.py`, IKKE kørt (`mcp__workspace__bash` fejlede, 35. selvstændige bekræftelse) — kun manuel linje-for-linje-verifikation. Dette er et observability-lag, IKKE selve bekræftelsen — C-03 forbliver 🔴, kræver stadig en faktisk manuel kontrol på rd/staging/prod-maskinerne. Ingen RISK_ASSESSMENT-risikopost ændret (C-03 hører hjemme i GO_LIVE_CHECKLIST, ikke i denne risikoliste) — kun nævnt her for fuldstændig sporing af rundens arbejde. Ikke committet (Peter/Codex committer selv). |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek, docs-sync) | Claude: Peter committede/mergede selv hele #33-#85-backlogget (`079f2496` → PR #1 → `main`, CI grøn, deployet til rd via `deploy-macmini`) — den lange "ukommitteret siden #33"-bekymring (#62, #66-#86) er lukket. Fandt ved samme lejlighed at §11 P0 #6 (denne fil) var kommet ét lag bagud ift. R19-detaljeafsnittet ovenfor og `GO_LIVE_CHECKLIST_v10.md` M-05, som begge allerede var opdateret med merge/deploy-bekræftelsen — §11 P0 #6 nævnte stadig kun "rettet i working tree". Rettet til at matche. Ren docs-lag-synkronisering internt i samme dokument, ingen ny vurdering, ingen kode rørt. |
| 10 (tilføjelse) | 2026-07-06 (periodisk tjek, docs-sync efter M-05 layer-2-kodning) | Claude: M-05 "layer 2" (env-flag + hård afvisning af `role="agent"` i `/api/auth/login`/`get_current_user()`, se R19-detaljeafsnittet ovenfor) blev kodet i en direkte Peter-anmodet session (ikke et periodisk tjek), samtidig med at Codex var utilgængeligt. `GO_LIVE_CHECKLIST_v10.md` M-05/§J var allerede opdateret til at afspejle dette korrekt ("kode skrevet, IKKE testet/committet/deployet"), men **denne fils §11 P0 #6 var kommet bagud** — sagde stadig kun at håndhævelsen "FORTSAT IKKE er bygget". Rettet til at matche R19-detaljeafsnittet og GO_LIVE_CHECKLIST. Uafhængig manuel code review udført samme runde (`headend/main.py` §`_agent_role_blocked_in_this_environment`/`get_current_user`/login, `headend/database.py` rollekommentar, alle 15 tests i `test_agent_principal_lockdown.py`) — ingen fejl fundet, konsistent med koden. Ren docs-lag-synkronisering + verifikation, ingen kode rørt, ikke committet. |

---

*Næste review: ved go-live-gate eller ved væsentlige arkitekturændringer*

---

## 13. PKI og nøgleinfrastruktur (bevaret fra v6)

### 13.1 Intern CA-arkitektur

```
TimeLapse Root CA  (Mac Mini — offline privat nøgle)
  ├── Headend Server Cert  (HTTPS API — fornyes årligt)
  ├── Device Client Certs  (pr. Orange Pi — fornyes halvårligt)
  └── SFTP SSH CA          (underskriver device SSH-nøgler)
```

### 13.2 Certifikat-levetider

**Rettet 2026-07-05 (Peter, designspørgsmål #52 besvaret):** Device client cert-levetiden
nedenfor er ændret fra 6 måneder til **10 år som default**, og gjort **konfigurerbar** pr.
global/kunde/site/kamera via den eksisterende config-hierarki-mekanisme
(`_resolve_config_hierarchy()` i `headend/main.py`) — se
`Claude_Intern_CA_mTLS_Design_2026-07-05.md` §4.3 for den fulde begrundelse og konsekvensen for
CRL-friskhed (bliver vigtigere med en så lang levetid). Peter har desuden besluttet at et
**udløbet** (men ikke revokeret) certifikat konfigurerbart kan tillades at fortsætte drift
("grace"-tilstand) — men et **revokeret** certifikat skal ALTID stoppe kommunikation
øjeblikkeligt, uden undtagelse.

| Type | Levetid | Fornyelse |
|------|---------|-----------|
| Root CA | 10 år | Manuel |
| Headend server cert | 1 år | Halvautomatisk (Key Mgmt UI) |
| Device client cert | **10 år, default — konfigurerbar pr. global/kunde/site/kamera** (ændret 2026-07-05, var 6 måneder) | Automatisk ved bootstrap, eller manuel rotation via Key Mgmt UI |
| SFTP SSH user key | Ubegrænset | Revokering ved kompromittering |
| SSH tunnel key | Ubegrænset | Revokering via Key Mgmt UI |
| JWT access token | 12 timer | Automatisk ved login |

### 13.3 Vurdering: Self-signed vs. intern CA

Self-signed individuelle certifikater frarådes (manuel trust-konfiguration pr. device). Intern mini-CA anbefales: rotation (ny headend-cert signeres af CA → edges opdateres ved næste config-pull), revokering (nyt device kræver CA-signering), skalering O(1) uanset antal devices, implementation ~50 linjer `cryptography` (allerede i venv). Status pr. v10: intern CA/mTLS er stadig **ikke implementeret** (jf. SEC-009/R07).

**Design-notat 2026-07-05 (Claude):** Se `Claude_Intern_CA_mTLS_Design_2026-07-05.md` for et
udfoldet forslag — Root CA → Issuing CA → device client cert (ECDSA P-256, CN=`device_id`),
mTLS lagt *ved siden af* eksisterende HMAC-lag (ikke erstatning), CRL fremfor OCSP given
fleet-størrelsen. **Opdateret 2026-07-05 (Peter har besvaret alle 4 designspørgsmål, jf.
designdokumentets §10 og RISK_ASSESSMENT §11 P1.2):** Model B (ende-til-ende mTLS til
nginx/Headend, ingen Cloudflare Access/Tunnel) er valgt — se §6 i designdokumentet. Ingen
blockers tilbage; næste skridt er en dedikeret kodefase (designdokumentets §9, trin 2-9), ikke
yderligere afklaring fra Peter/Codex.

## 14. Key Management UI — funktionskrav (bevaret fra v6)

Side i TimeLapse UI: **Nøglehåndtering** (kun `super_admin`):

- **CA & Certifikater:** vis CA fingerprint + udløb; download CA cert; udsted nyt headend server cert; list aktive device client certs m. udløb.
- **SSH-nøgler (SFTP):** list sftp_*-brugere + nøgler; generér ny SSH-nøgle pr. site; kopiér public key; markér revokeret (fjern fra authorized_keys).
- **SSH-nøgler (Tunnel):** list device tunnel-nøgler; generér nøglepar; download provisioneringspakke (bootstrap.yaml + nøgle + CA cert); markér revokeret.
- **Bootstrap tokens:** generér éngangs bootstrap-token; list aktive tokens m. udløb (24t); invalider manuelt.
- **Provisioneringspakke:** vælg kunde → site → kamera → "Generér pakke" → `timelapse_provision_<site>.zip` (bootstrap.yaml, headend_ca.crt, tunnel_key(.pub), INSTALL.md).

## 15. Codex-supplement — standardmapping og go/no-go (samstemmende)

| Standard | Codex-vurdering |
|---|---|
| SABSA | God arkitekturretning; business attributes skal bindes til frisk evidence + risikoejere |
| ISO 27001 | Asset/access/logging/change controls delvist; formelt ISMS/risk treatment mangler |
| IEC 62443 | Edge/Headend kan modelleres som zones/conduits; secure update + identity skal styrkes |
| CRA | Secure update på vej; SBOM, lifecycle support + vulnerability process mangler |
| NIS2 | Relevans som leverandør; continuity, incident handling + supply chain skal dokumenteres |
| GDPR | Ikke klar før DPIA, retention, DPA, subprocessor-liste + access logs er på plads |

**Go/no-go (Codex, samstemmende med §11):** LAB/R&D = **Go**. Første kontrollerede testsite = næsten go (hvis backup/restore, Nikon LAB, node-agent lukkes). Internet-facing production = **No-go** pr. 2026-06-23. `timelapse-pro.dk` backend = **No-go** indtil port/proxy, backup, GDPR og MFA/credentials er lukket.
