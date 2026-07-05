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
| VPEN-006 SAST backlog (73 signals) | Delvist — **se VPEN-2026-008 og VPEN-2026-009 (2026-07-05):** signal-optællingen var upålidelig (scanner-fejl rettet), og en første triage-batch (56 af 80 aktuelle signaler: `hardcoded_secret_terms`, `shell_execution`, `legacy_update_paths`) er nu gennemført — ingen fundet reelle sårbarheder i disse tre kategorier. `dangerous_file_ops` (24 signaler) er fortsat helt utriaget |
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
**Beskrivelse:** nginx binder til `*:80` og `*:443`. Med Cloudflare foran er dette acceptabelt i lab, men i production-model uden Cloudflare Tunnel er det en angrebsflade.
**Anbefaling:** Migrer til Cloudflare Tunnel + nginx på `127.0.0.1:18443`. Se PORT_AUDIT_og_WEBSITE_2026-06-23.md.

#### VPEN-2026-002 — SSH port 22 eksponeret til internet
**Prioritet:** P1
**Beskrivelse:** Port 22 er synlig i ældre port-/asset-evidens som macOS/system-SSH. TimeLapse's egne sftp_*-brugere er blokeret via Match-regler, men admin-SSH-adgang må ikke være en uklassificeret public produktionsflade.
**Anbefaling:** Flyt admin SSH til non-standard administrativ kanal eller bag VPN/Cloudflare Access. Aktiver fail2ban. Brug ikke TCP/22 til TimeLapse SFTP.

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
- **`dangerous_file_ops` (24 signaler) — IKKE triageret i denne runde.** Kræver individuel gennemgang af hver `unlink()`/`rmtree()`/`chown`-forekomst (bl.a. backup-, thumbnail-, docker- og OS-bundle-relateret driftskode) for at vurdere path-validering/race conditions. Overlades bevidst til en efterfølgende periodisk runde — for stort til at forceres igennem overfladisk i denne 20-minutters kørsel.
**Verifikation:** `python3 -m py_compile main.py database.py tests/test_aiops_static_scan.py` ren. `pytest tests/` (hele `headend/tests/`): **32/32 bestået**. Kørte `_aiops_static_scan()` direkte to gange (før/efter fix) for at bekræfte at ingen fund længere refererer scannerens egen opslagstabel-definition. `git diff --stat` bagefter: kun `headend/main.py` (+32/-5) og `headend/tests/test_aiops_static_scan.py` (+42/-1) ændret.
**Ikke gjort — bevidst:** `dangerous_file_ops`-triage (se ovenfor). Ingen ændring af det hårde 80-fund-loft. Ingen commit/push (Peter/Codex committer selv).

---

## 6. IEC 62443 zone-model (opdateret)

```
Zone 0: Public internet
  ↕ Conduit: Cloudflare → nginx
Zone 1: DMZ / Reverse proxy (nginx, Cloudflare Tunnel)
  ↕ Conduit: nginx → uvicorn 127.0.0.1:8000
Zone 2: Headend applikation (FastAPI, PostgreSQL)
  ↕ Conduit: API → Ollama 127.0.0.1:11434
Zone 3: AI/Tooling services (Ollama, OpenWebUI)
  ↕ Conduit: HTTPS/JWT → Edge API
Zone 4: Edge management (Reverse SSH tunnel, update artifacts)
  ↕ Conduit: SFTP port 22222, gphoto2, GPIO
Zone 5: Kamera/relay/lokal enhedsgrænseflade
```

**Implementeringsstatus:**
- Zone 0→1: ✅ nginx/TLS/Cloudflare
- Zone 1→2: ✅ reverse proxy
- Zone 2→3: 🟡 Ollama intern, OpenWebUI nede
- Zone 2→4: ✅ JWT/HMAC; stale credentials
- Zone 4→5: ✅ gphoto2/GPIO

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
| Art. 33/34 — Brudnotifikation | Procedure ved databrud | 🔴 Mangler |
| Art. 35 — DPIA | Billedovervågning med høj risiko | 🔴 Mangler pr. kunde/site |
| Art. 28 — Databehandleraftale | Aftale med Peter/TimeLapse Pro | 🔴 Mangler |
| Art. 13/14 — Oplysningspligt | Information til registrerede | 🔴 Ikke dokumenteret |
| Retention | Opbevaringsbegrænsning | 🔴 Ingen retention policy implementeret |
| Adgangslog | Log pr. billede/download | 🔴 Mangler |
| Subprocessorer | Google Cloud/Gemini, evt. andre | 🔴 Subprocessor-liste mangler |

**Anbefaling:** Inden første rigtige produktionssite:
1. DPIA-template pr. kunde/site
2. Retention policy konfigureres pr. kamera
3. Download/adgangslog implementeres
4. Databehandleraftale-template

