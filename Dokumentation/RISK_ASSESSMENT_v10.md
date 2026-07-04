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
| VPEN-006 SAST backlog (73 signals) | Åben — triage ikke udført |
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
- **Implementerede kontroller:** Offline artifact-model, change tickets, staged rollout, rollback
- **Åbent:** OS E2E på aktiv Edge ikke testet; per-target deployment status mangler
- **Residualrisiko:** 🟢 4

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
- **Status:** 🔴 Åben
- **Implementerede kontroller:** Backup til /Volumes/Backup (sti rettet); edge circular buffer
- **Åbent:** Off-site backup, restore-test, backup change ticket, RTO/RPO dokumenteret
- **Sandsynlighed:** 2, **Konsekvens:** 4, **Score:** 🟠 8

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

### R17 — Debug/lab mode kan efterlades aktiveret uden overvågning (NY, fundet 2026-07-04)
- **Status:** 🟡 Delvist kontrolleret
- **Fund (Claude, ifm. GPS-fejlsøgning):** `debug_mode.enabled` er en flad, per-enhed config-nøgle (ingen DB-kolonne, ingen udløb/TTL), sat udelukkende via `PUT /api/admin/devices/{id}/debug` (kræver admin-rolle — ingen adgangskontrol-svaghed). Mens aktiv holder edge-agenten kamera-relæet konstant tændt og springer den normale optagelsesplan over (interaktiv "lab"-tilstand til kamera-tuning). Fundet aktiveret på et produktionskamera (TL-C87FF9587CA0), tilsyneladende en efterladt flag fra en tidligere test-session — opdaget udelukkende ved manuel log-gennemgang, ikke via noget dashboard/alarm.
- **Konsekvens:** Ingen adgangskompromittering, men operationel/tilgængelighedsrisiko: uventet konstant relæ-belastning, optagelsesplan brydes uden varsel, og (jf. GPS-fixet 2026-07-04) reduceret GPS-pålidelighed pga. relæets effekt på GPS-modtagerens strømforsyning. Ingen automatisk måde at opdage "enhed X har kørt i lab mode i N dage" på.
- **Sandsynlighed:** 3, **Konsekvens:** 2, **Score:** 🟡 6
- **Anbefaling:** CMDB/dashboard-indikator for `debug_mode.enabled=true` pr. enhed; overvej auto-timeout (fx maks. 4-8 timer, kræver eksplicit forlængelse); log aktivering/deaktivering (hvem/hvornår) til audit/SIEM.

### R13 — Node-agent nede på Headend (NY)
- **Status:** 🔴 Åben
- **Konsekvens:** CMDB inventory for Mac Mini er stale; patch/risk score ufuldstændig
- **Handling:** Genetabler som user LaunchAgent under peter (ikke root)

### R14 — Nikon Z30 camera config drift (NY)
- **Status:** 🔴 Åben
- **Sandsynlighed:** 4, **Konsekvens:** 3, **Score:** 🟠 12
- **Handling:** Nikon Z30 capabilities-mapping; skeln readonly vs. enforceable; "desired state" + "accepted equivalent labels"

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

#### VPEN-2026-004 — ESLint-gæld (219 fejl)
**Prioritet:** P2 (blocker for production release)
**Beskrivelse:** Frontend-lint fejler med 219 errors. Dette skjuler potentielle regressions og sikkerhedsproblemer.
**Anbefaling:** Indfør lint-gate i CI. Triage og fix eksisterende fejl i batches.

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
| R14 Nikon Z30 config drift | 🟠 12 | 🆕 Ny |
| R15 SIEM uden auth + MFA-gab CMDB/ITIM | 🟢 4 | ✅ Ny/løst — fundet og rettet, live-verificeret 2026-07-03 |
| R16 Kryds-kunde-lækage ved Edge-gentildeling | 🟢 4 | ✅ Ny/løst — fundet, rettet og backfillet komplet i produktion 2026-07-03 |
| R17 Debug/lab mode uden overvågning | 🟡 6 | 🆕 Ny — fundet 2026-07-04, ingen adgangskompromittering |

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
2. Intern CA + device client certs (R05, R07, R08)
3. Nikon Z30 config-model — desired state + accepted equivalents (R14)
4. Per-target deployment status (update-flow)
5. ESLint-gate i CI

### 🟡 P2 — Production hardening
1. Disk-kryptering på Edge (R05)
2. Off-site backup (R09)
3. GDPR adgangslog pr. billede
4. SAST backlog triage (73 signaler)
5. Secrets → macOS Keychain
6. AI resource governor + Ollama beslutning
7. CMDB-indikator/auto-timeout for debug/lab mode pr. enhed (R17)

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