---

## 10. Samlet risikooversigt

| Risk | Score | Trend siden v6 |
|---|---|---|
| R01 SFTP data-adskillelse | 🟢 4 | ↓↓ Løst |
| R02 UI adgangskontrol (MFA mangler) | 🟡 6 | ↓ Forbedret |
| R03 Hardware-historik | 🟢 3 | ↓↓ Løst |
| R04 Remote adgang | 🟢 3 | ↓↓ Løst |
| R05 Kompromitteret edge | 🟠 8 | → Uændret |
| R06 Opdateringsfejl | 🟢 4 | ↓↓ Lab-løst |
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

**Kritiske/blokkerende risici for go-live (Internet):** R05, R09, R12, nginx port-eksponering (VPEN-2026-001). R16 er fuldt lukket (kode + deploy + backfill).

---

## 11. Prioriteret risikobehandlingsplan

### 🔴 P0 — Blokkerer production/Internet-eksponering
1. Migrer nginx væk fra public 80/443 → Cloudflare Tunnel
2. Backup + restore-test dokumenteret (R09)
3. DPIA-template + retention policy (R12)
4. Node-agent genetableret (R13)
5. HMAC enforcement globalt — stale credentials migreret/afviklet

### 🟠 P1 — Skal lukkes inden første rigtige kunde-site
1. MFA/WebAuthn til admin-login (R02)
2. Intern CA + device client certs (R05, R07, R08) — design-notat klar
   (`Claude_Intern_CA_mTLS_Design_2026-07-05.md`), afventer Peter/Codex' arkitekturvalg
   (Cloudflare Access mTLS vs. ende-til-ende) før kode
3. Nikon Z30 config-model — desired state + accepted equivalents (R14); detektion + UI-visning
   af non-enforceable parametre er nu på plads (2026-07-05), resterer kun live-verifikation på
   hardware og en eksplicit beslutning om aperture/shutter_speed-drift-mål
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
3. GDPR adgangslog pr. billede
4. SAST backlog triage (73 signaler) — **OBS 2026-07-05:** selve tallet "73" var upålideligt
   (scanneren talte vendored tredjeparts-bibliotekskode med som egne signaler, se
   VPEN-2026-008); scanner-fejlen er nu rettet og testdækket. **Opdatering (VPEN-2026-009,
   periodisk tjek #18):** endnu en scanner-selvreference fundet/rettet (samme testfil, nu
   32/32 bestået), og en første triage-batch er gennemført — `hardcoded_secret_terms` (10),
   `shell_execution` (40) og `legacy_update_paths` (5), i alt 56 af 80 aktuelle signaler.
   Ingen reelle sårbarheder fundet i disse tre kategorier (kun ét opmærksomhedspunkt: lokalt
   dev-værktøj `claude_proxy.py` bruger `shell=True` med dynamisk input — se VPEN-2026-009).
   `dangerous_file_ops` (24 signaler) er fortsat helt utriaget — resterer til næste runde
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

| Type | Levetid | Fornyelse |
|------|---------|-----------|
| Root CA | 10 år | Manuel |
| Headend server cert | 1 år | Halvautomatisk (Key Mgmt UI) |
| Device client cert | 6 måneder | Automatisk ved bootstrap |
| SFTP SSH user key | Ubegrænset | Revokering ved kompromittering |
| SSH tunnel key | Ubegrænset | Revokering via Key Mgmt UI |
| JWT access token | 12 timer | Automatisk ved login |

### 13.3 Vurdering: Self-signed vs. intern CA

Self-signed individuelle certifikater frarådes (manuel trust-konfiguration pr. device). Intern mini-CA anbefales: rotation (ny headend-cert signeres af CA → edges opdateres ved næste config-pull), revokering (nyt device kræver CA-signering), skalering O(1) uanset antal devices, implementation ~50 linjer `cryptography` (allerede i venv). Status pr. v10: intern CA/mTLS er stadig **ikke implementeret** (jf. SEC-009/R07).

**Design-notat 2026-07-05 (Claude):** Se `Claude_Intern_CA_mTLS_Design_2026-07-05.md` for et
udfoldet forslag — Root CA → Issuing CA → device client cert (ECDSA P-256, CN=`device_id`),
mTLS lagt *ved siden af* eksisterende HMAC-lag (ikke erstatning), CRL fremfor OCSP given
fleet-størrelsen. **Blocker for kode:** valg mellem Cloudflare Access mTLS og ende-til-ende
mTLS til nginx/Headend (§6 i notatet) kræver kig i Cloudflare-dashboardet/-planniveau, som
Claude ikke har adgang til — kræver Peter/Codex' input før implementering kan starte.

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
